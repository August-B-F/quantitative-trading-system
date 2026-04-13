"""Spec test: SMA gate boundary at -4%."""
from __future__ import annotations

from strategy.sma_gate import gate_fired, apply_gate_to_top1_return


def test_gate_boundary_exact() -> None:
    """Distance exactly -0.04 must fire (gate is `not (d > -0.04)`)."""
    assert gate_fired(-0.04) is True
    assert gate_fired(-0.041) is True
    assert gate_fired(-0.039) is False


def test_apply_gate_swap_to_cash() -> None:
    """Swaps top-1 return with cash return on fire; pass-through otherwise."""
    assert apply_gate_to_top1_return(0.05, 0.002, spy_distance=-0.05) == 0.002
    assert apply_gate_to_top1_return(0.05, 0.002, spy_distance=0.01) == 0.05
