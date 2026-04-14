"""Multi-strategy backtest engine.

Runs all N strategies over the same backtest window using shared panel +
walk-forward classifier output, and returns a dict of per-strategy results.
This is the entry point used by ``scripts/run_multi_backtest.py`` for the
9-strategy comparison.
"""
from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd

from backtest.engine import compute_stats
from strategy.portfolio import StrategyRunner

log = logging.getLogger(__name__)


def _apply_cost(monthly: pd.Series, cost_bps: float) -> pd.Series:
    if cost_bps <= 0:
        return monthly
    return monthly - (cost_bps / 1e4)


def _extended_metrics(monthly: pd.Series) -> dict:
    """Stats: CAGR, Sharpe, MaxDD, Sortino, Win%, WorstYr."""
    s = compute_stats(monthly.values)
    r = monthly.dropna().values
    # Sortino — downside dev of monthly returns, annualised
    downside = r[r < 0]
    if len(downside) > 1:
        dd_std = downside.std(ddof=1)
        sortino = float(r.mean() / dd_std * np.sqrt(12)) if dd_std > 0 else float("nan")
    else:
        sortino = float("nan")
    s["sortino"] = sortino
    s["win_pct"] = float((r > 0).sum() / len(r)) if len(r) else float("nan")
    # Annual returns -> worst year
    yearly = (1 + monthly).groupby(monthly.index.year).prod() - 1
    s["worst_year"] = float(yearly.min()) if len(yearly) else float("nan")
    s["annual_returns"] = yearly
    return s


class MultiStrategyBacktest:
    """Run N strategies in parallel, returning per-strategy monthly series + stats."""

    def __init__(
        self,
        strategy_configs: list[str | Path],
        start: str | None = None,
        end: str | None = None,
        cost_bps: float = 0.0,
    ):
        self.runners = [StrategyRunner(cfg) for cfg in strategy_configs]
        self.start = start
        self.end = end
        self.cost_bps = cost_bps

    def run(self, bundle, pred_reg, test_dates, cfg_global) -> dict:
        """Run all strategies over the shared window. Returns per-strategy results."""
        results: dict[str, dict] = {}
        for runner in self.runners:
            log.info("running %s (slot %d)", runner.name, runner.slot)
            monthly, weights_history = runner.run(bundle, pred_reg, test_dates, cfg_global)
            # Trim to [start, end] if requested
            if self.start is not None:
                monthly = monthly[monthly.index >= pd.Timestamp(self.start)]
                weights_history = [(d, w) for d, w in weights_history
                                   if d >= pd.Timestamp(self.start)]
            if self.end is not None:
                monthly = monthly[monthly.index <= pd.Timestamp(self.end)]
                weights_history = [(d, w) for d, w in weights_history
                                   if d <= pd.Timestamp(self.end)]
            monthly_net = _apply_cost(monthly, self.cost_bps)
            metrics = _extended_metrics(monthly_net)
            results[runner.name] = {
                "slot": runner.slot,
                "monthly_returns": monthly_net,
                "weights_history": weights_history,
                "metrics": metrics,
            }
        return results
