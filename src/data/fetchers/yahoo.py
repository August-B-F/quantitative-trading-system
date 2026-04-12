"""Yahoo Finance fetcher. Downloads OHLCV + Adjusted Close, cleans, validates, catalogs."""
from __future__ import annotations

import time
from pathlib import Path
from typing import Iterable, Optional

import pandas as pd
import yfinance as yf

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


RAW_DIR = DATA_DIR / "raw" / "yahoo"
CLEAN_DIR = DATA_DIR / "clean" / "prices"


def download_ticker(ticker: str, start: str, end: Optional[str] = None) -> pd.DataFrame:
    """Download daily OHLCV + Adj Close for a single ticker. Returns empty DF on failure."""
    try:
        df = yf.download(
            ticker,
            start=start,
            end=end,
            auto_adjust=False,
            progress=False,
            threads=False,
        )
    except Exception as e:
        print(f"  ! {ticker}: download exception: {e}")
        return pd.DataFrame()
    if df is None or df.empty:
        return pd.DataFrame()
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df.rename(
        columns={
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Adj Close": "adj_close",
            "Volume": "volume",
        }
    )
    keep = [c for c in ["open", "high", "low", "close", "adj_close", "volume"] if c in df.columns]
    df = df[keep]
    df.index = pd.to_datetime(df.index)
    if df.index.tz is not None:
        df.index = df.index.tz_localize(None)
    return df


def _safe_name(t: str) -> str:
    return t.replace("^", "_")


def fetch_universe(
    tickers: Iterable[str],
    start: str = "2005-01-01",
    end: Optional[str] = None,
    batch_size: int = 12,
    pause: float = 1.5,
) -> dict:
    """Download, clean, validate, and catalog a list of tickers. Returns summary dict."""
    tickers = list(dict.fromkeys(tickers))  # de-dupe, preserve order
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    CLEAN_DIR.mkdir(parents=True, exist_ok=True)
    summary = {"ok": [], "failed": [], "starts": {}}

    for i in range(0, len(tickers), batch_size):
        batch = tickers[i : i + batch_size]
        print(f"\n=== batch {i // batch_size + 1}: {batch} ===")
        for t in batch:
            safe = _safe_name(t)
            raw_path = RAW_DIR / f"{safe}.parquet"
            clean_path = CLEAN_DIR / f"{safe}.parquet"
            df = download_ticker(t, start=start, end=end)
            if df.empty:
                print(f"  x {t}: empty")
                log_failure(FAILED_PATH, f"yahoo:{t}", "no data returned", f"download_ticker {start}..{end}")
                summary["failed"].append(t)
                continue
            try:
                df.to_parquet(raw_path)
            except Exception as e:
                print(f"  ! {t}: raw save failed: {e}")

            cleaned = align_to_trading_days(df, method="ffill", source_freq="daily")
            status = "OK"
            notes = ""
            if len(cleaned) < 252:
                status = "SHORT"
                notes = f"only {len(cleaned)} rows"
            try:
                save_clean(
                    cleaned,
                    clean_path,
                    metadata={"ticker": t, "source": "yahoo", "frequency": "daily"},
                )
            except Exception as e:
                print(f"  ! {t}: clean save failed: {e}")
                log_failure(FAILED_PATH, f"yahoo:{t}", f"save failed: {e}", "save_clean")
                summary["failed"].append(t)
                continue

            start_date = str(cleaned.index.min().date())
            end_date = str(cleaned.index.max().date())
            summary["starts"][t] = start_date
            summary["ok"].append(t)
            print(f"  + {t}: {start_date}..{end_date}  rows={len(cleaned)}")

            log_to_catalog(
                CATALOG_PATH,
                {
                    "source": "yahoo",
                    "series_name": t,
                    "frequency": "daily",
                    "date_range": f"{start_date}..{end_date}",
                    "file_path": str(clean_path.relative_to(DATA_DIR.parent)).replace("\\", "/"),
                    "status": status,
                    "notes": notes,
                },
            )
        time.sleep(pause)

    return summary
