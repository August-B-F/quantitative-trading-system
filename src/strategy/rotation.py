"""Blend-rank rotation — the relaunch candidate strategy.

Implements the frozen spec adopted by pre-registered Study 4
(research/droplets/study4_blended_momentum/SPEC_blend_126_252.yaml):

- score(t, d) = mean of cross-sectional ranks (ascending, average ties) of
  the 126d and 252d trailing total returns across the 8-ETF universe
- top-3 by score, inverse-63d-vol weighted
- SPY SMA200 gate: 100% SHY when SPY adj_close <= its 200d SMA at decision
- monthly decision at month-end close, fill next open (ledger convention)

Also provides the 4-tranche staggered schedule builder recommended by
Study 2 (research/droplets/study2_timing_luck): rebalancing the same rule
at month-end +0/+5/+10/+15 trading days removes ~2/3 of rebalance-timing
luck at ~zero measured cost. Each tranche computes its signal at its OWN
decision date.

All signal functions use data strictly <= as_of (truncation-invariant).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

ROTATION_UNIVERSE = ["SOXX", "QQQ", "XLK", "VGT", "IGV", "XLE", "GLD", "SHY"]
GATE_TICKER = "SPY"
GATE_SMA_WINDOW = 200
RISK_OFF_ASSET = "SHY"
BLEND_LOOKBACKS = (126, 252)
TOP_N = 3
VOL_LOOKBACK = 63
TRADING_DAYS_PER_YEAR = 252
TRANCHE_OFFSETS = (0, 5, 10, 15)   # trading days after month-end (study 2)


def _adj_close_upto(prices: dict, ticker: str, as_of: pd.Timestamp) -> pd.Series:
    s = prices[ticker]["adj_close"].dropna()
    return s[s.index <= as_of]


def _trailing_return(s: pd.Series, lookback: int) -> float:
    """Total return over the last `lookback` bars, NaN if history is short."""
    if len(s) <= lookback:
        return np.nan
    return float(s.iloc[-1] / s.iloc[-1 - lookback] - 1.0)


def blend_scores(
    prices: dict,
    as_of: pd.Timestamp,
    universe: list[str] = None,
    lookbacks: tuple = BLEND_LOOKBACKS,
) -> pd.Series:
    """Mean of cross-sectional ranks of each lookback's trailing return.

    Ranks ascending with average ties (best asset gets the highest rank),
    matching the frozen SPEC exactly. NaN returns rank as NaN and the
    asset's score becomes NaN (excluded from selection).
    """
    universe = list(universe or ROTATION_UNIVERSE)
    as_of = pd.Timestamp(as_of)
    rets = pd.DataFrame(
        {
            lb: {
                t: _trailing_return(_adj_close_upto(prices, t, as_of), lb)
                for t in universe
            }
            for lb in lookbacks
        }
    )
    ranks = rets.rank(axis=0, method="average", ascending=True)
    return ranks.mean(axis=1, skipna=False)


def gate_risk_off(prices: dict, as_of: pd.Timestamp) -> bool:
    """True when SPY adj_close <= its 200d SMA at the decision date."""
    s = _adj_close_upto(prices, GATE_TICKER, pd.Timestamp(as_of))
    if len(s) < GATE_SMA_WINDOW:
        return True  # not enough history to trust the gate — stay safe
    sma = float(s.iloc[-GATE_SMA_WINDOW:].mean())
    return float(s.iloc[-1]) <= sma


def blend_rotation_weights(
    prices: dict,
    as_of: pd.Timestamp,
    universe: list[str] = None,
    top_n: int = TOP_N,
    vol_lookback: int = VOL_LOOKBACK,
) -> dict[str, float]:
    """Target weights for one decision date per the frozen blend_126_252 spec."""
    as_of = pd.Timestamp(as_of)
    if gate_risk_off(prices, as_of):
        return {RISK_OFF_ASSET: 1.0}
    scores = blend_scores(prices, as_of, universe=universe).dropna()
    if scores.empty:
        return {RISK_OFF_ASSET: 1.0}
    # DETERMINISTIC tie-break (study8 found blended ranks of 2 legs tie on
    # ~15% of decisions and an unstable sort moved dev Sharpe by ±0.085):
    # ties go to the higher 252d trailing return (the slower, more robust
    # leg), then ticker alphabetical for absolute reproducibility.
    slow_lb = max(BLEND_LOOKBACKS)
    slow_ret = {
        t: _trailing_return(_adj_close_upto(prices, t, as_of), slow_lb)
        for t in scores.index
    }
    order = sorted(
        scores.index,
        key=lambda t: (
            -float(scores[t]),
            -(slow_ret[t] if np.isfinite(slow_ret[t]) else float("-inf")),
            t,
        ),
    )
    top = order[:top_n]

    inv_vols: dict[str, float] = {}
    for t in top:
        s = _adj_close_upto(prices, t, as_of)
        daily = s.iloc[-(vol_lookback + 1):].pct_change().dropna()
        vol = float(daily.std(ddof=1) * np.sqrt(TRADING_DAYS_PER_YEAR))
        inv_vols[t] = 1.0 / vol if np.isfinite(vol) and vol > 0 else np.nan
    if not np.isfinite(list(inv_vols.values())).any():
        return {t: 1.0 / len(top) for t in top}   # degenerate vols: equal weight
    total = np.nansum(list(inv_vols.values()))
    return {
        t: (iv / total if np.isfinite(iv) else 0.0) for t, iv in inv_vols.items()
    }


def month_end_offset_dates(
    calendar: pd.DatetimeIndex, offset_td: int = 0
) -> pd.DatetimeIndex:
    """Month-end + `offset_td` trading days, on the given trading calendar.

    Offsets that spill past the calendar's end are dropped.
    """
    cal = pd.DatetimeIndex(calendar).sort_values()
    month_ends = cal.to_series().groupby(cal.to_period("M")).last()
    pos = cal.get_indexer(pd.DatetimeIndex(month_ends.values)) + offset_td
    pos = pos[(pos >= 0) & (pos < len(cal))]
    return pd.DatetimeIndex(cal[pos]).unique().sort_values()


def tranche_decision_days(
    calendar, offsets: tuple = TRANCHE_OFFSETS
) -> dict[pd.Timestamp, int]:
    """Map each tranche decision date on `calendar` to its offset k.

    For every month on the trading calendar the decision dates are
    month-end + k trading days for each k in `offsets` (dates spilling past
    the calendar end are dropped, same as month_end_offset_dates). With the
    production offsets (0, 5, 10, 15) and ~21-trading-day months decision
    dates never collide; if custom offsets ever did collide on a date, the
    LATER k in `offsets` wins that date.
    """
    cal = pd.DatetimeIndex(calendar).sort_values()
    out: dict[pd.Timestamp, int] = {}
    for k in offsets:
        for d in month_end_offset_dates(cal, int(k)):
            out[pd.Timestamp(d)] = int(k)
    return out


def account_target_from_state(
    state: dict,
    tranche_k: int,
    new_weights: dict,
    offsets: tuple = TRANCHE_OFFSETS,
) -> dict[str, float]:
    """Account-level target: equal-weight average of the tranches' weights.

    Each tranche runs 1/len(offsets) of account equity. The persisted
    weights of tranche `tranche_k` are replaced by `new_weights` (today's
    decision); every other tranche keeps its CURRENT persisted weights.
    Missing tranches default to {RISK_OFF_ASSET: 1.0} so a fresh (empty)
    state is risk-off by construction.

    `state` schema (persisted per strategy at logs/tranche_state.json):
        {"tranches": {"0": {ticker: w}, "5": {...}, "10": {...}, "15": {...}},
         "updated":  {"0": "YYYY-MM-DD", ...}}
    """
    if int(tranche_k) not in {int(k) for k in offsets}:
        raise ValueError(f"tranche_k={tranche_k} not in offsets {tuple(offsets)}")
    tranches = (state or {}).get("tranches", {}) or {}
    n = len(offsets)
    target: dict[str, float] = {}
    for k in offsets:
        if int(k) == int(tranche_k):
            w = dict(new_weights)
        else:
            w = dict(tranches.get(str(int(k))) or {RISK_OFF_ASSET: 1.0})
        for t, x in w.items():
            target[t] = target.get(t, 0.0) + float(x) / n
    return target


def build_tranched_schedules(
    prices: dict,
    start,
    end,
    weight_fn=blend_rotation_weights,
    offsets: tuple = TRANCHE_OFFSETS,
) -> dict[int, list[tuple[pd.Timestamp, dict[str, float]]]]:
    """One ledger-engine weight_schedule per tranche offset.

    Each tranche computes its signal at its OWN decision date (month-end +
    offset trading days) — never sharing signals across tranches (study 2).
    The live executor runs each tranche against 1/len(offsets) of account
    equity; for backtests, run each schedule through the ledger engine and
    average the NAVs.
    """
    tickers = set(ROTATION_UNIVERSE) | {GATE_TICKER}
    cal = None
    for t in tickers:
        idx = prices[t]["adj_close"].dropna().index
        cal = idx if cal is None else cal.intersection(idx)
    cal = cal[(cal >= pd.Timestamp(start)) & (cal <= pd.Timestamp(end))]
    out: dict[int, list] = {}
    for k in offsets:
        dates = month_end_offset_dates(cal, k)
        out[k] = [(d, weight_fn(prices, d)) for d in dates]
    return out
