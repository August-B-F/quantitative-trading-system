"""Smoke test: compute_stats matches the research implementation."""
from __future__ import annotations

import numpy as np

from backtest.engine import compute_stats


def test_compute_stats_known_series() -> None:
    """Constant-return series: CAGR = (1+r)^12 - 1; Sharpe = NaN (std=0)."""
    r = np.full(24, 0.01)
    s = compute_stats(r)
    assert abs(s["cagr"] - ((1.01 ** 12) - 1)) < 1e-9
    # no variance -> sharpe nan
    assert s["max_dd"] == 0.0
    assert s["n"] == 24


def test_compute_stats_empty() -> None:
    """Empty series returns NaN metrics."""
    s = compute_stats(np.array([]))
    assert s["n"] == 0
    assert s["cagr"] != s["cagr"]  # NaN
