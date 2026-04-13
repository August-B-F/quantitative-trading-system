"""Backtest engine — assembles the per-month series and computes metrics.

Canonical path matches run_m26_deep.run_variant + m26_followup's post-3d
run: month_end rebalance, FOMC post-window deferral, 50/50 + inverse-vol,
SMA200 gate. The monthly return series is the forward-21d return observed
from each executed rebalance position (gross, pre-transaction-cost).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd

from strategy.portfolio import PortfolioEngine, DecisionRecord
from strategy.rebalance import month_end_positions, fomc_window_mask, resolve_rebalance_index

log = logging.getLogger(__name__)


@dataclass
class BacktestResult:
    """Result bundle: series of monthly returns + decision log + metrics."""
    monthly_returns: pd.Series
    decisions: list[DecisionRecord]
    stats: dict[str, float]


def compute_stats(r: np.ndarray) -> dict[str, float]:
    """CAGR / Sharpe / MaxDD on a monthly return series. Matches run_m26_deep.stats()."""
    r = np.asarray(r, dtype=float)
    r = r[~np.isnan(r)]
    n = len(r)
    if n == 0:
        return {"cagr": float("nan"), "sharpe": float("nan"), "max_dd": float("nan"), "n": 0}
    eq = np.cumprod(1 + r)
    yrs = n / 12.0
    cagr = float(eq[-1] ** (1 / yrs) - 1)
    sd = r.std(ddof=1) if n > 1 else 0.0
    sh = float(r.mean() / sd * np.sqrt(12)) if sd > 0 else float("nan")
    peak = np.maximum.accumulate(eq)
    dd = float((eq / peak - 1).min())
    return {"cagr": cagr, "sharpe": sh, "max_dd": dd, "n": n}


def apply_transaction_costs(
    monthly: pd.Series, cost_bps: float
) -> pd.Series:
    """Apply a simple round-trip cost haircut per rebalance.

    Canonical backtest is gross (0 bps) — this is only used when the
    caller explicitly requests a cost-adjusted series for the degradation
    budget checks (§3.4). One-sided cost is `cost_bps/1e4 / 2` per leg,
    round trip per month ~ `cost_bps/1e4`.
    """
    if cost_bps <= 0:
        return monthly
    haircut = cost_bps / 1e4
    return monthly - haircut


def run_backtest(
    engine: PortfolioEngine,
    test_dates: pd.DatetimeIndex,
    cfg: dict,
    cost_bps: float = 0.0,
    start: pd.Timestamp | None = None,
    end: pd.Timestamp | None = None,
) -> BacktestResult:
    """Run the full month-end backtest loop over the walk-forward test window."""
    dates = engine.dates
    n_days = engine.n_days

    # Restrict the test window to [start, end] if provided — applied to the
    # test_dates set so the monthly cadence matches the research harness.
    td = test_dates
    if start is not None:
        td = td[td >= pd.Timestamp(start)]
    if end is not None:
        td = td[td <= pd.Timestamp(end)]

    td_positions = pd.Series(dates.get_indexer(td), index=td)
    # Month-end positions within the test window — last test date per month
    month_last = td_positions.groupby(td.to_period("M")).tail(1)

    # FOMC event mask per strategy.yaml
    defer_enabled = bool(cfg.get("fomc_defer_enabled", True))
    defer_days = int(cfg.get("fomc_defer_days", 3))
    pre = int(cfg.get("fomc_window_pre", 0))
    post = int(cfg.get("fomc_window_after", 2))
    fomc_idx = np.where(engine.bundle.is_fomc_day)[0]
    event_mask = fomc_window_mask(n_days, fomc_idx, pre_days=pre, post_days=post) if defer_enabled else None

    decisions: list[DecisionRecord] = []
    out: dict[pd.Timestamp, float] = {}

    for rebal_date, pos in month_last.items():
        sched_pos = int(pos)
        exec_pos, deferred = resolve_rebalance_index(
            sched_pos, defer_days if defer_enabled else 0, event_mask, n_days
        )
        rec = engine.decide(sched_pos, exec_pos, deferred)
        decisions.append(rec)
        out[rebal_date] = rec.fwd_ret

    monthly = pd.Series(out).sort_index()
    monthly_net = apply_transaction_costs(monthly, cost_bps)
    stats = compute_stats(monthly_net.values)
    log.info(
        "backtest: n=%d  CAGR=%.2f%%  Sharpe=%.2f  MaxDD=%.2f%%",
        stats["n"], stats["cagr"] * 100, stats["sharpe"], stats["max_dd"] * 100,
    )
    return BacktestResult(monthly_returns=monthly_net, decisions=decisions, stats=stats)
