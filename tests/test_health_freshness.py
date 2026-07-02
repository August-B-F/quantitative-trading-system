"""Tests for the SIGNAL FRESHNESS / CORE staleness health-check helpers.

scripts/run_health_check.py is not a package module, so it is loaded via
importlib. Synthetic parquet fixtures live in tmp_path; the CORE staleness
resolver is exercised against the real repo data (no network).
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]

_spec = importlib.util.spec_from_file_location(
    "run_health_check", ROOT / "scripts" / "run_health_check.py"
)
hc = importlib.util.module_from_spec(_spec)
sys.modules["run_health_check"] = hc  # dataclasses needs the module registered
_spec.loader.exec_module(hc)

TODAY = pd.Timestamp("2026-07-02")  # a Thursday, NYSE trading day
FRESH_END = pd.Timestamp("2026-07-01")
STALE_END = pd.Timestamp("2026-06-12")  # 13 trading days before TODAY


def _write_wide(path: Path, end: pd.Timestamp, cols: list[str], n: int = 30,
                nan_tail_cols: list[str] | None = None) -> None:
    idx = pd.bdate_range(end=end, periods=n)
    df = pd.DataFrame({c: np.linspace(0.0, 1.0, n) for c in cols}, index=idx)
    for c in nan_tail_cols or []:
        df.loc[df.index[-1], c] = np.nan
    df.to_parquet(path)


@pytest.fixture
def fixture_paths(tmp_path):
    def build(panel_end=FRESH_END, returns_end=FRESH_END, quality_end=FRESH_END,
              quality_nan_tail=False):
        panel = tmp_path / "master_panel.parquet"
        returns = tmp_path / "returns_63d.parquet"
        quality = tmp_path / "quality_dist_sma200.parquet"
        _write_wide(panel, panel_end, ["feat_a", "feat_b"])
        _write_wide(returns, returns_end, ["SPY", "QQQ"])
        _write_wide(quality, quality_end, ["SPY", "QQQ"],
                     nan_tail_cols=["SPY"] if quality_nan_tail else None)
        return panel, returns, quality
    return build


# ---------- check_signal_freshness -----------------------------------------


def test_signal_freshness_all_fresh(fixture_paths):
    panel, returns, quality = fixture_paths()
    section = hc.check_signal_freshness(
        TODAY, panel_path=panel, returns_path=returns, quality_path=quality)
    assert section.status == "OK"
    assert "returns_63d" in section.detail


def test_signal_freshness_stale_returns_alerts(fixture_paths):
    panel, returns, quality = fixture_paths(returns_end=STALE_END)
    section = hc.check_signal_freshness(
        TODAY, panel_path=panel, returns_path=returns, quality_path=quality)
    assert section.status == "ALERT"
    assert "returns_63d" in section.detail
    assert str(STALE_END.date()) in section.detail


def test_signal_freshness_stale_quality_alerts(fixture_paths):
    panel, returns, quality = fixture_paths(quality_end=STALE_END)
    section = hc.check_signal_freshness(
        TODAY, panel_path=panel, returns_path=returns, quality_path=quality)
    assert section.status == "ALERT"
    assert "quality_dist_sma200" in section.detail


def test_signal_freshness_stale_panel_only_warns(fixture_paths):
    """The 2026 Q2 shape: fresh per-feature parquets, frozen master panel."""
    panel, returns, quality = fixture_paths(panel_end=STALE_END)
    section = hc.check_signal_freshness(
        TODAY, panel_path=panel, returns_path=returns, quality_path=quality)
    assert section.status == "WARNING"
    assert "live_extend" in section.detail


def test_signal_freshness_nan_quality_tail_alerts(fixture_paths):
    """gate_fired(NaN) returns True — a NaN SPY tail must page even if
    the last *valid* observation is recent."""
    panel, returns, quality = fixture_paths(quality_nan_tail=True)
    section = hc.check_signal_freshness(
        TODAY, panel_path=panel, returns_path=returns, quality_path=quality)
    assert section.status == "ALERT"
    assert "NaN" in section.detail


def test_signal_freshness_missing_returns_alerts(fixture_paths, tmp_path):
    panel, _returns, quality = fixture_paths()
    section = hc.check_signal_freshness(
        TODAY, panel_path=panel,
        returns_path=tmp_path / "does_not_exist.parquet",
        quality_path=quality)
    assert section.status == "ALERT"
    assert "missing" in section.detail


# ---------- helper primitives -----------------------------------------------


def test_raw_index_max_ignores_nan_tail(tmp_path):
    p = tmp_path / "x.parquet"
    _write_wide(p, FRESH_END, ["SPY"], nan_tail_cols=["SPY"])
    assert hc._raw_index_max(p) == FRESH_END.normalize()


def test_column_last_valid_reports_nan_at_max(tmp_path):
    p = tmp_path / "x.parquet"
    _write_wide(p, FRESH_END, ["SPY", "QQQ"], nan_tail_cols=["SPY"])
    last_valid, value_at_max = hc._column_last_valid(p, "SPY")
    assert last_valid == pd.bdate_range(end=FRESH_END, periods=2)[0].normalize()
    assert value_at_max is None  # NaN at the file's max date


def test_column_last_valid_fresh(tmp_path):
    p = tmp_path / "x.parquet"
    _write_wide(p, FRESH_END, ["SPY"])
    last_valid, value_at_max = hc._column_last_valid(p, "SPY")
    assert last_valid == FRESH_END.normalize()
    assert value_at_max is not None


# ---------- core_feature_staleness vs real repo data ------------------------


def test_core_staleness_structure_real_repo():
    """Resolver returns one row per CORE feature, stalest first (no network)."""
    core = hc.load_yaml(ROOT / "configs" / "feature_sets.yaml")["core"]
    rows = hc.core_feature_staleness(ROOT, TODAY)

    assert len(rows) == len(core)
    assert {name for name, _, _ in rows} == set(core)
    for name, last, age in rows:
        assert isinstance(name, str)
        assert (last is None) == (age is None)
        if last is not None:
            assert isinstance(last, pd.Timestamp)
            assert isinstance(age, int)
            assert age >= 0

    ages = [age if age is not None else 10**9 for _, _, age in rows]
    assert ages == sorted(ages, reverse=True)  # stalest first
