"""Re-align macrotrends commodity series with correct source_freq='monthly'.

Original fetch treated them as daily with ffill limit=5, which produced ~73% NaN.
Raw data is monthly (median gap 31d). Re-align with source_freq='monthly'
(ffill limit=22). Copper is actually daily and is left untouched.
"""
from __future__ import annotations

import json
import re

import pandas as pd
import requests

from src.data.utils import (
    DATA_DIR,
    align_to_trading_days,
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
}

# All four confirmed-monthly commodity series
SERIES = [
    ("gold_london_fix", 1333),
    ("silver_price", 1470),
    ("crude_oil_wti", 1369),
    ("natural_gas_henry_hub", 2478),
]

_DATA_RE = re.compile(r"originalData\s*=\s*(\[.*?\]);", re.S)


def fetch_raw(chart_id: int) -> pd.DataFrame:
    url = f"https://www.macrotrends.net/assets/php/chart_iframe_comp.php?id={chart_id}"
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    m = _DATA_RE.search(r.text)
    raw = json.loads(m.group(1))
    df = pd.DataFrame(raw)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["close"] = pd.to_numeric(df["close"], errors="coerce")
    df = df.dropna().set_index("date").sort_index()
    return df[["close"]]


def main() -> None:
    for name, cid in SERIES:
        print(f"[fix] {name} (id={cid})")
        raw = fetch_raw(cid).rename(columns={"close": name})
        aligned = align_to_trading_days(raw, source_freq="monthly")
        path = CLEAN_DIR / f"sector_{name}.parquet"
        save_clean(
            aligned,
            path,
            metadata={
                "source": "macrotrends",
                "chart_id": cid,
                "source_freq": "monthly",
                "note": "re-aligned 2026-04-12: original fetch used source_freq=daily which produced ~73% NaN",
            },
        )
        validate_data(aligned, name=f"sector_{name}")
        if name == "gold_london_fix":
            spot = aligned.loc["2020-08-06", name] if "2020-08-06" in aligned.index else None
            print(f"  spot check gold 2020-08-06: {spot}")


if __name__ == "__main__":
    main()
