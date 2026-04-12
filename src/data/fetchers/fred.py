"""FRED fetcher. Downloads macro series via fredapi/pdr/CSV fallback, cleans, validates, catalogs."""
from __future__ import annotations

import io
import os
import time
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional

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


RAW_DIR = DATA_DIR / "raw" / "fred"
CLEAN_DIR = DATA_DIR / "clean" / "macro"

FRED_CSV_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}"

try:
    from fredapi import Fred  # type: ignore
    _HAS_FREDAPI = True
except ImportError:
    _HAS_FREDAPI = False

try:
    import pandas_datareader.data as pdr  # type: ignore
    _HAS_PDR = True
except ImportError:
    _HAS_PDR = False


_FRED_CLIENT = None


def _get_fred_client():
    global _FRED_CLIENT
    if _FRED_CLIENT is not None:
        return _FRED_CLIENT
    if not _HAS_FREDAPI:
        return None
    key = os.environ.get("FRED_API_KEY")
    if not key:
        return None
    _FRED_CLIENT = Fred(api_key=key)
    return _FRED_CLIENT


def _download_csv(series_id: str, timeout: int = 30) -> pd.DataFrame:
    """Direct CSV download from FRED website. No API key needed."""
    url = FRED_CSV_URL.format(sid=series_id)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (data-fetcher)"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
    df = pd.read_csv(io.BytesIO(raw))
    # FRED CSVs use either 'observation_date' or 'DATE' as the date column
    date_col = "observation_date" if "observation_date" in df.columns else "DATE"
    df[date_col] = pd.to_datetime(df[date_col])
    df = df.set_index(date_col).sort_index()
    df.index.name = None
    # Coerce values; FRED uses '.' for missing
    for c in df.columns:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(how="all")
    return df


def download_fred(
    series_id: str,
    start: Optional[str] = None,
    end: Optional[str] = None,
) -> pd.DataFrame:
    """Download a single FRED series. Tries fredapi -> pandas_datareader -> CSV.
    Returns a DataFrame indexed by date with one column named series_id."""
    df = pd.DataFrame()

    client = _get_fred_client()
    if client is not None:
        try:
            s = client.get_series(series_id, observation_start=start, observation_end=end)
            df = pd.DataFrame({series_id: s})
            df.index = pd.to_datetime(df.index)
        except Exception as e:
            print(f"  ! {series_id}: fredapi failed: {e}")
            df = pd.DataFrame()

    if df.empty and _HAS_PDR:
        try:
            df = pdr.DataReader(series_id, "fred", start=start, end=end)
        except Exception as e:
            print(f"  ! {series_id}: pdr failed: {e}")
            df = pd.DataFrame()

    if df.empty:
        try:
            df = _download_csv(series_id)
        except urllib.error.HTTPError as e:
            print(f"  ! {series_id}: CSV HTTP {e.code}")
            return pd.DataFrame()
        except Exception as e:
            print(f"  ! {series_id}: CSV failed: {e}")
            return pd.DataFrame()

    if df.empty:
        return df

    if df.index.tz is not None:
        df.index = df.index.tz_localize(None)
    if start:
        df = df[df.index >= pd.Timestamp(start)]
    if end:
        df = df[df.index <= pd.Timestamp(end)]
    if list(df.columns) != [series_id]:
        df.columns = [series_id]
    df = df.dropna(how="all")
    return df


# Series catalog: (series_id, descriptive_name, source_freq, category)
# source_freq controls ffill limit when aligning to trading days
SERIES = [
    # YIELD CURVE & RATES (daily)
    ("DGS10",   "treasury_10y",         "daily",   "rates"),
    ("DGS2",    "treasury_2y",          "daily",   "rates"),
    ("DGS3MO",  "treasury_3m",          "daily",   "rates"),
    ("DGS5",    "treasury_5y",          "daily",   "rates"),
    ("DGS30",   "treasury_30y",         "daily",   "rates"),
    ("FEDFUNDS","fed_funds_rate",       "monthly", "rates"),
    ("DFF",     "fed_funds_daily",      "daily",   "rates"),
    # INFLATION
    ("CPIAUCSL",        "cpi_all_urban",        "monthly", "inflation"),
    ("CPILFESL",        "cpi_core",             "monthly", "inflation"),
    ("PCEPI",           "pce_price_index",      "monthly", "inflation"),
    ("PCEPILFE",        "pce_core",             "monthly", "inflation"),
    ("PPIACO",          "ppi_all_commodities",  "monthly", "inflation"),
    ("T5YIE",           "breakeven_5y",         "daily",   "inflation"),
    ("T10YIE",          "breakeven_10y",        "daily",   "inflation"),
    ("TRIMMEDMEANPCE",  "trimmed_mean_pce",     "monthly", "inflation"),
    # LABOR
    ("UNRATE",          "unemployment_rate",    "monthly", "labor"),
    ("ICSA",            "initial_claims",       "weekly",  "labor"),
    ("CCSA",            "continuing_claims",    "weekly",  "labor"),
    ("PAYEMS",          "nonfarm_payrolls",     "monthly", "labor"),
    ("CIVPART",         "labor_force_partic",   "monthly", "labor"),
    ("JTSJOL",          "jolts_job_openings",   "monthly", "labor"),
    ("CES0500000003",   "avg_hourly_earnings",  "monthly", "labor"),
    # ECONOMIC ACTIVITY
    ("NAPM",            "ism_manufacturing_pmi","monthly", "activity"),
    ("NMFBAI",          "ism_services_pmi",     "monthly", "activity"),
    ("NAPMNOI",         "ism_new_orders",       "monthly", "activity"),
    ("GDP",             "gdp_nominal",          "quarterly","activity"),
    ("GDPC1",           "gdp_real",             "quarterly","activity"),
    ("INDPRO",          "industrial_production","monthly", "activity"),
    ("TCU",             "capacity_utilization", "monthly", "activity"),
    ("DGORDER",         "durable_goods_orders", "monthly", "activity"),
    ("RSXFS",           "retail_sales_ex_food", "monthly", "activity"),
    # CONSUMER
    ("CSCICP03USM665S", "oecd_consumer_conf_us","monthly", "consumer"),
    ("UMCSENT",         "umich_sentiment",      "monthly", "consumer"),
    ("CONCCONF",        "conference_board_conf","monthly", "consumer"),  # CONCORD likely wrong
    ("PSAVERT",         "personal_savings_rate","monthly", "consumer"),
    ("PCE",             "personal_consumption", "monthly", "consumer"),
    ("TOTALSL",         "consumer_credit_total","monthly", "consumer"),
    # MONEY & LIQUIDITY
    ("M2SL",            "m2_money_supply",      "monthly", "money"),
    ("M1SL",            "m1_money_supply",      "monthly", "money"),
    ("BOGMBASE",        "monetary_base",        "monthly", "money"),
    ("WALCL",           "fed_balance_sheet",    "weekly",  "money"),
    ("RRPONTSYD",       "overnight_repo",       "daily",   "money"),
    # CREDIT & FINANCIAL CONDITIONS
    ("BAMLH0A0HYM2",    "hy_oas",               "daily",   "credit"),
    ("BAMLC0A4CBBB",    "bbb_oas",              "daily",   "credit"),
    ("AAA",             "moodys_aaa",           "daily",   "credit"),
    ("BAA",             "moodys_baa",           "daily",   "credit"),
    ("TEDRATE",         "ted_spread",           "daily",   "credit"),
    ("CPFF",             "commercial_paper_rate","daily",  "credit"),
    ("NFCI",            "nfci",                 "weekly",  "credit"),
    ("STLFSI2",         "stlfsi",               "weekly",  "credit"),
    ("KCFSI",           "kcfsi",                "monthly", "credit"),
    # HOUSING
    ("CSUSHPINSA",      "case_shiller_hpi",     "monthly", "housing"),
    ("HOUST",           "housing_starts",       "monthly", "housing"),
    ("PERMIT",          "building_permits",     "monthly", "housing"),
    ("EXHOSLUSM495S",   "existing_home_sales",  "monthly", "housing"),
    ("MORTGAGE30US",    "mortgage_30y",         "weekly",  "housing"),
    # TRADE
    ("BOPGSTB",         "trade_balance",        "monthly", "trade"),
    ("IMPGS",           "imports_gs",           "quarterly","trade"),
    ("EXPGS",           "exports_gs",           "quarterly","trade"),
    # CURRENCY
    ("DTWEXBGS",        "usd_broad",            "daily",   "fx"),
    ("DEXUSEU",         "usd_eur",              "daily",   "fx"),
    ("DEXJPUS",         "jpy_usd",              "daily",   "fx"),
    ("DEXCHUS",         "cny_usd",              "daily",   "fx"),
    # COMMODITIES
    ("DCOILWTICO",      "wti_crude",            "daily",   "commodities"),
    ("DCOILBRENTEU",    "brent_crude",          "daily",   "commodities"),
    ("DHHNGSP",         "henry_hub_natgas",     "daily",   "commodities"),
    ("GOLDAMGBD228NLBM","gold_london_fix",      "daily",   "commodities"),
    ("SLVPRUSD",        "silver_fix",           "daily",   "commodities"),  # DEXSLVFIX likely wrong
    ("PCOPPUSDM",       "copper_price",         "monthly", "commodities"),
    ("WPU10250105",     "platinum_ppi",         "monthly", "commodities"),  # WPU081 likely wrong
    ("PALUMUSDM",       "aluminum_price",       "monthly", "commodities"),  # PCU3313133131 likely wrong
    # LEADING INDICATORS
    ("USSLIND",         "leading_econ_index",   "monthly", "leading"),
    ("USALOLITONOSTSAM","oecd_cli_us",          "monthly", "leading"),
    # MISC
    ("TOTALSA",         "vehicle_sales",        "monthly", "misc"),
    ("DRCCLACBS",       "credit_card_delinq",   "quarterly","misc"),
    ("DRALACBN",        "auto_loan_delinq",     "quarterly","misc"),  # DRSFRMACBS likely wrong
    ("BOGZ1FL073164003Q","student_loan_delinq", "quarterly","misc"),
]


# Fallback alternate IDs for series that often fail or have changed names
ALTERNATES = {
    "NMFBAI":   ["ISMNONMFG", "NMFCI"],
    "CONCCONF": ["UMCSENT"],   # already downloaded; will be skipped
    "CPFF":     ["DCPF1M", "DCPF3M"],
    "TEDRATE":  [],            # discontinued 2022; accept short history
    "EXHOSLUSM495S": ["HSN1F"],
    "DRALACBN": ["DRSFRMACBS", "DALLACBW027SBOG"],
    "SLVPRUSD": [],
    "WPU10250105": [],
    "PALUMUSDM": [],
    "PCOPPUSDM": ["PCOPPUSDQ"],
    "GOLDAMGBD228NLBM": ["GOLDPMGBD228NLBM"],
}


_FREQ_LIMITS = {
    "daily":     5,
    "weekly":    5,
    "monthly":   22,
    "quarterly": 66,
}


def _try_download_with_alternates(series_id: str, start, end):
    df = download_fred(series_id, start=start, end=end)
    if not df.empty:
        return series_id, df
    for alt in ALTERNATES.get(series_id, []):
        print(f"  ~ {series_id}: trying alternate {alt}")
        df = download_fred(alt, start=start, end=end)
        if not df.empty:
            df.columns = [series_id]
            return alt, df
    return series_id, pd.DataFrame()


def fetch_series(
    series_id: str,
    descriptive_name: str,
    source_freq: str,
    start: Optional[str] = "2000-01-01",
    end: Optional[str] = None,
) -> dict:
    """Download one series, save raw + clean, return summary dict."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    CLEAN_DIR.mkdir(parents=True, exist_ok=True)
    raw_path = RAW_DIR / f"{series_id}.parquet"
    clean_path = CLEAN_DIR / f"{descriptive_name}.parquet"

    used_id, df = _try_download_with_alternates(series_id, start, end)
    if df.empty:
        log_failure(FAILED_PATH, f"fred:{series_id}", "no data after alternates", "")
        return {"series_id": series_id, "ok": False, "reason": "no_data"}

    try:
        df.to_parquet(raw_path)
    except Exception as e:
        print(f"  ! {series_id}: raw save failed: {e}")

    limit = _FREQ_LIMITS.get(source_freq, 5)
    cleaned = align_to_trading_days(df, method="ffill", limit=limit, source_freq=source_freq)
    cleaned.columns = [descriptive_name]

    status = "OK"
    notes = "" if used_id == series_id else f"alt:{used_id}"
    valid = cleaned.dropna()
    if valid.empty:
        status = "EMPTY"
    else:
        years = (valid.index.max() - valid.index.min()).days / 365.25
        if years < 5:
            status = "SHORT"
            notes = (notes + f" history={years:.1f}y").strip()

    save_clean(
        cleaned,
        clean_path,
        metadata={
            "series_id": series_id,
            "used_id": used_id,
            "descriptive_name": descriptive_name,
            "source": "fred",
            "source_frequency": source_freq,
        },
    )

    if not valid.empty:
        s_date = str(valid.index.min().date())
        e_date = str(valid.index.max().date())
    else:
        s_date = e_date = "n/a"

    log_to_catalog(
        CATALOG_PATH,
        {
            "source": "fred",
            "series_name": series_id,
            "frequency": source_freq,
            "date_range": f"{s_date}..{e_date}",
            "file_path": str(clean_path.relative_to(DATA_DIR.parent)).replace("\\", "/"),
            "status": status,
            "notes": notes,
        },
    )

    return {
        "series_id": series_id,
        "used_id": used_id,
        "descriptive_name": descriptive_name,
        "ok": True,
        "status": status,
        "rows": int(len(cleaned)),
        "start": s_date,
        "end": e_date,
        "freq": source_freq,
        "notes": notes,
    }


def fetch_margin_debt() -> dict:
    """FRED BOGZ1FL663067003Q: Margin Accounts at Brokers/Dealers (quarterly, Z.1).

    Substitute for the Akamai-blocked FINRA margin debt statistics. Saved to
    data/clean/sentiment/ rather than macro/ because it's a sentiment signal.
    """
    sentiment_dir = DATA_DIR / "clean" / "sentiment"
    sentiment_dir.mkdir(parents=True, exist_ok=True)
    series_id = "BOGZ1FL663067003Q"
    descriptive_name = "margin_debt_fred"
    clean_path = sentiment_dir / f"{descriptive_name}.parquet"
    raw_path = RAW_DIR / f"{series_id}.parquet"
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    df = download_fred(series_id, start="2000-01-01")
    if df.empty:
        log_failure(FAILED_PATH, f"fred:{series_id}", "no data", "")
        return {"series_id": series_id, "ok": False}
    try:
        df.to_parquet(raw_path)
    except Exception as e:
        print(f"  ! raw save failed: {e}")

    cleaned = align_to_trading_days(df, method="ffill", limit=66, source_freq="quarterly")
    cleaned.columns = [descriptive_name]
    valid = cleaned.dropna()
    s_date = str(valid.index.min().date()) if not valid.empty else "n/a"
    e_date = str(valid.index.max().date()) if not valid.empty else "n/a"
    save_clean(
        cleaned,
        clean_path,
        metadata={
            "series_id": series_id,
            "descriptive_name": descriptive_name,
            "source": "fred",
            "source_frequency": "quarterly",
            "note": "Substitute for FINRA margin debt (Akamai-blocked). Z.1 line 663067003: Margin Accounts at Brokers/Dealers.",
        },
    )
    log_to_catalog(
        CATALOG_PATH,
        {
            "source": "fred",
            "series_name": series_id,
            "frequency": "quarterly",
            "date_range": f"{s_date}..{e_date}",
            "file_path": str(clean_path.relative_to(DATA_DIR.parent)).replace("\\", "/"),
            "status": "OK",
            "notes": "margin debt; substitute for FINRA (Akamai-blocked)",
        },
    )
    return {"series_id": series_id, "ok": True, "rows": int(len(cleaned)), "start": s_date, "end": e_date}


def fetch_all(
    start: str = "2000-01-01",
    end: Optional[str] = None,
    pause: float = 0.4,
) -> dict:
    """Download every series in SERIES. Returns summary dict."""
    summary = {"ok": [], "failed": [], "details": []}
    for sid, name, freq, cat in SERIES:
        print(f"--- {sid} ({name}, {freq}) ---")
        try:
            res = fetch_series(sid, name, freq, start=start, end=end)
        except Exception as e:
            print(f"  ! {sid}: exception {e}")
            log_failure(FAILED_PATH, f"fred:{sid}", f"exception: {e}", "")
            summary["failed"].append(sid)
            continue
        if res.get("ok"):
            summary["ok"].append(sid)
            summary["details"].append(res)
            print(f"  + {sid} -> {res['start']}..{res['end']}  rows={res['rows']}  {res['status']}  {res['notes']}")
        else:
            summary["failed"].append(sid)
            print(f"  x {sid}: {res.get('reason')}")
        time.sleep(pause)
    return summary
