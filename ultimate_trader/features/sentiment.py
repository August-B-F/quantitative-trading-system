"""Build sentiment feature arrays from daily scored news DataFrames.

Sentiment features per symbol per day:
  - sentiment_score      : mean(pos - neg) across articles
  - sentiment_pos        : mean positive probability
  - sentiment_neg        : mean negative probability
  - sentiment_vol        : intra-day std of article scores
  - article_count        : number of articles (log-scaled)
  - sent_momentum_3d     : 3-day change in sentiment_score
  - sent_momentum_5d     : 5-day change in sentiment_score
  - sent_zscore_20d      : z-score of sentiment_score vs 20d rolling window

Missing dates (no news) are forward-filled then zero-filled.
"""
import numpy as np
import pandas as pd
from typing import Optional


def build_sentiment_features(
    raw_sentiment_df: pd.DataFrame,
    price_index: pd.DatetimeIndex,
) -> pd.DataFrame:
    """
    Align sentiment data to the trading calendar index and engineer features.

    Args:
        raw_sentiment_df: DataFrame from alpaca_news.score_and_save_news
                          with columns: sentiment_score, sentiment_pos,
                          sentiment_neg, sentiment_vol, article_count
        price_index: DatetimeIndex from the symbol's OHLCV DataFrame
                     (defines the output index)

    Returns:
        DataFrame indexed on price_index with sentiment feature columns.
    """
    if raw_sentiment_df.empty:
        return pd.DataFrame(
            0.0,
            index=price_index,
            columns=[
                "sentiment_score", "sentiment_pos", "sentiment_neg",
                "sentiment_vol", "article_count_log",
                "sent_momentum_3d", "sent_momentum_5d", "sent_zscore_20d",
            ],
        )

    # Reindex to full trading calendar, forward-fill then zero-fill
    df = raw_sentiment_df.reindex(price_index).ffill().fillna(0.0)

    # Derived features
    df["article_count_log"] = np.log1p(df.get("article_count", 0))
    df["sent_momentum_3d"] = df["sentiment_score"].diff(3)
    df["sent_momentum_5d"] = df["sentiment_score"].diff(5)
    roll_mu = df["sentiment_score"].rolling(20).mean()
    roll_std = df["sentiment_score"].rolling(20).std().replace(0, np.nan)
    df["sent_zscore_20d"] = (df["sentiment_score"] - roll_mu) / roll_std

    keep = [
        "sentiment_score", "sentiment_pos", "sentiment_neg",
        "sentiment_vol", "article_count_log",
        "sent_momentum_3d", "sent_momentum_5d", "sent_zscore_20d",
    ]
    return df[keep].fillna(0.0)
