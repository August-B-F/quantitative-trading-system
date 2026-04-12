"""AAR rail traffic fetcher.

Association of American Railroads weekly traffic data is published as PDF press
releases on aar.org. There is no public structured download. We do not scrape
HTML/PDF here; this fetcher logs the source as inaccessible.
"""
from __future__ import annotations

from src.data.utils import FAILED_PATH, log_failure


def main() -> None:
    print("[aar] rail traffic — no public structured feed")
    log_failure(
        FAILED_PATH,
        "aar:rail_traffic",
        "AAR weekly rail traffic published only as PDF press releases on aar.org; no structured download or public API. HTML scraping not in scope.",
        attempted="https://www.aar.org/data-center/",
    )


if __name__ == "__main__":
    main()
