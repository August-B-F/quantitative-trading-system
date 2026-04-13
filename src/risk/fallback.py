"""Fallback hierarchy — §3.4.

1. classifier unavailable -> 63d-always
2. one ETF price feed missing -> exclude from ranking
3. FRED macro stale -> forward-fill, >60d -> fallback to (1)
4. all data unavailable -> SHY 100%
5. FOMC calendar missing -> no deferral
"""
from __future__ import annotations

import logging

import numpy as np

log = logging.getLogger(__name__)


def classifier_fallback_pred(n_days: int) -> np.ndarray:
    """Return an all-(-1) prediction vector — use 63d stable always."""
    log.warning("classifier fallback: 63d-always")
    return np.full(n_days, -1, dtype=int)


def exclude_missing_etf(universe: list[str], missing: list[str]) -> list[str]:
    """Return the ranking-universe with missing tickers dropped (§2.9)."""
    return [t for t in universe if t not in set(missing)]


def full_cash_fallback(cash: str = "SHY") -> dict[str, float]:
    """100% cash proxy — the 'all data unavailable' safe mode."""
    log.error("full cash fallback: 100%% %s", cash)
    return {cash: 1.0}
