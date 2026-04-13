"""Canary regression tests.

Two tiers:

1. Fast integration test (default): runs a shortened 2018-2022 backtest
   and checks that metrics sit in reasonable ranges. Runs in CI.
2. Full canonical canary (@pytest.mark.slow): runs the full walk-forward
   backtest and asserts CAGR within 0.5pp of 23.61%, Sharpe within 0.05
   of 1.50, MaxDD within 1pp of -12.94%. ~25 seconds on dev machine.

The full canary is the non-negotiable check before any merge to prod.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from data.pipeline import load_config, load_panel
from features.engineer import load_core_feature_list, select_core_features
from model.classifier import walk_forward_predict
from strategy.portfolio import PortfolioEngine
from backtest.engine import run_backtest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def wf_bundle():
    """Load panel + run walk-forward classifier once for all tests in this module."""
    cfg = load_config(ROOT)
    bundle = load_panel(ROOT, cfg)
    core = load_core_feature_list(ROOT, cfg["classifier"]["feature_set"])
    core_present = select_core_features(bundle.df, core)
    pred_reg, test_dates, accs = walk_forward_predict(bundle.df, core_present, cfg)
    engine = PortfolioEngine(bundle, pred_reg, cfg)
    return cfg, engine, test_dates, sum(accs) / max(len(accs), 1)


def test_wf_accuracy_baseline(wf_bundle) -> None:
    """WF 4-class accuracy should match ~0.665 (§2.5, §5)."""
    _, _, _, acc = wf_bundle
    assert 0.60 < acc < 0.72, f"WF accuracy {acc} outside expected range"


def test_shortened_backtest_reasonable(wf_bundle) -> None:
    """2018-2022 backtest should produce defensible numbers (fast)."""
    cfg, engine, test_dates, _ = wf_bundle
    res = run_backtest(engine, test_dates, cfg, cost_bps=0.0, start="2018-01-01", end="2022-12-31")
    s = res.stats
    assert s["n"] >= 50, f"too few monthly returns: {s['n']}"
    assert -0.30 < s["max_dd"] < 0, f"MaxDD out of range: {s['max_dd']}"
    assert 0.5 < s["sharpe"] < 3.0, f"Sharpe out of range: {s['sharpe']}"
    assert -0.05 < s["cagr"] < 0.60, f"CAGR out of range: {s['cagr']}"


@pytest.mark.slow
def test_full_canonical_canary(wf_bundle) -> None:
    """Full walk-forward backtest must reproduce 23.61% / 1.50 / -12.94%.

    Tolerances are the NON-NEGOTIABLE production bar from MASTER_ARCHITECTURE §9.3.
    """
    cfg, engine, test_dates, _ = wf_bundle
    res = run_backtest(engine, test_dates, cfg, cost_bps=0.0)
    s = res.stats
    assert abs(s["cagr"] - 0.2361) < 0.005, f"CAGR {s['cagr']*100:.2f}% off canonical 23.61%"
    assert abs(s["sharpe"] - 1.50) < 0.05, f"Sharpe {s['sharpe']:.3f} off canonical 1.50"
    assert abs(s["max_dd"] - (-0.1294)) < 0.01, f"MaxDD {s['max_dd']*100:.2f}% off canonical -12.94%"
    assert s["n"] == 188, f"expected 188 months, got {s['n']}"
