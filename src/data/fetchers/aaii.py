"""AAII Investor Sentiment Survey.

Weekly bull/neutral/bear percentages. AAII publishes the full history as
an .xls spreadsheet at a stable url. We download + parse it.
"""
from __future__ import annotations

import io
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

CLEAN_DIR = DATA_DIR / "clean" / "sentiment"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    ),
    "Accept": "*/*",
}

URLS = [
    "https://www.aaii.com/files/surveys/sentiment.xls",
    "https://www.aaii.com/files/surveys/sentiment.xlsx",
    # Wayback mirrors — AAII serves a bot-challenge page to direct
    # requests, but the Internet Archive has clean snapshots.
    "https://web.archive.org/web/2025im_/https://www.aaii.com/files/surveys/sentiment.xls",
    "https://web.archive.org/web/2024im_/https://www.aaii.com/files/surveys/sentiment.xls",
]


def _looks_like_html(blob: bytes) -> bool:
    head = blob[:512].lstrip().lower()
    return head.startswith(b"<!doctype") or head.startswith(b"<html")


def _download() -> tuple[bytes, str] | None:
    for url in URLS:
        try:
            r = requests.get(url, headers=HEADERS, timeout=60)
            if (
                r.status_code == 200
                and len(r.content) > 10000
                and not _looks_like_html(r.content)
            ):
                print(f"  + {url} ({len(r.content)} bytes)")
                return r.content, url
            print(f"  - {url} status={r.status_code} bytes={len(r.content)}")
        except requests.RequestException as e:
            print(f"  ! {url}: {e}")
        time.sleep(2)
    return None


def _parse(blob: bytes) -> pd.DataFrame:
    for engine in ("xlrd", "openpyxl", None):
        try:
            kwargs = {"engine": engine} if engine else {}
            raw = pd.read_excel(io.BytesIO(blob), sheet_name=0, header=None, **kwargs)
            break
        except Exception:
            raw = None
            continue
    if raw is None:
        return pd.DataFrame()

    # locate header row — contains 'Bullish' etc
    header_row = None
    for i in range(min(20, len(raw))):
        row = [str(v).lower() for v in raw.iloc[i].tolist()]
        joined = " ".join(row)
        if "bullish" in joined and "bearish" in joined:
            header_row = i
            break
    if header_row is None:
        return pd.DataFrame()
    df = raw.iloc[header_row + 1:].copy()
    df.columns = [str(c).strip().lower() for c in raw.iloc[header_row].tolist()]
    # first col is date (may be unnamed)
    date_col = df.columns[0]
    cols = {}
    for c in df.columns:
        cl = str(c).lower()
        if "bull" in cl and "bear" not in cl and "neutr" not in cl and "spread" not in cl:
            cols[c] = "bullish"
        elif "bear" in cl and "spread" not in cl:
            cols[c] = "bearish"
        elif "neutr" in cl:
            cols[c] = "neutral"
    keep = [date_col] + list(cols.keys())
    df = df[keep].rename(columns={date_col: "date", **cols})
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"]).set_index("date")
    for c in ("bullish", "neutral", "bearish"):
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
            # values may be 0-1 fractions, coerce to percent
            if df[c].dropna().max() is not None and df[c].dropna().max() <= 1.5:
                df[c] = df[c] * 100.0
    df = df.dropna(how="all")
    if {"bullish", "bearish"}.issubset(df.columns):
        df["bull_bear_spread"] = df["bullish"] - df["bearish"]
    return df.sort_index()


def main() -> None:
    CLEAN_DIR.mkdir(parents=True, exist_ok=True)
    print("[aaii] downloading sentiment.xls")
    got = _download()
    if got is None:
        log_failure(FAILED_PATH, "aaii", "download failed", attempted=URLS[0])
        print("  ! all urls failed")
        return
    blob, url = got
    df = _parse(blob)
    if df.empty:
        log_failure(FAILED_PATH, "aaii", "parse empty", attempted=url)
        return
    aligned = align_to_trading_days(df, source_freq="weekly")
    path = CLEAN_DIR / "aaii_sentiment.parquet"
    save_clean(aligned, path, metadata={"source": "aaii", "url": url})
    validate_data(aligned, name="aaii_sentiment")
    log_to_catalog(CATALOG_PATH, {
        "source": "aaii",
        "series_name": "aaii_sentiment",
        "frequency": "weekly",
        "date_range": f"{aligned.index.min().date()}..{aligned.index.max().date()}",
        "file_path": str(path.relative_to(DATA_DIR.parent)).replace("\\", "/"),
        "status": "OK",
        "notes": "bull/bear/neutral % + spread",
    })


if __name__ == "__main__":
    main()
