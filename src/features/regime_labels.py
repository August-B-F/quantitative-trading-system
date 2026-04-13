"""Growth-inflation regime labels (§2.5).

Quadrant from ISM PMI proxy (>50) x CPI YoY (>=3%). Used both as the
*current regime* input at rebalance time and as the training target at
t+21td for the walk-forward classifier. The panel already carries the
one-hot features `regime_growth_inflation__regime_*`; this module
exposes helpers to read them out.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

REGIME_CLASSES: list[str] = [
    "regime_hg_li",
    "regime_hg_hi",
    "regime_lg_li",
    "regime_lg_hi_stagflation",
]
REGIME_FEATS: list[str] = [f"regime_growth_inflation__{c}" for c in REGIME_CLASSES]


@dataclass
class RegimeState:
    """Current regime vector + int index per date."""
    index: np.ndarray            # (NDAYS,) int in [0..3], argmax of one-hot
    onehot: np.ndarray           # (NDAYS, 4)


def current_regime(df: pd.DataFrame) -> RegimeState:
    """Return the current-regime index/one-hot from the master panel."""
    missing = [c for c in REGIME_FEATS if c not in df.columns]
    if missing:
        raise KeyError(f"missing regime one-hot columns: {missing}")
    onehot = df[REGIME_FEATS].values
    idx = onehot.argmax(axis=1)
    return RegimeState(index=idx, onehot=onehot)
