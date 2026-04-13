"""Rebalance scheduling + FOMC deferral (§2.7, §2.9).

- Default rebalance = last test date of each calendar month (matches the
  canonical research cadence used by run_m26_deep.month_last_positions()).
- FOMC post-3d deferral: if the scheduled date falls within [FOMC, FOMC+N]
  trading days, defer by `defer_days` trading days. Asymmetric post-only
  window, per M26_post_3d (§7.7).
- §2.9 deferred-collision rule: the deferred date IS the rebalance date
  for that month, even if it spills into the next calendar month. The
  next month's schedule is unaffected.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def month_end_positions(dates: pd.DatetimeIndex) -> pd.Series:
    """Last trading day of each calendar month within `dates`.

    Returns a Series index=month-end-date, values=integer position into `dates`.
    """
    positions = pd.Series(np.arange(len(dates)), index=dates)
    last = positions.groupby(dates.to_period("M")).tail(1)
    return last


def fomc_window_mask(
    n_days: int, fomc_day_idx: np.ndarray, pre_days: int = 0, post_days: int = 2
) -> np.ndarray:
    """Boolean mask over trading-day positions within [-pre, +post] of any FOMC day."""
    mask = np.zeros(n_days, dtype=bool)
    for i in fomc_day_idx:
        lo = max(0, int(i) - int(pre_days))
        hi = min(n_days - 1, int(i) + int(post_days))
        mask[lo : hi + 1] = True
    return mask


def resolve_rebalance_index(
    scheduled_pos: int, defer_days: int, event_mask: np.ndarray, n_days: int
) -> tuple[int, bool]:
    """Return (executed_pos, deferred?) after applying the FOMC rule.

    Matches run_m26_deep.run_variant():186-190 — when the scheduled day is
    in the event mask, slide forward by `defer_days` trading days capped at
    the last available index.
    """
    if defer_days > 0 and event_mask is not None and event_mask[scheduled_pos]:
        return min(scheduled_pos + int(defer_days), n_days - 1), True
    return scheduled_pos, False
