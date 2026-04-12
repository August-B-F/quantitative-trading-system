"""CNN Fear & Greed Index.

CNN exposes historical data via an undocumented JSON endpoint that the
site's dataviz frontend consumes. Returns roughly 3 years of daily values.
"""
from __future__ import annotations

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
    "Accept": "application/json, text/plain, */*",
    "Origin": "https://edition.cnn.com",
    "Referer": "https://edition.cnn.com/",
}
API = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"


def main() -> None:
    CLEAN_DIR.mkdir(parents=True, exist_ok=True)
    print(f"[cnn_fg] GET {API}")
    try:
        r = requests.get(API, headers=HEADERS, timeout=30)
    except requests.RequestException as e:
        log_failure(FAILED_PATH, "cnn_fg", f"request error: {e}", attempted=API)
        return
    if r.status_code != 200:
        log_failure(FAILED_PATH, "cnn_fg", f"HTTP {r.status_code}", attempted=API)
        return
    try:
        data = r.json()
    except ValueError:
        log_failure(FAILED_PATH, "cnn_fg", "invalid json", attempted=API)
        return
    series = (data.get("fear_and_greed_historical") or {}).get("data", [])
    if not series:
        log_failure(FAILED_PATH, "cnn_fg", "empty history in response", attempted=API)
        return
    rows = []
    for pt in series:
        ts = pt.get("x")
        val = pt.get("y")
        if ts is None or val is None:
            continue
        dt = pd.to_datetime(int(ts), unit="ms")
        rows.append((dt, float(val)))
    df = pd.DataFrame(rows, columns=["date", "cnn_fear_greed"]).set_index("date").sort_index()
    df.index = df.index.normalize()
    df = df[~df.index.duplicated(keep="last")]

    # current point (often in fear_and_greed.score)
    cur = data.get("fear_and_greed") or {}
    if "score" in cur and "timestamp" in cur:
        try:
            cdt = pd.to_datetime(cur["timestamp"]).normalize()
            df.loc[cdt, "cnn_fear_greed"] = float(cur["score"])
        except (TypeError, ValueError):
            pass
    idx = pd.to_datetime(df.index.tolist(), utc=True)
    df.index = idx.tz_convert(None) if getattr(idx, "tz", None) else idx
    df.index = pd.DatetimeIndex(df.index)
    df = df.sort_index()
    df = df[~df.index.duplicated(keep="last")]

    aligned = align_to_trading_days(df, source_freq="daily")
    path = CLEAN_DIR / "cnn_fear_greed.parquet"
    save_clean(aligned, path, metadata={"source": "cnn", "url": API})
    validate_data(aligned, name="cnn_fear_greed")
    log_to_catalog(CATALOG_PATH, {
        "source": "cnn",
        "series_name": "cnn_fear_greed",
        "frequency": "daily",
        "date_range": f"{aligned.index.min().date()}..{aligned.index.max().date()}",
        "file_path": str(path.relative_to(DATA_DIR.parent)).replace("\\", "/"),
        "status": "OK",
        "notes": "CNN Fear & Greed Index (0-100); ~3y history from undocumented API",
    })


if __name__ == "__main__":
    main()
