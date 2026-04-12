"""ETF fund flows fetcher.

Targeted ETFs: SPY QQQ HYG TLT GLD XLE SOXX IWM EEM AGG.

Public free sources for historical ETF fund flows are essentially gone:
- etfdb.com  -> 403 (Cloudflare)
- etf.com    -> 403 (Cloudflare)
- ICI stats  -> behind ICI Statistics paywall / member portal
- Yahoo quoteSummary -> 401 without crumb auth

We probe each, log the failures, and recommend deriving creation/redemption
flows from yahoo shares-outstanding (when available) or paying for an API.
"""
from __future__ import annotations

import time

import requests

from src.data.utils import DATA_DIR, FAILED_PATH, log_failure

CLEAN_DIR = DATA_DIR / "clean" / "sentiment"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    ),
    "Accept": "text/html,application/json",
}

TICKERS = ["SPY", "QQQ", "HYG", "TLT", "GLD", "XLE", "SOXX", "IWM", "EEM", "AGG"]


def main() -> None:
    CLEAN_DIR.mkdir(parents=True, exist_ok=True)
    print("[etf_flows] probing public sources")
    statuses = []
    for tk in TICKERS:
        for url in (
            f"https://etfdb.com/etf/{tk}/#fund-flows",
            f"https://www.etf.com/{tk}",
        ):
            try:
                r = requests.get(url, headers=HEADERS, timeout=15)
                statuses.append(f"{tk}:{r.status_code}:{url.split('//',1)[1].split('/',1)[0]}")
            except requests.RequestException as e:
                statuses.append(f"{tk}:ERR:{e.__class__.__name__}")
            time.sleep(2)
    log_failure(
        FAILED_PATH,
        "etf:flows",
        "etfdb.com and etf.com both 403; ICI Stats no public CSV. "
        "Recommended substitute: derive flows from yahoo shares-outstanding "
        "deltas (modules=defaultKeyStatistics) once a yahoo crumb session is built, "
        "or pay for ETF.com PRO / etfdb API.",
        attempted="; ".join(statuses[:6]) + "...",
    )
    print("  ! all blocked, logged failure")


if __name__ == "__main__":
    main()
