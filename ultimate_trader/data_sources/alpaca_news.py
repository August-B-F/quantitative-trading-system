"""Fetch news articles from Alpaca News API and score with FinBERT."""
import os
import json
import time
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict
import pandas as pd
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import NewsRequest
import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from ultimate_trader.utils.logging import get_logger
from ultimate_trader.utils.config_loader import Config

logger = get_logger(__name__)

# FinBERT labels
LABELS = ["positive", "negative", "neutral"]
FINBERT_MODEL = "ProsusAI/finbert"


class NewsFetcher:
    """
    Fetches news from Alpaca News API and scores each article with FinBERT.
    Results saved per-symbol as JSON to data/raw/news/{symbol}.json.
    FinBERT model is loaded ONCE at init, not per article.
    """

    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.client = StockHistoricalDataClient(
            cfg.alpaca.key_id, cfg.alpaca.secret_key
        )
        self.news_dir = os.path.join(cfg.paths.raw_dir, "news")
        os.makedirs(self.news_dir, exist_ok=True)

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
        """
        Score an article using headline + summary combined.
        Full content is used if available and non-trivial.
        """
        headline = article.get("headline", "")
        summary = article.get("summary", "")
        content = article.get("content", "")

        # Prefer full content if it looks real (>100 chars and not a cookie wall)
        if len(content) > 100 and "cookie" not in content[:200].lower():
            text = f"{headline}. {content[:1500]}"
        else:
            text = f"{headline}. {summary}"

        result = self._score_text(text)
        article["finbert"] = result
        return article

    def fetch_and_score(self, symbols: List[str], lookback_days: int = None) -> Dict:
        """
        Fetches news for each symbol from Alpaca and scores with FinBERT.
        Returns {symbol: pd.DataFrame} indexed by date with columns:
            num_articles, avg_score, score_std, pos_ratio, neg_ratio,
            sentiment_momentum_3d, sentiment_momentum_5d
        """
        lookback_days = lookback_days or self.cfg.news.lookback_days
        end_dt = datetime.utcnow()
        start_dt = end_dt - timedelta(days=lookback_days)

        aggregated = {}

        for symbol in symbols:
            cache_path = os.path.join(self.news_dir, f"{symbol}.json")

            # Load existing cache
            if os.path.exists(cache_path):
                with open(cache_path, "r") as f:
                    raw_articles = json.load(f)
            else:
                raw_articles = []

            # Find which dates we already have
            cached_ids = {a["id"] for a in raw_articles if "id" in a}

            try:
                req = NewsRequest(
                    symbols=[symbol],
                    start=start_dt,
                    end=end_dt,
                    limit=self.cfg.news.max_articles_per_day * lookback_days,
                    sort="desc",
                    include_content=True,
                )
                news = self.client.get_news(req)
                new_articles = []
                for item in news.news:
                    if item.id not in cached_ids:
                        a = {
                            "id": item.id,
                            "headline": item.headline,
                            "summary": item.summary or "",
                            "content": item.content or "",
                            "date": item.created_at.strftime("%Y-%m-%d"),
                            "created_at": item.created_at.isoformat(),
                            "source": item.source,
                            "url": item.url,
                            "finbert": None,
                        }
                        a = self._score_article(a)
                        new_articles.append(a)

                raw_articles = raw_articles + new_articles

                # Save updated cache
                with open(cache_path, "w") as f:
                    json.dump(raw_articles, f, indent=2)

                logger.info(f"News {symbol}: {len(new_articles)} new articles scored")

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
        Falls back to 1.0 if unparseable.
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

        # Recency weights from time-of-day (exp decay, fallback to 1.0)
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
            "score_std":    float(g["score"].std()),   # unweighted for stability
            "pos_ratio":    _wm(g, "positive"),
            "neg_ratio":    _wm(g, "negative"),
        })).fillna(0)

        # Fill missing dates with 0
        date_range = pd.bdate_range(
            start=start_dt.strftime("%Y-%m-%d"),
            end=end_dt.strftime("%Y-%m-%d")
        )
        daily = daily.reindex(date_range, fill_value=0)

        # Sentiment momentum: change in avg_score over N days
        daily["sentiment_momentum_3d"] = daily["avg_score"].diff(3)
        daily["sentiment_momentum_5d"] = daily["avg_score"].diff(5)
        daily["sentiment_vol_5d"] = daily["avg_score"].rolling(5).std().fillna(0)
        daily["news_surge"] = (daily["num_articles"] /
                                (daily["num_articles"].rolling(20).mean().fillna(1) + 1e-9))

        return daily
