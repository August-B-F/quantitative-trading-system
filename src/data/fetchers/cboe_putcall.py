"""CBOE put/call ratios. Uses cdn.cboe.com CSVs with Referer header (required)."""
from __future__ import annotations

import io
import pandas as pd
import requests

from src.data.utils import (
    CATALOG_PATH,
    DATA_DIR,
    align_to_trading_days,
    log_to_catalog,
    save_clean,
    validate_data,
)

CLEAN_DIR = DATA_DIR / "clean" / "sentiment"
BASE = "https://cdn.cboe.com/resources/options/volume_and_call_put_ratios/"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36",
    "Referer": "https://www.cboe.com/us/options/market_statistics/historical_data/",
    "Accept": "*/*",
}

SOURCES = {
    "total":  ("totalpcarchive.csv",  "totalpc.csv"),
    "equity": ("equitypcarchive.csv", "equitypc.csv"),
    "index":  ("indexpcarchive.csv",  "indexpc.csv"),
}


def _fetch_csv(name: str) -> pd.DataFrame:
    r = requests.get(BASE + name, headers=HEADERS, timeout=30)
    r.raise_for_status()
    lines = r.text.splitlines()
    # Find header row (contains both a date column and "P/C Ratio")
    hdr_idx = None
    for i, ln in enumerate(lines[:10]):
        low = ln.lower()
        if "p/c ratio" in low and ("date" in low or "trade_date" in low):
            hdr_idx = i
            break
    if hdr_idx is None:
        return pd.DataFrame()
    df = pd.read_csv(io.StringIO("\n".join(lines[hdr_idx:])))
    df.columns = [c.strip().lower() for c in df.columns]
    date_col = next((c for c in df.columns if "date" in c), None)
    pc_col = next((c for c in df.columns if "p/c" in c or c == "ratio"), None)
    if date_col is None or pc_col is None:
        return pd.DataFrame()
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    df = df.dropna(subset=[date_col]).set_index(date_col).sort_index()
    df[pc_col] = pd.to_numeric(df[pc_col], errors="coerce")
    return df[[pc_col]].rename(columns={pc_col: "pc_ratio"}).dropna()


def fetch_variant(variant: str) -> dict:
    archive_name, current_name = SOURCES[variant]
    archive = _fetch_csv(archive_name)
    current = _fetch_csv(current_name)
    df = pd.concat([archive, current]).sort_index()
    df = df[~df.index.duplicated(keep="last")]
    if df.empty:
        return {"variant": variant, "ok": False}

    aligned = align_to_trading_days(df, source_freq="daily")
    aligned.columns = [f"cboe_putcall_{variant}"]
    path = CLEAN_DIR / f"cboe_putcall_{variant}.parquet"
    save_clean(aligned, path, metadata={
        "source": "cboe",
        "variant": variant,
        "archive_url": BASE + archive_name,
        "current_url": BASE + current_name,
        "note": "Requires Referer header to bypass CDN 403.",
    })
    validate_data(aligned, name=f"cboe_putcall_{variant}")
    log_to_catalog(CATALOG_PATH, {
        "source": "cboe",
        "series_name": f"putcall_{variant}",
        "frequency": "daily",
        "date_range": f"{aligned.index.min().date()}..{aligned.index.max().date()}",
        "file_path": str(path.relative_to(DATA_DIR.parent)).replace("\\", "/"),
        "status": "OK",
        "notes": "cdn.cboe.com with Referer header",
    })
    return {
        "variant": variant,
        "ok": True,
        "rows": int(len(aligned)),
        "start": str(aligned.index.min().date()),
        "end": str(aligned.index.max().date()),
    }


def main() -> None:
    CLEAN_DIR.mkdir(parents=True, exist_ok=True)
    for v in SOURCES:
        try:
            print(f"--- cboe put/call {v} ---")
            r = fetch_variant(v)
            print(r)
        except Exception as e:
            print(f"  ! {v}: {e}")


if __name__ == "__main__":
    main()
