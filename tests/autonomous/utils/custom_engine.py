"""Run a backtest with a custom momentum signal.

Monkey-patches the bundle's returns[lb] table with a custom per-ticker DataFrame
so that PortfolioEngine's `build_momentum_array(bundle.returns[lb], ...)` picks
up our signal without any engine modifications.

The signal DataFrame must have the same index as bundle.dates and columns for
every ticker in the universe (and enough extras to cover feature_extras).
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from utils.base_test import _load, _STATE, run, CHAMPION  # noqa: E402
from strategy.portfolio import PortfolioEngine  # noqa: E402
from backtest.engine import run_backtest  # noqa: E402


def run_custom(stable_signal: pd.DataFrame | None,
               trans_signal: pd.DataFrame | None = None,
               overrides: dict | None = None):
    """Run backtest with custom stable/transition momentum signals.

    stable_signal: per-ticker DataFrame keyed off bundle.dates, used for lookback_stable.
    trans_signal:  same for lookback_transition. If None, default 21d returns are kept.
    """
    _load()
    cfg = copy.deepcopy(_STATE["cfg"])
    if overrides:
        cfg.update(overrides)
    bundle = _STATE["bundle"]
    # Clone returns dict to avoid polluting cached state.
    new_returns = dict(bundle.returns)
    lbs = cfg["lookback_stable"]
    lbt = cfg["lookback_transition"]
    if stable_signal is not None:
        new_returns[lbs] = stable_signal
    if trans_signal is not None:
        new_returns[lbt] = trans_signal

    class _Shim:
        pass
    shim = _Shim()
    for attr in ("df", "dates", "atr21", "fwd21", "spy_dist_sma200", "is_fomc_day"):
        setattr(shim, attr, getattr(bundle, attr))
    shim.returns = new_returns

    engine = PortfolioEngine(shim, _STATE["pred_reg"], cfg)
    res = run_backtest(engine, _STATE["test_dates"], cfg)
    return res.stats


def load_prices():
    """Load adj-close for all tickers we have in the panel (via atr21 columns)."""
    _load()
    bundle = _STATE["bundle"]
    # Try to reconstruct prices from the raw parquet files; simplest path:
    # use returns_21d as proxy — we don't actually need prices themselves,
    # we need the ability to build any N-day return. Do it via returns_Nd files.
    return bundle.returns
