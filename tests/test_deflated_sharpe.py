"""Tests for scripts/research/deflated_sharpe.py (Bailey & Lopez de Prado DSR)."""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "research" / "deflated_sharpe.py"
LEDGER = ROOT / "results" / "TRIAL_LEDGER.csv"


def _load_module():
    spec = importlib.util.spec_from_file_location("deflated_sharpe", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ds = _load_module()


class TestDeflationBitesWhenTrialsExceedOne:
    def test_dsr_below_psr_for_multiple_trials(self):
        sr, T = 0.8, 96
        psr = ds.probabilistic_sharpe(sr, 0.0, T)
        dsr = ds.deflated_sharpe(sr, T, skew=0.0, kurt=3.0,
                                 n_trials=316, sr_variance_across_trials=0.05)
        assert dsr < psr

    def test_dsr_equals_psr_for_single_trial(self):
        sr, T = 0.8, 96
        psr = ds.probabilistic_sharpe(sr, 0.0, T)
        dsr = ds.deflated_sharpe(sr, T, skew=0.0, kurt=3.0,
                                 n_trials=1, sr_variance_across_trials=0.05)
        assert dsr == pytest.approx(psr)

    def test_dsr_monotone_decreasing_in_trials(self):
        sr, T, var = 0.8, 96, 0.05
        dsrs = [ds.deflated_sharpe(sr, T, 0.0, 3.0, n, var) for n in (2, 10, 100, 1000)]
        assert all(a > b for a, b in zip(dsrs, dsrs[1:]))


class TestExpectedMaxIsTheCoinflipPoint:
    def test_dsr_is_half_at_analytic_expected_max(self):
        n, var, T = 316, 0.09, 96
        sr0 = ds.expected_max_sharpe(n, var)
        dsr = ds.deflated_sharpe(sr0, T, skew=0.0, kurt=3.0,
                                 n_trials=n, sr_variance_across_trials=var)
        assert abs(dsr - 0.5) < 0.15

    def test_dsr_near_half_for_simulated_noise_max(self):
        """Best-of-N pure-noise Sharpes should score DSR ~ 0.5, not skill."""
        rng = np.random.default_rng(42)
        n_trials, T = 316, 96
        dsrs = []
        for _ in range(20):
            rets = rng.normal(0.0, 0.04, size=(n_trials, T))
            srs = rets.mean(axis=1) / rets.std(axis=1, ddof=1)
            dsrs.append(ds.deflated_sharpe(
                float(srs.max()), T, skew=0.0, kurt=3.0,
                n_trials=n_trials, sr_variance_across_trials=float(srs.var(ddof=1)),
            ))
        assert abs(float(np.mean(dsrs)) - 0.5) < 0.15


class TestLedgerAndCli:
    def test_ledger_stats(self):
        n_trials, var = ds.ledger_stats(LEDGER)
        assert n_trials >= 600  # 316 MASTER_SUMMARY + ~300 autonomous
        assert var > 0

    def test_cli_runs_on_seeded_ledger_and_prints_a_number(self):
        proc = subprocess.run(
            [sys.executable, str(SCRIPT),
             "--sharpe", "0.962", "--T", "96", "--ledger", str(LEDGER)],
            capture_output=True, text=True, timeout=120,
        )
        assert proc.returncode == 0, proc.stderr
        dsr_lines = [l for l in proc.stdout.splitlines() if l.startswith("DSR:")]
        assert len(dsr_lines) == 1
        dsr = float(dsr_lines[0].split(":")[1])
        assert 0.0 <= dsr <= 1.0

    def test_cli_explicit_trials_override_ledger(self):
        proc = subprocess.run(
            [sys.executable, str(SCRIPT),
             "--sharpe", "0.962", "--T", "96", "--trials", "316",
             "--ledger", str(LEDGER)],
            capture_output=True, text=True, timeout=120,
        )
        assert proc.returncode == 0, proc.stderr
        assert "n_trials=316" in proc.stdout
