"""Historical news headline backfill via SerpAPI (Google News tab).

Iterates 10 financial topics across monthly date-ranges from 2010-01 to
2024-01 using engine=google&tbm=nws. The fetcher is resumable:
before each (topic, month) call it consults an on-disk checkpoint set
built from already-saved rows so re-runs skip completed work.

Key is loaded from the project .env (SERPAPI_KEY). Never hardcode.
"""
from __future__ import annotations

import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

import pandas as pd
import requests
from dotenv import load_dotenv

from src.data.utils import DATA_DIR, FAILED_PATH, log_failure

load_dotenv()
SERPAPI_KEY = os.getenv("SERPAPI_KEY")

RAW_DIR = DATA_DIR / "raw" / "news"
OUT = RAW_DIR / "serpapi_headlines.parquet"
CHECKPOINT = RAW_DIR / "serpapi_checkpoint.txt"

API = "https://serpapi.com/search.json"
TOPICS: list[str] = [
    "stock market",
    "S&P 500",
    "tech stocks semiconductor",
    "oil prices energy",
    "inflation interest rates",
    "recession economy",
    "gold prices",
    "housing market",
    "federal reserve",
    "earnings report",
]
START = pd.Timestamp("2010-01-01")
END = pd.Timestamp("2024-02-01")  # overlap one month with existing RSS
SLEEP = 0.1  # per-thread sleep between calls (throttled by pool size)
N_WORKERS = 6
FLUSH_EVERY = 50  # save incremental rows every N successful calls

_lock = threading.Lock()


def _month_ranges(start: pd.Timestamp, end: pd.Timestamp) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    out = []
    cur = start
    while cur < end:
        nxt = (cur + pd.offsets.MonthBegin(1))
        out.append((cur, nxt - pd.Timedelta(days=1)))
        cur = nxt
    return out


def _tbs(a: pd.Timestamp, b: pd.Timestamp) -> str:
    return f"cdr:1,cd_min:{a.strftime('%m/%d/%Y')},cd_max:{b.strftime('%m/%d/%Y')}"


def _load_checkpoint() -> set[str]:
    if not CHECKPOINT.exists():
        return set()
    return {ln.strip() for ln in CHECKPOINT.read_text().splitlines() if ln.strip()}


def _append_checkpoint(key: str) -> None:
    with _lock, CHECKPOINT.open("a") as f:
        f.write(key + "\n")


def _save(rows: list[dict], mode: str = "merge") -> None:
    if not rows:
        return
    with _lock:
        new = pd.DataFrame(rows)
        if OUT.exists():
            old = pd.read_parquet(OUT)
            merged = pd.concat([old, new], ignore_index=True)
        else:
            merged = new
        merged = merged.drop_duplicates(subset=["title", "source", "date_str"]).reset_index(drop=True)
        merged.to_parquet(OUT, index=False)


def _query(topic: str, a: pd.Timestamp, b: pd.Timestamp) -> list[dict]:
    params = {
        "engine": "google",
        "tbm": "nws",
        "q": topic,
        "tbs": _tbs(a, b),
        "num": 100,
        "hl": "en",
        "gl": "us",
        "api_key": SERPAPI_KEY,
    }
    try:
        r = requests.get(API, params=params, timeout=45)
    except requests.RequestException as e:
        raise RuntimeError(f"request error: {e}") from e
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code}: {r.text[:150]}")
    data = r.json()
    if data.get("error"):
        raise RuntimeError(f"api error: {data['error']}")
    results = data.get("news_results") or []
    out = []
    for item in results:
        title = (item.get("title") or "").strip()
        if not title:
            continue
        out.append({
            "title": title,
            "snippet": (item.get("snippet") or "").strip(),
            "source": (item.get("source") or "").strip(),
            "date_str": item.get("date", ""),
            "link": item.get("link", ""),
            "topic_query": topic,
            "window_start": a.date().isoformat(),
            "window_end": b.date().isoformat(),
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        })
    return out


def main() -> None:
    if not SERPAPI_KEY:
        log_failure(FAILED_PATH, "serpapi_news", "SERPAPI_KEY missing in .env", attempted=API)
        print("[serpapi] ERROR: SERPAPI_KEY not set")
        return
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    done = _load_checkpoint()
    print(f"[serpapi] checkpoint has {len(done)} completed (topic,month) pairs")
    months = _month_ranges(START, END)
    total = len(TOPICS) * len(months)
    print(f"[serpapi] plan: {len(TOPICS)} topics x {len(months)} months = {total} calls")

    work = [(t, a, b, f"{t}|{a.strftime('%Y-%m')}") for t in TOPICS for a, b in months
            if f"{t}|{a.strftime('%Y-%m')}" not in done]
    print(f"[serpapi] pending={len(work)} workers={N_WORKERS}")

    pending: list[dict] = []
    done_count = 0
    fail_count = 0

    def _task(job):
        topic, a, b, key = job
        try:
            rows = _query(topic, a, b)
            time.sleep(SLEEP)
            return key, rows, None
        except Exception as e:
            return key, [], str(e)

    with ThreadPoolExecutor(max_workers=N_WORKERS) as ex:
        futs = [ex.submit(_task, j) for j in work]
        for fut in as_completed(futs):
            key, rows, err = fut.result()
            if err is not None:
                print(f"  ! {key}: {err}")
                fail_count += 1
                log_failure(FAILED_PATH, f"serpapi:{key}", err[:150], attempted=key)
                continue
            pending.extend(rows)
            done_count += 1
            _append_checkpoint(key)
            if done_count % 25 == 0:
                print(f"  .. {done_count}/{len(work)} calls, {len(pending)} rows buffered, last={key} ({len(rows)} hits)")
            if len(pending) >= FLUSH_EVERY * 20:
                with _lock:
                    buf = list(pending); pending.clear()
                _save(buf)

    _save(pending)
    pending.clear()
    print(f"[serpapi] done. calls={done_count} failures={fail_count}")
    if OUT.exists():
        df = pd.read_parquet(OUT)
        print(f"[serpapi] total rows={len(df)} file={OUT}")


if __name__ == "__main__":
    main()
