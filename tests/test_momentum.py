"""Smoke test: momentum array builder + ranker."""
from __future__ import annotations

import numpy as np
import pandas as pd

from strategy.momentum import build_momentum_array, rank_by_momentum


def test_rank_by_momentum_nan_handling() -> None:
    """NaN is treated as -inf and sinks to the bottom."""
    row = np.array([0.1, np.nan, 0.3, 0.2])
    order = rank_by_momentum(row)
    assert order[0] == 2  # 0.3 wins
    assert order[-1] == 1  # NaN last


def test_build_momentum_array_alignment() -> None:
    """Array builder aligns columns to the requested universe order."""
    dates = pd.date_range("2020-01-01", periods=5, freq="D")
    rdf = pd.DataFrame(
        {"A": [0.1, 0.2, 0.3, 0.4, 0.5], "B": [1, 2, 3, 4, 5], "Z": [9, 9, 9, 9, 9]},
        index=dates,
    )
    arr = build_momentum_array(rdf, ["B", "A", "MISSING"], dates)
    assert arr.shape == (5, 3)
    assert arr[0, 0] == 1  # B
    assert arr[0, 1] == 0.1  # A
    assert np.isnan(arr[0, 2])  # MISSING
