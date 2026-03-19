"""Assemble complete per-symbol feature matrices and training labels.

Pipeline:
  1. Load raw OHLCV bars
  2. Add all technical indicators
  3. Merge sentiment features
  4. Merge regime features
  5. Merge macro features (VIX, yield spread, sector ETF returns)
  6. Build forward-return labels
  7. Create rolling windows -> (X, y) tensors
  8. Fit and save StandardScaler per feature group

Outputs per symbol:
  X shape: (N_samples, price_window, n_price_features)  <- time-series
           (N_samples, sentiment_window, n_sent_features)
           (N_samples, macro_window, n_macro_features)
           (N_samples,)  <- symbol_idx (integer for embedding)
  y shape: (N_samples,) integer class label 0-4
"""
import numpy as np
import pandas as pd
import joblib
from pathlib import Path
from typing import Optional

from sklearn.preprocessing import StandardScaler

from ultimate_trader.features.technicals import add_all_technicals
from ultimate_trader.features.sentiment import build_sentiment_features
from ultimate_trader.features.regimes import predict_regimes, add_regime_features
from ultimate_trader.utils.logging import get_logger
from ultimate_trader.utils.config_loader import get_full_config

logger = get_logger(__name__)

# Feature column groups
PRICE_FEATURES = [
    "ret_1d", "ret_3d", "ret_5d", "ret_10d", "ret_20d",
    "rsi", "macd", "macd_signal", "macd_hist",
    "obv_zscore", "atr_pct", "bb_width", "bb_pct",
    "vol_anomaly", "rvol_5d", "rvol_10d", "rvol_20d",
    "stoch_k", "stoch_d",
]

SENTIMENT_FEATURES = [
    "sentiment_score", "sentiment_pos", "sentiment_neg",
    "sentiment_vol", "article_count_log",
    "sent_momentum_3d", "sent_momentum_5d", "sent_zscore_20d",
]

MACRO_FEATURES = [
    "vix", "vix_change_10d", "vix_regime",
    "yield_spread",
    "spy_ret_1d", "spy_ret_5d",
    "sector_ret_1d",  # sector ETF 1d return for this symbol's sector
    "regime_0", "regime_1", "regime_2",
]


def make_labels(
    close: pd.Series,
    horizon: int,
    r_hi: float,
    r_lo: float,
) -> pd.Series:
    """
    Build 5-class labels from forward N-day returns.

    Classes:
        0 = strong sell  (ret < -r_hi)
        1 = sell         (-r_hi <= ret < -r_lo)
        2 = hold         (-r_lo <= ret <= r_lo)
        3 = buy          (r_lo < ret <= r_hi)
        4 = strong buy   (ret > r_hi)

    Args:
        close: pd.Series of close prices
        horizon: prediction horizon in days
        r_hi: strong signal threshold
        r_lo: weak signal threshold

    Returns:
        pd.Series of integer labels (NaN at tail where forward return unavailable)
    """
    fwd_ret = close.pct_change(horizon).shift(-horizon)
    conditions = [
        fwd_ret < -r_hi,
        (fwd_ret >= -r_hi) & (fwd_ret < -r_lo),
        (fwd_ret >= -r_lo) & (fwd_ret <= r_lo),
        (fwd_ret > r_lo) & (fwd_ret <= r_hi),
        fwd_ret > r_hi,
    ]
    labels = pd.Series(np.nan, index=close.index)
    for cls, cond in enumerate(conditions):
        labels[cond] = cls
    return labels


def build_windows(
    df: pd.DataFrame,
    feature_cols: list[str],
    window: int,
    label_col: str = "label",
) -> tuple[np.ndarray, np.ndarray, pd.DatetimeIndex]:
    """
    Slice a DataFrame into overlapping windows for sequence modelling.

    Args:
        df: merged feature DataFrame with DatetimeIndex
        feature_cols: list of columns to include
        window: look-back window size
        label_col: column containing integer class labels

    Returns:
        X: np.ndarray (N, window, len(feature_cols))
        y: np.ndarray (N,)  integer labels
        dates: DatetimeIndex of prediction dates (last day of each window)
    """
    data = df[feature_cols + [label_col]].dropna()
    xs, ys, dates = [], [], []
    values = data.values
    feat_idx = list(range(len(feature_cols)))
    label_idx = len(feature_cols)

    for i in range(window, len(values)):
        window_slice = values[i - window: i, feat_idx]
        lbl = values[i - 1, label_idx]  # label is for end-of-window date
        if np.isnan(lbl):
            continue
        xs.append(window_slice)
        ys.append(int(lbl))
        dates.append(data.index[i - 1])

    return np.array(xs, dtype=np.float32), np.array(ys, dtype=np.int64), pd.DatetimeIndex(dates)


def build_symbol_dataset(
    symbol: str,
    symbol_idx: int,
    bars_dict: dict,
    sentiment_dict: dict,
    macro_df: pd.DataFrame,
    regime_series: pd.Series,
    sector_etf_bars: dict,
    symbol_to_sector_etf: dict,
    cfg: Optional[dict] = None,
    scaler_dir: str = "data/scalers",
    fit_scalers: bool = True,
) -> Optional[dict]:
    """
    Build the full feature matrix and labels for a single symbol.

    Args:
        symbol: ticker string
        symbol_idx: integer index for embedding lookup
        bars_dict: dict of symbol -> OHLCV DataFrame
        sentiment_dict: dict of symbol -> sentiment DataFrame
        macro_df: macro features DataFrame
        regime_series: regime labels from HMM
        sector_etf_bars: dict of ETF ticker -> OHLCV DataFrame
        symbol_to_sector_etf: dict mapping symbol -> sector ETF ticker
        cfg: config dict
        scaler_dir: directory to save/load scalers
        fit_scalers: if True, fit new scalers and save; if False, load existing

    Returns:
        dict with keys:
            X_price: (N, price_window, n_price_features)
            X_sent: (N, sent_window, n_sent_features)
            X_macro: (N, macro_window, n_macro_features)
            symbol_idx: int
            y: (N,) labels
            dates: pd.DatetimeIndex
        or None if insufficient data
    """
    if cfg is None:
        cfg = get_full_config()

    model_cfg = cfg["model"]
    target_cfg = cfg["targets"]
    price_window = model_cfg["price_window"]
    sent_window = model_cfg["sentiment_window"]
    macro_window = model_cfg["macro_window"]

    if symbol not in bars_dict or bars_dict[symbol].empty:
        logger.warning(f"{symbol}: no bar data")
        return None

    # --- Price + technicals ---
    bars = bars_dict[symbol].copy()
    bars.columns = [c.lower() for c in bars.columns]
    bars = add_all_technicals(bars)

    # --- Sentiment ---
    sent_raw = sentiment_dict.get(symbol, pd.DataFrame())
    sent_df = build_sentiment_features(sent_raw, bars.index)

    # --- Regime + macro ---
    bars = add_regime_features(bars, regime_series)

    # Add SPY returns to bars
    if "SPY" in bars_dict:
        spy = bars_dict["SPY"][["close"]].copy()
        spy.columns = ["spy_close"]
        bars["spy_ret_1d"] = np.log(spy["spy_close"] / spy["spy_close"].shift(1)).reindex(bars.index).ffill().fillna(0)
        bars["spy_ret_5d"] = np.log(spy["spy_close"] / spy["spy_close"].shift(5)).reindex(bars.index).ffill().fillna(0)

    # Add sector ETF return
    sector_etf = symbol_to_sector_etf.get(symbol, "XLK")
    if sector_etf in sector_etf_bars:
        sec = sector_etf_bars[sector_etf][["close"]].copy()
        bars["sector_ret_1d"] = np.log(sec["close"] / sec["close"].shift(1)).reindex(bars.index).ffill().fillna(0)
    else:
        bars["sector_ret_1d"] = 0.0

    # Add macro features
    if macro_df is not None and not macro_df.empty:
        for col in ["vix", "vix_change_10d", "vix_regime", "yield_spread"]:
            if col in macro_df.columns:
                bars[col] = macro_df[col].reindex(bars.index).ffill().fillna(0)
    else:
        for col in ["vix", "vix_change_10d", "vix_regime", "yield_spread"]:
            bars[col] = 0.0

    # --- Labels ---
    bars["label"] = make_labels(
        bars["close"],
        target_cfg["horizon_days"],
        target_cfg["r_hi"],
        target_cfg["r_lo"],
    )

    # --- Merge sentiment into bars ---
    for col in SENTIMENT_FEATURES:
        bars[col] = sent_df[col].reindex(bars.index).fillna(0) if col in sent_df.columns else 0.0

    # --- Validate available features ---
    avail_price = [c for c in PRICE_FEATURES if c in bars.columns]
    avail_sent = [c for c in SENTIMENT_FEATURES if c in bars.columns]
    avail_macro = [c for c in MACRO_FEATURES if c in bars.columns]

    if len(bars.dropna(subset=avail_price)) < price_window + 30:
        logger.warning(f"{symbol}: insufficient data after NA drop")
        return None

    # --- Scale features ---
    Path(scaler_dir).mkdir(parents=True, exist_ok=True)

    def scale_group(df_sub: pd.DataFrame, name: str, cols: list[str]) -> pd.DataFrame:
        scaler_path = Path(scaler_dir) / f"{symbol}_{name}_scaler.joblib"
        vals = df_sub[cols].values
        if fit_scalers:
            scaler = StandardScaler()
            scaled = scaler.fit_transform(vals)
            joblib.dump(scaler, scaler_path)
        else:
            scaler = joblib.load(scaler_path)
            scaled = scaler.transform(vals)
        return pd.DataFrame(scaled, index=df_sub.index, columns=cols)

    bars[avail_price] = scale_group(bars, "price", avail_price)[avail_price]
    bars[avail_sent] = scale_group(bars, "sent", avail_sent)[avail_sent]
    bars[avail_macro] = scale_group(bars, "macro", avail_macro)[avail_macro]

    # --- Build windows ---
    X_p, _, dates_p = build_windows(bars, avail_price, price_window)
    X_s, _, dates_s = build_windows(bars, avail_sent, sent_window)
    X_m, y, dates_m = build_windows(bars, avail_macro, macro_window)

    # Align on common dates
    common_dates = dates_p.intersection(dates_s).intersection(dates_m)
    if len(common_dates) < 50:
        logger.warning(f"{symbol}: too few aligned samples ({len(common_dates)})")
        return None

    idx_p = np.isin(dates_p, common_dates)
    idx_s = np.isin(dates_s, common_dates)
    idx_m = np.isin(dates_m, common_dates)

    return {
        "symbol": symbol,
        "symbol_idx": symbol_idx,
        "X_price": X_p[idx_p],
        "X_sent": X_s[idx_s],
        "X_macro": X_m[idx_m],
        "y": y[idx_m],
        "dates": common_dates,
    }
