"""Technical indicator computation on OHLCV bar DataFrames."""
import pandas as pd
import numpy as np
from ultimate_trader.utils.logging import get_logger

logger = get_logger(__name__)


def add_technicals(df: pd.DataFrame) -> pd.DataFrame:
    """
    Takes a DataFrame with columns [open, high, low, close, volume]
    and adds all technical indicator columns in-place.
    Returns the same DataFrame with new columns appended.
    """
    c = df["close"]
    h = df["high"]
    l = df["low"]
    v = df["volume"]

    # Returns
    df["return_1d"] = c.pct_change(1)
    df["return_3d"] = c.pct_change(3)
    df["return_5d"] = c.pct_change(5)
    df["return_10d"] = c.pct_change(10)
    df["return_20d"] = c.pct_change(20)

    # Volatility
    df["vol_5d"] = df["return_1d"].rolling(5).std()
    df["vol_20d"] = df["return_1d"].rolling(20).std()

    # RSI
    df["rsi_14"] = _rsi(c, 14)
    df["rsi_28"] = _rsi(c, 28)

    # MACD
    ema12 = c.ewm(span=12, adjust=False).mean()
    ema26 = c.ewm(span=26, adjust=False).mean()
    df["macd"] = ema12 - ema26
    df["macd_signal"] = df["macd"].ewm(span=9, adjust=False).mean()
    df["macd_hist"] = df["macd"] - df["macd_signal"]

    # Bollinger Bands
    sma20 = c.rolling(20).mean()
    std20 = c.rolling(20).std()
    df["bb_upper"] = sma20 + 2 * std20
    df["bb_lower"] = sma20 - 2 * std20
    df["bb_width"] = (df["bb_upper"] - df["bb_lower"]) / sma20
    df["bb_pct_b"] = (c - df["bb_lower"]) / (df["bb_upper"] - df["bb_lower"] + 1e-9)

    # ATR (Average True Range)
    tr = pd.concat([
        h - l,
        (h - c.shift(1)).abs(),
        (l - c.shift(1)).abs()
    ], axis=1).max(axis=1)
    df["atr_14"] = tr.rolling(14).mean()
    df["atr_pct"] = df["atr_14"] / c

    # OBV (On-Balance Volume)
    obv = [0.0]
    for i in range(1, len(c)):
        if c.iloc[i] > c.iloc[i - 1]:
            obv.append(obv[-1] + v.iloc[i])
        elif c.iloc[i] < c.iloc[i - 1]:
            obv.append(obv[-1] - v.iloc[i])
        else:
            obv.append(obv[-1])
    df["obv"] = obv
    df["obv_change_5d"] = pd.Series(obv, index=c.index).pct_change(5)

    # Volume anomaly (today vs 20d avg)
    df["volume_anomaly"] = v / (v.rolling(20).mean() + 1e-9)

    # SMA crossovers
    sma50 = c.rolling(50).mean()
    sma200 = c.rolling(200).mean()
    df["sma_50_200_ratio"] = sma50 / (sma200 + 1e-9)
    df["price_vs_sma50"] = c / (sma50 + 1e-9)
    df["price_vs_sma200"] = c / (sma200 + 1e-9)

    # Stochastic oscillator
    low14 = l.rolling(14).min()
    high14 = h.rolling(14).max()
    df["stoch_k"] = 100 * (c - low14) / (high14 - low14 + 1e-9)
    df["stoch_d"] = df["stoch_k"].rolling(3).mean()

    # Williams %R
    df["williams_r"] = -100 * (high14 - c) / (high14 - low14 + 1e-9)

    # Momentum
    df["momentum_10"] = c - c.shift(10)
    df["momentum_20"] = c - c.shift(20)

    # Price position in N-day range
    df["price_range_20d"] = (c - c.rolling(20).min()) / (
        c.rolling(20).max() - c.rolling(20).min() + 1e-9
    )

    # Log price (sometimes helps models with non-stationarity)
    df["log_close"] = np.log(c + 1e-9)
    df["log_volume"] = np.log(v + 1e-9)

    return df.fillna(0)


def _rsi(series: pd.Series, window: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = gain.ewm(com=window - 1, adjust=False).mean()
    avg_loss = loss.ewm(com=window - 1, adjust=False).mean()
    rs = avg_gain / (avg_loss + 1e-9)
    return 100 - (100 / (1 + rs))
