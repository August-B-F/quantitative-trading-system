"""SIA monthly global semiconductor sales scraper.

SIA publishes a monthly press release titled like
"Global Semiconductor Sales Increase X% in <Month>". Each release contains
the headline three-month-moving-average sales figure (USD billions). We:

1. Walk the /news-events/latest-news/ paginated listing.
2. Filter to URLs containing "semiconductor-sales".
3. Fetch each release and extract: month/year + sales figure + YoY/MoM %.
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
LISTING = "https://www.semiconductors.org/news-events/latest-news/page/{n}/"
MAX_PAGES = 80

MONTHS = "January|February|March|April|May|June|July|August|September|October|November|December"
RE_SALES = re.compile(
    r"\$(\d+\.?\d*)\s*billion[^.]*?(?:in|during)\s+(?:the\s+month\s+of\s+)?(" + MONTHS + r")\s+(\d{4})",
    re.I,
)
RE_YOY = re.compile(r"(-?\d+\.?\d*)\s*%\s*(?:more|increase|higher|year[- ]to[- ]year|y[- ]?o[- ]?y)", re.I)
RE_MOM = re.compile(r"(-?\d+\.?\d*)\s*%\s*(?:compared to the .{0,30}total of|month[- ]to[- ]month)", re.I)


def _get(url: str, retries: int = 3) -> str | None:
    for i in range(retries):
        try:
            r = requests.get(url, headers=HEADERS, timeout=30)
            if r.status_code == 200:
                return r.text
            if r.status_code == 404:
                return None
            if r.status_code in (429, 503):
                time.sleep(2 ** i * 3)
                continue
            return None
        except requests.RequestException:
            time.sleep(2 + i)
    return None


def collect_release_urls() -> list[str]:
    seen: set[str] = set()
    urls: list[str] = []
    empty_streak = 0
    for n in range(1, MAX_PAGES + 1):
        html = _get(LISTING.format(n=n))
        if html is None:
            empty_streak += 1
            if empty_streak >= 3:
                break
            continue
        empty_streak = 0
        soup = BeautifulSoup(html, "lxml")
        new_count = 0
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "semiconductor-sales" not in href.lower():
                continue
            href = href.split("?")[0]
            if href not in seen:
                seen.add(href)
                urls.append(href)
                new_count += 1
        print(f"  page {n}: +{new_count} ({len(urls)} total)")
        time.sleep(2.5)
        if new_count == 0:
            empty_streak += 1
            if empty_streak >= 3:
                break
    return urls


def parse_release(url: str) -> dict | None:
    html = _get(url)
    if html is None:
        return None
    soup = BeautifulSoup(html, "lxml")
    art = soup.find("article") or soup
    text = art.get_text(" ", strip=True)
    m = RE_SALES.search(text)
    if not m:
        return None
    sales = float(m.group(1))
    month = m.group(2)
    year = int(m.group(3))
    try:
        d = pd.Timestamp(f"{year}-{month}-01") + pd.offsets.MonthEnd(0)
    except ValueError:
        return None
    yoy = RE_YOY.search(text)
    mom = RE_MOM.search(text)
    return {
        "date": d,
        "sales_usd_bn": sales,
        "yoy_pct": float(yoy.group(1)) if yoy else None,
        "mom_pct": float(mom.group(1)) if mom else None,
        "url": url,
    }


def main() -> None:
    CLEAN_DIR.mkdir(parents=True, exist_ok=True)
    print("[sia] collecting press release URLs")
    urls = collect_release_urls()
    print(f"[sia] {len(urls)} candidate releases")
    rows = []
    for u in urls:
        rec = parse_release(u)
        if rec:
            rows.append(rec)
        time.sleep(2.5)
    if not rows:
        log_failure(FAILED_PATH, "sia:semi_sales", "no releases parsed", attempted=LISTING)
        return
    df = pd.DataFrame(rows).drop_duplicates(subset=["date"]).set_index("date").sort_index()
    df = df[["sales_usd_bn", "yoy_pct", "mom_pct"]]
    aligned = align_to_trading_days(df, source_freq="monthly")
    path = CLEAN_DIR / "sia_semiconductor_sales.parquet"
    save_clean(aligned, path, metadata={"source": "sia"})
    validate_data(aligned, name="sia_semiconductor_sales")
    log_to_catalog(CATALOG_PATH, {
        "source": "sia",
        "series_name": "sia_semiconductor_sales",
        "frequency": "monthly",
        "date_range": f"{aligned.index.min().date()}..{aligned.index.max().date()}",
        "file_path": str(path.relative_to(DATA_DIR.parent)).replace("\\", "/"),
        "status": "OK",
        "notes": "scraped from press release headlines (3-month moving average)",
    })


if __name__ == "__main__":
    main()
