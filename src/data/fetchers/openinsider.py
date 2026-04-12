"""OpenInsider Form 4 aggregator.

OpenInsider's screener returns max 5000 rows per query (cnt= and page= are
ignored above 5000). To collect long history we iterate by month, fetching
buys (xp=1) and sales (xs=1) separately. If a month hits the 5000 cap we
recursively halve the date range.

We aggregate to daily totals: trade count and dollar value, split by
buy/sell, plus a daily and rolling 21d sentiment score.
"""
from __future__ import annotations

import re
import sys
import time
import urllib.parse
from datetime import date, timedelta

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

CLEAN_DIR = DATA_DIR / "clean" / "sentiment"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    ),
    "Accept": "text/html",
}

START_DATE = date(2014, 1, 1)
END_DATE = date.today()
HARD_CAP = 5000
DELAY = 1.0


_SESSION = requests.Session()


def _get(url: str, retries: int = 4) -> str | None:
    for i in range(retries):
        try:
            r = _SESSION.get(url, headers=HEADERS, timeout=60)
            if r.status_code == 200:
                return r.text
            if r.status_code in (429, 503):
                time.sleep(2 ** i * 3)
                continue
            print(f"  ! HTTP {r.status_code} {url[:90]}")
            return None
        except requests.RequestException as e:
            print(f"  ! {e}")
            time.sleep(3 + i * 2)
    return None


def _build_url(d1: date, d2: date) -> str:
    fdr = f"{d1.strftime('%m/%d/%Y')} - {d2.strftime('%m/%d/%Y')}"
    fdr = urllib.parse.quote(fdr)
    # Both xp=1 and xs=1 must be set; we split buy vs sell by trade-type column.
    return (
        f"http://openinsider.com/screener?fdr={fdr}&xp=1&xs=1"
        f"&cnt={HARD_CAP}&sortcol=1"
    )


def _parse_rows(html: str) -> pd.DataFrame:
    soup = BeautifulSoup(html, "lxml")
    tables = soup.find_all("table", class_="tinytable")
    if not tables:
        return pd.DataFrame()
    rows = tables[0].find_all("tr")
    out = []
    for tr in rows[1:]:
        cells = [td.get_text(" ", strip=True) for td in tr.find_all("td")]
        if len(cells) < 13:
            continue
        try:
            trade_date = pd.to_datetime(cells[2])
        except (ValueError, TypeError):
            continue
        ttype = cells[7]  # Trade Type column, e.g. "P - Purchase" or "S - Sale+OE"
        kind = "buy" if ttype.startswith("P") else ("sell" if ttype.startswith("S") else None)
        if kind is None:
            continue
        val_str = cells[12].replace(",", "").replace("$", "").replace("+", "")
        try:
            val = float(val_str)
        except ValueError:
            continue
        out.append((trade_date, kind, abs(val)))
    if not out:
        return pd.DataFrame()
    return pd.DataFrame(out, columns=["trade_date", "kind", "value"])


def _fetch_range(d1: date, d2: date) -> pd.DataFrame:
    """Recursively split if cap hit."""
    url = _build_url(d1, d2)
    html = _get(url)
    time.sleep(DELAY)
    if html is None:
        return pd.DataFrame()
    m = re.search(r"(\d+)\s+results", html)
    n = int(m.group(1)) if m else 0
    df = _parse_rows(html)
    if n >= HARD_CAP and (d2 - d1).days > 1:
        mid = d1 + (d2 - d1) // 2
        print(f"  split {d1}..{d2} ({n} rows)")
        a = _fetch_range(d1, mid)
        b = _fetch_range(mid + timedelta(days=1), d2)
        return pd.concat([a, b], ignore_index=True)
    return df


def _quarter_starts(start: date, end: date):
    """Yield (start, end) for each calendar quarter overlapping [start, end]."""
    y, q = start.year, (start.month - 1) // 3
    while True:
        m1 = q * 3 + 1
        d1 = date(y, m1, 1)
        if d1 > end:
            return
        if q == 3:
            nxt = date(y + 1, 1, 1)
        else:
            nxt = date(y, m1 + 3, 1)
        yield max(d1, start), min(nxt - timedelta(days=1), end)
        q += 1
        if q == 4:
            q = 0
            y += 1


def main() -> None:
    CLEAN_DIR.mkdir(parents=True, exist_ok=True)
    print(f"[openinsider] {START_DATE}..{END_DATE}")

    # Quick health check: openinsider's screener backend is sometimes broken
    # ("ERROR: Unable to select tables for main"). If so, fall back to the
    # preset /insider-purchases + /insider-sales pages (latest ~100 each).
    test_html = _get(_build_url(date(2024, 1, 1), date(2024, 1, 31)))
    if test_html and "ERROR: Unable to select tables" in test_html:
        log_failure(
            FAILED_PATH,
            "openinsider:screener",
            "screener backend returns 'ERROR: Unable to select tables for main' "
            "for any fdr date-range query (server-side bug, not a block). "
            "Falling back to /insider-purchases + /insider-sales preset snapshots "
            "(latest ~100 rows each, no historical depth).",
            attempted="screener?fdr=...&xp=1&xs=1",
        )
        chunks: list[pd.DataFrame] = []
        for url in (
            "http://openinsider.com/insider-purchases",
            "http://openinsider.com/insider-sales",
        ):
            html = _get(url)
            if html:
                df = _parse_rows(html)
                if not df.empty:
                    chunks.append(df)
            time.sleep(DELAY)
        if not chunks:
            log_failure(FAILED_PATH, "openinsider", "preset pages also failed", attempted="preset")
            return
    else:
        chunks = []
        for d1, d2 in _quarter_starts(START_DATE, END_DATE):
            sys.stdout.write(f"  {d1}..{d2} "); sys.stdout.flush()
            df = _fetch_range(d1, d2)
            if df.empty:
                print("rows=0")
                continue
            nb = int((df["kind"] == "buy").sum())
            ns = int((df["kind"] == "sell").sum())
            print(f"buys={nb} sells={ns}")
            chunks.append(df)
        if not chunks:
            log_failure(FAILED_PATH, "openinsider", "no data fetched", attempted="screener")
            return

    all_df = pd.concat(chunks, ignore_index=True)
    buy_df = all_df[all_df["kind"] == "buy"][["trade_date", "value"]]
    sell_df = all_df[all_df["kind"] == "sell"][["trade_date", "value"]]

    # Daily aggregations
    def agg(df: pd.DataFrame, prefix: str) -> pd.DataFrame:
        if df.empty:
            return pd.DataFrame()
        g = df.groupby(df["trade_date"].dt.normalize())
        return pd.DataFrame({
            f"{prefix}_count": g.size(),
            f"{prefix}_value": g["value"].sum(),
        })

    bd = agg(buy_df, "insider_buy")
    sd = agg(sell_df, "insider_sell")
    daily = pd.concat([bd, sd], axis=1).sort_index().fillna(0.0)

    total_val = daily["insider_buy_value"] + daily["insider_sell_value"]
    total_cnt = daily["insider_buy_count"] + daily["insider_sell_count"]
    daily["net_value"] = daily["insider_buy_value"] - daily["insider_sell_value"]
    daily["buy_sell_value_ratio"] = daily["insider_buy_value"] / total_val.replace(0, pd.NA)
    daily["buy_sell_count_ratio"] = daily["insider_buy_count"] / total_cnt.replace(0, pd.NA)
    daily["sentiment_21d"] = (
        daily["net_value"].rolling(21, min_periods=5).sum()
        / total_val.rolling(21, min_periods=5).sum().replace(0, pd.NA)
    )

    aligned = align_to_trading_days(daily, source_freq="daily")
    path = CLEAN_DIR / "insider_transactions.parquet"
    save_clean(aligned, path, metadata={"source": "openinsider"})
    validate_data(aligned, name="insider_transactions")
    log_to_catalog(CATALOG_PATH, {
        "source": "openinsider",
        "series_name": "insider_transactions",
        "frequency": "daily",
        "date_range": f"{aligned.index.min().date()}..{aligned.index.max().date()}",
        "file_path": str(path.relative_to(DATA_DIR.parent)).replace("\\", "/"),
        "status": "OK",
        "notes": "buy/sell counts, dollar value, 21d sentiment from openinsider screener",
    })


if __name__ == "__main__":
    main()
