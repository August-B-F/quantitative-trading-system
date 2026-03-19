"""
technicals.py

Computes all technical indicators from OHLCV bar data.
All functions operate on pandas Series/DataFrames and return Series.

Indicators:
  - Returns (1d, 3d, 5d, 10d, 20d)
  - Rolling volatility (std of returns)
  - RSI (Wilder smoothing)
  - MACD + signal + histogram
  - OBV (On-Balance Volume)
  - ATR (Average True Range)
  - Bollinger Band width
  - Volume anomaly score (z-score of volume)
  - Price distance from 52-week high/low
  - Beta vs benchmark (rolling 60d)
"""

import numpy as np
import pandas as pd
from typing import Optional


def compute_returns(close: pd.Series) -> pd.DataFrame:
    return pd.DataFrame({
        "ret_1d": close.pct_change(1),
        "ret_3d": close.pct_change(3),
        "ret_5d": close.pct_change(5),
        "ret_10d": close.pct_change(10),
        "ret_20d": close.pct_change(20),
    })


def compute_volatility(close: pd.Series, windows=(5, 10, 20)) -> pd.DataFrame:
    ret = close.pct_change()
    return pd.DataFrame({
        f"vol_{w}d": ret.rolling(w).std() for w in windows
    })


def compute_rsi(close: pd.Series, window: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=window - 1, min_periods=window).mean()
    avg_loss = loss.ewm(com=window - 1, min_periods=window).mean()
    rs = avg_gain / (avg_loss + 1e-10)
    rsi = 100 - (100 / (1 + rs))
    rsi.name = "rsi"
    return rsi


def compute_macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return pd.DataFrame({
        "macd": macd_line,
        "macd_signal": signal_line,
        "macd_hist": histogram,
    })


def compute_obv(close: pd.Series, volume: pd.Series) -> pd.Series:
    direction = np.sign(close.diff()).fillna(0)
    obv = (direction * volume).cumsum()
    obv.name = "obv"
    return obv


def compute_atr(high: pd.Series, low: pd.Series, close: pd.Series, window: int = 14) -> pd.Series:
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    atr = tr.ewm(com=window - 1, min_periods=window).mean()
    atr.name = "atr"
    return atr


def compute_bollinger(close: pd.Series, window: int = 20, num_std: float = 2.0) -> pd.DataFrame:
    mid = close.rolling(window).mean()
    std = close.rolling(window).std()
    upper = mid + num_std * std
    lower = mid - num_std * std
    width = (upper - lower) / (mid + 1e-10)
    pct_b = (close - lower) / (upper - lower + 1e-10)
    return pd.DataFrame({
        "bb_width": width,
        "bb_pct_b": pct_b,
    })


def compute_volume_anomaly(volume: pd.Series, window: int = 20) -> pd.Series:
    """Z-score of today's volume vs rolling mean. High values = unusual activity."""
    rolling_mean = volume.rolling(window).mean()
    rolling_std = volume.rolling(window).std()
    z = (volume - rolling_mean) / (rolling_std + 1e-10)
    z.name = "volume_z"
    return z


def compute_price_extremes(close: pd.Series, window: int = 252) -> pd.DataFrame:
    """Distance from rolling high and low (52-week by default)."""
    rolling_high = close.rolling(window).max()
    rolling_low = close.rolling(window).min()
    dist_from_high = (close - rolling_high) / (rolling_high + 1e-10)
    dist_from_low = (close - rolling_low) / (rolling_low + 1e-10)
    return pd.DataFrame({
        "dist_from_52w_high": dist_from_high,
        "dist_from_52w_low": dist_from_low,
    })


def compute_beta(returns: pd.Series, benchmark_returns: pd.Series, window: int = 60) -> pd.Series:
    """Rolling beta of asset vs benchmark."""
    cov = returns.rolling(window).cov(benchmark_returns)
    var = benchmark_returns.rolling(window).var()
    beta = cov / (var + 1e-10)
    beta.name = "beta"
    return beta


def compute_all(bars: pd.DataFrame, benchmark_returns: Optional[pd.Series] = None) -> pd.DataFrame:
    """
    Master function: takes a bars DataFrame with OHLCV columns,
    returns a DataFrame of all technical features aligned to the same index.
    """
    close = bars["close"]
    high = bars["high"]
    low = bars["low"]
    volume = bars["volume"]

    parts = [
        compute_returns(close),
        compute_volatility(close),
        compute_rsi(close).to_frame(),
        compute_macd(close),
        compute_obv(close, volume).to_frame(),
        compute_atr(high, low, close).to_frame(),
        compute_bollinger(close),
        compute_volume_anomaly(volume).to_frame(),
        compute_price_extremes(close),
    ]

    if benchmark_returns is not None:
        asset_returns = close.pct_change()
        parts.append(compute_beta(asset_returns, benchmark_returns).to_frame())

    result = pd.concat(parts, axis=1)
    result.index = bars.index
    return result
