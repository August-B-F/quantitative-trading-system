"""Technical indicator computation."""
import numpy as np
import pandas as pd
from typing import Tuple


def compute_returns(close: pd.Series, windows=(1, 3, 5, 10, 20)) -> pd.DataFrame:
    """Compute rolling returns for multiple windows."""
    out = {}
    for w in windows:
        out[f"return_{w}d"] = close.pct_change(w)
    return pd.DataFrame(out, index=close.index)


def compute_rsi(close: pd.Series, window: int = 14) -> pd.Series:
    """Wilder RSI."""
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1/window, min_periods=window, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/window, min_periods=window, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return (100 - 100 / (1 + rs)).rename("rsi")


def compute_macd(close: pd.Series,
                 fast: int = 12, slow: int = 26, signal: int = 9
                 ) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """MACD line, signal line, histogram."""
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd = (ema_fast - ema_slow).rename("macd")
    signal_line = macd.ewm(span=signal, adjust=False).mean().rename("macd_signal")
    histogram = (macd - signal_line).rename("macd_hist")
    return macd, signal_line, histogram


def compute_obv(close: pd.Series, volume: pd.Series) -> pd.Series:
    """On-Balance Volume."""
    direction = np.sign(close.diff()).fillna(0)
    obv = (direction * volume).cumsum().rename("obv")
    return obv


def compute_atr(high: pd.Series, low: pd.Series, close: pd.Series,
                window: int = 14) -> pd.Series:
    """Average True Range."""
    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low - close.shift()).abs(),
    ], axis=1).max(axis=1)
    return tr.ewm(span=window, adjust=False).mean().rename("atr")


def compute_bollinger(close: pd.Series, window: int = 20,
                      n_std: float = 2.0) -> pd.DataFrame:
    """Bollinger Bands: mid, upper, lower, width, %B."""
    mid = close.rolling(window).mean()
    std = close.rolling(window).std()
    upper = mid + n_std * std
    lower = mid - n_std * std
    width = ((upper - lower) / mid).rename("bb_width")
    pct_b = ((close - lower) / (upper - lower)).rename("bb_pct_b")
    return pd.DataFrame({"bb_width": width, "bb_pct_b": pct_b})


def compute_volume_anomaly(volume: pd.Series, window: int = 20) -> pd.Series:
    """Volume anomaly: today's volume / rolling mean. >2 is unusual."""
    return (volume / volume.rolling(window).mean()).rename("volume_anomaly")


def compute_rolling_volatility(close: pd.Series, window: int = 20) -> pd.Series:
    """Annualised rolling volatility."""
    return (close.pct_change().rolling(window).std() * np.sqrt(252)).rename("volatility")


def compute_price_vs_ma(close: pd.Series, windows=(20, 50, 200)) -> pd.DataFrame:
    """Price relative to moving averages. >1 means above MA."""
    out = {}
    for w in windows:
        ma = close.rolling(w).mean()
        out[f"price_vs_ma{w}"] = close / ma
    return pd.DataFrame(out, index=close.index)


def compute_beta(returns: pd.Series, benchmark_returns: pd.Series,
                 window: int = 60) -> pd.Series:
    """Rolling beta of stock returns vs benchmark."""
    cov = returns.rolling(window).cov(benchmark_returns)
    var = benchmark_returns.rolling(window).var()
    return (cov / var).rename("beta")


def compute_all_technicals(bars: pd.DataFrame,
                           benchmark_returns: pd.Series = None) -> pd.DataFrame:
    """
    Compute the full technical feature set from an OHLCV DataFrame.
    bars must have columns: open, high, low, close, volume
    benchmark_returns: optional Series of daily benchmark returns (for beta)
    Returns a DataFrame with all technical features.
    """
    close  = bars["close"]
    high   = bars["high"]
    low    = bars["low"]
    volume = bars["volume"]

    returns_df     = compute_returns(close)
    rsi            = compute_rsi(close)
    macd, sig, hist = compute_macd(close)
    obv            = compute_obv(close, volume)
    atr            = compute_atr(high, low, close)
    boll           = compute_bollinger(close)
    vol_anom       = compute_volume_anomaly(volume)
    roll_vol       = compute_rolling_volatility(close)
    price_ma       = compute_price_vs_ma(close)

    features = pd.concat([
        returns_df, rsi, macd, sig, hist, obv, atr,
        boll, vol_anom, roll_vol, price_ma
    ], axis=1)

    if benchmark_returns is not None:
        stock_ret = close.pct_change()
        beta = compute_beta(stock_ret, benchmark_returns)
        rel_return = (stock_ret - benchmark_returns).rename("relative_return")
        features = pd.concat([features, beta, rel_return], axis=1)

    return features
