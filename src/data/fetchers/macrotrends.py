"""Macrotrends fetcher.

Macrotrends embeds chart data as JSON inside an iframe page:
  https://www.macrotrends.net/assets/php/chart_iframe_comp.php?id=<ID>
The page contains a JS literal `originalData = [{"date":..., "close":...}, ...]`
which we extract directly with a regex (no JS execution needed).

robots.txt allows the chart paths but blocks /search/, /series/, etc., so we
only hit known IDs and the iframe endpoint, never the search.

Sector PE / profit-margin / buyback-yield series IDs are not stable / not
findable without site search; logged as not-attempted. Commodity series serve
as FRED backups.
"""
from __future__ import annotations

import json
import re
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

CLEAN_DIR = DATA_DIR / "clean" / "fundamental"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    ),
    "Referer": "https://www.macrotrends.net/",
    "Accept": "text/html",
}

# (name, id, frequency)
SERIES = [
    ("sp500_pe_ratio", 2577, "monthly"),
    ("crude_oil_wti", 1369, "daily"),
    ("gold_london_fix", 1333, "daily"),
    ("silver_price", 1470, "daily"),
    ("copper_price", 1476, "daily"),
    ("natural_gas_henry_hub", 2478, "daily"),
]

_DATA_RE = re.compile(r"originalData\s*=\s*(\[.*?\]);", re.S)


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


def _parse(text: str) -> pd.DataFrame:
    m = _DATA_RE.search(text)
    if not m:
        return pd.DataFrame()
    raw = json.loads(m.group(1))
    df = pd.DataFrame(raw)
    if "date" not in df.columns or "close" not in df.columns:
        return pd.DataFrame()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["close"] = pd.to_numeric(df["close"], errors="coerce")
    df = df.dropna(subset=["date", "close"]).set_index("date").sort_index()
    return df[["close"]]


def fetch_one(name: str, chart_id: int, freq: str) -> None:
    url = f"https://www.macrotrends.net/assets/php/chart_iframe_comp.php?id={chart_id}"
    print(f"[macrotrends] {name} <- id={chart_id}")
    r = _get(url)
    if r is None or r.status_code != 200:
        sc = r.status_code if r is not None else "ERR"
        log_failure(FAILED_PATH, f"macrotrends:{name}", f"HTTP {sc}", attempted=url)
        print(f"  ! failed {sc}")
        return
    df = _parse(r.text)
    if df.empty:
        log_failure(FAILED_PATH, f"macrotrends:{name}", "originalData not found", attempted=url)
        print("  ! no data")
        return
    df = df.rename(columns={"close": name})
    aligned = align_to_trading_days(df, source_freq=freq)
    path = CLEAN_DIR / f"sector_{name}.parquet"
    save_clean(aligned, path, metadata={"source": "macrotrends", "chart_id": chart_id, "url": url})
    validate_data(aligned, name=f"sector_{name}")
    log_to_catalog(CATALOG_PATH, {
        "source": "macrotrends",
        "series_name": f"sector_{name}",
        "frequency": freq,
        "date_range": f"{aligned.index.min().date()}..{aligned.index.max().date()}",
        "file_path": str(path.relative_to(DATA_DIR.parent)).replace("\\", "/"),
        "status": "OK",
        "notes": f"chart_iframe_comp id={chart_id}",
    })


def main() -> None:
    CLEAN_DIR.mkdir(parents=True, exist_ok=True)
    for name, cid, freq in SERIES:
        fetch_one(name, cid, freq)
        time.sleep(3)
    # Series with unknown stable IDs — log so future work can fill in
    for missing in ("tech_sector_pe", "energy_sector_earnings", "sp500_profit_margin", "sp500_buyback_yield"):
        log_failure(
            FAILED_PATH,
            f"macrotrends:{missing}",
            "no stable chart_iframe_comp ID known; would require site search (disallowed by robots /search/)",
            attempted="search bypass not attempted",
        )


if __name__ == "__main__":
    main()
