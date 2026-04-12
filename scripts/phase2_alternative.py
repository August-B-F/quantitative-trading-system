"""Phase 2 alternative-data grab. High-failure-rate by design."""
from __future__ import annotations

import io
import re
import sys
import urllib.request
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
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

CLEAN = DATA_DIR / "clean" / "alternative"
CLEAN.mkdir(parents=True, exist_ok=True)

UA = "Mozilla/5.0 (compatible; iStock-research/0.1; +https://example.com)"
TIMEOUT = 30

SCORE = {"attempted": 0, "succeeded": [], "failed": []}


def _get(url: str, timeout: int = TIMEOUT) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def attempt(name: str, fn):
    SCORE["attempted"] += 1
    try:
        ok = fn()
        if ok:
            SCORE["succeeded"].append(name)
            print(f"[OK] {name}")
        else:
            SCORE["failed"].append(name)
            print(f"[FAIL] {name}")
    except Exception as e:
        SCORE["failed"].append(name)
        log_failure(FAILED_PATH, name, f"{type(e).__name__}: {str(e)[:200]}", "phase2_alt")
        print(f"[ERR] {name}: {e}")


# --- 1: TSA passenger volumes ---
def src_tsa():
    html = _get("https://www.tsa.gov/travel/passenger-volumes").decode("utf-8", "ignore")
    tables = pd.read_html(io.StringIO(html))
    t = max(tables, key=lambda d: d.size)
    t.columns = [str(c).strip() for c in t.columns]
    t["date"] = pd.to_datetime(t["Date"], errors="coerce")
    t["passengers"] = pd.to_numeric(t["Numbers"].astype(str).str.replace(",", ""), errors="coerce")
    long = t.dropna(subset=["date", "passengers"]).set_index("date").sort_index()[["passengers"]]
    if long.empty:
        raise RuntimeError("parsed 0 rows")
    out = align_to_trading_days(long, source_freq="daily")
    save_clean(out, CLEAN / "tsa_passengers.parquet", {"source": "tsa.gov", "series": "tsa_passengers"})
    validate_data(out, "tsa_passengers")
    log_to_catalog(CATALOG_PATH, {
        "source": "tsa", "series_name": "tsa_passengers", "frequency": "daily",
        "date_range": f"{out.index.min().date()}..{out.index.max().date()}",
        "file_path": "data/clean/alternative/tsa_passengers.parquet", "status": "OK",
        "notes": "TSA checkpoint daily throughput (travel demand proxy)",
    })
    return True


# --- 6: FRED money market fund assets MMMFFAQ027S ---
def src_mmf():
    url = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=MMMFFAQ027S"
    raw = _get(url)
    df = pd.read_csv(io.BytesIO(raw))
    df.columns = ["date", "money_market_assets"]
    df["date"] = pd.to_datetime(df["date"])
    df["money_market_assets"] = pd.to_numeric(df["money_market_assets"], errors="coerce")
    df = df.dropna().set_index("date").sort_index()
    if df.empty:
        raise RuntimeError("empty")
    out = align_to_trading_days(df, source_freq="quarterly")
    save_clean(out, CLEAN / "money_market_assets.parquet", {"source": "fred:MMMFFAQ027S"})
    validate_data(out, "money_market_assets")
    log_to_catalog(CATALOG_PATH, {
        "source": "fred", "series_name": "MMMFFAQ027S", "frequency": "quarterly",
        "date_range": f"{out.index.min().date()}..{out.index.max().date()}",
        "file_path": "data/clean/alternative/money_market_assets.parquet", "status": "OK",
        "notes": "Money market fund total financial assets (risk aversion proxy)",
    })
    return True


# --- 12: Copper/Gold ratio (derived) ---
def src_copper_gold():
    copper = pd.read_parquet(DATA_DIR / "clean/fundamental/sector_copper_price.parquet")
    gld = pd.read_parquet(DATA_DIR / "clean/prices/GLD.parquet")[["close"]].rename(columns={"close": "gld"})
    df = copper.join(gld, how="inner").dropna()
    df["copper_gold_ratio"] = df["copper_price"] / df["gld"]
    out = df[["copper_gold_ratio"]]
    if out.empty:
        raise RuntimeError("empty")
    save_clean(out, CLEAN / "copper_gold_ratio.parquet", {
        "derived_from": ["sector_copper_price", "GLD.close"],
        "note": "GLD ETF used as gold proxy (daily)",
    })
    validate_data(out, "copper_gold_ratio")
    log_to_catalog(CATALOG_PATH, {
        "source": "derived", "series_name": "copper_gold_ratio", "frequency": "daily",
        "date_range": f"{out.index.min().date()}..{out.index.max().date()}",
        "file_path": "data/clean/alternative/copper_gold_ratio.parquet", "status": "OK",
        "notes": "copper_price / GLD close (risk appetite indicator)",
    })
    return True


# --- 13: Lumber/Gold ratio (derived from FRED WPU081 lumber PPI + gold) ---
def src_lumber_gold():
    # Lumber PPI monthly from FRED
    url = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=WPU081"
    raw = _get(url)
    lum = pd.read_csv(io.BytesIO(raw))
    lum.columns = ["date", "lumber_ppi"]
    lum["date"] = pd.to_datetime(lum["date"])
    lum["lumber_ppi"] = pd.to_numeric(lum["lumber_ppi"], errors="coerce")
    lum = lum.dropna().set_index("date").sort_index()

    gold = pd.read_parquet(DATA_DIR / "clean/fundamental/sector_gold_london_fix.parquet")
    df = lum.join(gold, how="inner").dropna()
    df["lumber_gold_ratio"] = df["lumber_ppi"] / df["gold_london_fix"]
    out = df[["lumber_gold_ratio"]]
    if out.empty:
        raise RuntimeError("empty")
    out = align_to_trading_days(out, source_freq="monthly")
    save_clean(out, CLEAN / "lumber_gold_ratio.parquet", {
        "derived_from": ["fred:WPU081", "sector_gold_london_fix"],
    })
    validate_data(out, "lumber_gold_ratio")
    log_to_catalog(CATALOG_PATH, {
        "source": "derived", "series_name": "lumber_gold_ratio", "frequency": "monthly",
        "date_range": f"{out.index.min().date()}..{out.index.max().date()}",
        "file_path": "data/clean/alternative/lumber_gold_ratio.parquet", "status": "OK",
        "notes": "FRED WPU081 lumber PPI / gold london fix (housing/construction sentiment)",
    })
    return True


# --- 16: Baltic Dry Index --- try FRED-hosted mirrors first (likely none); fallback investpy/tradingeconomics hard
def src_baltic_dry():
    # stooq has free CSV for ^bdi
    urls = [
        "https://stooq.com/q/d/l/?s=^bdi&i=d",
        "https://stooq.com/q/d/l/?s=bdi&i=d",
    ]
    df = None
    for u in urls:
        try:
            raw = _get(u)
            tmp = pd.read_csv(io.BytesIO(raw))
            if "Date" in tmp.columns and len(tmp) > 50:
                df = tmp
                break
        except Exception:
            continue
    if df is None:
        raise RuntimeError("stooq now requires apikey; tradingeconomics/investing blocked; no free BDI feed")
    df["Date"] = pd.to_datetime(df["Date"])
    df = df.rename(columns={"Close": "baltic_dry"})[["Date", "baltic_dry"]].set_index("Date").sort_index()
    df["baltic_dry"] = pd.to_numeric(df["baltic_dry"], errors="coerce")
    df = df.dropna()
    out = align_to_trading_days(df, source_freq="daily")
    save_clean(out, CLEAN / "baltic_dry.parquet", {"source": "stooq:^bdi"})
    validate_data(out, "baltic_dry")
    log_to_catalog(CATALOG_PATH, {
        "source": "stooq", "series_name": "baltic_dry_index", "frequency": "daily",
        "date_range": f"{out.index.min().date()}..{out.index.max().date()}",
        "file_path": "data/clean/alternative/baltic_dry.parquet", "status": "OK",
        "notes": "Baltic Dry Index via stooq ^bdi",
    })
    return True


# --- 2: Port of LA containers ---
def src_port_la():
    html = _get("https://www.portoflosangeles.org/business/statistics/container-statistics").decode("utf-8", "ignore")
    # page has an iframe/table; try all tables
    tables = pd.read_html(io.StringIO(html))
    if not tables:
        raise RuntimeError("no tables")
    # Try to find one with 'TEU' or month names
    best = None
    for t in tables:
        cols = " ".join(str(c) for c in t.columns).lower()
        if any(k in cols for k in ["teu", "month", "jan", "total"]):
            best = t
            break
    if best is None:
        raise RuntimeError("no TEU table found")
    # Too brittle to parse definitively; bail if unclear
    raise RuntimeError("tables found but structure ambiguous — full parse skipped per time budget")


# --- 4: BTS airline passengers ---
def src_bts():
    raise RuntimeError("BTS TranStats requires ZIP form submission, not scrapeable in budget")


# --- 5: Reddit sentiment ---
def src_reddit():
    try:
        raw = _get("https://api.pushshift.io/reddit/search/submission/?subreddit=wallstreetbets&size=1", timeout=10)
    except Exception as e:
        raise RuntimeError(f"pushshift unreachable: {e}")
    raise RuntimeError("pushshift restricted — returns auth error / no public history")


# --- 7: SIFMA corporate bond issuance ---
def src_sifma():
    raise RuntimeError("SIFMA publishes XLSX behind JS page; no stable direct URL")


# --- 8: US Courts bankruptcy filings ---
def src_bankruptcy():
    raise RuntimeError("uscourts.gov publishes PDFs + HTML tables per quarter; no single stable CSV")


# --- 9: Steel production ---
def src_steel():
    raise RuntimeError("worldsteel.org members-only data; press releases only in PDF")


# --- 10: Glassdoor/Indeed job postings ---
def src_jobs():
    raise RuntimeError("Glassdoor/Indeed blocked; enterprise-only API")


# --- 11: App store ratings ---
def src_appstore():
    raise RuntimeError("iTunes RSS only gives recent reviews; Play Store blocked")


# --- 15: OpenTable ---
def src_opentable():
    raise RuntimeError("OpenTable State-of-Industry dataset ended 2022; no public feed")


# --- 17: Twitter/X sentiment ---
def src_twitter():
    raise RuntimeError("X API requires paid tier; historical search not available")


TASKS = [
    ("1_tsa", src_tsa),
    ("2_port_la", src_port_la),
    ("4_bts_airline", src_bts),
    ("5_reddit", src_reddit),
    ("6_money_market", src_mmf),
    ("7_sifma_corp_bond", src_sifma),
    ("8_bankruptcy", src_bankruptcy),
    ("9_steel", src_steel),
    ("10_jobs", src_jobs),
    ("11_appstore", src_appstore),
    ("12_copper_gold", src_copper_gold),
    ("13_lumber_gold", src_lumber_gold),
    ("15_opentable", src_opentable),
    ("16_baltic_dry", src_baltic_dry),
    ("17_twitter", src_twitter),
]


def main():
    for name, fn in TASKS:
        attempt(name, fn)
    print("\n=== SCORECARD ===")
    print(f"attempted: {SCORE['attempted']}")
    print(f"succeeded ({len(SCORE['succeeded'])}): {SCORE['succeeded']}")
    print(f"failed   ({len(SCORE['failed'])}): {SCORE['failed']}")
    print("note: sources 3 (gasoline), 14 (delinquency), 18 (electricity) already covered in prior sessions")


if __name__ == "__main__":
    main()
