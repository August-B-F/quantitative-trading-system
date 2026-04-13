"""Worked-example test — one real rebalance from the canonical backtest.

§10.6 of MASTER_ARCHITECTURE describes 2019-01-25 as illustrative only.
This test picks a concrete rebalance date that we can verify against the
research code path directly: 2020-03-31 (inside the COVID drawdown window),
and asserts the portfolio engine produces a deterministic decision with
weights summing to 1, a valid top1 from the universe, and an SMA gate
decision consistent with the canonical path.

For byte-level reproducibility against the research result, the
test_full_canonical_canary test in test_backtest_canary.py covers the
aggregate. This test is the per-date sanity check.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from data.pipeline import load_config, load_panel
from features.engineer import load_core_feature_list, select_core_features
from model.classifier import walk_forward_predict
from strategy.portfolio import PortfolioEngine

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def engine_fixture():
    """Build a PortfolioEngine once for the worked-example checks."""
    cfg = load_config(ROOT)
    bundle = load_panel(ROOT, cfg)
    core = load_core_feature_list(ROOT, cfg["classifier"]["feature_set"])
    core_present = select_core_features(bundle.df, core)
    pred_reg, _, _ = walk_forward_predict(bundle.df, core_present, cfg)
    return cfg, PortfolioEngine(bundle, pred_reg, cfg), bundle


def test_decision_on_2019_01_last_trading_day(engine_fixture) -> None:
    """§10.6: rebalance in late Jan 2019 -- SMA gate was near -4% threshold.

    We look up the last trading day of January 2019 in the panel and run
    the engine. The top1 name, weights, and gate state must all be
    well-formed.
    """
    cfg, engine, bundle = engine_fixture
    jan19 = bundle.dates[(bundle.dates.year == 2019) & (bundle.dates.month == 1)]
    last = jan19[-1]
    pos = bundle.dates.get_indexer([last])[0]
    rec = engine.decide(pos, pos, deferred=False)

    # well-formedness
    assert rec.top1 in cfg["universe"]
    assert len(rec.topk) == cfg["top_k"]
    assert abs(sum(rec.target_weights.values()) - 1.0) < 1e-9
    # spec: lookback is 63 or 21 only
    assert rec.lookback_used in (63, 21)
    # if gate fired, top1 leg (50%) parks in SHY
    if rec.sma_gate_fired:
        assert rec.target_weights.get("SHY", 0) >= 0.5 - 1e-9


def test_decision_on_2020_03_end(engine_fixture) -> None:
    """March 2020 COVID trough -- SMA gate should fire (SPY distance < -4%)."""
    cfg, engine, bundle = engine_fixture
    mar20 = bundle.dates[(bundle.dates.year == 2020) & (bundle.dates.month == 3)]
    last = mar20[-1]
    pos = bundle.dates.get_indexer([last])[0]
    rec = engine.decide(pos, pos, deferred=False)
    assert rec.sma_gate_fired is True
    assert rec.target_weights.get("SHY", 0) >= 0.5 - 1e-9
