"""FINRA ATS dark pool fetcher.

The OTC Transparency portal provides ATS data. Some endpoints are JS-rendered;
the public OTC summary endpoint is JSON-driven via FINRA's data API. We attempt
the documented JSON API. If unavailable, log to FAILED_SOURCES.md and exit.
"""
from __future__ import annotations

import json
import urllib.request

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

# FINRA's public JSON endpoint for ATS weekly summary
URL = "https://api.finra.org/data/group/otcMarket/name/weeklySummary"


def _post(url: str, body: dict, timeout: int = 60) -> dict | None:
    data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, headers={
        "User-Agent": "Mozilla/5.0",
        "Content-Type": "application/json",
        "Accept": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except Exception as e:
        print(f"  ! finra: {e}")
        return None


def main() -> None:
    CLEAN_DIR.mkdir(parents=True, exist_ok=True)
    print("[finra] dark pool weekly volume")
    body = {"limit": 5000, "offset": 0}
    payload = _post(URL, body)
    if payload is None or not isinstance(payload, list) or not payload:
        log_failure(
            FAILED_PATH,
            "finra:darkpool",
            "FINRA OTC API not publicly accessible without registration / requires auth",
            attempted=URL,
        )
        print("  ! finra: not accessible, logged failure")
        return
    df = pd.DataFrame(payload)
    date_col = next((c for c in df.columns if "weekStart" in c.lower() or "date" in c.lower()), None)
    if date_col is None:
        log_failure(FAILED_PATH, "finra:darkpool", "no date column in payload", attempted=URL)
        return
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    df = df.dropna(subset=[date_col]).set_index(date_col).sort_index()
    keep = [c for c in df.columns if any(k in c.lower() for k in ("share", "trade", "volume"))]
    df = df[keep] if keep else df
    aligned = align_to_trading_days(df, source_freq="weekly")
    path = CLEAN_DIR / "finra_darkpool.parquet"
    save_clean(aligned, path, metadata={"source": "finra"})
    log_to_catalog(CATALOG_PATH, {
        "source": "finra",
        "series_name": "finra_darkpool",
        "frequency": "weekly",
        "date_range": f"{aligned.index.min().date()}..{aligned.index.max().date()}",
        "file_path": str(path.relative_to(DATA_DIR.parent)).replace("\\", "/"),
        "status": "OK",
        "notes": "ATS weekly summary",
    })


if __name__ == "__main__":
    main()
