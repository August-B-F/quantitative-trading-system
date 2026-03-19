"""
sentiment.py

Loads pre-computed FinBERT sentiment from data/raw/news_{SYMBOL}.parquet
and builds the feature vectors used in the model.

All scaling happens in feature_builder.py, not here.
"""

import os
import pandas as pd
import numpy as np
from typing import List

from ultimate_trader.utils.logging import get_logger

logger = get_logger("sentiment")


def load_sentiment(symbol: str, raw_dir: str) -> pd.DataFrame:
    """
    Load daily aggregated sentiment for a symbol.
    Returns DataFrame indexed by date with columns:
      avg_score, score_std, pos_ratio, neg_ratio,
      sentiment_momentum_3d, sentiment_momentum_5d, num_articles
    """
    path = os.path.join(raw_dir, f"news_{symbol}.parquet")
    if not os.path.exists(path):
        return pd.DataFrame()
    df = pd.read_parquet(path)
    df.index = pd.to_datetime(df.index)
    return df.sort_index()


def align_sentiment_to_bars(sentiment: pd.DataFrame, bars_index: pd.DatetimeIndex) -> pd.DataFrame:
    """
    Reindex sentiment to match bar dates.
    Forward-fill up to 3 days to handle weekends/gaps.
    Fill remaining NaN with neutral (0).
    """
    if sentiment.empty:
        return pd.DataFrame(
            0.0,
            index=bars_index,
            columns=[
                "avg_score", "score_std", "pos_ratio", "neg_ratio",
                "sentiment_momentum_3d", "sentiment_momentum_5d", "num_articles"
            ]
        )
    aligned = sentiment.reindex(bars_index).ffill(limit=3).fillna(0.0)
    return aligned


def compute_sentiment_features(symbol: str, raw_dir: str,
                                bars_index: pd.DatetimeIndex) -> pd.DataFrame:
    """
    Full pipeline: load -> align -> return feature DataFrame.
    """
    raw = load_sentiment(symbol, raw_dir)
    return align_sentiment_to_bars(raw, bars_index)
