"""EIA energy data fetcher. Uses EIA v2 API (free key in EIA_API_KEY env var)."""
from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
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

CLEAN_DIR = DATA_DIR / "clean" / "alternative"

# (key, route, params, frequency)
SERIES = [
    ("crude_oil_inventory",   "petroleum/stoc/wstk/data/", {"frequency": "weekly", "data[0]": "value", "facets[series][]": "WCESTUS1"}, "weekly"),
    ("gasoline_inventory",    "petroleum/stoc/wstk/data/", {"frequency": "weekly", "data[0]": "value", "facets[series][]": "WGTSTUS1"}, "weekly"),
    ("gasoline_demand",       "petroleum/cons/wpsup/data/", {"frequency": "weekly", "data[0]": "value", "facets[series][]": "WGFUPUS2"}, "weekly"),
    ("refinery_utilization",  "petroleum/pnp/wiup/data/",  {"frequency": "weekly", "data[0]": "value", "facets[series][]": "WPULEUS3"}, "weekly"),
    ("natgas_storage",        "natural-gas/stor/wkly/data/", {"frequency": "weekly", "data[0]": "value", "facets[series][]": "NW2_EPG0_SWO_R48_BCF"}, "weekly"),
    ("electricity_generation","electricity/electric-power-operational-data/data/", {"frequency": "monthly", "data[0]": "generation", "facets[location][]": "US", "facets[sectorid][]": "99", "facets[fueltypeid][]": "ALL"}, "monthly"),
    ("electricity_sales",     "electricity/retail-sales/data/", {"frequency": "monthly", "data[0]": "sales", "facets[stateid][]": "US"}, "monthly"),
]

BASE = "https://api.eia.gov/v2/"


def _request(route: str, params: dict, key: str, timeout: int = 60) -> dict:
    p = list(params.items()) + [("api_key", key), ("offset", "0"), ("length", "5000")]
    url = BASE + route + "?" + urllib.parse.urlencode(p, doseq=True)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def _to_df(payload: dict, value_key: str) -> pd.DataFrame:
    data = payload.get("response", {}).get("data", [])
    if not data:
        return pd.DataFrame()
    rows = []
    for r in data:
        period = r.get("period")
        v = r.get(value_key)
        if period is None or v is None:
            continue
        rows.append((period, v))
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows, columns=["date", value_key])
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"]).set_index("date").sort_index()
    df[value_key] = pd.to_numeric(df[value_key], errors="coerce")
    df = df.groupby(df.index).last()
    return df


def main() -> None:
    CLEAN_DIR.mkdir(parents=True, exist_ok=True)
    key = os.environ.get("EIA_API_KEY")
    if not key:
        for name, *_ in SERIES:
            log_failure(FAILED_PATH, f"eia:{name}", "EIA_API_KEY env var not set", attempted="api.eia.gov v2")
        print("[eia] no EIA_API_KEY set, skipping all")
        return
    for name, route, params, freq in SERIES:
        print(f"[eia] {name}")
        try:
            payload = _request(route, params, key)
        except Exception as e:
            print(f"  ! {name}: {e}")
            log_failure(FAILED_PATH, f"eia:{name}", str(e), attempted=route)
            continue
        value_key = params.get("data[0]", "value")
        df = _to_df(payload, value_key)
        if df.empty:
            log_failure(FAILED_PATH, f"eia:{name}", "empty payload", attempted=route)
            continue
        df.columns = [name]
        aligned = align_to_trading_days(df, source_freq=freq)
        path = CLEAN_DIR / f"eia_{name}.parquet"
        save_clean(aligned, path, metadata={"source": "eia", "route": route, "frequency": freq})
        log_to_catalog(CATALOG_PATH, {
            "source": "eia",
            "series_name": f"eia_{name}",
            "frequency": freq,
            "date_range": f"{aligned.index.min().date()}..{aligned.index.max().date()}",
            "file_path": str(path.relative_to(DATA_DIR.parent)).replace("\\", "/"),
            "status": "OK",
            "notes": "",
        })


if __name__ == "__main__":
    main()
