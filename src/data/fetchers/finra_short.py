"""FINRA Reg SHO daily short volume aggregator.

The bi-monthly short-interest report files at cdn.finra.org are 403-blocked,
but the daily Reg SHO short volume files (CNMSshvolYYYYMMDD.txt) are public.
These contain per-stock short volume + total volume for each NMS-listed stock
on each trading day.

We pull the last N years of daily files and compute the market-wide short
volume ratio (sum_short / sum_total). This is a noisy proxy for short
interest but gives a daily-frequency contrarian sentiment signal.
"""
from __future__ import annotations

import io
import time
from datetime import date

import pandas as pd
import requests

from src.data.utils import (
    CATALOG_PATH,
    DATA_DIR,
    FAILED_PATH,
    align_to_trading_days,
    get_trading_calendar,
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
    "Accept": "text/plain",
}

START = date(2023, 1, 1)
END = date.today()
DELAY = 0.5  # files are small static text on a CDN
BASE = "https://cdn.finra.org/equity/regsho/daily"


def _get(url: str, retries: int = 3) -> str | None:
    for i in range(retries):
        try:
            r = requests.get(url, headers=HEADERS, timeout=30)
            if r.status_code == 200:
                return r.text
            if r.status_code == 404:
                return None
            if r.status_code in (429, 503):
                time.sleep(2 ** i * 3)
                continue
            return None
        except requests.RequestException:
            time.sleep(2 + i)
    return None


def _parse(text: str) -> tuple[float, float, float]:
    """Return (short_vol, short_exempt_vol, total_vol) summed across all stocks."""
    df = pd.read_csv(io.StringIO(text), sep="|")
    cols = {c.lower(): c for c in df.columns}
    sv = df[cols["shortvolume"]].sum()
    sev = df[cols.get("shortexemptvolume", cols["shortvolume"])].sum() if "shortexemptvolume" in cols else 0.0
    tv = df[cols["totalvolume"]].sum()
    return float(sv), float(sev), float(tv)


def main() -> None:
    CLEAN_DIR.mkdir(parents=True, exist_ok=True)
    cal = get_trading_calendar(START, END)
    print(f"[finra_short] {START}..{END}  trading days={len(cal)}")
    rows = []
    failures = 0
    for i, ts in enumerate(cal):
        d = ts.date()
        url = f"{BASE}/CNMSshvol{d.strftime('%Y%m%d')}.txt"
        text = _get(url)
        if text is None or len(text) < 100:
            failures += 1
            time.sleep(DELAY)
            continue
        try:
            sv, sev, tv = _parse(text)
            rows.append((d, sv, sev, tv))
        except Exception as e:
            print(f"  ! parse {d}: {e}")
        time.sleep(DELAY)
        if i % 50 == 0:
            print(f"  [{i}/{len(cal)}] {d}  rows={len(rows)} fails={failures}")

    if not rows:
        log_failure(FAILED_PATH, "finra:shortvol", "no daily files fetched", attempted=BASE)
        return

    df = pd.DataFrame(rows, columns=["date", "short_volume", "short_exempt_volume", "total_volume"])
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date").sort_index()
    df["short_volume_ratio"] = df["short_volume"] / df["total_volume"]
    df["short_volume_ratio_21d"] = df["short_volume_ratio"].rolling(21, min_periods=5).mean()

    aligned = align_to_trading_days(df, source_freq="daily")
    path = CLEAN_DIR / "short_interest.parquet"
    save_clean(aligned, path, metadata={"source": "finra:regsho-cnms"})
    validate_data(aligned, name="short_interest")
    log_to_catalog(CATALOG_PATH, {
        "source": "finra",
        "series_name": "short_interest",
        "frequency": "daily",
        "date_range": f"{aligned.index.min().date()}..{aligned.index.max().date()}",
        "file_path": str(path.relative_to(DATA_DIR.parent)).replace("\\", "/"),
        "status": "OK",
        "notes": "market-wide Reg SHO daily short volume aggregate",
    })


if __name__ == "__main__":
    main()
