"""Wikipedia pageviews fetcher. Uses Wikimedia REST API. No auth required."""
from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from datetime import datetime

import pandas as pd

from src.data.utils import (
    CATALOG_PATH,
    DATA_DIR,
    FAILED_PATH,
    align_to_trading_days,
    log_failure,
    log_to_catalog,
    save_clean,
)

CLEAN_DIR = DATA_DIR / "clean" / "alternative"

TITLES = [
    "Recession", "Inflation", "Cryptocurrency", "Artificial_intelligence",
    "Stock_market_crash", "Federal_Reserve", "Yield_curve", "Semiconductor",
    "Gold_as_an_investment", "S%26P_500", "NASDAQ-100", "Bear_market",
    "Quantitative_easing", "Stagflation", "Oil_crisis", "Unemployment",
    "Bitcoin", "NVIDIA", "Dot-com_bubble", "Subprime_mortgage_crisis",
    "Trade_war", "Bank_run", "Margin_(finance)", "Short_selling",
]

BASE = "https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/en.wikipedia/all-access/all-agents/{title}/daily/{start}/{end}"


def _slug(title: str) -> str:
    s = urllib.parse.unquote(title).lower()
    s = "".join(c if c.isalnum() else "_" for c in s).strip("_")
    while "__" in s:
        s = s.replace("__", "_")
    return s


def _fetch_title(title: str, start: str, end: str, timeout: int = 30) -> pd.DataFrame:
    url = BASE.format(title=urllib.parse.quote(title, safe="%"), start=start, end=end)
    req = urllib.request.Request(url, headers={"User-Agent": "quant-research-bot/1.0 (contact@example.com)"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        payload = json.loads(resp.read())
    items = payload.get("items", [])
    if not items:
        return pd.DataFrame()
    rows = [(i["timestamp"][:8], i["views"]) for i in items]
    df = pd.DataFrame(rows, columns=["date", "views"])
    df["date"] = pd.to_datetime(df["date"], format="%Y%m%d")
    df = df.set_index("date").sort_index()
    return df


def main(start: str = "20150701", end: str | None = None) -> None:
    CLEAN_DIR.mkdir(parents=True, exist_ok=True)
    if end is None:
        end = datetime.utcnow().strftime("%Y%m%d")
    for title in TITLES:
        slug = _slug(title)
        print(f"[wikipedia] {title}")
        try:
            df = _fetch_title(title, start, end)
        except Exception as e:
            print(f"  ! {title}: {e}")
            log_failure(FAILED_PATH, f"wikipedia:{slug}", str(e), attempted=title)
            time.sleep(0.2)
            continue
        if df.empty:
            log_failure(FAILED_PATH, f"wikipedia:{slug}", "empty payload", attempted=title)
            continue
        df.columns = [f"wiki_{slug}_views"]
        aligned = align_to_trading_days(df, source_freq="daily", limit=3)
        path = CLEAN_DIR / f"wikipedia_{slug}.parquet"
        save_clean(aligned, path, metadata={"source": "wikipedia", "title": title})
        log_to_catalog(CATALOG_PATH, {
            "source": "wikipedia",
            "series_name": f"wikipedia_{slug}",
            "frequency": "daily",
            "date_range": f"{aligned.index.min().date()}..{aligned.index.max().date()}",
            "file_path": str(path.relative_to(DATA_DIR.parent)).replace("\\", "/"),
            "status": "OK",
            "notes": title,
        })
        time.sleep(0.15)


if __name__ == "__main__":
    main()
