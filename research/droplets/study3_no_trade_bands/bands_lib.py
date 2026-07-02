"""STUDY 3 no-trade-band library — schedule post-processing for the ledger engine.

All functions are pure schedule transforms: they take month-end (decision_date,
target_weights) pairs and emit a banded weight_schedule in the exact format
run_ledger_backtest consumes. Drift between decisions is approximated with
adj_close-to-adj_close ratios from the previous decision date (one-overnight
approximation of the engine's open-fill drift; documented in HYPOTHESIS.md).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

TDY = 252


# ---------------------------------------------------------------- price utils
def adj_close_frame(prices: dict, tickers) -> pd.DataFrame:
    """Union-calendar adj_close frame, ffilled (matches ledger ffill semantics)."""
    cols = {t: prices[t]["adj_close"].astype(float) for t in tickers if t in prices}
    return pd.DataFrame(cols).sort_index().ffill()


def drift_weights(w: dict, d_from: pd.Timestamp, d_to: pd.Timestamp,
                  px: pd.DataFrame) -> dict:
    """Drift weights (summing to 1) from close of d_from to close of d_to."""
    raw = {}
    for t, x in w.items():
        if x <= 0:
            continue
        f = 1.0
        if t in px.columns:
            a = px[t].asof(d_from)
            b = px[t].asof(d_to)
            if np.isfinite(a) and np.isfinite(b) and a > 0:
                f = b / a
        raw[t] = x * f
    tot = sum(raw.values())
    if tot <= 0:
        return dict(w)
    return {t: v / tot for t, v in raw.items()}


# ------------------------------------------------------------- rule A targets
def month_ends(prices: dict, tickers, start, end) -> list[pd.Timestamp]:
    cal = None
    for t in tickers:
        idx = prices[t].index
        cal = idx if cal is None else cal.union(idx)
    cal = cal[(cal >= pd.Timestamp(start)) & (cal <= pd.Timestamp(end))]
    return [pd.Timestamp(d) for d in cal.to_series().groupby(cal.to_period("M")).last()]


def _mom_and_vol(prices: dict, universe, as_of, mom_lb=63, vol_lb=63):
    """(momentum dict, inv-vol dict) over eligible assets, data <= as_of."""
    mom, ivol = {}, {}
    for t in universe:
        s = prices[t]["adj_close"].loc[:as_of].dropna()
        if len(s) < mom_lb + 1:
            continue
        mom[t] = float(s.iloc[-1] / s.iloc[-1 - mom_lb] - 1.0)
        daily = s.iloc[-(vol_lb + 1):].pct_change().dropna()
        v = float(daily.std(ddof=1) * np.sqrt(TDY))
        if np.isfinite(v) and v > 0:
            ivol[t] = 1.0 / v
    return mom, ivol


def rotation_choose(prices: dict, universe, as_of, held: set,
                    k: int = 3, m: int = 0) -> tuple[dict, set]:
    """Top-k 63d-momentum inverse-vol weights with rank hysteresis m.

    held = currently held membership (empty on first call). m=0 → plain top-k.
    Returns (weights, new_held_set). Assets lacking history/vol are ineligible.
    """
    mom, ivol = _mom_and_vol(prices, universe, as_of)
    elig = [t for t in universe if t in mom and t in ivol]
    if len(elig) == 0:
        return {}, set()
    ranked = sorted(elig, key=lambda t: mom[t], reverse=True)
    rank = {t: i + 1 for i, t in enumerate(ranked)}
    kk = min(k, len(ranked))
    if m > 0 and held:
        keep = [t for t in ranked if t in held and rank[t] <= kk + m][:kk]
        chosen = list(keep)
        for t in ranked:
            if len(chosen) >= kk:
                break
            if t not in chosen:
                chosen.append(t)
    else:
        chosen = ranked[:kk]
    tot = sum(ivol[t] for t in chosen)
    w = {t: ivol[t] / tot for t in chosen}
    return w, set(chosen)


# --------------------------------------------------------------- band engines
def apply_position_band(targets: list, px: pd.DataFrame, band: float,
                        cash: str = "SHV") -> list:
    """Per-position drift band: trade only legs with |target - drifted| > band.

    targets: [(date, weights)] full-rebalance targets. Emits a mixed schedule;
    a month with no breaching leg is skipped entirely (no schedule entry).
    First month always trades fully (from cash).
    """
    out = []
    last_w, last_d = None, None
    for d, tgt in targets:
        if last_w is None:
            out.append((d, dict(tgt)))
            last_w, last_d = dict(tgt), d
            continue
        cur = drift_weights(last_w, last_d, d, px)
        legs = set(tgt) | set(cur)
        breach = [t for t in legs if abs(tgt.get(t, 0.0) - cur.get(t, 0.0)) > band]
        # drift state forward regardless of trading
        if not breach:
            last_w, last_d = cur, d
            continue
        mixed = {}
        for t in legs:
            x = tgt.get(t, 0.0) if t in breach else cur.get(t, 0.0)
            if x > 1e-9:
                mixed[t] = x
        tot = sum(mixed.values())
        if tot > 1.0:
            mixed = {t: x / tot for t, x in mixed.items()}
        out.append((d, mixed))
        last_w, last_d = dict(mixed), d
        # residual (1 - tot) sits in cash inside the engine; track it for drift
        if tot < 1.0 - 1e-9:
            last_w[cash] = last_w.get(cash, 0.0) + (1.0 - min(tot, 1.0))
    return out


def apply_portfolio_skip(targets: list, px: pd.DataFrame, min_half_turnover: float) -> list:
    """Skip a month entirely unless 0.5*sum|target-drifted| > threshold."""
    out = []
    last_w, last_d = None, None
    for d, tgt in targets:
        if last_w is None:
            out.append((d, dict(tgt)))
            last_w, last_d = dict(tgt), d
            continue
        cur = drift_weights(last_w, last_d, d, px)
        legs = set(tgt) | set(cur)
        ht = 0.5 * sum(abs(tgt.get(t, 0.0) - cur.get(t, 0.0)) for t in legs)
        if ht > min_half_turnover:
            out.append((d, dict(tgt)))
            last_w, last_d = dict(tgt), d
        else:
            last_w, last_d = cur, d
    return out


def build_rotation_targets(prices: dict, universe, start, end, m: int = 0) -> list:
    """Monthly (date, weights) for rule A with hysteresis m (m=0 baseline)."""
    out, held = [], set()
    for d in month_ends(prices, universe, start, end):
        w, held = rotation_choose(prices, universe, d, held, k=3, m=m)
        if w:
            out.append((d, w))
    return out
