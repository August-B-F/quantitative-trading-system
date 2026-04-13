"""Portfolio orchestrator — §2.8 step-by-step in code.

Runs the full month-end decision for one rebalance date: deferral check ->
SMA gate -> regime lookback -> rank -> size -> target weights. Also exposes
the array-oriented engine used by the backtest.

This is a faithful port of scripts/model/run_m26_deep.py's pick_at/ret_at/
run_variant functions (lines 150-200). The numeric behavior must match
byte-for-byte modulo reordering.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd

from data.pipeline import PanelBundle
from strategy.momentum import build_momentum_array
from strategy.regime_switch import select_momentum
from strategy.position_sizing import build_atr_array, final_weights, inverse_vol_weights
from strategy.sma_gate import gate_fired

log = logging.getLogger(__name__)


@dataclass
class DecisionRecord:
    """One-rebalance decision log row — §2.8 step 10."""
    date: pd.Timestamp
    scheduled_date: pd.Timestamp
    deferred: bool
    lookback_used: int
    current_regime: int
    predicted_regime: int
    sma_distance: float
    sma_gate_fired: bool
    top1: str
    topk: list[str]
    target_weights: dict[str, float]
    fwd_ret: float                # realized fwd21 return (backtest)


class PortfolioEngine:
    """Stateful engine that precomputes arrays once and decides per rebalance date."""

    def __init__(self, bundle: PanelBundle, pred_reg: np.ndarray, cfg: dict):
        """Build per-universe momentum / ATR / forward-return arrays."""
        self.cfg = cfg
        self.bundle = bundle
        self.universe: list[str] = list(cfg["universe"])
        self.n_uni = len(self.universe)
        self.dates = bundle.dates
        self.n_days = len(self.dates)
        self.cash = cfg["cash_proxy"]
        self.top1_w = float(cfg["top1_weight"])
        self.topk_w = float(cfg["top3_weight"])
        self.k = int(cfg["top_k"])
        self.sma_buffer = float(cfg["sma_gate_buffer"])

        # momentum arrays at the two lookbacks
        lb_s = cfg["lookback_stable"]
        lb_t = cfg["lookback_transition"]
        self.m_stable = build_momentum_array(bundle.returns[lb_s], self.universe, self.dates)
        self.m_trans = build_momentum_array(bundle.returns[lb_t], self.universe, self.dates)

        # regime-selected momentum matrix (vectorized across the full index)
        from features.regime_labels import current_regime as _cr
        self.current_reg = _cr(bundle.df).index
        self.pred_reg = pred_reg
        self.mom, self.use_trans = select_momentum(
            self.m_stable, self.m_trans, self.pred_reg, self.current_reg
        )
        # safe momentum for argsort (NaN -> -inf)
        self.sf = np.where(np.isnan(self.mom), -np.inf, self.mom)

        # forward-21d returns aligned to universe
        self.fwd_arr = np.full((self.n_days, self.n_uni), np.nan)
        for j, t in enumerate(self.universe):
            self.fwd_arr[:, j] = bundle.fwd21[t]
        self.cash_fwd = bundle.fwd21[self.cash]

        # ATR array (for inv-vol weighting)
        self.atr_arr = build_atr_array(bundle.atr21, self.universe, self.dates)

        # SPY distance from SMA200
        self.spy_dist = bundle.spy_dist_sma200

    def pick_at(self, i: int) -> tuple[int, np.ndarray]:
        """Return (top1_idx, topk_indices) at daily position i."""
        row = self.sf[i]
        top1 = int(np.argmax(row))
        tk = np.argsort(-row)[: self.k]
        return top1, tk

    def fwd_return_at(self, i: int, top1: int, tk: np.ndarray) -> float:
        """Compute the blended 50/50 forward-21d return after SMA gate.

        Matches run_m26_deep.ret_at:158-168 exactly — SMA override on top-1
        only, inverse-vol top-k with NaN fallback to equal-weight mean.
        """
        r1 = self.fwd_arr[i, top1] if self.spy_dist[i] > self.sma_buffer else self.cash_fwd[i]
        sel_atr = self.atr_arr[i, tk]
        inv = 1.0 / np.where(sel_atr > 0, sel_atr, np.nan)
        if np.isnan(inv).all():
            rk = np.nanmean(self.fwd_arr[i, tk])
        else:
            w = inv / np.nansum(inv)
            rk = np.nansum(self.fwd_arr[i, tk] * w)
        return float(self.top1_w * r1 + self.topk_w * rk)

    def decide(self, scheduled_pos: int, executed_pos: int, deferred: bool) -> DecisionRecord:
        """Full §2.8 decision for a single rebalance date."""
        i = executed_pos
        top1, tk = self.pick_at(i)
        gate = gate_fired(self.spy_dist[i], self.sma_buffer)
        cash_override = self.cash if gate else None
        weights = final_weights(
            self.universe,
            top1,
            tk,
            self.atr_arr[i],
            self.top1_w,
            self.topk_w,
            cash_override=cash_override,
            cash_proxy=self.cash,
        )
        lookback = (
            self.cfg["lookback_transition"]
            if self.use_trans[i]
            else self.cfg["lookback_stable"]
        )
        fwd = self.fwd_return_at(i, top1, tk)
        return DecisionRecord(
            date=self.dates[i],
            scheduled_date=self.dates[scheduled_pos],
            deferred=deferred,
            lookback_used=int(lookback),
            current_regime=int(self.current_reg[i]),
            predicted_regime=int(self.pred_reg[i]),
            sma_distance=float(self.spy_dist[i]),
            sma_gate_fired=bool(gate),
            top1=self.universe[top1],
            topk=[self.universe[int(j)] for j in tk],
            target_weights=weights,
            fwd_ret=fwd,
        )
