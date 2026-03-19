"""Fetch news articles from Alpaca News API and run FinBERT sentiment analysis."""
import json
import time
import datetime
from pathlib import Path
from typing import Optional
import pandas as pd
import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import NewsRequest

from ultimate_trader.utils.logging import get_logger
from ultimate_trader.utils.config_loader import get_full_config

logger = get_logger(__name__)

# Module-level FinBERT cache so we only load the model ONCE per process
_FINBERT_CACHE: dict = {}


def _get_finbert():
    """Load FinBERT tokenizer and model once, then cache."""
    if not _FINBERT_CACHE:
        logger.info("Loading FinBERT model (first use)...")
        model_name = "ProsusAI/finbert"
        _FINBERT_CACHE["tokenizer"] = AutoTokenizer.from_pretrained(model_name)
        _FINBERT_CACHE["model"] = AutoModelForSequenceClassification.from_pretrained(model_name)
        _FINBERT_CACHE["device"] = "cuda" if torch.cuda.is_available() else "cpu"
        _FINBERT_CACHE["model"].to(_FINBERT_CACHE["device"])
        _FINBERT_CACHE["model"].eval()
        _FINBERT_CACHE["labels"] = ["positive", "negative", "neutral"]
        logger.info(f"FinBERT loaded on {_FINBERT_CACHE['device']}")
    return _FINBERT_CACHE


def score_text(text: str) -> dict:
    """
    Run FinBERT on a text string. Truncates to 512 tokens.

    Returns:
        dict with keys: positive, negative, neutral (probabilities),
                        sentiment (string label), score (pos - neg)
    """
    fb = _get_finbert()
    tokens = fb["tokenizer"](
        text,
        return_tensors="pt",
        truncation=True,
        max_length=512,
        padding=True,
    )
    tokens = {k: v.to(fb["device"]) for k, v in tokens.items()}
    with torch.no_grad():
        logits = fb["model"](**tokens).logits
    probs = torch.softmax(logits, dim=-1).squeeze().cpu().tolist()
    label = fb["labels"][int(torch.argmax(torch.tensor(probs)))]
    return {
        "positive": probs[0],
        "negative": probs[1],
        "neutral": probs[2],
        "sentiment": label,
        "score": probs[0] - probs[1],  # Ranges from -1 to +1
    }


def fetch_news_for_symbol(
    symbol: str,
    start: str,
    end: str,
    cfg: dict,
    max_per_day: int = 20,
) -> dict:
    """
    Fetch news from Alpaca News API for one symbol between start and end.
    Returns raw news grouped by date.

    Args:
        symbol: ticker string
        start: ISO date
        end: ISO date
        cfg: full config dict
        max_per_day: cap articles per day to avoid massive batches

    Returns:
        dict of {date_str: [article_dicts]}
    """
    client = StockHistoricalDataClient(
        api_key=cfg["alpaca"]["key_id"],
        secret_key=cfg["alpaca"]["secret_key"],
    )
    by_date = {}
    try:
        req = NewsRequest(
            symbols=[symbol],
            start=start,
            end=end,
            limit=1000,
        )
        news_resp = client.get_news(req)
        articles = news_resp.news if hasattr(news_resp, "news") else []

        for article in articles:
            date = article.created_at.strftime("%Y-%m-%d") if hasattr(article.created_at, 'strftime') else str(article.created_at)[:10]
            if date not in by_date:
                by_date[date] = []
            if len(by_date[date]) < max_per_day:
                by_date[date].append({
                    "headline": getattr(article, "headline", ""),
                    "summary": getattr(article, "summary", ""),
                    "source": getattr(article, "source", ""),
                    "url": getattr(article, "url", ""),
                })
    except Exception as e:
        logger.error(f"{symbol}: news fetch failed — {e}")

    return by_date


def score_and_save_news(
    symbol: str,
    raw_news: dict,
    save_dir: str = "data/raw/news",
) -> pd.DataFrame:
    """
    Run FinBERT over all fetched articles and aggregate to a per-day DataFrame.
    Caches scored results as JSON. Only scores articles that haven't been scored yet.

    Aggregation per day:
        - mean positive, negative, neutral probabilities
        - mean score (pos - neg)
        - article count
        - sentiment volatility (std of scores for that day)

    Args:
        symbol: ticker string
        raw_news: dict from fetch_news_for_symbol
        save_dir: directory to save scored JSON

    Returns:
        DataFrame with DatetimeIndex and sentiment columns
    """
    Path(save_dir).mkdir(parents=True, exist_ok=True)
    cache_path = Path(save_dir) / f"{symbol}_scored.json"

    # Load existing scored cache
    if cache_path.exists():
        with open(cache_path) as f:
            scored_cache = json.load(f)
    else:
        scored_cache = {}

    # Score new articles only
    for date, articles in raw_news.items():
        if date not in scored_cache:
            scored_cache[date] = []
        scored_urls = {a.get("url") for a in scored_cache[date]}
        for article in articles:
            if article["url"] in scored_urls:
                continue
            # Score headline + summary concatenated for richer signal
            text = f"{article['headline']}. {article['summary']}".strip(". ")
            if not text:
                continue
            try:
                result = score_text(text)
                article.update(result)
                scored_cache[date].append(article)
            except Exception as e:
                logger.warning(f"{symbol} {date}: scoring failed — {e}")

    # Save updated cache
    with open(cache_path, "w") as f:
        json.dump(scored_cache, f, indent=2)

    # Aggregate to daily DataFrame
    rows = []
    for date, articles in scored_cache.items():
        scores = [a["score"] for a in articles if "score" in a]
        pos = [a["positive"] for a in articles if "positive" in a]
        neg = [a["negative"] for a in articles if "negative" in a]
        if not scores:
            continue
        rows.append({
            "date": pd.Timestamp(date),
            "sentiment_score": sum(scores) / len(scores),
            "sentiment_pos": sum(pos) / len(pos),
            "sentiment_neg": sum(neg) / len(neg),
            "sentiment_vol": pd.Series(scores).std() if len(scores) > 1 else 0.0,
            "article_count": len(scores),
        })

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows).set_index("date").sort_index()
    return df


def get_news_sentiment(
    symbols: list[str],
    start: str,
    end: Optional[str] = None,
    cfg: Optional[dict] = None,
) -> dict[str, pd.DataFrame]:
    """
    Main entry point. Fetches and scores news for all symbols.

    Returns:
        dict of symbol -> daily sentiment DataFrame
    """
    if cfg is None:
        cfg = get_full_config()
    end = end or datetime.datetime.now().strftime("%Y-%m-%d")
    result = {}
    for symbol in symbols:
        logger.info(f"Processing news for {symbol}")
        raw = fetch_news_for_symbol(symbol, start, end, cfg)
        df = score_and_save_news(symbol, raw)
        result[symbol] = df
        time.sleep(0.3)
    return result
