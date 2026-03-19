"""Technical indicator computation from OHLCV data.

All functions take a pd.Series or pd.DataFrame and return pd.Series.
Designed to work on raw price data - NO look-ahead bias.
"""
import numpy as np
import pandas as pd


# ── Price-based indicators ─────────────────────────────────────────────────────

def returns(close: pd.Series, periods: int = 1) -> pd.Series:
    """Simple returns over N periods."""
    return close.pct_change(periods).rename(f"ret_{periods}d")


def log_returns(close: pd.Series, periods: int = 1) -> pd.Series:
    return np.log(close / close.shift(periods)).rename(f"logret_{periods}d")


def rolling_volatility(close: pd.Series, window: int = 20) -> pd.Series:
    """Rolling std of daily log-returns (annualised)."""
    lr = log_returns(close)
    return (lr.rolling(window).std() * np.sqrt(252)).rename(f"vol_{window}d")


def atr(high: pd.Series, low: pd.Series, close: pd.Series, window: int = 14) -> pd.Series:
    """Average True Range."""
    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low - close.shift()).abs()
    ], axis=1).max(axis=1)
    return tr.rolling(window).mean().rename(f"atr_{window}")


def bollinger_width(close: pd.Series, window: int = 20, num_std: float = 2.0) -> pd.Series:
    """Bollinger Band width (upper - lower) / middle."""
    mid = close.rolling(window).mean()
    std = close.rolling(window).std()
    return ((mid + num_std * std) - (mid - num_std * std)) / mid.replace(0, np.nan).rename(f"bb_width_{window}")


def rsi(close: pd.Series, window: int = 14) -> pd.Series:
    """Wilder RSI."""
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = gain.ewm(com=window - 1, min_periods=window).mean()
    avg_loss = loss.ewm(com=window - 1, min_periods=window).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return (100 - (100 / (1 + rs))).rename(f"rsi_{window}")


def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    """Returns (macd_line, signal_line, histogram) as pd.Series tuple."""
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd_line = (ema_fast - ema_slow).rename("macd")
    signal_line = macd_line.ewm(span=signal, adjust=False).mean().rename("macd_signal")
    hist = (macd_line - signal_line).rename("macd_hist")
    return macd_line, signal_line, hist


def obv(close: pd.Series, volume: pd.Series) -> pd.Series:
    """On-Balance Volume."""
    direction = np.sign(close.diff()).fillna(0)
    return (direction * volume).cumsum().rename("obv")


def obv_momentum(close: pd.Series, volume: pd.Series, window: int = 10) -> pd.Series:
    """Rate of change of OBV."""
    o = obv(close, volume)
    return o.pct_change(window).rename(f"obv_mom_{window}")


def volume_anomaly(volume: pd.Series, window: int = 20) -> pd.Series:
    """Today's volume / rolling mean volume."""
    return (volume / volume.rolling(window).mean()).rename(f"vol_anomaly_{window}")


def price_momentum(close: pd.Series, windows: list = [5, 10, 20, 40]) -> pd.DataFrame:
    """Multi-period momentum (returns) as a DataFrame."""
    return pd.concat([returns(close, w) for w in windows], axis=1)


def market_beta(symbol_returns: pd.Series, market_returns: pd.Series, window: int = 60) -> pd.Series:
    """Rolling beta of symbol vs market."""
    cov = symbol_returns.rolling(window).cov(market_returns)
    var = market_returns.rolling(window).var()
    return (cov / var.replace(0, np.nan)).rename(f"beta_{window}d")


def relative_strength_vs_market(close: pd.Series, market_close: pd.Series, window: int = 20) -> pd.Series:
    """Symbol return / market return over rolling window."""
    s_ret = close.pct_change(window)
    m_ret = market_close.pct_change(window)
    return (s_ret - m_ret).rename(f"rel_strength_{window}d")


# ── Build full technical feature DataFrame ────────────────────────────────────

def build_technical_features(
    bars: pd.DataFrame,
    market_close: pd.Series = None,
) -> pd.DataFrame:
    """
    Build all technical features from an OHLCV DataFrame.
    bars must have columns: open, high, low, close, volume
    market_close: optional SPY close series for beta/relative-strength
    """
    close = bars["close"]
    high = bars["high"]
    low = bars["low"]
    volume = bars["volume"]

    feats = pd.DataFrame(index=bars.index)

    # returns
    for p in [1, 3, 5, 10, 20]:
        feats[f"ret_{p}d"] = returns(close, p)
        feats[f"logret_{p}d"] = log_returns(close, p)

    # volatility
    for w in [10, 20, 40]:
        feats[f"vol_{w}d"] = rolling_volatility(close, w)

    # ATR (normalised by close)
    feats["atr_14"] = atr(high, low, close, 14) / close

    # Bollinger width
    feats["bb_width_20"] = bollinger_width(close, 20)

    # RSI
    feats["rsi_14"] = rsi(close, 14)
    feats["rsi_28"] = rsi(close, 28)

    # MACD
    macd_line, sig_line, hist = macd(close)
    feats["macd"] = macd_line / close  # normalised
    feats["macd_signal"] = sig_line / close
    feats["macd_hist"] = hist / close

    # OBV
    o = obv(close, volume)
    feats["obv_norm"] = (o - o.rolling(20).mean()) / (o.rolling(20).std().replace(0, np.nan))
    feats["obv_mom_10"] = obv_momentum(close, volume, 10)

    # Volume
    feats["vol_anomaly_20"] = volume_anomaly(volume, 20)
    feats["vol_anomaly_5"] = volume_anomaly(volume, 5)

    # VWAP distance
    if "vwap" in bars.columns:
        feats["vwap_dist"] = (close - bars["vwap"]) / bars["vwap"].replace(0, np.nan)

    # Market-relative features
    if market_close is not None:
        aligned_market = market_close.reindex(close.index, method="ffill")
        m_ret = returns(aligned_market)
        s_ret = returns(close)
        feats["beta_60d"] = market_beta(s_ret, m_ret, 60)
        feats["rel_str_20d"] = relative_strength_vs_market(close, aligned_market, 20)
        feats["rel_str_5d"] = relative_strength_vs_market(close, aligned_market, 5)

    return feats
