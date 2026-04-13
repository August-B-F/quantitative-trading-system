"""Smoke test: configs load and carry the pinned parameters."""
from __future__ import annotations

from pathlib import Path

from data.pipeline import load_config

ROOT = Path(__file__).resolve().parents[1]


def test_strategy_config_pins() -> None:
    """Non-negotiable parameters must be present and correct."""
    cfg = load_config(ROOT)
    assert cfg["lookback_stable"] == 63
    assert cfg["lookback_transition"] == 21
    assert cfg["top1_weight"] == 0.5
    assert cfg["top3_weight"] == 0.5
    assert cfg["top_k"] == 3
    assert cfg["sma_gate_window"] == 200
    assert cfg["sma_gate_buffer"] == -0.04
    assert cfg["fomc_defer_days"] == 3
    assert cfg["fomc_window_after"] == 2
    assert cfg["rebalance_day"] == "month_end"
    assert cfg["universe"] == ["SOXX", "QQQ", "XLK", "VGT", "IGV", "XLE", "GLD", "SHY"]


def test_classifier_hyperparams() -> None:
    """Classifier hyperparameters match §5.2."""
    cfg = load_config(ROOT)
    c = cfg["classifier"]
    assert c["max_iter"] == 200
    assert c["max_depth"] == 4
    assert c["learning_rate"] == 0.05
    assert c["min_samples_leaf"] == 20
    assert c["l2_regularization"] == 1.0
    assert c["random_state"] == 0
