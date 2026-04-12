"""Financial news headline collector.

Pulls free RSS feeds (Yahoo Finance, Google News finance queries,
MarketWatch). RSS only exposes the last N days of headlines, so
real backfill needs repeated runs — we merge into an existing
parquet rather than overwrite.
"""
from __future__ import annotations

import time
from datetime import datetime, timezone

import feedparser
import pandas as pd

from src.data.utils import DATA_DIR, FAILED_PATH, log_failure

RAW_DIR = DATA_DIR / "raw" / "news"
OUT = RAW_DIR / "headlines.parquet"

# (name, url, category)
FEEDS: list[tuple[str, str, str]] = [
    ("yahoo", "https://finance.yahoo.com/news/rssindex", "top"),
    ("yahoo", "https://finance.yahoo.com/rss/topstories", "top"),
    ("yahoo", "https://finance.yahoo.com/rss/headline", "headline"),
    ("yahoo", "https://feeds.finance.yahoo.com/rss/2.0/headline?s=^GSPC&region=US&lang=en-US", "sp500"),
    ("yahoo", "https://feeds.finance.yahoo.com/rss/2.0/headline?s=^IXIC&region=US&lang=en-US", "nasdaq"),
    ("marketwatch", "https://feeds.marketwatch.com/marketwatch/topstories/", "top"),
    ("marketwatch", "https://feeds.marketwatch.com/marketwatch/marketpulse/", "market"),
    ("marketwatch", "https://feeds.marketwatch.com/marketwatch/realtimeheadlines/", "realtime"),
    ("cnbc", "https://www.cnbc.com/id/100003114/device/rss/rss.html", "top"),
    ("cnbc", "https://www.cnbc.com/id/10000664/device/rss/rss.html", "economy"),
    ("cnbc", "https://www.cnbc.com/id/15839069/device/rss/rss.html", "markets"),
    ("cnbc", "https://www.cnbc.com/id/19746125/device/rss/rss.html", "business"),
    ("cnbc", "https://www.cnbc.com/id/19854910/device/rss/rss.html", "tech"),
    ("cnbc", "https://www.cnbc.com/id/19836768/device/rss/rss.html", "finance"),
    ("reuters", "https://news.google.com/rss/search?q=site:reuters.com+when:30d&hl=en-US&gl=US&ceid=US:en", "reuters"),
    ("gnews", "https://news.google.com/rss/search?q=stock+market&hl=en-US&gl=US&ceid=US:en", "market"),
    ("gnews", "https://news.google.com/rss/search?q=inflation+federal+reserve&hl=en-US&gl=US&ceid=US:en", "inflation"),
    ("gnews", "https://news.google.com/rss/search?q=recession+economy&hl=en-US&gl=US&ceid=US:en", "recession"),
    ("gnews", "https://news.google.com/rss/search?q=oil+price+energy&hl=en-US&gl=US&ceid=US:en", "energy"),
    ("gnews", "https://news.google.com/rss/search?q=semiconductor+chip+AI&hl=en-US&gl=US&ceid=US:en", "tech"),
    ("gnews", "https://news.google.com/rss/search?q=bitcoin+crypto&hl=en-US&gl=US&ceid=US:en", "crypto"),
    ("gnews", "https://news.google.com/rss/search?q=housing+mortgage&hl=en-US&gl=US&ceid=US:en", "housing"),
    ("gnews", "https://news.google.com/rss/search?q=gold+price&hl=en-US&gl=US&ceid=US:en", "gold"),
]


def _entry_time(e) -> datetime | None:
    for k in ("published_parsed", "updated_parsed"):
        t = e.get(k)
        if t:
            return datetime(*t[:6], tzinfo=timezone.utc)
    return None


def _fetch_feed(source: str, url: str, category: str) -> list[dict]:
    rows = []
    try:
        d = feedparser.parse(url, request_headers={"User-Agent": "Mozilla/5.0"})
    except Exception as e:
        print(f"  ! {source}:{category}: {e}")
        return rows
    if getattr(d, "bozo", 0) and not d.entries:
        print(f"  ! {source}:{category}: bozo {getattr(d, 'bozo_exception', '')}")
        return rows
    for e in d.entries:
        title = (e.get("title") or "").strip()
        if not title:
            continue
        ts = _entry_time(e)
        rows.append({
            "timestamp": ts,
            "title": title,
            "source": source,
            "category": category,
            "link": e.get("link", ""),
        })
    print(f"  + {source}:{category}: {len(rows)} entries")
    return rows


def main() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    all_rows: list[dict] = []
    for source, url, cat in FEEDS:
        all_rows.extend(_fetch_feed(source, url, cat))
        time.sleep(1)
    if not all_rows:
        log_failure(FAILED_PATH, "news_headlines", "all feeds empty", attempted="multiple RSS")
        return
    new_df = pd.DataFrame(all_rows)
    new_df["timestamp"] = pd.to_datetime(new_df["timestamp"], utc=True, errors="coerce")
    new_df = new_df.dropna(subset=["timestamp"])
    if OUT.exists():
        old = pd.read_parquet(OUT)
        old["timestamp"] = pd.to_datetime(old["timestamp"], utc=True, errors="coerce")
        merged = pd.concat([old, new_df], ignore_index=True)
    else:
        merged = new_df
    merged = merged.drop_duplicates(subset=["title", "source"]).sort_values("timestamp")
    merged.to_parquet(OUT, index=False)
    print(f"[news_headlines] saved {len(merged)} rows ({new_df.shape[0]} new) -> {OUT}")
    if len(merged):
        print(f"  range {merged['timestamp'].min()} .. {merged['timestamp'].max()}")


if __name__ == "__main__":
    main()
