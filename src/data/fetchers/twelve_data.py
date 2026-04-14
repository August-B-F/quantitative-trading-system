"""Twelve Data price fetcher — backup for Yahoo on live rebalance day.

Free tier: 800 req/day, 8 req/min. 18 universe tickers + SPY + VIX + extras
fits comfortably within the daily budget.

Primary interface mirrors `yahoo_prices.fetch_ohlcv`: returns
`dict[ticker] -> DataFrame[open, high, low, close, adj_close, volume]`
with a tz-naive DatetimeIndex, or `None` on hard failure.
"""
from __future__ import annotations

import logging
import os
import time
from typing import Optional

import pandas as pd
import requests

log = logging.getLogger(__name__)

TD_URL = "https://api.twelvedata.com/time_series"

# Free tier: 8 req/min. Space requests ~8s apart to stay safely under.
_MIN_INTERVAL_S = 8.0
_last_call_ts: float = 0.0

# Yahoo tickers that need remapping for Twelve Data.
# Twelve Data uses "VIX" (no caret) for CBOE VIX.
_TICKER_MAP = {"^VIX": "VIX"}


def _throttle() -> None:
    global _last_call_ts
    wait = _MIN_INTERVAL_S - (time.monotonic() - _last_call_ts)
    if wait > 0:
        time.sleep(wait)
    _last_call_ts = time.monotonic()


def _map_ticker(t: str) -> str:
    return _TICKER_MAP.get(t, t)


def fetch_daily(
    ticker: str,
    api_key: Optional[str] = None,
    start: Optional[str] = None,
    end: Optional[str] = None,
    timeout: int = 20,
) -> Optional[pd.DataFrame]:
    """Fetch daily OHLCV for a single ticker from Twelve Data.

    Returns a DataFrame indexed by date with columns
    [open, high, low, close, adj_close, volume], or None on failure.
    Twelve Data's `time_series` endpoint returns split/dividend-adjusted
    close when `outputsize` is large and the underlying series is
    adjusted — for ETFs this matches Yahoo `Adj Close` within
    fractions of a cent in practice.
    """
    api_key = api_key or os.environ.get("TWELVE_DATA_KEY")
    if not api_key:
        log.error("twelve_data: TWELVE_DATA_KEY not set")
        return None

    symbol = _map_ticker(ticker)
    params = {
        "symbol": symbol,
        "interval": "1day",
        "apikey": api_key,
        "outputsize": "5000",
        "format": "JSON",
        "order": "ASC",
    }
    if start:
        params["start_date"] = start
    if end:
        params["end_date"] = end

    try:
        _throttle()
        r = requests.get(TD_URL, params=params, timeout=timeout)
    except Exception as e:
        log.error("twelve_data request failed for %s: %s", ticker, e)
        return None

    if r.status_code != 200:
        log.error("twelve_data HTTP %s for %s: %s", r.status_code, ticker, r.text[:120])
        return None

    try:
        payload = r.json()
    except Exception as e:
        log.error("twelve_data json decode failed for %s: %s", ticker, e)
        return None

    if payload.get("status") == "error" or "values" not in payload:
        log.error("twelve_data error for %s: %s", ticker, payload.get("message", payload))
        return None

    values = payload["values"]
    if not values:
        return None

    df = pd.DataFrame(values)
    df["datetime"] = pd.to_datetime(df["datetime"])
    df = df.set_index("datetime").sort_index()
    df.index.name = None
    if df.index.tz is not None:
        df.index = df.index.tz_localize(None)

    for col in ("open", "high", "low", "close", "volume"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Twelve Data's default `close` on the time_series endpoint for equities
    # and ETFs is already split-adjusted; we use it as `adj_close` to match
    # yahoo_prices' output contract. Consumers that need raw close should
    # use a different endpoint.
    df["adj_close"] = df["close"]

    keep = ["open", "high", "low", "close", "adj_close", "volume"]
    df = df[[c for c in keep if c in df.columns]].dropna(how="all")
    return df


def fetch_ohlcv(
    tickers: list[str],
    start: Optional[str] = None,
    end: Optional[str] = None,
) -> Optional[dict[str, pd.DataFrame]]:
    """Batched wrapper matching `yahoo_prices.fetch_ohlcv` interface.

    Iterates tickers sequentially (Twelve Data free tier is 8 req/min).
    Returns None if EVERY ticker failed; otherwise returns what we got
    and the caller decides whether the coverage is acceptable.
    """
    out: dict[str, pd.DataFrame] = {}
    for t in tickers:
        df = fetch_daily(t, start=start, end=end)
        if df is not None and not df.empty:
            out[t] = df
        else:
            log.warning("twelve_data: no data for %s", t)
    if not out:
        return None
    return out
