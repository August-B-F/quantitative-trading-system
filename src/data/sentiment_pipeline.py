"""News headline sentiment pipeline.

Reads raw headlines from data/raw/news/headlines.parquet, scores each
with VADER, tags topics by keyword, and writes daily aggregates per
topic plus an overall file.
"""
from __future__ import annotations

import re

import nltk
import pandas as pd

try:
    from nltk.sentiment.vader import SentimentIntensityAnalyzer  # noqa: E402
    _sia = SentimentIntensityAnalyzer()
except LookupError:
    nltk.download("vader_lexicon", quiet=True)
    from nltk.sentiment.vader import SentimentIntensityAnalyzer  # noqa: E402
    _sia = SentimentIntensityAnalyzer()

from src.data.utils import (
    CATALOG_PATH,
    DATA_DIR,
    align_to_trading_days,
    log_to_catalog,
    save_clean,
    validate_data,
)

RAW = DATA_DIR / "raw" / "news" / "headlines.parquet"
SERP = DATA_DIR / "raw" / "news" / "serpapi_headlines.parquet"
CLEAN_DIR = DATA_DIR / "clean" / "sentiment"

TOPICS: dict[str, list[str]] = {
    "tech": ["tech", "semiconductor", "chip", "ai ", "artificial intelligence",
             "nvidia", "apple", "microsoft", "software", "cloud"],
    "energy": ["oil", "gas", "energy", "opec", "crude", "drilling",
               "renewable", "solar", "pipeline"],
    "inflation": ["inflation", "cpi", "prices", "cost", "fed", "rate",
                  "interest rate", "monetary", "hawkish", "dovish"],
    "recession": ["recession", "slowdown", "downturn", "contraction",
                  "layoff", "unemployment", "gdp"],
    "market": ["stock", "market", "rally", "crash", "sell-off", "bull",
               "bear", "correction", "volatility"],
    "gold": ["gold", "precious metal", "safe haven", "bullion"],
    "housing": ["housing", "home", "mortgage", "real estate", "property"],
    "crypto": ["bitcoin", "crypto", "ethereum", "blockchain"],
}
TOPIC_RE = {t: re.compile("|".join(re.escape(k) for k in kws), re.I)
            for t, kws in TOPICS.items()}


def _tag_topics(title: str) -> list[str]:
    return [t for t, rx in TOPIC_RE.items() if rx.search(title)]


def _aggregate(df: pd.DataFrame, label: str) -> pd.DataFrame:
    if df.empty:
        return df
    g = df.groupby("day")
    out = pd.DataFrame({
        f"{label}_count": g.size(),
        f"{label}_mean_sent": g["compound"].mean(),
        f"{label}_neg_share": g["compound"].apply(lambda s: float((s < -0.05).mean())),
        f"{label}_pos_share": g["compound"].apply(lambda s: float((s > 0.05).mean())),
    })
    out.index = pd.to_datetime(out.index)
    out.index.name = "date"
    return out.sort_index()


def _save(df: pd.DataFrame, path, label: str, notes: str) -> None:
    if df.empty:
        return
    aligned = align_to_trading_days(df, source_freq="daily")
    save_clean(aligned, path, metadata={"source": "news_vader", "label": label})
    validate_data(aligned, name=path.stem)
    log_to_catalog(CATALOG_PATH, {
        "source": "news_vader",
        "series_name": path.stem,
        "frequency": "daily",
        "date_range": f"{aligned.index.min().date()}..{aligned.index.max().date()}",
        "file_path": str(path.relative_to(DATA_DIR.parent)).replace("\\", "/"),
        "status": "OK",
        "notes": notes,
    })


def _load_rss() -> pd.DataFrame:
    if not RAW.exists():
        return pd.DataFrame()
    df = pd.read_parquet(RAW)
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    df = df.dropna(subset=["timestamp", "title"])
    df["day"] = df["timestamp"].dt.tz_convert("US/Eastern").dt.normalize().dt.tz_localize(None)
    df["text"] = df["title"].astype(str)
    df["origin"] = "rss"
    return df[["day", "title", "text", "source", "origin"]]


def _parse_serp_date(s: str) -> pd.Timestamp | None:
    """SerpAPI returns 'Jun 18, 2015' or '3 days ago' etc. For relative
    strings we fall back to the midpoint of the query window encoded in
    window_start/window_end (handled by caller)."""
    if not s:
        return None
    try:
        return pd.to_datetime(s, errors="raise")
    except (ValueError, TypeError):
        return None


def _load_serp() -> pd.DataFrame:
    if not SERP.exists():
        return pd.DataFrame()
    df = pd.read_parquet(SERP)
    parsed = df["date_str"].map(_parse_serp_date)
    # Fallback: use window midpoint for unparseable dates
    mid = (pd.to_datetime(df["window_start"]) + (pd.to_datetime(df["window_end"]) - pd.to_datetime(df["window_start"])) / 2)
    parsed = parsed.fillna(mid)
    df = df.copy()
    df["day"] = pd.to_datetime(parsed).dt.normalize()
    df = df.dropna(subset=["day", "title"])
    df["text"] = (df["title"].astype(str) + ". " + df["snippet"].fillna("").astype(str)).str.strip()
    df["origin"] = "serpapi"
    return df[["day", "title", "text", "source", "origin"]]


def main() -> None:
    rss = _load_rss()
    serp = _load_serp()
    if rss.empty and serp.empty:
        print("[sentiment_pipeline] no input data")
        return
    raw = pd.concat([rss, serp], ignore_index=True)
    CLEAN_DIR.mkdir(parents=True, exist_ok=True)
    raw = raw.drop_duplicates(subset=["title", "source"]).reset_index(drop=True)
    print(f"[sentiment_pipeline] scoring {len(raw)} headlines (rss={len(rss)} serp={len(serp)})")
    raw["compound"] = raw["text"].map(lambda t: _sia.polarity_scores(t)["compound"])
    raw["topics"] = raw["text"].map(_tag_topics)

    # Overall
    overall = _aggregate(raw, "overall")
    _save(overall, CLEAN_DIR / "news_sentiment_overall.parquet",
          "overall", "VADER overall daily headline sentiment")

    # Per-topic
    for topic in TOPICS:
        mask = raw["topics"].map(lambda ts, t=topic: t in ts)
        sub = raw[mask]
        agg = _aggregate(sub, topic)
        if not agg.empty:
            _save(agg, CLEAN_DIR / f"news_sentiment_{topic}.parquet",
                  topic, f"VADER {topic}-topic daily headline sentiment")

    # sanity prints
    if not overall.empty:
        print(overall.tail(5))


if __name__ == "__main__":
    main()
