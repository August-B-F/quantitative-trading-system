"""Study 7 shared library — two-sleeve respec variants.

Implements the knobs pre-registered in HYPOTHESIS.md WITHOUT touching
src/strategy/sleeves.py. Reuses its helpers verbatim.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from backtest.ledger import load_prices, run_ledger_backtest  # noqa: E402
from strategy.sleeves import (  # noqa: E402
    CASH,
    TRADING_DAYS_PER_YEAR,
    TSMOM_UNIVERSE,
    GEM_RISK_ASSETS,
    _adj_close_upto,
    _cash_return,
    _vol_target_scale,
    _window_return,
    build_schedule,
)

DEV_START, DEV_END = "2005-01-01", "2017-12-31"
VAL_START = "2018-01-01"
CAL_TICKERS = sorted(set(TSMOM_UNIVERSE) | {CASH, "AGG"})
ALL_TICKERS = sorted(set(CAL_TICKERS) | {"SHY"})  # SHY only for spy_sma200 ref
ENS_HORIZONS = (63, 126, 252)


def get_prices():
    return load_prices(ROOT, ALL_TICKERS)


# ---------- trend rules -------------------------------------------------------

def _trend_on(prices: dict, t: str, as_of: pd.Timestamp, rule: str) -> bool:
    """ON/OFF per HYPOTHESIS.md; insufficient history -> False (skipped)."""
    s = _adj_close_upto(prices, t, as_of)
    if rule == "T12":
        r = _window_return(s, 252)
        return r is not None and r > _cash_return(prices, as_of, 252)
    if rule == "ENS":
        if len(s) < 253:
            return False
        votes = 0
        for L in ENS_HORIZONS:
            r = _window_return(s, L)
            if r is not None and r > _cash_return(prices, as_of, L):
                votes += 1
        return votes >= 2
    if rule == "FAB":
        if len(s) < 210:
            return False
        return float(s.iloc[-1]) > float(s.iloc[-210:].mean())
    raise ValueError(rule)


# ---------- sleeves -----------------------------------------------------------

def tsmom_var(prices: dict, as_of: pd.Timestamp, rule: str, weighting: str) -> dict[str, float]:
    raw: dict[str, float] = {}
    for t in TSMOM_UNIVERSE:
        if not _trend_on(prices, t, as_of, rule):
            continue
        if weighting == "EW":
            raw[t] = 1.0
        elif weighting == "IV":
            s = _adj_close_upto(prices, t, as_of)
            daily = s.iloc[-64:].pct_change().dropna()
            vol = float(daily.std(ddof=1) * np.sqrt(TRADING_DAYS_PER_YEAR))
            if not np.isfinite(vol) or vol <= 0.0:
                continue
            raw[t] = 1.0 / vol
        else:
            raise ValueError(weighting)
    if not raw:
        return {CASH: 1.0}
    total = sum(raw.values())
    return {t: v / total for t, v in raw.items()}


def gem_var(prices: dict, as_of: pd.Timestamp, fallback: str = "AGG"):
    """Antonacci GEM 12-1 exactly as sleeves.gem_weights, fallback knob."""
    mom: dict[str, float] = {}
    for t in GEM_RISK_ASSETS:
        r = _window_return(_adj_close_upto(prices, t, as_of), 252, 21)
        if r is None:
            return None
        mom[t] = r
    winner = max(GEM_RISK_ASSETS, key=lambda t: mom[t])
    hurdle = _cash_return(prices, as_of, 252, 21)
    return {winner: 1.0} if mom[winner] > hurdle else {fallback: 1.0}


def two_sleeve_var(prices, as_of, rule="T12", weighting="IV", vt=0.10,
                   frac=0.6, gemfb="AGG"):
    as_of = pd.Timestamp(as_of)
    ts = tsmom_var(prices, as_of, rule, weighting)
    gem = gem_var(prices, as_of, gemfb)
    if gem is None:
        return None
    combined: dict[str, float] = {}
    for t, w in ts.items():
        combined[t] = combined.get(t, 0.0) + frac * w
    for t, w in gem.items():
        combined[t] = combined.get(t, 0.0) + (1.0 - frac) * w
    scale = 1.0 if vt is None else _vol_target_scale(prices, as_of, combined, vt, 63)
    out = {t: w * scale for t, w in combined.items() if t != CASH}
    out[CASH] = max(0.0, 1.0 - sum(out.values()))
    return out


CONFIGS: dict[str, dict] = {
    "R0": dict(rule="T12", weighting="IV", vt=0.10, frac=0.6, gemfb="AGG"),
    "C1": dict(rule="T12", weighting="IV", vt=None, frac=0.6, gemfb="AGG"),
    "C2": dict(rule="T12", weighting="EW", vt=0.10, frac=0.6, gemfb="AGG"),
    "C3": dict(rule="ENS", weighting="IV", vt=0.10, frac=0.6, gemfb="AGG"),
    "C4": dict(rule="FAB", weighting="IV", vt=0.10, frac=0.6, gemfb="AGG"),
    "C5": dict(rule="ENS", weighting="EW", vt=None, frac=0.6, gemfb="AGG"),
    "C6": dict(rule="FAB", weighting="EW", vt=None, frac=0.6, gemfb="AGG"),
    "C7": dict(rule="ENS", weighting="EW", vt=0.12, frac=0.6, gemfb="AGG"),
    "C8": dict(rule="ENS", weighting="EW", vt=None, frac=0.7, gemfb="AGG"),
    "C9": dict(rule="ENS", weighting="EW", vt=None, frac=0.6, gemfb="IEF"),
}


def run_config(prices, params, start, end, costs=(10.0, 20.0)):
    """Build the schedule once, run the ledger at each cost. -> {bps: stats}"""
    cal_prices = {t: prices[t] for t in CAL_TICKERS}
    fn = lambda p, d: two_sleeve_var(p, d, **params)  # noqa: E731
    schedule = build_schedule(cal_prices, start, end, fn)
    out = {}
    for bps in costs:
        res = run_ledger_backtest(schedule, prices, cost_bps=bps,
                                  cash_ticker=CASH, start=schedule[0][0],
                                  end=end, benchmarks=())
        out[bps] = res.stats
    return out


def fmt(stats: dict) -> str:
    return ("CAGR %6.2f%%  vol %5.2f%%  Sharpe %5.3f  MaxDD %7.2f%%  "
            "turn %4.2fx  costdrag %4.1fbps  reb %d" % (
                stats["cagr"] * 100, stats["vol"] * 100, stats["sharpe"],
                stats["max_dd"] * 100, stats["ann_turnover"],
                stats["ann_cost_drag"] * 1e4, stats["n_rebalances"]))
