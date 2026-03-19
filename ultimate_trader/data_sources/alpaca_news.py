"""Fetch news from Alpaca News API. No scraping, no Selenium."""
import time
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional

from ultimate_trader.utils.logging import get_logger

log = get_logger(__name__)

try:
    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.data.requests import NewsRequest
    _USE_ALPACA_PY = True
except ImportError:
    import alpaca_trade_api as tradeapi
    _USE_ALPACA_PY = False


def fetch_news(
    symbols: List[str],
    start: str,
    end: Optional[str],
    api_key: str,
    secret_key: str,
    raw_dir: str = "data/raw/news",
    max_per_day: int = 20,
    force_refresh: bool = False,
) -> Dict[str, dict]:
    """
    Fetch news articles for each symbol from Alpaca News API.
    Saves raw JSON per symbol.
    Returns dict of symbol -> {date_str -> [{title, summary, content, url, published_at}]}
    """
    Path(raw_dir).mkdir(parents=True, exist_ok=True)
    end = end or datetime.now().strftime("%Y-%m-%d")
    result = {}

    for symbol in symbols:
        fpath = Path(raw_dir) / f"{symbol}.json"

        # load existing cache
        existing: dict = {}
        if fpath.exists():
            with open(fpath) as f:
                existing = json.load(f)

        # determine dates to fetch
        all_dates = _date_range(start, end)
        dates_to_fetch = [d for d in all_dates if d not in existing] if not force_refresh else all_dates

        if not dates_to_fetch:
            result[symbol] = existing
            continue

        log.info(f"Fetching news for {symbol}: {len(dates_to_fetch)} days")

        try:
            articles = _fetch_alpaca_news(symbol, dates_to_fetch[0], end, api_key, secret_key)
        except Exception as e:
            log.error(f"News fetch failed for {symbol}: {e}")
            result[symbol] = existing
            continue

        # organise by date
        for article in articles:
            pub = article.get("published_at", "")[:10]
            if pub not in existing:
                existing[pub] = []
            if len(existing[pub]) < max_per_day:
                existing[pub].append({
                    "title":        article.get("headline", ""),
                    "summary":      article.get("summary", ""),
                    "content":      article.get("content", ""),
                    "url":          article.get("url", ""),
                    "published_at": article.get("published_at", ""),
                    "sentiment":    None,
                    "score":        None,
                })

        with open(fpath, "w") as f:
            json.dump(existing, f, indent=2)

        result[symbol] = existing
        time.sleep(0.3)

    return result


def _fetch_alpaca_news(symbol: str, start: str, end: str,
                       api_key: str, secret_key: str) -> list:
    articles = []
    if _USE_ALPACA_PY:
        from alpaca.data.historical import StockHistoricalDataClient
        from alpaca.data.requests import NewsRequest
        client = StockHistoricalDataClient(api_key, secret_key)
        page_token = None
        while True:
            req = NewsRequest(
                symbols=[symbol],
                start=start,
                end=end,
                limit=50,
                page_token=page_token,
            )
            resp = client.get_news(req)
            batch = resp.news if hasattr(resp, "news") else list(resp)
            for item in batch:
                articles.append({
                    "headline":     getattr(item, "headline", ""),
                    "summary":      getattr(item, "summary", ""),
                    "content":      getattr(item, "content", ""),
                    "url":          getattr(item, "url", ""),
                    "published_at": str(getattr(item, "created_at", ""))[:10],
                })
            next_token = getattr(resp, "next_page_token", None)
            if not next_token:
                break
            page_token = next_token
            time.sleep(0.2)
    else:
        import alpaca_trade_api as tradeapi
        client = tradeapi.REST(api_key, secret_key,
                               base_url="https://data.alpaca.markets", api_version="v1beta1")
        resp = client.get_news(symbol, start=start, end=end, limit=50)
        for item in resp:
            articles.append({
                "headline":     item.headline,
                "summary":      item.summary,
                "content":      item.content or "",
                "url":          item.url,
                "published_at": str(item.created_at)[:10],
            })
    return articles


def _date_range(start: str, end: str) -> List[str]:
    dates = []
    cur = datetime.strptime(start, "%Y-%m-%d")
    end_dt = datetime.strptime(end, "%Y-%m-%d")
    while cur <= end_dt:
        dates.append(cur.strftime("%Y-%m-%d"))
        cur += timedelta(days=1)
    return dates
