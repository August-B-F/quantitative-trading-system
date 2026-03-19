"""
alpaca_news.py

Fetches news articles from the Alpaca News API for every symbol.
Scores each article with FinBERT (loaded ONCE globally).
Saves daily aggregated sentiment per symbol as Parquet.

Fixes vs old bot:
  - No Selenium / Tor — pure REST API
  - FinBERT loaded once, not per company
  - Scores full article content, not just title
  - Sentiment momentum computed here
"""

import os
import time
from datetime import datetime, timedelta
from typing import List, Optional

import pandas as pd
import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from alpaca.data.historical.news import NewsClient
from alpaca.data.requests import NewsRequest

from ultimate_trader.utils.logging import get_logger
from ultimate_trader.utils.config_loader import Config

logger = get_logger("alpaca_news")

FINBERT_MODEL = "ProsusAI/finbert"


class FinBERTScorer:
    """
    Singleton-style FinBERT wrapper.
    Load once, score many. Supports GPU if available.
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._loaded = False
        return cls._instance

    def load(self):
        if self._loaded:
            return
        logger.info("Loading FinBERT model...")
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.tokenizer = AutoTokenizer.from_pretrained(FINBERT_MODEL)
        self.model = AutoModelForSequenceClassification.from_pretrained(FINBERT_MODEL).to(self.device)
        self.model.eval()
        self.labels = ["positive", "negative", "neutral"]
        self._loaded = True
        logger.info(f"FinBERT loaded on {self.device}")

    def score(self, text: str) -> dict:
        """
        Returns {positive, negative, neutral} probabilities and a scalar score:
        score = P(positive) - P(negative), range [-1, 1]
        """
        if not text or len(text.strip()) < 5:
            return {"positive": 0.33, "negative": 0.33, "neutral": 0.34, "score": 0.0}

        # Truncate to model max
        text = text[:2000]
        tokens = self.tokenizer(
            text, return_tensors="pt", truncation=True,
            max_length=512, padding=True
        ).to(self.device)

        with torch.no_grad():
            logits = self.model(**tokens).logits
            probs = torch.softmax(logits, dim=-1).squeeze().cpu().tolist()

        result = dict(zip(self.labels, probs))
        result["score"] = result["positive"] - result["negative"]
        return result

    def score_batch(self, texts: List[str]) -> List[dict]:
        return [self.score(t) for t in texts]


# Global singleton
finbert = FinBERTScorer()


class NewsFetcher:
    """
    Fetches and scores news for all symbols via Alpaca News API.
    Output: data/raw/news_{SYMBOL}.parquet
      Columns: date, num_articles, avg_score, score_std, pos_ratio, neg_ratio,
               sentiment_momentum_3d, sentiment_momentum_5d
    """

    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.client = NewsClient(
            api_key=cfg.alpaca.key_id,
            secret_key=cfg.alpaca.secret_key,
        )
        self.raw_dir = cfg.paths.raw_dir
        os.makedirs(self.raw_dir, exist_ok=True)
        finbert.load()  # load once here

    def fetch_all(self, symbols: List[str], start: str, end: Optional[str] = None) -> None:
        end = end or datetime.today().strftime("%Y-%m-%d")
        for sym in symbols:
            try:
                self._fetch_symbol(sym, start, end)
            except Exception as e:
                logger.error(f"News fetch failed for {sym}: {e}")

    def get_sentiment(self, symbol: str) -> pd.DataFrame:
        path = self._news_path(symbol)
        if not os.path.exists(path):
            raise FileNotFoundError(f"No news data for {symbol}. Run fetch_all first.")
        df = pd.read_parquet(path)
        df.index = pd.to_datetime(df.index)
        return df.sort_index()

    # ------------------------------------------------------------------

    def _fetch_symbol(self, symbol: str, start: str, end: str) -> None:
        path = self._news_path(symbol)
        existing = None
        fetch_start = start

        if os.path.exists(path):
            existing = pd.read_parquet(path)
            existing.index = pd.to_datetime(existing.index)
            last_date = existing.index.max()
            fetch_start = (last_date + timedelta(days=1)).strftime("%Y-%m-%d")
            if fetch_start > end:
                logger.debug(f"{symbol} news: already up to date.")
                return

        logger.info(f"Fetching news for {symbol} from {fetch_start} to {end}")

        req = NewsRequest(
            symbols=[symbol],
            start=datetime.strptime(fetch_start, "%Y-%m-%d"),
            end=datetime.strptime(end, "%Y-%m-%d"),
            limit=self.cfg.news.max_articles_per_day * 200,
            include_content=True,
        )
        news_items = self.client.get_news(req)
        articles = news_items.news if hasattr(news_items, 'news') else list(news_items)

        if not articles:
            logger.warning(f"{symbol}: no news articles found.")
            return

        # Score all articles
        rows = []
        for article in articles:
            pub_date = article.created_at.strftime("%Y-%m-%d") if article.created_at else None
            if not pub_date:
                continue

            # Prefer content > summary > headline
            text = article.content or article.summary or article.headline or ""
            scored = finbert.score(text)

            rows.append({
                "date": pub_date,
                "positive": scored["positive"],
                "negative": scored["negative"],
                "neutral": scored["neutral"],
                "score": scored["score"],
            })

        if not rows:
            return

        df_raw = pd.DataFrame(rows)
        df_raw["date"] = pd.to_datetime(df_raw["date"])

        # Aggregate to daily
        daily = df_raw.groupby("date").agg(
            num_articles=("score", "count"),
            avg_score=("score", "mean"),
            score_std=("score", "std"),
            pos_ratio=("positive", "mean"),
            neg_ratio=("negative", "mean"),
        ).fillna(0)

        # Sentiment momentum (change in avg_score)
        daily["sentiment_momentum_3d"] = daily["avg_score"].diff(3)
        daily["sentiment_momentum_5d"] = daily["avg_score"].diff(5)

        if existing is not None:
            daily = pd.concat([existing, daily])
            daily = daily[~daily.index.duplicated(keep="last")]

        daily.sort_index(inplace=True)
        daily.to_parquet(path)
        logger.info(f"{symbol} news: saved {len(daily)} daily rows.")
        time.sleep(0.1)

    def _news_path(self, symbol: str) -> str:
        return os.path.join(self.raw_dir, f"news_{symbol}.parquet")
