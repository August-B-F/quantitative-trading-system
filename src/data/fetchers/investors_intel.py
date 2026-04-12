"""Investors Intelligence Bull/Bear Ratio.

Investors Intelligence is a paid service (chartcraft.com / Stockcharts
subscription). No reliable free historical feed. We log as unavailable
and move on — AAII is a close substitute for our purposes.
"""
from __future__ import annotations

from src.data.utils import FAILED_PATH, log_failure


def main() -> None:
    print("[investors_intel] no free source — logging failure, AAII is substitute")
    log_failure(
        FAILED_PATH,
        "investors_intelligence",
        reason="paid service; no free historical feed discovered",
        attempted="investorsintelligence.com / yardeni.com",
    )


if __name__ == "__main__":
    main()
