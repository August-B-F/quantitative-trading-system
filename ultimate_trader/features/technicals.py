"""Technical indicator computation on OHLCV DataFrames.

All functions accept a pd.DataFrame with at least ['close', 'high', 'low', 'volume']
columns and a DatetimeIndex.  They return a new DataFrame with indicator columns
appended, leaving the input unchanged.
"""
import numpy as np
import pandas as pd


def add_returns(df: pd.DataFrame) -> pd.DataFrame:
    """Add 1d, 3d, 5d, 10d, 20d log returns."""
    out = df.copy()
    for n in [1, 3, 5, 10, 20]:
        out[f"ret_{n}d"] = np.log(out["close"] / out["close"].shift(n))
    return out


def add_rsi(df: pd.DataFrame, window: int = 14) -> pd.DataFrame:
    """Relative Strength Index."""
    out = df.copy()
    delta = out["close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=window - 1, min_periods=window).mean()
    avg_loss = loss.ewm(com=window - 1, min_periods=window).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    out["rsi"] = 100 - (100 / (1 + rs))
    return out


def add_macd(
    df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9
) -> pd.DataFrame:
    """MACD line, signal line, and histogram."""
    out = df.copy()
    ema_fast = out["close"].ewm(span=fast, adjust=False).mean()
    ema_slow = out["close"].ewm(span=slow, adjust=False).mean()
    out["macd"] = ema_fast - ema_slow
    out["macd_signal"] = out["macd"].ewm(span=signal, adjust=False).mean()
    out["macd_hist"] = out["macd"] - out["macd_signal"]
    return out


def add_obv(df: pd.DataFrame) -> pd.DataFrame:
    """On-Balance Volume normalised to a z-score over a 20d rolling window."""
    out = df.copy()
    direction = np.sign(out["close"].diff())
    obv = (direction * out["volume"]).fillna(0).cumsum()
    mu = obv.rolling(20).mean()
    sigma = obv.rolling(20).std().replace(0, np.nan)
    out["obv_zscore"] = (obv - mu) / sigma
    return out


def add_atr(df: pd.DataFrame, window: int = 14) -> pd.DataFrame:
    """Average True Range (normalised by close)."""
    out = df.copy()
    hl = out["high"] - out["low"]
    hc = (out["high"] - out["close"].shift()).abs()
    lc = (out["low"] - out["close"].shift()).abs()
    tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
    out["atr"] = tr.ewm(span=window, adjust=False).mean()
    out["atr_pct"] = out["atr"] / out["close"]  # normalised
    return out


def add_bollinger(df: pd.DataFrame, window: int = 20, num_std: float = 2.0) -> pd.DataFrame:
    """Bollinger Band width and %B (position within bands)."""
    out = df.copy()
    sma = out["close"].rolling(window).mean()
    std = out["close"].rolling(window).std()
    upper = sma + num_std * std
    lower = sma - num_std * std
    out["bb_width"] = (upper - lower) / sma
    out["bb_pct"] = (out["close"] - lower) / (upper - lower + 1e-9)
    return out


def add_volume_anomaly(df: pd.DataFrame, window: int = 20) -> pd.DataFrame:
    """Volume anomaly: today's volume relative to rolling mean as a z-score."""
    out = df.copy()
    mu = out["volume"].rolling(window).mean()
    sigma = out["volume"].rolling(window).std().replace(0, np.nan)
    out["vol_anomaly"] = (out["volume"] - mu) / sigma
    return out


def add_rolling_volatility(df: pd.DataFrame, windows: list[int] = [5, 10, 20]) -> pd.DataFrame:
    """Rolling realised volatility of log returns at multiple horizons."""
    out = df.copy()
    log_ret = np.log(out["close"] / out["close"].shift(1))
    for w in windows:
        out[f"rvol_{w}d"] = log_ret.rolling(w).std() * np.sqrt(252)
    return out


def add_stochastic(df: pd.DataFrame, k_window: int = 14, d_window: int = 3) -> pd.DataFrame:
    """Stochastic oscillator %K and %D."""
    out = df.copy()
    low_min = out["low"].rolling(k_window).min()
    high_max = out["high"].rolling(k_window).max()
    out["stoch_k"] = 100 * (out["close"] - low_min) / (high_max - low_min + 1e-9)
    out["stoch_d"] = out["stoch_k"].rolling(d_window).mean()
    return out


def add_all_technicals(df: pd.DataFrame) -> pd.DataFrame:
    """Apply all technical indicator functions in sequence."""
    df = add_returns(df)
    df = add_rsi(df)
    df = add_macd(df)
    df = add_obv(df)
    df = add_atr(df)
    df = add_bollinger(df)
    df = add_volume_anomaly(df)
    df = add_rolling_volatility(df)
    df = add_stochastic(df)
    return df
