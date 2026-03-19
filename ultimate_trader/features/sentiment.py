"""FinBERT-based sentiment scoring for news articles.

Key improvements over old bot:
  - Model loaded ONCE globally, not per-company.
  - Scores headline + summary + content (truncated).
  - Returns per-day aggregated scores with sentiment momentum.
  - Handles GPU automatically.
"""
import json
import datetime
import numpy as np
import pandas as pd
from pathlib import Path
from typing import Optional
from ultimate_trader.utils.logging import get_logger

logger = get_logger("sentiment")

_TOKENIZER = None
_MODEL = None
_DEVICE = None
_LABELS = ["positive", "negative", "neutral"]


def _load_finbert():
    """Load FinBERT model and tokenizer once into module-level globals."""
    global _TOKENIZER, _MODEL, _DEVICE
    if _MODEL is not None:
        return
    import torch
    from transformers import AutoTokenizer, AutoModelForSequenceClassification
    logger.info("Loading FinBERT model...")
    _DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    _TOKENIZER = AutoTokenizer.from_pretrained("ProsusAI/finbert")
    _MODEL = AutoModelForSequenceClassification.from_pretrained("ProsusAI/finbert").to(_DEVICE)
    _MODEL.eval()
    logger.info(f"FinBERT loaded on {_DEVICE}")


def score_text(text: str) -> dict:
    """
    Score a single piece of text with FinBERT.
    Returns: {positive, negative, neutral, score} where score = pos - neg.
    """
    import torch
    _load_finbert()
    if not text or len(text.strip()) < 5:
        return {"positive": 0.0, "negative": 0.0, "neutral": 1.0, "score": 0.0}

    text = text[:512]  # FinBERT max tokens
    try:
        tokens = _TOKENIZER(
            text, return_tensors="pt",
            truncation=True, max_length=512,
            padding=True
        ).to(_DEVICE)
        with torch.no_grad():
            logits = _MODEL(**tokens).logits
        probs = torch.softmax(logits, dim=-1).squeeze().cpu().numpy()
        return {
            "positive": float(probs[0]),
            "negative": float(probs[1]),
            "neutral": float(probs[2]),
            "score": float(probs[0] - probs[1]),
        }
    except Exception as e:
        logger.warning(f"FinBERT scoring failed: {e}")
        return {"positive": 0.0, "negative": 0.0, "neutral": 1.0, "score": 0.0}


def score_article(article: dict) -> float:
    """
    Score a single article using headline + summary + content.
    Weights: headline 0.4, summary 0.4, content 0.2.
    Returns combined sentiment score.
    """
    headline = article.get("headline", "") or ""
    summary = article.get("summary", "") or ""
    content = (article.get("content", "") or "")[:512]

    scores = []
    weights = []

    if headline.strip():
        scores.append(score_text(headline)["score"])
        weights.append(0.4)
    if summary.strip():
        scores.append(score_text(summary)["score"])
        weights.append(0.4)
    if content.strip():
        scores.append(score_text(content)["score"])
        weights.append(0.2)

    if not scores:
        return 0.0

    total_w = sum(weights)
    return sum(s * w for s, w in zip(scores, weights)) / total_w


def score_and_cache_news(symbol: str, raw_dir: str = "data/raw/news"):
    """Score all unscored articles in the symbol's news cache in-place."""
    path = Path(raw_dir) / f"{symbol}.json"
    if not path.exists():
        logger.warning(f"No news cache for {symbol}")
        return

    with open(path, "r") as f:
        cache = json.load(f)

    changed = False
    for date_str, articles in cache.items():
        for article in articles:
            if article.get("sentiment_score") is not None:
                continue
            article["sentiment_score"] = score_article(article)
            changed = True

    if changed:
        with open(path, "w") as f:
            json.dump(cache, f, indent=2)


def build_daily_sentiment(
    symbol: str,
    raw_dir: str = "data/raw/news",
    momentum_windows: list = [3, 7, 14],
) -> pd.DataFrame:
    """
    Aggregate scored articles into a daily sentiment DataFrame.
    Columns:
      - sentiment_mean: avg score across articles
      - sentiment_std: std of scores (disagreement signal)
      - article_count: number of articles
      - sentiment_mom_Nd: N-day change in sentiment_mean
    Returns pd.DataFrame indexed by date.
    """
    path = Path(raw_dir) / f"{symbol}.json"
    if not path.exists():
        return pd.DataFrame()

    with open(path, "r") as f:
        cache = json.load(f)

    rows = []
    for date_str, articles in cache.items():
        scores = [a["sentiment_score"] for a in articles if a.get("sentiment_score") is not None]
        rows.append({
            "date": pd.Timestamp(date_str),
            "sentiment_mean": np.mean(scores) if scores else 0.0,
            "sentiment_std": np.std(scores) if len(scores) > 1 else 0.0,
            "article_count": len(scores),
        })

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows).set_index("date").sort_index()

    # sentiment momentum
    for w in momentum_windows:
        df[f"sentiment_mom_{w}d"] = df["sentiment_mean"].diff(w)

    # news volume anomaly
    df["news_vol_anomaly"] = df["article_count"] / (df["article_count"].rolling(20).mean() + 1e-6)

    return df
