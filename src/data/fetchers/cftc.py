"""CFTC Commitment of Traders fetcher.

Downloads annual zips of Disaggregated Futures Only (commodities) and
Traders in Financial Futures (financial instruments), filters by contract,
computes net positions, % of OI, and 52-week z-scores. Weekly data
ffilled to NYSE trading days.
"""
from __future__ import annotations

import io
import urllib.request
import urllib.error
import zipfile
from typing import Optional

import numpy as np
import pandas as pd

from src.data.utils import (
    CATALOG_PATH,
    DATA_DIR,
    FAILED_PATH,
    align_to_trading_days,
    log_failure,
    log_to_catalog,
    save_clean,
)

RAW_DIR = DATA_DIR / "raw" / "cftc"
CLEAN_DIR = DATA_DIR / "clean" / "sentiment"

DISAGG_URL = "https://www.cftc.gov/files/dea/history/fut_disagg_txt_{year}.zip"
TFF_URL = "https://www.cftc.gov/files/dea/history/fut_fin_txt_{year}.zip"

# (key, label, source ('disagg'|'tff'), include_substrings (any-match), exclude_substrings)
CONTRACTS = [
    ("crude_oil_wti", "WTI Crude Oil",     "disagg", ("CRUDE OIL, LIGHT SWEET",), ("DIFF", "FINANCIAL", "MICRO")),
    ("gold",          "Gold",              "disagg", ("GOLD - COMMODITY EXCHANGE",), ("MICRO",)),
    ("silver",        "Silver",            "disagg", ("SILVER - COMMODITY EXCHANGE",), ("MICRO",)),
    ("copper",        "Copper",            "disagg", ("COPPER",), ("MICRO",)),
    ("sp500_emini",   "S&P 500 E-mini",    "tff",    ("E-MINI S&P 500 -", "E-MINI S&P 500 STOCK INDEX"), ("MICRO", "DIVIDEND", "ANNUAL", "QUARTERLY", "TOTAL RETURN", "ADJUSTED")),
    ("nasdaq_emini",  "Nasdaq 100 E-mini", "tff",    ("NASDAQ MINI -", "NASDAQ-100 STOCK INDEX (MINI)"), ("MICRO", "CONSOLIDATED")),
    ("ust_10y",       "UST 10Y Note",      "tff",    ("UST 10Y NOTE -", "10-YEAR U.S. TREASURY NOTES", "10-YEAR U.S. TREASURY NOTE"), ("ULTRA",)),
    ("usd_index",     "USD Index",         "tff",    ("USD INDEX -", "U.S. DOLLAR INDEX"), ()),
]


def _download_zip(url: str, timeout: int = 60) -> Optional[bytes]:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (data-fetcher)"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except Exception as e:
        print(f"  ! cftc zip {url}: {e}")
        return None


def _read_year(year: int, source: str) -> pd.DataFrame:
    url = (DISAGG_URL if source == "disagg" else TFF_URL).format(year=year)
    raw = _download_zip(url)
    if raw is None:
        return pd.DataFrame()
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as zf:
            name = next((n for n in zf.namelist() if n.lower().endswith(".txt")), None)
            if name is None:
                return pd.DataFrame()
            with zf.open(name) as f:
                df = pd.read_csv(f, low_memory=False)
    except Exception as e:
        print(f"  ! cftc parse {year}/{source}: {e}")
        return pd.DataFrame()
    # Normalize date column across year-format variants
    date_col = None
    for c in df.columns:
        if c.startswith("Report_Date_as_") or "Report_Date_as_YYYY" in c:
            date_col = c
            break
    if date_col is not None:
        df["_date"] = pd.to_datetime(df[date_col], errors="coerce")
    return df


def _filter_contract(df: pd.DataFrame, includes, excludes: tuple = ()) -> pd.DataFrame:
    if df.empty:
        return df
    name_col = next((c for c in df.columns if "Market_and_Exchange" in c or "Market and Exchange" in c), None)
    if name_col is None:
        return pd.DataFrame()
    if isinstance(includes, str):
        includes = (includes,)
    names = df[name_col].astype(str).str.upper()
    mask = pd.Series(False, index=df.index)
    for inc in includes:
        mask |= names.str.contains(inc.upper(), na=False, regex=False)
    for ex in excludes:
        mask &= ~names.str.contains(ex.upper(), na=False, regex=False)
    return df.loc[mask].copy()


def _extract_positions(df: pd.DataFrame, source: str) -> pd.DataFrame:
    if df.empty:
        return df
    if "_date" not in df.columns:
        date_col = next((c for c in df.columns if c.startswith("Report_Date_as_") or "Report_Date_as_YYYY" in c), None)
        if date_col is None:
            return pd.DataFrame()
        df["_date"] = pd.to_datetime(df[date_col], errors="coerce")
    df = df.dropna(subset=["_date"])

    oi_col = next((c for c in df.columns if c.startswith("Open_Interest_All")), None)

    if source == "disagg":
        mm_long = next((c for c in df.columns if c.startswith("M_Money_Positions_Long_All")), None)
        mm_short = next((c for c in df.columns if c.startswith("M_Money_Positions_Short_All")), None)
        cm_long = next((c for c in df.columns if c.startswith("Prod_Merc_Positions_Long_All")), None)
        cm_short = next((c for c in df.columns if c.startswith("Prod_Merc_Positions_Short_All")), None)
    else:  # tff
        mm_long = next((c for c in df.columns if c.startswith("Lev_Money_Positions_Long_All")), None)
        mm_short = next((c for c in df.columns if c.startswith("Lev_Money_Positions_Short_All")), None)
        cm_long = next((c for c in df.columns if c.startswith("Dealer_Positions_Long_All")), None)
        cm_short = next((c for c in df.columns if c.startswith("Dealer_Positions_Short_All")), None)

    needed = [mm_long, mm_short, cm_long, cm_short, oi_col]
    if any(c is None for c in needed):
        return pd.DataFrame()

    out = pd.DataFrame({
        "managed_money_long": pd.to_numeric(df[mm_long], errors="coerce").values,
        "managed_money_short": pd.to_numeric(df[mm_short], errors="coerce").values,
        "commercial_long": pd.to_numeric(df[cm_long], errors="coerce").values,
        "commercial_short": pd.to_numeric(df[cm_short], errors="coerce").values,
        "open_interest": pd.to_numeric(df[oi_col], errors="coerce").values,
    }, index=pd.DatetimeIndex(df["_date"].values))
    out["managed_money_net"] = out["managed_money_long"] - out["managed_money_short"]
    out["commercial_net"] = out["commercial_long"] - out["commercial_short"]
    out["mm_net_pct_oi"] = out["managed_money_net"] / out["open_interest"].replace(0, np.nan)
    out = out.sort_index()
    out = out[~out.index.duplicated(keep="last")]
    # 52-week z-score (weekly data)
    roll = out["managed_money_net"].rolling(52, min_periods=12)
    out["mm_net_zscore_52w"] = (out["managed_money_net"] - roll.mean()) / roll.std().replace(0, np.nan)
    return out


def fetch_contract(key: str, label: str, source: str, substr, excludes: tuple = (),
                   start_year: int = 2010, end_year: int = 2026) -> pd.DataFrame:
    print(f"[cftc] {key} ({label}) source={source}")
    frames = []
    for year in range(start_year, end_year + 1):
        ydf = _read_year(year, source)
        if ydf.empty:
            continue
        sub = _filter_contract(ydf, substr, excludes)
        if not sub.empty:
            frames.append(sub)
    if not frames:
        log_failure(FAILED_PATH, f"cftc:{key}", "no rows extracted from any year", attempted=DISAGG_URL if source == "disagg" else TFF_URL)
        return pd.DataFrame()
    big = pd.concat(frames, ignore_index=True)
    out = _extract_positions(big, source)
    if out.empty:
        return out
    aligned = align_to_trading_days(out, source_freq="weekly")
    return aligned


def main(start_year: int = 2010) -> None:
    CLEAN_DIR.mkdir(parents=True, exist_ok=True)
    for key, label, source, substr, excludes in CONTRACTS:
        df = fetch_contract(key, label, source, substr, excludes, start_year=start_year)
        if df.empty:
            continue
        path = CLEAN_DIR / f"cot_{key}.parquet"
        save_clean(df, path, metadata={"source": "cftc", "contract": label})
        log_to_catalog(CATALOG_PATH, {
            "source": "cftc",
            "series_name": f"cot_{key}",
            "frequency": "weekly",
            "date_range": f"{df.index.min().date()}..{df.index.max().date()}",
            "file_path": str(path.relative_to(DATA_DIR.parent)).replace("\\", "/"),
            "status": "OK",
            "notes": label,
        })


if __name__ == "__main__":
    main()
