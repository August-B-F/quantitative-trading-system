"""SMA200 trend gate (§2.6).

Top-1 leg parks in cash (SHY) if SPY distance from its 200d SMA is below
the -4% buffer. Top-3 leg is unaffected. Matches run_m26_deep.py:159.
"""
from __future__ import annotations

import numpy as np


def gate_fired(spy_distance: float, buffer: float = -0.04) -> bool:
    """Return True if the gate should override the top-1 leg to cash."""
    return not (spy_distance > buffer)


def apply_gate_to_top1_return(
    top1_fwd_ret: float, cash_fwd_ret: float, spy_distance: float, buffer: float = -0.04
) -> float:
    """Swap the top-1 leg's forward return with the cash return on fire."""
    return top1_fwd_ret if spy_distance > buffer else cash_fwd_ret


def vectorized_gate(
    top1_fwd: np.ndarray, cash_fwd: np.ndarray, spy_dist: np.ndarray, buffer: float = -0.04
) -> np.ndarray:
    """Vectorized form: per-day top-1 return after SMA override."""
    return np.where(spy_dist > buffer, top1_fwd, cash_fwd)
