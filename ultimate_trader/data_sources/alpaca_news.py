"""Fetch financial news from Alpaca News API and run FinBERT sentiment scoring."""
import json
import time
from pathlib import Path
from datetime import datetime, timedelta

import torch
import pandas as pd
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from alpaca.data.historical.news import NewsClient
from alpaca.data.requests import NewsRequest

from ultimate_trader.utils.logging import get_logger
from ultimate_trader.utils.time_utils import today_str

log = get_logger(__name__)

FINBERT_MODEL = "ProsusAI/finbert"
LABELS = ["positive", "negative", "neutral"]


class NewsFetcher:
    """Fetches + scores news. FinBERT is loaded ONCE and reused for all companies."""

    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.raw_dir = Path(cfg["paths"]["raw_dir"]) / "news"
        self.raw_dir.mkdir(parents=True, exist_ok=True)

        self.client = NewsClient(
            api_key=cfg["alpaca"]["key_id"],
            secret_key=cfg["alpaca"]["secret_key"]
        )

        # Load FinBERT once
        log.info("Loading FinBERT model...")
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.tokenizer = AutoTokenizer.from_pretrained(FINBERT_MODEL)
        self.model = AutoModelForSequenceClassification.from_pretrained(FINBERT_MODEL).to(self.device)
        self.model.eval()
        log.info(f"FinBERT loaded on {self.device}")

    def fetch_news(
        self,
        symbols: list[str],
        start: str,
        end: str | None = None,
        save: bool = True
    ) -> dict[str, list[dict]]:
        """Fetch raw news articles for each symbol from Alpaca News API."""
        end = end or today_str()
        all_news: dict[str, list[dict]] = {sym: [] for sym in symbols}

        log.info(f"Fetching news for {len(symbols)} symbols from {start} to {end}")

        for symbol in symbols:
            existing = self._load_raw_news(symbol)
            request = NewsRequest(
                symbols=[symbol],
                start=start,
                end=end,
                limit=self.cfg["news"]["max_articles_per_day"] * 30
            )
            try:
                news_items = self.client.get_news(request)
                articles = []
                for item in news_items.news:
                    article = {
                        "id": item.id,
                        "date": item.created_at.strftime("%Y-%m-%d"),
                        "title": item.headline or "",
                        "summary": item.summary or "",
                        "content": item.content or "",
                        "source": item.source or "",
                        "url": item.url or "",
                        "sentiment_score": None,
                        "sentiment_label": None,
                        "p_positive": None,
                        "p_negative": None,
                        "p_neutral": None,
                    }
                    articles.append(article)

                # Merge with existing (avoid re-scoring already processed)
                existing_ids = {a["id"] for a in existing}
                new_articles = [a for a in articles if a["id"] not in existing_ids]
                all_articles = existing + new_articles

                all_news[symbol] = all_articles
                log.debug(f"{symbol}: {len(new_articles)} new articles fetched")

            except Exception as e:
                log.error(f"Failed to fetch news for {symbol}: {e}")
                all_news[symbol] = existing

            if save:
                self._save_raw_news(symbol, all_news[symbol])

        return all_news

    def score_sentiment(self, all_news: dict[str, list[dict]], save: bool = True) -> dict[str, list[dict]]:
        """Run FinBERT over headline+summary for each unscored article."""
        for symbol, articles in all_news.items():
            log.debug(f"Scoring sentiment for {symbol} ({len(articles)} articles)")
            changed = False
            for article in articles:
                if article["sentiment_score"] is not None:
                    continue  # Already scored

                text = (article["title"] + " " + article["summary"]).strip()
                if not text:
                    article["sentiment_score"] = 0.0
                    article["sentiment_label"] = "neutral"
                    article["p_positive"] = 0.0
                    article["p_negative"] = 0.0
                    article["p_neutral"] = 1.0
                    changed = True
                    continue

                # Truncate to 512 tokens max
                text = text[:1024]
                try:
                    probs = self._run_finbert(text)
                    article["p_positive"] = round(probs[0], 4)
                    article["p_negative"] = round(probs[1], 4)
                    article["p_neutral"] = round(probs[2], 4)
                    article["sentiment_score"] = round(probs[0] - probs[1], 4)  # signed score
                    article["sentiment_label"] = LABELS[int(probs.argmax())]
                    changed = True
                except Exception as e:
                    log.warning(f"Sentiment scoring failed for article in {symbol}: {e}")
                    article["sentiment_score"] = 0.0
                    article["sentiment_label"] = "neutral"

            if save and changed:
                self._save_raw_news(symbol, articles)

        return all_news

    def build_daily_sentiment(
        self, all_news: dict[str, list[dict]]
    ) -> dict[str, pd.DataFrame]:
        """
        Aggregate per-day sentiment features per symbol.
        Returns dict symbol -> DataFrame with columns:
            date, sentiment_mean, sentiment_std, sentiment_momentum_3d,
            sentiment_momentum_5d, article_count, p_positive_mean, p_negative_mean
        """
        result = {}
        for symbol, articles in all_news.items():
            if not articles:
                result[symbol] = pd.DataFrame()
                continue

            df = pd.DataFrame(articles)
            df = df[df["sentiment_score"].notna()]
            df["date"] = pd.to_datetime(df["date"])

            daily = df.groupby("date").agg(
                sentiment_mean=("sentiment_score", "mean"),
                sentiment_std=("sentiment_score", "std"),
                article_count=("sentiment_score", "count"),
                p_positive_mean=("p_positive", "mean"),
                p_negative_mean=("p_negative", "mean")
            ).reset_index()

            daily = daily.sort_values("date").set_index("date")
            daily["sentiment_std"] = daily["sentiment_std"].fillna(0)

            # Sentiment momentum: change from N days ago
            daily["sentiment_momentum_3d"] = daily["sentiment_mean"].diff(3)
            daily["sentiment_momentum_5d"] = daily["sentiment_mean"].diff(5)
            daily["news_volume_anomaly"] = (
                daily["article_count"] / daily["article_count"].rolling(20, min_periods=1).mean()
            )

            result[symbol] = daily

        return result

    def fetch_and_score_all(
        self,
        symbols: list[str],
        start: str,
        end: str | None = None
    ) -> dict[str, pd.DataFrame]:
        """Full pipeline: fetch -> score -> aggregate. Returns daily sentiment DataFrames."""
        raw = self.fetch_news(symbols, start, end)
        scored = self.score_sentiment(raw)
        return self.build_daily_sentiment(scored)

    # ------------------------------------------------------------------ internal

    @torch.no_grad()
    def _run_finbert(self, text: str) -> torch.Tensor:
        inputs = self.tokenizer(
            text,
            return_tensors="pt",
            truncation=True,
            max_length=512,
            padding=True
        ).to(self.device)
        logits = self.model(**inputs).logits
        return torch.softmax(logits, dim=-1).squeeze().cpu()

    def _raw_news_path(self, symbol: str) -> Path:
        return self.raw_dir / f"{symbol}.json"

    def _load_raw_news(self, symbol: str) -> list[dict]:
        path = self._raw_news_path(symbol)
        if not path.exists():
            return []
        with open(path) as f:
            return json.load(f)

    def _save_raw_news(self, symbol: str, articles: list[dict]) -> None:
        path = self._raw_news_path(symbol)
        with open(path, "w") as f:
            json.dump(articles, f, indent=2, default=str)
