"""Momentum computation (§2.2).

N-day total return from adjusted close prices. In the canonical path we
read pre-computed return tables (data/features/price/returns_{N}d.parquet)
via src/data/pipeline.py. This module exposes an array-builder aligned to
the universe and date index — matches run_m26_deep.py:107-117.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def build_momentum_array(
    returns_df: pd.DataFrame,
    universe: list[str],
    dates: pd.DatetimeIndex,
) -> np.ndarray:
    """Return (NDAYS, n_universe) momentum array at a given lookback.

    returns_df is one of pipeline.PanelBundle.returns[N] — a wide DataFrame
    indexed by date with one column per ticker.
    """
    arr = np.full((len(dates), len(universe)), np.nan, dtype=float)
    for j, t in enumerate(universe):
        if t in returns_df.columns:
            arr[:, j] = returns_df[t].reindex(dates).values
    return arr


def rank_by_momentum(mom_row: np.ndarray) -> np.ndarray:
    """Descending argsort with NaN treated as -inf (matches research)."""
    safe = np.where(np.isnan(mom_row), -np.inf, mom_row)
    return np.argsort(-safe)
