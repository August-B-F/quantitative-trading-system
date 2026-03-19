"""Utilities for processing and aligning sentiment features."""
import pandas as pd
import numpy as np


def fill_missing_sentiment_days(
    daily_sentiment: pd.DataFrame,
    full_date_index: pd.DatetimeIndex
) -> pd.DataFrame:
    """
    Forward-fill sentiment over a complete business-day index.
    Days with no news get the last known sentiment carried forward.
    If no prior sentiment, fill with 0 (neutral).
    """
    df = daily_sentiment.reindex(full_date_index)
    df["article_count"] = df["article_count"].fillna(0)
    df = df.ffill().fillna(0)
    return df


def build_sentiment_features(
    daily_sentiment: pd.DataFrame,
    full_date_index: pd.DatetimeIndex
) -> pd.DataFrame:
    """
    Returns a DataFrame aligned to full_date_index with these columns:
      sentiment_mean, sentiment_std, sentiment_momentum_3d, sentiment_momentum_5d,
      article_count, news_volume_anomaly, p_positive_mean, p_negative_mean,
      sentiment_regime (high/neutral/low as 0/1/2)
    """
    df = fill_missing_sentiment_days(daily_sentiment, full_date_index)

    # Sentiment regime: 20d percentile of sentiment
    rolling_25 = df["sentiment_mean"].rolling(20, min_periods=5).quantile(0.25)
    rolling_75 = df["sentiment_mean"].rolling(20, min_periods=5).quantile(0.75)
    conditions = [
        df["sentiment_mean"] >= rolling_75,
        df["sentiment_mean"] <= rolling_25
    ]
    df["sentiment_regime"] = np.select(conditions, [2, 0], default=1).astype(float)

    return df
