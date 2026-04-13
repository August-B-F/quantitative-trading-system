"""Smoke test: regime-conditional momentum selector."""
from __future__ import annotations

import numpy as np

from strategy.regime_switch import select_momentum


def test_select_momentum_stable_and_transition() -> None:
    """use_trans fires only when pred != -1 AND pred != current."""
    m_stable = np.array([[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]])
    m_trans = np.array([[9.0, 8.0], [7.0, 6.0], [5.0, 4.0]])
    current = np.array([0, 1, 0])
    pred = np.array([-1, 1, 1])  # no-pred, stable, transition
    chosen, use_trans = select_momentum(m_stable, m_trans, pred, current)
    assert use_trans.tolist() == [False, False, True]
    # day 0 -> stable, day 1 -> stable, day 2 -> trans
    assert chosen[0].tolist() == [1.0, 2.0]
    assert chosen[1].tolist() == [3.0, 4.0]
    assert chosen[2].tolist() == [5.0, 4.0]
