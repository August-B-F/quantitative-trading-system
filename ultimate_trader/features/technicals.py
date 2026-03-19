"""Technical indicator computation.
All functions take a pd.Series or pd.DataFrame and return pd.Series.
"""
import numpy as np
import pandas as pd


def compute_rsi(close: pd.Series, window: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=window - 1, min_periods=window).mean()
    avg_loss = loss.ewm(com=window - 1, min_periods=window).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return (100 - 100 / (1 + rs)).rename("rsi")


def compute_macd(
    close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9
) -> pd.DataFrame:
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return pd.DataFrame({"macd": macd_line, "macd_signal": signal_line, "macd_hist": histogram})


def compute_obv(close: pd.Series, volume: pd.Series) -> pd.Series:
    direction = np.sign(close.diff()).fillna(0)
    return (direction * volume).cumsum().rename("obv")


def compute_atr(high: pd.Series, low: pd.Series, close: pd.Series, window: int = 14) -> pd.Series:
    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low - close.shift()).abs()
    ], axis=1).max(axis=1)
    return tr.ewm(com=window - 1, min_periods=window).mean().rename("atr")


def compute_bollinger(
    close: pd.Series, window: int = 20, num_std: float = 2.0
) -> pd.DataFrame:
    ma = close.rolling(window).mean()
    std = close.rolling(window).std()
    upper = ma + num_std * std
    lower = ma - num_std * std
    width = ((upper - lower) / ma).rename("bb_width")
    pct_b = ((close - lower) / (upper - lower)).rename("bb_pct_b")
    return pd.DataFrame({"bb_width": width, "bb_pct_b": pct_b})


def compute_volume_anomaly(volume: pd.Series, window: int = 20) -> pd.Series:
    """Ratio of today's volume to rolling mean. >2 = anomalous."""
    return (volume / volume.rolling(window, min_periods=1).mean()).rename("volume_anomaly")


def compute_returns(close: pd.Series) -> pd.DataFrame:
    return pd.DataFrame({
        "return_1d": close.pct_change(1),
        "return_3d": close.pct_change(3),
        "return_5d": close.pct_change(5),
        "return_10d": close.pct_change(10),
        "return_20d": close.pct_change(20),
    })


def compute_rolling_volatility(close: pd.Series) -> pd.DataFrame:
    r = close.pct_change()
    return pd.DataFrame({
        "vol_5d": r.rolling(5).std(),
        "vol_10d": r.rolling(10).std(),
        "vol_20d": r.rolling(20).std(),
    })


def compute_all_technicals(df: pd.DataFrame) -> pd.DataFrame:
    """
    Given a bar DataFrame with columns [open, high, low, close, volume],
    compute all technical indicators and return a wide DataFrame.
    """
    close = df["close"]
    high = df["high"]
    low = df["low"]
    volume = df["volume"]

    parts = [
        compute_returns(close),
        compute_rolling_volatility(close),
        compute_rsi(close, 14).to_frame(),
        compute_rsi(close, 7).rename("rsi_7").to_frame(),
        compute_macd(close),
        compute_obv(close, volume).to_frame(),
        compute_atr(high, low, close).to_frame(),
        compute_bollinger(close),
        compute_volume_anomaly(volume).to_frame(),
    ]

    tech = pd.concat(parts, axis=1)
    tech.index = df.index
    return tech
