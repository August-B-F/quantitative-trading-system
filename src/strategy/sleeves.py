"""Literature-parameterized minimal portfolio — the two-sleeve candidate.

ZERO parameter search. Every number here is verbatim from the published
spec it cites; nothing was tuned on our data:

- TSMOM sleeve — Moskowitz, Ooi & Pedersen (2012), "Time Series
  Momentum", JFE 104(2): 12-month (252 trading day) time-series momentum,
  long-only. An asset is ON iff its 252-day total return (adj_close)
  exceeds SHV's over the same window; ON assets are inverse-63d-vol
  weighted (normalized across ON assets); if nothing is ON the sleeve
  parks in SHV.
- GEM sleeve — Antonacci (2014), "Dual Momentum Investing": 12-1 month
  momentum (return over [as_of - 252 td, as_of - 21 td]) picks the winner
  of SPY vs EFA (developed ex-US leg; VEA is absent from
  data/clean/prices); hold the winner iff its 12-1 return beats SHV's
  same-window return, else park in AGG.
- Combination: 60% TSMOM / 40% GEM, then a 10% annualized vol target
  (63d realized vol of the combined book held constant over the trailing
  window; scale = min(1, target/realized) — no leverage). Excess weight
  goes to SHV.

All signals use data strictly <= as_of (each asset's own adj_close
series truncated at the decision date), so the weights are safe to trade
at the NEXT day's open — exactly the fill convention of
src/backtest/ledger.py, whose ``weight_schedule`` format
``build_schedule`` emits.
"""
from __future__ import annotations

import logging
from typing import Callable, Optional

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)

TRADING_DAYS_PER_YEAR = 252

# Asset-class coverage: US equity, developed ex-US, EM, 7-10y & 20y+
# treasuries, IG credit, gold, broad commodities, US real estate. All
# present in data/clean/prices (VEA is not, so EFA is the developed leg).
TSMOM_UNIVERSE = ["SPY", "EFA", "EEM", "IEF", "TLT", "LQD", "GLD", "DBC", "VNQ"]
CASH = "SHV"

GEM_RISK_ASSETS = ("SPY", "EFA")
GEM_FALLBACK = "AGG"

WeightFn = Callable[[dict, pd.Timestamp], Optional[dict]]


def _adj_close_upto(prices: dict, ticker: str, as_of: pd.Timestamp) -> pd.Series:
    """Adjusted-close series for ``ticker`` truncated to data <= as_of."""
    return prices[ticker]["adj_close"].loc[:as_of].dropna()


def _window_return(s: pd.Series, lookback: int, skip: int = 0) -> float | None:
    """Total return from ``lookback`` td before the last bar to ``skip`` td
    before it (skip=0 → plain trailing return). None if history is short."""
    if len(s) < lookback + 1:
        return None
    return float(s.iloc[-1 - skip] / s.iloc[-1 - lookback] - 1.0)


def _cash_return(prices: dict, as_of: pd.Timestamp, lookback: int, skip: int = 0) -> float:
    """SHV total return over the same window; 0.0 when SHV history is too
    short (pre-2008 month-ends — a zero cash hurdle, the MOP convention)."""
    if CASH not in prices:
        return 0.0
    r = _window_return(_adj_close_upto(prices, CASH, as_of), lookback, skip)
    return 0.0 if r is None else r


def tsmom_weights(
    prices: dict,
    as_of: pd.Timestamp,
    lookback: int = 252,
    vol_lookback: int = 63,
) -> dict[str, float]:
    """Long-only 12-month TSMOM weights (Moskowitz-Ooi-Pedersen 2012).

    Per asset: ON iff its ``lookback``-trading-day total return (adj_close)
    strictly exceeds SHV's over the same window. ON assets are weighted by
    inverse ``vol_lookback``-day realized vol (daily std * sqrt(252)),
    normalized across ON assets. When no asset is ON (or an ON asset has a
    degenerate zero vol), the weight goes to SHV. Data strictly <= as_of.
    """
    as_of = pd.Timestamp(as_of)
    hurdle = _cash_return(prices, as_of, lookback)
    inv_vol: dict[str, float] = {}
    for t in TSMOM_UNIVERSE:
        s = _adj_close_upto(prices, t, as_of)
        r = _window_return(s, lookback)
        if r is None or r <= hurdle:
            continue  # insufficient history or OFF — weight falls to SHV
        daily = s.iloc[-(vol_lookback + 1):].pct_change().dropna()
        vol = float(daily.std(ddof=1) * np.sqrt(TRADING_DAYS_PER_YEAR))
        if not np.isfinite(vol) or vol <= 0.0:
            log.warning("tsmom: %s ON at %s but 63d vol=%s — excluded", t, as_of.date(), vol)
            continue
        inv_vol[t] = 1.0 / vol
    if not inv_vol:
        return {CASH: 1.0}
    total = sum(inv_vol.values())
    return {t: iv / total for t, iv in inv_vol.items()}


def gem_weights(
    prices: dict,
    as_of: pd.Timestamp,
    lookback: int = 252,
    skip: int = 21,
) -> dict[str, float] | None:
    """Antonacci GEM (dual momentum, 12-1) weights.

    Momentum = total return over [as_of - ``lookback`` td, as_of - ``skip``
    td]. Winner = argmax over SPY/EFA; hold the winner iff its 12-1 return
    strictly beats SHV's same-window return, else hold AGG. Returns None
    when a risk asset lacks ``lookback`` + 1 bars of history at ``as_of``.
    """
    as_of = pd.Timestamp(as_of)
    mom: dict[str, float] = {}
    for t in GEM_RISK_ASSETS:
        r = _window_return(_adj_close_upto(prices, t, as_of), lookback, skip)
        if r is None:
            return None
        mom[t] = r
    winner = max(GEM_RISK_ASSETS, key=lambda t: mom[t])
    hurdle = _cash_return(prices, as_of, lookback, skip)
    if mom[winner] > hurdle:
        return {winner: 1.0}
    return {GEM_FALLBACK: 1.0}


def _vol_target_scale(
    prices: dict,
    as_of: pd.Timestamp,
    weights: dict[str, float],
    target_vol: float,
    vol_lookback: int,
) -> float:
    """min(1, target/realized) where realized = annualized std of the
    portfolio's implied daily returns over the trailing ``vol_lookback``
    days, holding ``weights`` constant. Data strictly <= as_of; a missing
    row for a ticker contributes a zero return that day. Degenerate
    windows (too short, zero vol) return 1.0 (no scaling)."""
    rets: dict[str, pd.Series] = {}
    for t in weights:
        s = _adj_close_upto(prices, t, as_of)
        if len(s) >= 2:
            # slice before pct_change — only vol_lookback values are used,
            # and full-history pct_change per month-end is O(n^2) per backtest
            rets[t] = s.iloc[-(vol_lookback + 1):].pct_change().dropna()
    if not rets:
        return 1.0
    frame = pd.DataFrame(rets).tail(vol_lookback).fillna(0.0)
    if len(frame) < 2:
        return 1.0
    port = frame.mul(pd.Series({t: weights[t] for t in frame.columns})).sum(axis=1)
    realized = float(port.std(ddof=1) * np.sqrt(TRADING_DAYS_PER_YEAR))
    if not np.isfinite(realized) or realized <= 0.0:
        return 1.0
    return min(1.0, target_vol / realized)


def two_sleeve_weights(
    prices: dict,
    as_of: pd.Timestamp,
    tsmom_frac: float = 0.6,
    target_vol: float = 0.10,
    lookback: int = 252,
    skip: int = 21,
    vol_lookback: int = 63,
) -> dict[str, float] | None:
    """The candidate: 0.6 * TSMOM + 0.4 * GEM, vol-targeted to 10% ann.

    Combined weights are scaled by min(1, target_vol / realized_63d_vol)
    on all non-SHV legs (no leverage — capped at 1); the excess goes to
    SHV. Returns None while GEM history is insufficient.
    """
    as_of = pd.Timestamp(as_of)
    ts = tsmom_weights(prices, as_of, lookback=lookback, vol_lookback=vol_lookback)
    gem = gem_weights(prices, as_of, lookback=lookback, skip=skip)
    if gem is None:
        return None
    combined: dict[str, float] = {}
    for t, w in ts.items():
        combined[t] = combined.get(t, 0.0) + tsmom_frac * w
    for t, w in gem.items():
        combined[t] = combined.get(t, 0.0) + (1.0 - tsmom_frac) * w
    scale = _vol_target_scale(prices, as_of, combined, target_vol, vol_lookback)
    out = {t: w * scale for t, w in combined.items() if t != CASH}
    out[CASH] = max(0.0, 1.0 - sum(out.values()))
    return out


def build_schedule(
    prices: dict,
    start,
    end,
    fn: WeightFn,
) -> list[tuple[pd.Timestamp, dict[str, float]]]:
    """Month-end decision schedule in the ledger engine's format.

    Decision dates are the last trading day of each month on the
    INTERSECTION calendar of every frame in ``prices``, clipped to
    [start, end] (``end=None`` → calendar max). ``fn(prices, as_of)``
    entries returning None (insufficient history) are skipped, so the
    schedule starts at the first month-end the strategy can trade.
    """
    cal: pd.DatetimeIndex | None = None
    for df in prices.values():
        cal = df.index if cal is None else cal.intersection(df.index)
    if cal is None or len(cal) == 0:
        raise ValueError("prices is empty or the ticker calendars do not intersect")
    start_ts = pd.Timestamp(start)
    end_ts = pd.Timestamp(end) if end is not None else cal.max()
    cal = cal[(cal >= start_ts) & (cal <= end_ts)]
    if len(cal) == 0:
        raise ValueError(f"no trading days in [{start_ts.date()}, {end_ts.date()}]")
    month_ends = cal.to_series().groupby(cal.to_period("M")).last()
    schedule: list[tuple[pd.Timestamp, dict[str, float]]] = []
    for d in month_ends:
        w = fn(prices, pd.Timestamp(d))
        if w is None:
            continue
        schedule.append((pd.Timestamp(d), w))
    return schedule
