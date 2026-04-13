"""Smoke + spec tests: inverse-vol weighting and final weight aggregation."""
from __future__ import annotations

import numpy as np

from strategy.position_sizing import inverse_vol_weights, final_weights


def test_inverse_vol_weights_basic() -> None:
    """Lower vol name gets a larger share."""
    atr = np.array([0.1, 0.2, 0.4])
    w = inverse_vol_weights(atr)
    assert abs(w.sum() - 1.0) < 1e-9
    assert w[0] > w[1] > w[2]


def test_inverse_vol_all_nan_fallback_equal() -> None:
    """All-NaN falls back to equal weights (research branch)."""
    atr = np.array([np.nan, np.nan, np.nan])
    w = inverse_vol_weights(atr)
    assert np.allclose(w, [1 / 3, 1 / 3, 1 / 3])


def test_final_weights_sma_override_worked_example() -> None:
    """§10.6: SMA gate fires -> SHY 50% + top-3 basket 50% (not rolled in)."""
    universe = ["GLD", "IGV", "QQQ", "SHY"]
    atr = np.array([0.11, 0.22, 0.19, 0.005])  # realistic-ish
    top1 = 0  # GLD (overridden)
    tk = np.array([0, 1, 2])  # GLD IGV QQQ
    w = final_weights(
        universe, top1, tk, atr, top1_weight=0.5, topk_weight=0.5,
        cash_override="SHY", cash_proxy="SHY",
    )
    assert abs(sum(w.values()) - 1.0) < 1e-9
    assert w["SHY"] >= 0.5
    # top-3 leg allocates inv-vol over {GLD, IGV, QQQ}, GLD lowest vol -> largest share
    top3_total = w["GLD"] + w["IGV"] + w["QQQ"]
    assert abs(top3_total - 0.5) < 1e-9
    assert w["GLD"] > w["QQQ"] > w["IGV"]
