"""Master feature builder: assembles all feature types into a single aligned DataFrame per symbol.

Also computes target labels for training.

Design:
  - All features aligned to trading-day index of the symbol's bar data.
  - Returns forward-filled where appropriate, NaN-dropped for training.
  - Scalers fitted per feature group and saved to disk.
"""
import numpy as np
import pandas as pd
import joblib
import os
from pathlib import Path
from typing import Optional

from ultimate_trader.features.technicals import build_technical_features
from ultimate_trader.features.sentiment import build_daily_sentiment
from ultimate_trader.features.regimes import build_regime_features
from ultimate_trader.data_sources.alpaca_market import load_bars
from ultimate_trader.utils.logging import get_logger

logger = get_logger("feature_builder")

FEATURE_GROUPS = ["price", "sentiment", "macro", "regime"]


def compute_labels(
    close: pd.Series,
    horizon: int = 3,
    r_hi: float = 0.03,
    r_lo: float = 0.005,
) -> pd.Series:
    """
    Compute 5-class labels:
      4 = strong buy  (forward return > r_hi)
      3 = weak buy    (r_lo < forward return <= r_hi)
      2 = hold        (|forward return| <= r_lo)
      1 = weak sell   (-r_hi <= forward return < -r_lo)
      0 = strong sell (forward return < -r_hi)
    """
    fwd_ret = close.shift(-horizon) / close - 1
    labels = pd.Series(2, index=close.index, dtype=int, name="label")
    labels[fwd_ret > r_hi] = 4
    labels[(fwd_ret > r_lo) & (fwd_ret <= r_hi)] = 3
    labels[(fwd_ret < -r_lo) & (fwd_ret >= -r_hi)] = 1
    labels[fwd_ret < -r_hi] = 0
    return labels


def build_features_for_symbol(
    symbol: str,
    symbol_idx: int,
    num_symbols: int,
    cfg: dict,
    market_close: pd.Series,
    market_regime: pd.DataFrame,
    macro_data: dict,
    raw_bars_dir: str = "data/raw/bars",
    raw_news_dir: str = "data/raw/news",
    price_window: int = 40,
    sentiment_window: int = 20,
) -> pd.DataFrame:
    """
    Build a full feature DataFrame for one symbol.
    Rows = trading days. Columns = all features + label.
    """
    bars = load_bars(symbol, raw_bars_dir)
    close = bars["close"]

    # ── Technical features ───────────────────────────────────────────────────
    tech = build_technical_features(bars, market_close=market_close)

    # ── Sentiment features ───────────────────────────────────────────────────
    try:
        sent = build_daily_sentiment(symbol, raw_news_dir)
        sent = sent.reindex(close.index, method="ffill").fillna(0)
    except Exception as e:
        logger.warning(f"  Sentiment failed for {symbol}: {e}")
        sent = pd.DataFrame(index=close.index)

    # ── Regime features (market-level, same for all symbols) ─────────────────
    regime = market_regime.reindex(close.index, method="ffill").fillna(0)

    # ── Macro features ────────────────────────────────────────────────────────
    macro_cols = {}
    for ticker, series in macro_data.items():
        col_name = ticker.replace("^", "").replace("=", "").replace("-", "_").replace(".", "")
        aligned = series.reindex(close.index, method="ffill").pct_change().fillna(0)
        macro_cols[f"macro_{col_name}_ret"] = aligned
        # level normalised
        macro_cols[f"macro_{col_name}_lvl"] = (
            (series.reindex(close.index, method="ffill") - series.mean()) / (series.std() + 1e-8)
        ).fillna(0)
    macro_df = pd.DataFrame(macro_cols, index=close.index)

    # ── Symbol identity ───────────────────────────────────────────────────────
    # Integer index (0..N-1) used by embedding layer
    identity = pd.DataFrame(
        {"symbol_idx": symbol_idx},
        index=close.index
    )

    # ── Labels ────────────────────────────────────────────────────────────────
    h = cfg["targets"]["horizon_days"]
    r_hi = cfg["targets"]["r_hi"]
    r_lo = cfg["targets"]["r_lo"]
    labels = compute_labels(close, h, r_hi, r_lo)

    # ── Concatenate all ───────────────────────────────────────────────────────
    df = pd.concat([tech, sent, regime, macro_df, identity, labels], axis=1)
    df = df.replace([np.inf, -np.inf], np.nan)
    df.dropna(inplace=True)

    return df


def build_all_features(
    cfg: dict,
    raw_bars_dir: str = "data/raw/bars",
    raw_news_dir: str = "data/raw/news",
    raw_alt_dir: str = "data/raw/alt",
    processed_dir: str = "data/processed",
):
    """
    Build and save feature DataFrames for all symbols.
    Returns dict: {symbol: pd.DataFrame}.
    """
    from ultimate_trader.data_sources.alpaca_market import load_bars
    from ultimate_trader.features.regimes import build_regime_features
    from ultimate_trader.data_sources.alt_data import fetch_yfinance_series
    import datetime

    Path(processed_dir).mkdir(parents=True, exist_ok=True)
    symbols = cfg["universe"]["symbols"]
    benchmark = cfg["universe"]["benchmark"]

    # Load benchmark
    try:
        market_bars = load_bars(benchmark, raw_bars_dir)
        market_close = market_bars["close"]
    except Exception as e:
        logger.error(f"Cannot load benchmark bars: {e}")
        return {}

    # Build regime features
    logger.info("Building regime features...")
    market_regime = build_regime_features(market_close)

    # Load macro data
    logger.info("Loading macro data...")
    start = cfg["data"]["start_date"]
    end = cfg["data"].get("end_date") or datetime.date.today().isoformat()
    macro_tickers = ["^VIX", "^TNX", "^IRX", "GC=F", "CL=F"]
    try:
        macro_data = fetch_yfinance_series(macro_tickers, start, end, raw_dir=raw_alt_dir)
    except Exception as e:
        logger.warning(f"Macro data fetch failed: {e}")
        macro_data = {}

    # Build per-symbol features
    all_features = {}
    for idx, symbol in enumerate(symbols):
        logger.info(f"Building features [{idx+1}/{len(symbols)}]: {symbol}")
        try:
            df = build_features_for_symbol(
                symbol=symbol,
                symbol_idx=idx,
                num_symbols=len(symbols),
                cfg=cfg,
                market_close=market_close,
                market_regime=market_regime,
                macro_data=macro_data,
                raw_bars_dir=raw_bars_dir,
                raw_news_dir=raw_news_dir,
                price_window=cfg["model"]["price_window"],
                sentiment_window=cfg["model"]["sentiment_window"],
            )
            out_path = Path(processed_dir) / f"{symbol}.parquet"
            df.to_parquet(out_path)
            all_features[symbol] = df
            logger.info(f"  {symbol}: {len(df)} rows, {len(df.columns)} features")
        except Exception as e:
            logger.error(f"  Failed to build features for {symbol}: {e}")
            continue

    return all_features
