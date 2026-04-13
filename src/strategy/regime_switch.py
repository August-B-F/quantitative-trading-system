"""Regime-conditional lookback switch (§2.5).

Returns the per-day selected-momentum matrix: use `m_trans` where the
classifier disagrees with the current regime, else `m_stable`. Ports the
one-liner from run_m26_deep.py:116-117.
"""
from __future__ import annotations

import numpy as np


def select_momentum(
    m_stable: np.ndarray,
    m_trans: np.ndarray,
    pred_reg: np.ndarray,
    current_reg: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Return (chosen_mom, use_trans_mask).

    use_trans is True only where the classifier both produced a prediction
    (pred_reg != -1) AND disagrees with the current regime. Anywhere else
    (no prediction, or stable regime) falls back to m_stable.
    """
    use_trans = (pred_reg != -1) & (pred_reg != current_reg)
    chosen = np.where(use_trans[:, None], m_trans, m_stable)
    return chosen, use_trans
