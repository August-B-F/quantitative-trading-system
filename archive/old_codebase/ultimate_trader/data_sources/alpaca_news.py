"""Fetch news articles and score with FinBERT.

Primary source: Alpaca News API (when API keys are configured).
Fallback: Google News RSS feed scraping (no API keys needed).

FinBERT sentiment scoring is always done locally regardless of news source.
"""
import os
import json
import time
import random
import re
import xml.etree.ElementTree as ET
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from html import unescape
import pandas as pd
import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from ultimate_trader.utils.logging import get_logger
from ultimate_trader.utils.config_loader import Config

logger = get_logger(__name__)

# FinBERT labels
LABELS = ["positive", "negative", "neutral"]
FINBERT_MODEL = "ProsusAI/finbert"

# Realistic browser headers for web scraping
_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]


def _alpaca_keys_valid(cfg: Config) -> bool:
    """Check whether Alpaca keys look real (not placeholders)."""
    key = getattr(cfg.alpaca, "key_id", "")
    secret = getattr(cfg.alpaca, "secret_key", "")
    for val in (key, secret):
        if not val or "YOUR" in val.upper() or len(val) < 10:
            return False
    return True


def _random_headers() -> dict:
    """Generate realistic HTTP headers."""
    return {
        "User-Agent": random.choice(_USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "keep-alive",
        "DNT": "1",
    }


def _clean_html(text: str) -> str:
    """Strip HTML tags and unescape entities."""
    text = unescape(text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


class NewsFetcher:
    """
    Fetches news and scores each article with FinBERT.

    Uses Alpaca News API when API keys are configured.
    Falls back to Google News RSS scraping when keys are placeholders.
    Results saved per-symbol as JSON to data/raw/news/{symbol}.json.
    FinBERT model is loaded ONCE at init, not per article.
    """

    def __init__(self, cfg: Config):
        self.cfg = cfg
        self._use_alpaca = _alpaca_keys_valid(cfg)
        self.news_dir = os.path.join(cfg.paths.raw_dir, "news")
        os.makedirs(self.news_dir, exist_ok=True)

        if self._use_alpaca:
            from alpaca.data.historical import StockHistoricalDataClient
            self.client = StockHistoricalDataClient(
                cfg.alpaca.key_id, cfg.alpaca.secret_key
            )
            logger.info("NewsFetcher: using Alpaca News API")
        else:
            self.client = None
            logger.info("NewsFetcher: Alpaca keys not set, using Google News RSS fallback")

        # Load FinBERT once
        logger.info("Loading FinBERT model...")
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.tokenizer = AutoTokenizer.from_pretrained(FINBERT_MODEL)
        self.finbert = AutoModelForSequenceClassification.from_pretrained(
            FINBERT_MODEL
        ).to(self.device)
        self.finbert.eval()
        logger.info(f"FinBERT loaded on {self.device}")

    def _score_text(self, text: str) -> Dict:
        """
        Run FinBERT on a single text string.
        Returns {'positive': p, 'negative': p, 'neutral': p, 'sentiment': str, 'score': float}
        score = positive_prob - negative_prob (range -1 to +1)
        """
        if not text or len(text.strip()) < 5:
            return {"positive": 0.33, "negative": 0.33, "neutral": 0.34,
                    "sentiment": "neutral", "score": 0.0}

        # Truncate to 512 tokens max
        tokens = self.tokenizer(
            text[:2000], return_tensors="pt",
            padding=True, truncation=True, max_length=512
        ).to(self.device)

        with torch.no_grad():
            logits = self.finbert(**tokens).logits
            probs = torch.softmax(logits, dim=-1).squeeze().cpu().tolist()

        # finbert order: positive=0, negative=1, neutral=2
        pos, neg, neu = probs[0], probs[1], probs[2]
        sentiment = LABELS[int(torch.tensor(probs).argmax())]
        return {
            "positive": round(pos, 4),
            "negative": round(neg, 4),
            "neutral": round(neu, 4),
            "sentiment": sentiment,
            "score": round(pos - neg, 4),
        }

    def _score_article(self, article: dict) -> dict:
        """Score an article using headline + summary combined."""
        headline = article.get("headline", "")
        summary = article.get("summary", "")
        content = article.get("content", "")

        if len(content) > 100 and "cookie" not in content[:200].lower():
            text = f"{headline}. {content[:1500]}"
        else:
            text = f"{headline}. {summary}"

        result = self._score_text(text)
        article["finbert"] = result
        return article

    # ── Google News RSS Scraping ─────────────────────────────────────────────

    def _fetch_google_news_rss(self, symbol: str, lookback_days: int) -> List[dict]:
        """
        Scrape Google News RSS feed for stock-specific headlines.
        Returns list of article dicts with keys: id, headline, summary, date, created_at, source, url
        """
        import urllib.request
        import urllib.error

        # Build search query: symbol + "stock" for relevance
        query = f"{symbol}+stock"
        url = f"https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"

        articles = []
        try:
            req = urllib.request.Request(url, headers=_random_headers())
            with urllib.request.urlopen(req, timeout=15) as resp:
                xml_data = resp.read().decode("utf-8", errors="replace")

            root = ET.fromstring(xml_data)

            cutoff = datetime.utcnow() - timedelta(days=lookback_days)
            items = root.findall(".//item")

            for item in items[:30]:  # Limit to 30 articles per symbol
                title = _clean_html(item.findtext("title", ""))
                description = _clean_html(item.findtext("description", ""))
                pub_date_str = item.findtext("pubDate", "")
                link = item.findtext("link", "")
                source = item.findtext("source", "")

                # Parse date
                try:
                    pub_date = pd.Timestamp(pub_date_str)
                except Exception:
                    pub_date = pd.Timestamp.now()

                if pub_date.tz is not None:
                    pub_date = pub_date.tz_localize(None)
                if pub_date < pd.Timestamp(cutoff):
                    continue

                article_id = f"gn_{symbol}_{hash(title) % 10**8}"
                articles.append({
                    "id": article_id,
                    "headline": title,
                    "summary": description,
                    "content": "",
                    "date": pub_date.strftime("%Y-%m-%d"),
                    "created_at": pub_date.isoformat(),
                    "source": source or "Google News",
                    "url": link,
                    "finbert": None,
                })

        except Exception as e:
            logger.warning(f"Google News RSS fetch failed for {symbol}: {e}")

        return articles

    # ── Alpaca News Fetching ─────────────────────────────────────────────────

    def _fetch_alpaca_news(self, symbol: str, lookback_days: int) -> List[dict]:
        """Fetch from Alpaca News API."""
        from alpaca.data.requests import NewsRequest

        end_dt = datetime.utcnow()
        start_dt = end_dt - timedelta(days=lookback_days)

        req = NewsRequest(
            symbols=[symbol],
            start=start_dt,
            end=end_dt,
            limit=self.cfg.news.max_articles_per_day * lookback_days,
            sort="desc",
            include_content=True,
        )
        news = self.client.get_news(req)
        articles = []
        for item in news.news:
            articles.append({
                "id": item.id,
                "headline": item.headline,
                "summary": item.summary or "",
                "content": item.content or "",
                "date": item.created_at.strftime("%Y-%m-%d"),
                "created_at": item.created_at.isoformat(),
                "source": item.source,
                "url": item.url,
                "finbert": None,
            })
        return articles

    # ── Main Entry Point ─────────────────────────────────────────────────────

    def fetch_and_score(self, symbols: List[str], lookback_days: int = None) -> Dict:
        """
        Fetches news for each symbol and scores with FinBERT.
        Returns {symbol: pd.DataFrame} indexed by date with sentiment columns.
        """
        lookback_days = lookback_days or self.cfg.news.lookback_days
        end_dt = datetime.utcnow()
        start_dt = end_dt - timedelta(days=lookback_days)

        aggregated = {}

        for i, symbol in enumerate(symbols):
            cache_path = os.path.join(self.news_dir, f"{symbol}.json")

            # Load existing cache
            if os.path.exists(cache_path):
                with open(cache_path, "r") as f:
                    raw_articles = json.load(f)
            else:
                raw_articles = []

            cached_ids = {a["id"] for a in raw_articles if "id" in a}

            try:
                # Fetch new articles from appropriate source
                if self._use_alpaca:
                    new_raw = self._fetch_alpaca_news(symbol, lookback_days)
                else:
                    new_raw = self._fetch_google_news_rss(symbol, lookback_days)
                    # Polite delay between requests (1-3 seconds, randomized)
                    if i < len(symbols) - 1:
                        time.sleep(random.uniform(1.0, 2.5))

                # Score only new articles
                new_articles = []
                for a in new_raw:
                    if a["id"] not in cached_ids:
                        a = self._score_article(a)
                        new_articles.append(a)

                raw_articles = raw_articles + new_articles

                # Save updated cache
                with open(cache_path, "w") as f:
                    json.dump(raw_articles, f, indent=2)

                logger.info(f"News {symbol}: {len(new_articles)} new articles scored "
                            f"({len(raw_articles)} total cached)")

            except Exception as e:
                logger.error(f"News fetch failed for {symbol}: {e}")

            # Aggregate into daily sentiment features
            aggregated[symbol] = self._aggregate_daily(raw_articles, start_dt, end_dt)

        return aggregated

    @staticmethod
    def _recency_weight(created_at_str: str) -> float:
        """
        Exponential decay by time-of-day: exp(-hour / 6).
        News published at midnight gets weight ~1.0; at 18:00 gets ~0.05.
        """
        try:
            ts = pd.Timestamp(created_at_str)
            h = ts.hour + ts.minute / 60.0
            return float(np.exp(-h / 6.0))
        except Exception:
            return 1.0

    def _aggregate_daily(self, articles: list, start_dt: datetime,
                          end_dt: datetime) -> pd.DataFrame:
        """
        Aggregates per-article sentiment into a daily feature DataFrame.
        Uses recency-weighted aggregation when created_at timestamps are available.
        """
        if not articles:
            return pd.DataFrame()

        df = pd.DataFrame(articles)
        df = df[df["finbert"].notna()].copy()

        if df.empty:
            return pd.DataFrame()

        df["date"] = pd.to_datetime(df["date"])
        df["score"] = df["finbert"].apply(lambda x: x["score"] if x else 0.0)
        df["positive"] = df["finbert"].apply(lambda x: x["positive"] if x else 0.33)
        df["negative"] = df["finbert"].apply(lambda x: x["negative"] if x else 0.33)

        if "created_at" in df.columns:
            df["_w"] = df["created_at"].apply(self._recency_weight)
        else:
            df["_w"] = 1.0

        def _wm(g, col):
            w = g["_w"].values
            v = g[col].values
            return float((v * w).sum() / (w.sum() + 1e-9))

        daily = df.groupby("date").apply(lambda g: pd.Series({
            "num_articles": len(g),
            "avg_score":    _wm(g, "score"),
            "score_std":    float(g["score"].std()),
            "pos_ratio":    _wm(g, "positive"),
            "neg_ratio":    _wm(g, "negative"),
        })).fillna(0)

        date_range = pd.bdate_range(
            start=start_dt.strftime("%Y-%m-%d"),
            end=end_dt.strftime("%Y-%m-%d")
        )
        daily = daily.reindex(date_range, fill_value=0)

        daily["sentiment_momentum_3d"] = daily["avg_score"].diff(3)
        daily["sentiment_momentum_5d"] = daily["avg_score"].diff(5)
        daily["sentiment_vol_5d"] = daily["avg_score"].rolling(5).std().fillna(0)
        daily["news_surge"] = (daily["num_articles"] /
                                (daily["num_articles"].rolling(20).mean().fillna(1) + 1e-9))

        return daily
