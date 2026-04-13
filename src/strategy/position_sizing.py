"""Position sizing — 50/50 top-1 + inverse-vol top-3 (§2.4, M11).

The canonical research path uses ATR-21d as the inverse-vol proxy; the spec
in §2.4 describes realized 63d-std but the code that produced 23.61%/1.50/-12.94
uses atr_21d (see run_m26_deep.py:125 and the comment there). We match the
code here; a separate `realized_vol_63d` path is available for spec-compliant
variants but is not the default.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def topk_indices(mom_row: np.ndarray, k: int) -> np.ndarray:
    """Return indices of the top-k momentum names, NaN-safe."""
    safe = np.where(np.isnan(mom_row), -np.inf, mom_row)
    return np.argsort(-safe)[:k]


def build_atr_array(
    atr21: pd.DataFrame, universe: list[str], dates: pd.DatetimeIndex
) -> np.ndarray:
    """Align the ATR21 table to (NDAYS, n_universe)."""
    arr = np.full((len(dates), len(universe)), np.nan, dtype=float)
    aligned = atr21.reindex(dates)
    for j, t in enumerate(universe):
        if t in aligned.columns:
            arr[:, j] = aligned[t].values
    return arr


def inverse_vol_weights(atr_slice: np.ndarray) -> np.ndarray:
    """Return inv-vol weights summing to 1. Fallback to equal weights if all NaN.

    atr_slice: 1-D array (length k) of vol proxy values. Zero/negative values
    are treated as NaN. If every value is NaN/0 the weights degrade to 1/k
    (equal weighting) — this mirrors the research fallback branch.
    """
    inv = 1.0 / np.where(atr_slice > 0, atr_slice, np.nan)
    if np.isnan(inv).all():
        k = len(atr_slice)
        return np.full(k, 1.0 / k)
    # treat NaN as 0 weight, renormalize
    inv = np.where(np.isnan(inv), 0.0, inv)
    total = inv.sum()
    if total <= 0:
        k = len(atr_slice)
        return np.full(k, 1.0 / k)
    return inv / total


def top_leg_returns(
    fwd_arr: np.ndarray,
    mom_row: np.ndarray,
    atr_row: np.ndarray,
    k: int,
    weighting: str = "inverse_vol",
) -> tuple[int, np.ndarray, float, float]:
    """Compute (top1_idx, topk_idx, top1_fwd_ret, topk_fwd_ret) on one date.

    fwd_arr: (n_universe,) forward-21d returns row.
    mom_row: (n_universe,) momentum row.
    atr_row: (n_universe,) ATR row.
    """
    safe = np.where(np.isnan(mom_row), -np.inf, mom_row)
    top1 = int(np.argmax(safe))
    tk = np.argsort(-safe)[:k]
    r1 = float(fwd_arr[top1])
    sel_fwd = fwd_arr[tk]
    if weighting == "inverse_vol":
        w = inverse_vol_weights(atr_row[tk])
        rk = float(np.nansum(sel_fwd * w))
    elif weighting == "equal":
        rk = float(np.nanmean(sel_fwd))
    else:
        raise ValueError(f"unknown weighting {weighting!r}")
    return top1, tk, r1, rk


def final_weights(
    universe: list[str],
    top1_idx: int,
    topk_idx: np.ndarray,
    atr_row: np.ndarray,
    top1_weight: float,
    topk_weight: float,
    cash_override: str | None = None,
    cash_proxy: str = "SHY",
) -> dict[str, float]:
    """Aggregate leg weights into final per-ticker target weights.

    If cash_override is set (SMA gate fired) the top-1 leg is parked in
    the cash proxy; the top-k leg still computes normally on the real ranks.
    Per §2.6 worked example: SHY 50% + top-k normal split (top-1 slot is
    NOT folded back into the override — see §10.6).
    """
    weights: dict[str, float] = {t: 0.0 for t in universe}
    # top-1 leg
    if cash_override:
        if cash_override not in weights:
            weights[cash_override] = 0.0
        weights[cash_override] += top1_weight
    else:
        weights[universe[top1_idx]] += top1_weight
    # top-k leg with inverse-vol weighting
    w = inverse_vol_weights(atr_row[topk_idx])
    for j, pos in enumerate(topk_idx):
        weights[universe[int(pos)]] += float(topk_weight * w[j])
    return weights
