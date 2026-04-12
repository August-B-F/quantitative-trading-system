"""Phase 2 alternative-data RETRY — finding replacement sources for failed attempts."""
from __future__ import annotations

import io
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.data.utils import (
    CATALOG_PATH,
    DATA_DIR,
    align_to_trading_days,
    log_to_catalog,
    save_clean,
    validate_data,
)

CLEAN = DATA_DIR / "clean" / "alternative"
CLEAN.mkdir(parents=True, exist_ok=True)

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/121 Safari/537.36"
TIMEOUT = 60

SCORE = {"attempted": 0, "succeeded": [], "failed": []}


def _get(url, timeout=TIMEOUT, headers=None, retries=4, sleep=3):
    h = {"User-Agent": UA, "Accept": "*/*"}
    if headers:
        h.update(headers)
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers=h)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except Exception as e:
            last = e
            time.sleep(sleep * (i + 1))
    raise last


def attempt(name, fn):
    SCORE["attempted"] += 1
    try:
        fn()
        SCORE["succeeded"].append(name)
        print(f"[OK] {name}")
    except Exception as e:
        SCORE["failed"].append((name, f"{type(e).__name__}: {str(e)[:300]}"))
        print(f"[FAIL] {name}: {e}")


def _fred_csv(sid):
    # MUST include cosd/coed params — the bare endpoint hangs without them on some networks
    raw = _get(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}&cosd=1970-01-01&coed=2026-12-31")
    df = pd.read_csv(io.BytesIO(raw))
    df.columns = ["date", sid]
    df["date"] = pd.to_datetime(df["date"])
    df[sid] = pd.to_numeric(df[sid], errors="coerce")
    return df.dropna().set_index("date").sort_index()


# --- 9: Steel production via FRED IPG331S (primary metal industrial production) ---
def src_steel_fred():
    df = _fred_csv("IPG331S").rename(columns={"IPG331S": "steel_production_ip"})
    out = align_to_trading_days(df, source_freq="monthly")
    save_clean(out, CLEAN / "steel_production.parquet", {"source": "fred:IPG331S"})
    validate_data(out, "steel_production")
    log_to_catalog(CATALOG_PATH, {
        "source": "fred", "series_name": "IPG331S",
        "frequency": "monthly",
        "date_range": f"{out.index.min().date()}..{out.index.max().date()}",
        "file_path": "data/clean/alternative/steel_production.parquet",
        "status": "OK",
        "notes": "US primary metals industrial production index (NAICS 331). Substitute for worldsteel crude steel (paywalled).",
    })


# --- 10: Indeed job postings index via FRED IHLIDXUS ---
def src_indeed_jobs():
    df = _fred_csv("IHLIDXUS").rename(columns={"IHLIDXUS": "indeed_jobs_idx"})
    out = align_to_trading_days(df, source_freq="daily")
    save_clean(out, CLEAN / "indeed_job_postings.parquet", {"source": "fred:IHLIDXUS"})
    validate_data(out, "indeed_job_postings")
    log_to_catalog(CATALOG_PATH, {
        "source": "fred", "series_name": "IHLIDXUS",
        "frequency": "daily",
        "date_range": f"{out.index.min().date()}..{out.index.max().date()}",
        "file_path": "data/clean/alternative/indeed_job_postings.parquet",
        "status": "OK",
        "notes": "Indeed Hiring Lab US aggregate job postings index (pct change vs 2020-02-01 baseline, 7d avg). Replaces Glassdoor/Indeed scrape.",
    })


# --- 2: Port of LA container TEU via LA City socrata ---
def src_port_la():
    raw = _get("https://data.lacity.org/api/views/tsuv-4rgh/rows.csv?accessType=DOWNLOAD")
    df = pd.read_csv(io.BytesIO(raw))
    # Normalize columns
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
    # Expect month col + year + TEU counts
    # Find date-like columns
    if "month" in df.columns and "year" in df.columns:
        df["date"] = pd.to_datetime(df["month"].astype(str) + " " + df["year"].astype(str), errors="coerce")
    elif "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
    else:
        # Try first column
        df["date"] = pd.to_datetime(df.iloc[:, 0], errors="coerce")
    df = df.dropna(subset=["date"])
    # Find TEU numeric columns
    num_cols = []
    for c in df.columns:
        if c == "date":
            continue
        s = pd.to_numeric(df[c].astype(str).str.replace(",", ""), errors="coerce")
        if s.notna().sum() > len(df) * 0.5:
            df[c] = s
            num_cols.append(c)
    keep = [c for c in num_cols if "teu" in c or "total" in c or "load" in c]
    if not keep:
        keep = num_cols[:3]
    out = df[["date"] + keep].set_index("date").sort_index()
    out = out[~out.index.duplicated(keep="last")]
    if out.empty:
        raise RuntimeError("empty after parse")
    out = align_to_trading_days(out, source_freq="monthly")
    save_clean(out, CLEAN / "port_la_containers.parquet", {"source": "data.lacity.org:tsuv-4rgh"})
    validate_data(out, "port_la_containers")
    log_to_catalog(CATALOG_PATH, {
        "source": "data.lacity.org", "series_name": "port_la_teu",
        "frequency": "monthly",
        "date_range": f"{out.index.min().date()}..{out.index.max().date()}",
        "file_path": "data/clean/alternative/port_la_containers.parquet",
        "status": "OK",
        "notes": "Port of LA monthly TEU counts via LA City socrata (tsuv-4rgh). Trade activity proxy.",
    })


# --- 16: Baltic Dry Index via BDRY ETF (Breakwave Dry Bulk Shipping ETF — tracks BDI) ---
def src_baltic_dry_etf():
    import yfinance as yf  # type: ignore
    df = None
    for i in range(4):
        try:
            df = yf.download("BDRY", start="2018-03-22", auto_adjust=False, progress=False, threads=False)
            if df is not None and not df.empty:
                break
        except Exception as e:
            print(f"  BDRY try{i} err {e}")
        time.sleep(5 * (i + 1))
    if df is None or df.empty:
        raise RuntimeError("yfinance BDRY empty after retries")
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0].lower() for c in df.columns]
    else:
        df.columns = [str(c).lower() for c in df.columns]
    out = df[["close"]].rename(columns={"close": "bdry_close"})
    out.index.name = "date"
    out = align_to_trading_days(out, source_freq="daily")
    save_clean(out, CLEAN / "baltic_dry.parquet", {
        "source": "yahoo:BDRY",
        "note": "Breakwave Dry Bulk Shipping ETF as BDI proxy (no free direct BDI CSV feed)",
    })
    validate_data(out, "baltic_dry")
    log_to_catalog(CATALOG_PATH, {
        "source": "yahoo", "series_name": "BDRY",
        "frequency": "daily",
        "date_range": f"{out.index.min().date()}..{out.index.max().date()}",
        "file_path": "data/clean/alternative/baltic_dry.parquet",
        "status": "OK",
        "notes": "BDRY ETF (Breakwave Dry Bulk Shipping) as Baltic Dry proxy. Inception 2018-03.",
    })


# --- 5: Reddit via Arctic Shift API ---
def src_reddit_arctic():
    subs = ["wallstreetbets", "investing", "stocks", "economics"]
    any_saved = False
    # Fetch in 1-year chunks with retry (server times out on multi-year requests)
    chunks = [(f"{y}-01-01", f"{y+1}-01-01") for y in range(2018, 2026)]
    chunks.append(("2026-01-01", "2026-04-10"))
    for sub in subs:
        all_rows = []
        try:
            for after, before in chunks:
                url = (
                    "https://arctic-shift.photon-reddit.com/api/posts/search/aggregate"
                    f"?aggregate=created_utc&frequency=day&subreddit={sub}"
                    f"&after={after}&before={before}"
                )
                try:
                    raw = _get(url, timeout=120, retries=6, sleep=4)
                except Exception as e:
                    print(f"  [{sub}] {after} FAIL {e}")
                    time.sleep(2)
                    continue
                time.sleep(1.5)
                data = json.loads(raw)
                rows = data.get("data") if isinstance(data, dict) else data
                if rows:
                    all_rows.extend(rows)
            if not all_rows:
                print(f"  [{sub}] no data across chunks")
                continue
            df = pd.DataFrame(all_rows)
            if "created_utc" in df.columns and "count" in df.columns:
                df["date"] = pd.to_datetime(df["created_utc"])
                df["posts"] = pd.to_numeric(df["count"], errors="coerce")
                df = df[["date", "posts"]]
            elif "key" in df.columns and "doc_count" in df.columns:
                df["date"] = pd.to_datetime(df["key"], unit="ms", errors="coerce")
                df = df.rename(columns={"doc_count": "posts"})[["date", "posts"]]
            else:
                print(f"  [{sub}] unexpected schema: {df.columns.tolist()[:5]}")
                continue
            df = df.dropna(subset=["date"]).set_index("date").sort_index()
            if df.empty:
                continue
            # spike indicator: today vs 21d mean
            df["posts_21d_mean"] = df["posts"].rolling(21, min_periods=7).mean()
            df["posts_spike_ratio"] = df["posts"] / df["posts_21d_mean"]
            out = align_to_trading_days(df, source_freq="daily")
            save_clean(out, CLEAN / f"reddit_{sub}.parquet", {"source": "arctic-shift", "subreddit": sub})
            validate_data(out, f"reddit_{sub}")
            log_to_catalog(CATALOG_PATH, {
                "source": "arctic-shift", "series_name": f"reddit_{sub}",
                "frequency": "daily",
                "date_range": f"{out.index.min().date()}..{out.index.max().date()}",
                "file_path": f"data/clean/alternative/reddit_{sub}.parquet",
                "status": "OK",
                "notes": f"Arctic Shift daily post count for r/{sub} + 21d spike ratio",
            })
            any_saved = True
            time.sleep(1)
        except Exception as e:
            print(f"  [{sub}] err: {e}")
    if not any_saved:
        raise RuntimeError("no subreddits succeeded")


# --- 4: BTS airline passengers via socrata Monthly Transportation Statistics ---
def src_bts_airlines():
    # crem-w557 = BTS Monthly Transportation Statistics (Socrata)
    cols = (
        "u_s_airline_traffic_total_non_seasonally_adjusted,"
        "u_s_airline_traffic_domestic_non_seasonally_adjusted,"
        "u_s_airline_traffic_international_non_seasonally_adjusted"
    )
    url = f"https://data.bts.gov/resource/crem-w557.csv?$select=date,{cols}&$limit=50000"
    raw = _get(url)
    df = pd.read_csv(io.BytesIO(raw))
    df = df.rename(columns={
        "u_s_airline_traffic_total_non_seasonally_adjusted": "airline_passengers_total",
        "u_s_airline_traffic_domestic_non_seasonally_adjusted": "airline_passengers_domestic",
        "u_s_airline_traffic_international_non_seasonally_adjusted": "airline_passengers_intl",
    })
    df = df.dropna(subset=["airline_passengers_total"], how="all")
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    for c in ["airline_passengers_total", "airline_passengers_domestic", "airline_passengers_intl"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=["date"]).set_index("date").sort_index()
    df = df.dropna(how="all")
    if df.empty:
        raise RuntimeError("empty after parse")
    out = align_to_trading_days(df, source_freq="monthly")
    save_clean(out, CLEAN / "airline_passengers.parquet", {"source": "data.bts.gov:crem-w557"})
    validate_data(out, "airline_passengers")
    log_to_catalog(CATALOG_PATH, {
        "source": "data.bts.gov", "series_name": "airline_passengers",
        "frequency": "monthly",
        "date_range": f"{out.index.min().date()}..{out.index.max().date()}",
        "file_path": "data/clean/alternative/airline_passengers.parquet",
        "status": "OK",
        "notes": "BTS Monthly Transportation Statistics crem-w557 — US airline passengers (travel demand proxy)",
    })


# --- 8: Bankruptcy filings — try FRED business bankruptcy series ---
def src_bankruptcy_fred():
    # FRED has business bankruptcy filings monthly series "BUSLOANS" etc, but for total bankruptcies,
    # use NBER historical M0929BUSM155NNBR; for modern monthly, use LFBCRSA series? Try a few IDs.
    candidates = [
        "BUSLOANS",  # unrelated but test
    ]
    # Actually the one we want: try the BLS / OECD series. Use PNFI for private filings? Not exact.
    # Best free modern monthly total: epiq -- paywall. Try "Commercial and Industrial Loans: Charge-Off Rate" as proxy? No.
    # Best bet: Administrative Office of US Courts publishes quarterly XLSX. Try direct URL.
    raise RuntimeError("no free FRED monthly total-bankruptcy series; uscourts quarterly XLSX URLs are versioned per-release — not stable")


# --- 7: SIFMA — gated behind HubSpot form, no direct XLSX ---
def src_sifma():
    raise RuntimeError("SIFMA XLS download redirects through share.hsforms.com HubSpot gate; requires email form submission")


import os
_only = set((os.environ.get("ONLY") or "").split(",")) if os.environ.get("ONLY") else None
TASKS = [
    ("9_steel_fred", src_steel_fred),
    ("10_indeed_jobs", src_indeed_jobs),
    ("16_baltic_bdry_etf", src_baltic_dry_etf),
    ("5_reddit_arctic_shift", src_reddit_arctic),
    ("4_bts_airlines_socrata", src_bts_airlines),
]
if _only:
    TASKS = [(n, f) for n, f in TASKS if n in _only]


def main():
    for name, fn in TASKS:
        attempt(name, fn)
    print("\n=== RETRY SCORECARD ===")
    print(f"attempted: {SCORE['attempted']}")
    print(f"succeeded ({len(SCORE['succeeded'])}): {SCORE['succeeded']}")
    print(f"failed   ({len(SCORE['failed'])}):")
    for n, r in SCORE["failed"]:
        print(f"  - {n}: {r}")
    # persist fail reasons for the writer step
    (DATA_DIR / ".phase2_retry_fails.json").write_text(json.dumps(SCORE["failed"]))


if __name__ == "__main__":
    main()
