"""Spec tests: rebalance scheduling and FOMC post-3d deferral."""
from __future__ import annotations

import numpy as np
import pandas as pd

from strategy.rebalance import month_end_positions, fomc_window_mask, resolve_rebalance_index


def test_month_end_positions_count() -> None:
    """One entry per calendar month."""
    dates = pd.bdate_range("2020-01-01", "2020-04-30")
    me = month_end_positions(dates)
    assert len(me) == 4


def test_fomc_post_window_shape() -> None:
    """Post-only window with post_days=2 covers exactly 3 positions per FOMC day."""
    n = 20
    idx = np.array([10])
    mask = fomc_window_mask(n, idx, pre_days=0, post_days=2)
    assert mask[10] and mask[11] and mask[12]
    assert not mask[9]
    assert not mask[13]


def test_resolve_defer_fires() -> None:
    """When the scheduled position is in the mask we slide by defer_days."""
    mask = np.zeros(10, dtype=bool)
    mask[5] = True
    pos, deferred = resolve_rebalance_index(5, defer_days=3, event_mask=mask, n_days=10)
    assert deferred and pos == 8


def test_resolve_defer_no_fire() -> None:
    """Out-of-window schedules pass through unchanged."""
    mask = np.zeros(10, dtype=bool)
    pos, deferred = resolve_rebalance_index(5, defer_days=3, event_mask=mask, n_days=10)
    assert not deferred and pos == 5


def test_resolve_defer_spillover_cap() -> None:
    """Deferral past the last index clamps to n_days-1 (§2.9 spillover rule)."""
    mask = np.zeros(10, dtype=bool)
    mask[9] = True
    pos, deferred = resolve_rebalance_index(9, defer_days=3, event_mask=mask, n_days=10)
    assert deferred and pos == 9  # capped
