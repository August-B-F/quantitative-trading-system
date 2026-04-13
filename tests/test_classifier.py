"""Smoke test: classifier estimator builder carries the pinned hyperparameters."""
from __future__ import annotations

from pathlib import Path

from data.pipeline import load_config
from model.classifier import build_estimator, build_splitter

ROOT = Path(__file__).resolve().parents[1]


def test_build_estimator_hyperparameters() -> None:
    """HistGB is built with the locked §5.2 settings."""
    cfg = load_config(ROOT)
    est = build_estimator(cfg)
    assert est.max_iter == 200
    assert est.max_depth == 4
    assert est.learning_rate == 0.05
    assert est.random_state == 0


def test_build_splitter_hyperparameters() -> None:
    """ExpandingSplitter is built with the §5.4 config."""
    cfg = load_config(ROOT)
    sp = build_splitter(cfg)
    assert sp.min_train_months == 60
    assert sp.test_months == 3
    assert sp.step_months == 3
