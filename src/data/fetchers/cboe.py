"""CBOE public-CDN fetcher: SKEW + VIX term structure.

CBOE's www.cboe.com pages block scrapers (robots.txt + WAF). The cdn.cboe.com
historical CSV endpoints for index series (VIX/SKEW family) ARE publicly
accessible. The put/call ratio CSV endpoints currently return 403 from the
CDN; we log that and skip.
"""
from __future__ import annotations

import io
import time

import pandas as pd
import requests

from src.data.utils import (
    CATALOG_PATH,
    DATA_DIR,
    FAILED_PATH,
    align_to_trading_days,
    log_failure,
    log_to_catalog,
    save_clean,
    validate_data,
)

CLEAN_DIR = DATA_DIR / "clean" / "sentiment"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    ),
    "Accept": "text/csv,*/*",
    "Referer": "https://www.cboe.com/",
}

CBOE_CDN = "https://cdn.cboe.com/api/global/us_indices/daily_prices"

INDEX_SERIES = {
    "skew": "SKEW_History.csv",
    "vix": "VIX_History.csv",
    "vix9d": "VIX9D_History.csv",
    "vix3m": "VIX3M_History.csv",
    "vix6m": "VIX6M_History.csv",
}


def _get(url: str, retries: int = 3) -> requests.Response | None:
    for i in range(retries):
        try:
            r = requests.get(url, headers=HEADERS, timeout=30)
            if r.status_code == 200:
                return r
            if r.status_code in (429, 503):
                time.sleep(2 ** i * 3)
                continue
            return r
        except requests.RequestException as e:
            print(f"  ! {url}: {e}")
            time.sleep(2 + i)
    return None


def _parse_cboe_csv(text: str) -> pd.DataFrame:
    df = pd.read_csv(io.StringIO(text))
    date_col = df.columns[0]
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    df = df.dropna(subset=[date_col]).set_index(date_col).sort_index()
    df.columns = [c.strip().lower() for c in df.columns]
    return df


def fetch_index_series() -> None:
    for name, fname in INDEX_SERIES.items():
        url = f"{CBOE_CDN}/{fname}"
        print(f"[cboe] {name} <- {fname}")
        r = _get(url)
        if r is None or r.status_code != 200:
            sc = r.status_code if r is not None else "ERR"
            log_failure(FAILED_PATH, f"cboe:{name}", f"HTTP {sc}", attempted=url)
            print(f"  ! failed {sc}")
            continue
        df = _parse_cboe_csv(r.text)
        # SKEW has one col; VIX-family have OHLC; keep close-only for VIX
        if "close" in df.columns:
            df = df[["close"]].rename(columns={"close": name})
        else:
            df.columns = [name]
        aligned = align_to_trading_days(df, source_freq="daily")
        path = CLEAN_DIR / f"cboe_{name}.parquet"
        save_clean(aligned, path, metadata={"source": "cboe", "url": url})
        validate_data(aligned, name=f"cboe_{name}")
        log_to_catalog(CATALOG_PATH, {
            "source": "cboe",
            "series_name": f"cboe_{name}",
            "frequency": "daily",
            "date_range": f"{aligned.index.min().date()}..{aligned.index.max().date()}",
            "file_path": str(path.relative_to(DATA_DIR.parent)).replace("\\", "/"),
            "status": "OK",
            "notes": "from cdn.cboe.com",
        })
        time.sleep(2.5)


def build_term_structure() -> None:
    """Compute VIX vs VIX3M ratio (contango/backwardation proxy)."""
    try:
        vix = pd.read_parquet(CLEAN_DIR / "cboe_vix.parquet")
        v3 = pd.read_parquet(CLEAN_DIR / "cboe_vix3m.parquet")
    except FileNotFoundError:
        print("  ! term structure skipped (missing inputs)")
        return
    df = pd.concat([vix["vix"], v3["vix3m"]], axis=1).dropna()
    df["vix_vix3m_ratio"] = df["vix"] / df["vix3m"]
    df["vix_vix3m_spread"] = df["vix"] - df["vix3m"]
    out = df[["vix_vix3m_ratio", "vix_vix3m_spread"]]
    path = CLEAN_DIR / "cboe_vix_term_structure.parquet"
    save_clean(out, path, metadata={"source": "cboe", "derived": True})
    validate_data(out, name="cboe_vix_term_structure")
    log_to_catalog(CATALOG_PATH, {
        "source": "cboe",
        "series_name": "cboe_vix_term_structure",
        "frequency": "daily",
        "date_range": f"{out.index.min().date()}..{out.index.max().date()}",
        "file_path": str(path.relative_to(DATA_DIR.parent)).replace("\\", "/"),
        "status": "OK",
        "notes": "VIX/VIX3M ratio and spread (derived)",
    })


def attempt_put_call() -> None:
    """Put/call CSV endpoints currently 403 from CDN; record as blocked."""
    candidates = [
        "https://cdn.cboe.com/api/global/us_indices/daily_prices/PCRATIO_History.csv",
        "https://cdn.cboe.com/data/us/options/market_statistics/daily/totalpc.csv",
        "https://cdn.cboe.com/data/us/options/market_statistics/daily/indexpc.csv",
        "https://cdn.cboe.com/data/us/options/market_statistics/daily/equitypc.csv",
    ]
    print("[cboe] put/call probe")
    blocked = []
    for u in candidates:
        r = _get(u, retries=2)
        sc = r.status_code if r is not None else "ERR"
        blocked.append(f"{sc}:{u.rsplit('/',1)[-1]}")
        time.sleep(2)
    log_failure(
        FAILED_PATH,
        "cboe:put_call",
        "all CDN put/call endpoints 403; HTML pages blocked by robots+WAF; "
        "register at datashop.cboe.com for historical PCR feeds",
        attempted="; ".join(blocked),
    )
    print("  ! put/call blocked, logged failure")


def main() -> None:
    CLEAN_DIR.mkdir(parents=True, exist_ok=True)
    fetch_index_series()
    build_term_structure()
    attempt_put_call()


if __name__ == "__main__":
    main()
