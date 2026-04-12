"""Multpl.com fundamentals scraper.

Long-history monthly S&P 500 valuation series. Single HTML table per page,
two columns (Date, Value). Site is robots-friendly and stable.
"""
from __future__ import annotations

import re
import time

import pandas as pd
import requests
from bs4 import BeautifulSoup

from src.data.utils import (
    CATALOG_PATH,
    DATA_DIR,
    FAILED_PATH,
    align_to_trading_days,
    log_failure,
    log_to_catalog,
    save_clean,
    validate_data,
)

CLEAN_DIR = DATA_DIR / "clean" / "fundamental"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    ),
    "Accept": "text/html",
}

SERIES = {
    "pe_ratio": "s-p-500-pe-ratio",
    "shiller_cape": "shiller-pe",
    "earnings_yield": "s-p-500-earnings-yield",
    "dividend_yield": "s-p-500-dividend-yield",
    "earnings": "s-p-500-earnings",
    "price_to_book": "s-p-500-price-to-book",
    "price_to_sales": "s-p-500-price-to-sales",
}


def _get(url: str, retries: int = 3) -> requests.Response | None:
    for i in range(retries):
        try:
            r = requests.get(url, headers=HEADERS, timeout=30)
            if r.status_code == 200:
                return r
            if r.status_code in (429, 503):
                time.sleep(2 ** i * 3)
                continue
            return r
        except requests.RequestException as e:
            print(f"  ! {url}: {e}")
            time.sleep(2 + i)
    return None


_NUM_RE = re.compile(r"-?\d+(?:\.\d+)?")


def _parse_value(s: str) -> float | None:
    s = s.replace(",", "").replace("$", "").replace("%", "")
    m = _NUM_RE.search(s)
    return float(m.group(0)) if m else None


def _parse_table(html: str) -> pd.DataFrame:
    soup = BeautifulSoup(html, "lxml")
    table = soup.find("table")
    if table is None:
        return pd.DataFrame()
    dates, vals = [], []
    for tr in table.find_all("tr")[1:]:
        cells = [td.get_text(strip=True) for td in tr.find_all("td")]
        if len(cells) < 2:
            continue
        try:
            d = pd.to_datetime(cells[0])
        except (ValueError, TypeError):
            continue
        v = _parse_value(cells[1])
        if v is None:
            continue
        dates.append(d)
        vals.append(v)
    return pd.DataFrame({"value": vals}, index=pd.DatetimeIndex(dates)).sort_index()


def fetch_one(name: str, slug: str) -> None:
    url = f"https://www.multpl.com/{slug}/table/by-month"
    print(f"[multpl] {name} <- {slug}")
    r = _get(url)
    if r is None or r.status_code != 200:
        sc = r.status_code if r is not None else "ERR"
        log_failure(FAILED_PATH, f"multpl:{name}", f"HTTP {sc}", attempted=url)
        print(f"  ! failed {sc}")
        return
    df = _parse_table(r.text)
    if df.empty:
        log_failure(FAILED_PATH, f"multpl:{name}", "empty table parse", attempted=url)
        return
    df = df.rename(columns={"value": name})
    aligned = align_to_trading_days(df, source_freq="monthly")
    path = CLEAN_DIR / f"sp500_{name}.parquet"
    save_clean(aligned, path, metadata={"source": "multpl", "url": url})
    validate_data(aligned, name=f"sp500_{name}")
    log_to_catalog(CATALOG_PATH, {
        "source": "multpl",
        "series_name": f"sp500_{name}",
        "frequency": "monthly",
        "date_range": f"{aligned.index.min().date()}..{aligned.index.max().date()}",
        "file_path": str(path.relative_to(DATA_DIR.parent)).replace("\\", "/"),
        "status": "OK",
        "notes": "monthly S&P 500 fundamentals",
    })


def main() -> None:
    CLEAN_DIR.mkdir(parents=True, exist_ok=True)
    for name, slug in SERIES.items():
        fetch_one(name, slug)
        time.sleep(3)


if __name__ == "__main__":
    main()
