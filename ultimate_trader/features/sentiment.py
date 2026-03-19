"""FinBERT-based news sentiment analysis."""
import json
import re
import torch
import numpy as np
import pandas as pd
from pathlib import Path
from typing import Dict, Optional
from transformers import AutoTokenizer, AutoModelForSequenceClassification

from ultimate_trader.utils.logging import get_logger

log = get_logger(__name__)

FINBERT_MODEL = "ProsusAI/finbert"
_LABELS = ["positive", "negative", "neutral"]


class SentimentAnalyser:
    """
    FinBERT sentiment analyser. Loaded ONCE and reused for all symbols.
    Scores articles and aggregates per-symbol daily sentiment features.
    """

    def __init__(self, model_name: str = FINBERT_MODEL, device: str = None):
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        log.info(f"Loading FinBERT on {self.device}...")
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForSequenceClassification.from_pretrained(model_name)
        self.model.to(self.device)
        self.model.eval()
        log.info("FinBERT loaded.")

    @torch.no_grad()
    def score_text(self, text: str) -> Dict[str, float]:
        """
        Score a single text. Returns dict with:
            positive, negative, neutral probabilities
            score = positive - negative  (range -1 to 1)
        """
        text = re.sub(r"[^\x00-\x7F]+", " ", text)
        text = text[:512]  # FinBERT max token limit
        inputs = self.tokenizer(text, return_tensors="pt",
                                padding=True, truncation=True, max_length=512)
        inputs = {k: v.to(self.device) for k, v in inputs.items()}
        logits = self.model(**inputs).logits
        probs = torch.softmax(logits, dim=-1).squeeze().cpu().numpy()
        return {
            "positive": float(probs[0]),
            "negative": float(probs[1]),
            "neutral":  float(probs[2]),
            "score":    float(probs[0] - probs[1]),
        }

    def score_article(self, title: str, summary: str = "", content: str = "") -> Dict[str, float]:
        """
        Score an article using best available text: content > summary > title.
        Weights: content 60%, summary 25%, title 15%.
        """
        scores = []
        weights = []

        if content and len(content.strip()) > 100:
            scores.append(self.score_text(content[:1000]))
            weights.append(0.60)

        if summary and len(summary.strip()) > 30:
            scores.append(self.score_text(summary))
            weights.append(0.25 if content else 0.70)

        if title:
            scores.append(self.score_text(title))
            weights.append(0.15 if content else (0.30 if summary else 1.0))

        if not scores:
            return {"positive": 0.33, "negative": 0.33, "neutral": 0.34, "score": 0.0}

        w = np.array(weights[:len(scores)])
        w = w / w.sum()
        composite = {}
        for key in ["positive", "negative", "neutral", "score"]:
            composite[key] = float(sum(s[key] * wt for s, wt in zip(scores, w)))
        return composite

    def score_symbol_news(self, news_json_path: str,
                          force_rescore: bool = False) -> str:
        """
        Score all articles in a symbol's news JSON that don't yet have scores.
        Saves back to the same file. Returns the path.
        """
        fpath = Path(news_json_path)
        if not fpath.exists():
            return news_json_path

        with open(fpath) as f:
            data = json.load(f)

        changed = False
        for date_str, articles in data.items():
            for article in articles:
                if article.get("score") is not None and not force_rescore:
                    continue
                result = self.score_article(
                    article.get("title", ""),
                    article.get("summary", ""),
                    article.get("content", ""),
                )
                article.update(result)
                changed = True

        if changed:
            with open(fpath, "w") as f:
                json.dump(data, f, indent=2)

        return news_json_path


def build_sentiment_features(
    symbol: str,
    news_raw_dir: str = "data/raw/news",
    lookback_days: int = 40,
) -> pd.DataFrame:
    """
    Build daily sentiment feature DataFrame for a symbol.
    Features per day:
        sentiment_score         - avg composite score
        sentiment_pos           - avg positive probability
        sentiment_neg           - avg negative probability
        article_count           - number of articles that day
        sentiment_3d_momentum   - 3-day change in score
        sentiment_5d_momentum   - 5-day change in score
        sentiment_volatility    - 10-day rolling std of score
    """
    fpath = Path(news_raw_dir) / f"{symbol}.json"
    if not fpath.exists():
        return pd.DataFrame()

    with open(fpath) as f:
        data = json.load(f)

    rows = []
    for date_str, articles in data.items():
        if not articles:
            continue
        scored = [a for a in articles if a.get("score") is not None]
        if not scored:
            continue
        scores    = [a["score"] for a in scored]
        positives = [a.get("positive", 0) for a in scored]
        negatives = [a.get("negative", 0) for a in scored]
        rows.append({
            "date":              date_str,
            "sentiment_score":   np.mean(scores),
            "sentiment_pos":     np.mean(positives),
            "sentiment_neg":     np.mean(negatives),
            "article_count":     len(scored),
        })

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date").sort_index()

    df["sentiment_3d_momentum"] = df["sentiment_score"].diff(3)
    df["sentiment_5d_momentum"] = df["sentiment_score"].diff(5)
    df["sentiment_volatility"]  = df["sentiment_score"].rolling(10, min_periods=3).std()
    df["article_count_z"]       = (
        (df["article_count"] - df["article_count"].rolling(20).mean()) /
        df["article_count"].rolling(20).std()
    )
    df.fillna(0, inplace=True)
    return df
