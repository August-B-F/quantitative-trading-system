"""FINRA margin debt fetcher.

The finra.org margin-statistics page sits behind Akamai bot protection
(returns 403 to scripted requests regardless of headers). The downloadable
xlsx is similarly blocked. We try, and on failure log the source as blocked
and recommend the FRED BOGZ1FL663067003Q quarterly series as a substitute.
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
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

CANDIDATES = [
    "https://www.finra.org/investors/learn-to-invest/advanced-investing/margin-statistics",
    "https://www.finra.org/finra-data/browse-catalog/margin-statistics/data",
    "https://www.finra.org/sites/default/files/2024-02/margin-statistics.xlsx",
]


def main() -> None:
    CLEAN_DIR.mkdir(parents=True, exist_ok=True)
    print("[margin] FINRA margin debt")
    statuses = []
    for url in CANDIDATES:
        try:
            r = requests.get(url, headers=HEADERS, timeout=20)
            statuses.append(f"{r.status_code}:{url[-40:]}")
            if r.status_code == 200 and "margin" in r.text.lower():
                print(f"  unexpectedly accessible: {url} (manual parse needed)")
                # Page actually parses to a styled HTML table that requires
                # row-by-row extraction. Recorded as partial; not implemented.
                log_failure(
                    FAILED_PATH,
                    "finra:margin_debt",
                    "page accessible but table is JS-rendered or styled; needs manual parse",
                    attempted=url,
                )
                return
            time.sleep(2)
        except requests.RequestException as e:
            statuses.append(f"ERR:{e}")
    log_failure(
        FAILED_PATH,
        "finra:margin_debt",
        "Akamai bot block (HTTP 403) on all FINRA margin URLs; no public CSV. "
        "Substitute: FRED BOGZ1FL663067003Q (Margin Accounts at Brokers, quarterly).",
        attempted="; ".join(statuses),
    )
    print("  ! all blocked, logged failure")


if __name__ == "__main__":
    main()
