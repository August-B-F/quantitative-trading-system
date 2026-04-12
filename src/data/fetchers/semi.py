"""SEMI book-to-bill fetcher (low priority).

semi.org is wholly behind Akamai bot protection (403 to all requests, all
endpoints). The book-to-bill report itself was discontinued for public release
in 2017 and is now SEMI-member only. Logged and skipped.
"""
from __future__ import annotations

import time

import requests

from src.data.utils import DATA_DIR, FAILED_PATH, log_failure

CLEAN_DIR = DATA_DIR / "clean" / "fundamental"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en-US,en;q=0.9",
}

CANDIDATES = [
    "https://www.semi.org/en/products-services/market-data/billing-reports",
    "https://www.semi.org/en/news/press-releases",
    "https://www.semi.org/en",
]


def main() -> None:
    CLEAN_DIR.mkdir(parents=True, exist_ok=True)
    print("[semi] book-to-bill")
    statuses = []
    for url in CANDIDATES:
        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
            statuses.append(f"{r.status_code}")
        except requests.RequestException as e:
            statuses.append(f"ERR:{e.__class__.__name__}")
        time.sleep(2)
    log_failure(
        FAILED_PATH,
        "semi:book_to_bill",
        "semi.org Akamai-blocked (403 all endpoints); SEMI book-to-bill "
        "discontinued for public release in 2017, member-only since. No fallback.",
        attempted="; ".join(statuses),
    )
    print("  ! all blocked, logged failure")


if __name__ == "__main__":
    main()
