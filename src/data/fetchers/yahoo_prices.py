"""Yahoo price fetcher — production refresh path for live rebalance days.

The canonical backtest reads `data/features/master_panel.parquet` (built by
phase1_download.py). This module is the live entry point: it fetches a
fresh adjusted-close panel and an OHLCV panel for the universe, with
graceful failure modes (returns None on hard failure rather than raising).
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import pandas as pd

log = logging.getLogger(__name__)


def _import_yfinance():
    try:
        import yfinance as yf
        return yf
    except Exception as e:  # pragma: no cover
        log.error("yfinance import failed: %s", e)
        return None


def fetch_adj_close(
    tickers: list[str],
    start: str = "2005-01-01",
    end: Optional[str] = None,
) -> Optional[pd.DataFrame]:
    """Fetch daily adjusted close for the given tickers from Yahoo.

    Returns a wide DataFrame indexed by date, columns = tickers, or None
    on hard failure (caller decides whether to defer the rebalance).
    """
    yf = _import_yfinance()
    if yf is None:
        return None
    log.info("yahoo: fetching %d tickers (%s..%s)", len(tickers), start, end or "today")
    try:
        data = yf.download(
            tickers, start=start, end=end,
            auto_adjust=False, progress=False, threads=True,
        )
    except Exception as e:
        log.error("yfinance download failed: %s", e)
        return None
    if data is None or data.empty:
        log.error("yfinance returned empty frame")
        return None

    if isinstance(data.columns, pd.MultiIndex):
        if "Adj Close" not in data.columns.get_level_values(0):
            log.error("no Adj Close column in yahoo response")
            return None
        df = data["Adj Close"].copy()
    else:
        df = data[["Adj Close"]].rename(columns={"Adj Close": tickers[0]}).copy()

    df = df.sort_index().dropna(how="all")
    df.index = pd.to_datetime(df.index)
    if df.index.tz is not None:
        df.index = df.index.tz_localize(None)
    return df


def fetch_ohlcv(
    tickers: list[str],
    start: str = "2005-01-01",
    end: Optional[str] = None,
) -> Optional[dict[str, pd.DataFrame]]:
    """Fetch OHLCV per ticker. Returns dict[ticker] -> DataFrame[open,high,low,close,adj_close,volume].

    Used by the feature builders that need high/low (ATR) plus adj_close.
    Returns None on hard failure.
    """
    yf = _import_yfinance()
    if yf is None:
        return None
    out: dict[str, pd.DataFrame] = {}
    try:
        raw = yf.download(
            tickers, start=start, end=end,
            auto_adjust=False, progress=False, threads=True, group_by="ticker",
        )
    except Exception as e:
        log.error("yfinance ohlcv download failed: %s", e)
        return None
    if raw is None or raw.empty:
        return None

    rename = {"Open": "open", "High": "high", "Low": "low", "Close": "close",
              "Adj Close": "adj_close", "Volume": "volume"}

    if isinstance(raw.columns, pd.MultiIndex):
        for t in tickers:
            if t not in raw.columns.get_level_values(0):
                log.warning("yahoo: no panel for %s", t)
                continue
            sub = raw[t].rename(columns=rename).copy()
            sub.index = pd.to_datetime(sub.index)
            if sub.index.tz is not None:
                sub.index = sub.index.tz_localize(None)
            out[t] = sub.dropna(how="all")
    else:
        sub = raw.rename(columns=rename).copy()
        sub.index = pd.to_datetime(sub.index)
        if sub.index.tz is not None:
            sub.index = sub.index.tz_localize(None)
        out[tickers[0]] = sub.dropna(how="all")
    return out


def load_cached(prices_dir: Path, ticker: str) -> pd.DataFrame:
    """Load a single ticker from the cached clean directory."""
    p = Path(prices_dir) / f"{ticker}.parquet"
    if not p.exists():
        raise FileNotFoundError(p)
    return pd.read_parquet(p)
