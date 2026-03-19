"""Fetch news articles from Alpaca News API and cache to disk."""
import os
import json
import time
import datetime
from pathlib import Path
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import NewsRequest
from ultimate_trader.utils.logging import get_logger

logger = get_logger("alpaca_news")


def fetch_news_for_symbol(
    client: StockHistoricalDataClient,
    symbol: str,
    start: str,
    end: str,
    limit: int = 50,
    raw_dir: str = "data/raw/news",
) -> list:
    """
    Fetch news articles for a symbol between start and end dates.
    Saves raw JSON and returns list of article dicts.
    """
    Path(raw_dir).mkdir(parents=True, exist_ok=True)
    cache_path = Path(raw_dir) / f"{symbol}.json"

    # load existing cache
    if cache_path.exists():
        with open(cache_path, "r") as f:
            cache = json.load(f)
    else:
        cache = {}

    start_dt = datetime.date.fromisoformat(start)
    end_dt = datetime.date.fromisoformat(end)
    delta = datetime.timedelta(days=1)
    current = start_dt
    new_dates = []

    while current <= end_dt:
        date_str = current.isoformat()
        if date_str not in cache:
            new_dates.append(date_str)
        current += delta

    if not new_dates:
        logger.info(f"  News cache up to date for {symbol}")
        return _flatten_cache(cache)

    logger.info(f"  Fetching news for {symbol}: {len(new_dates)} new dates")

    for date_str in new_dates:
        try:
            req = NewsRequest(
                symbols=[symbol],
                start=date_str + "T00:00:00Z",
                end=date_str + "T23:59:59Z",
                limit=limit,
                sort="desc",
            )
            news = client.get_news(req)
            articles = []
            for item in news.news:
                articles.append({
                    "id": item.id,
                    "headline": item.headline,
                    "summary": item.summary,
                    "content": item.content,
                    "url": item.url,
                    "author": item.author,
                    "created_at": str(item.created_at),
                    "updated_at": str(item.updated_at),
                    "sentiment_score": None,
                    "sentiment_label": None,
                })
            cache[date_str] = articles
            time.sleep(0.15)
        except Exception as e:
            logger.warning(f"  Could not fetch news for {symbol} on {date_str}: {e}")
            cache[date_str] = []

    with open(cache_path, "w") as f:
        json.dump(cache, f, indent=2)

    return _flatten_cache(cache)


def _flatten_cache(cache: dict) -> list:
    """Flatten date-keyed cache into flat list of article dicts with date field."""
    articles = []
    for date_str, arts in cache.items():
        for a in arts:
            a["date"] = date_str
            articles.append(a)
    return articles


def fetch_all_news(cfg: dict, raw_dir: str = "data/raw/news"):
    """Fetch news for all symbols in config."""
    from alpaca.data.historical import StockHistoricalDataClient
    client = StockHistoricalDataClient(
        cfg["alpaca"]["key_id"], cfg["alpaca"]["secret_key"]
    )
    start = cfg["data"]["start_date"]
    end = cfg["data"].get("end_date") or datetime.date.today().isoformat()
    for symbol in cfg["universe"]["symbols"]:
        logger.info(f"Fetching news: {symbol}")
        fetch_news_for_symbol(client, symbol, start, end, raw_dir=raw_dir)
