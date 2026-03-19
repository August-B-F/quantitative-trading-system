"""Merge and normalise daily sentiment features from NewsFetcher output."""
import pandas as pd
import numpy as np
from typing import Dict
from ultimate_trader.utils.logging import get_logger

logger = get_logger(__name__)


def build_sentiment_features(daily_sentiment: Dict[str, pd.DataFrame],
                              window: int = 20) -> Dict[str, pd.DataFrame]:
    """
    Takes the per-symbol sentiment DataFrames from NewsFetcher and
    returns a cleaned, aligned version with only the most recent `window` days.

    Output columns per symbol:
        avg_score, score_std, pos_ratio, neg_ratio,
        sentiment_momentum_3d, sentiment_momentum_5d,
        sentiment_vol_5d, news_surge, num_articles
    """
    out = {}
    for symbol, df in daily_sentiment.items():
        if df is None or df.empty:
            logger.warning(f"No sentiment data for {symbol}, using zeros")
            out[symbol] = _zero_sentiment(window)
            continue

        # Ensure sorted
        df = df.sort_index()

        # Keep only the columns we want
        cols = [
            "avg_score", "score_std", "pos_ratio", "neg_ratio",
            "sentiment_momentum_3d", "sentiment_momentum_5d",
            "sentiment_vol_5d", "news_surge", "num_articles"
        ]
        cols = [c for c in cols if c in df.columns]
        df = df[cols].fillna(0)

        # Take last `window` trading days
        out[symbol] = df.iloc[-window:]

    return out


def _zero_sentiment(window: int) -> pd.DataFrame:
    """Returns a window-row zero DataFrame as fallback."""
    dates = pd.bdate_range(end=pd.Timestamp.today(), periods=window)
    return pd.DataFrame(0.0, index=dates, columns=[
        "avg_score", "score_std", "pos_ratio", "neg_ratio",
        "sentiment_momentum_3d", "sentiment_momentum_5d",
        "sentiment_vol_5d", "news_surge", "num_articles"
    ])
