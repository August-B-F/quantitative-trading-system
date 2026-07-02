"""Tests for scripts/run_race_report.py (loaded via importlib — scripts/ is
not a package). Runs the report against the REAL repo logs into a tmp output
path, and checks the EVALUATION.md tripwire logic on synthetic drawdown
fixtures.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "run_race_report.py"

_spec = importlib.util.spec_from_file_location("run_race_report", SCRIPT)
rr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rr)

REQUIRED_SECTIONS = [
    "# RACE REPORT",
    "## Data era",
    "## Per-arm equity vs SPY",
    "## Implementation fidelity",
    "## Drawdown vs tripwires",
    "## Execution errors",
    "## Race clock",
    "## Power-corrected verdict language",
]


# ---------- real logs ----------------------------------------------------------

def test_report_runs_against_real_logs(tmp_path):
    out = tmp_path / "RACE_REPORT.md"
    rc = rr.main(["--out", str(out)])
    assert rc == 0
    assert out.exists()
    text = out.read_text(encoding="utf-8")
    for section in REQUIRED_SECTIONS:
        assert section in text, f"missing section: {section}"
    # No --race-start => the current logs are the voided 2026 H1 record and
    # must be labelled as such.
    assert "PRE-RELAUNCH / VOIDED ERA" in text
    assert "race clock has NOT started" in text
    # The power-corrected verdict must carry the Study 13 numbers.
    assert "TIEBREAK only" in text
    assert "research/droplets/study13_race_power/" in text


def test_real_logs_error_count_positive(tmp_path):
    # The voided-era log contains known execution errors (insufficient buying
    # power on 2026-04-30 etc.) — the counter must see a non-zero total.
    entries = json.loads((ROOT / "logs" / "rebalance_log.json").read_text(encoding="utf-8"))
    table, total, _warn = rr.count_execution_errors(entries)
    assert total > 0
    assert len(table) > 0


# ---------- tripwire unit logic --------------------------------------------------

@pytest.mark.parametrize(
    "dd,flag",
    [
        (-0.10, "OK"),
        (-0.1999, "OK"),
        (-0.20, "DERISK"),   # boundary: -20% fires de-risk
        (-0.22, "DERISK"),
        (-0.25, "HALT"),     # boundary: -25% fires halt
        (-0.26, "HALT"),
    ],
)
def test_tripwire_flag(dd, flag):
    assert rr.tripwire_flag(dd) == flag


def test_drawdown_stats_uses_high_water_mark():
    # Rise to 120k then fall to 93k: DD vs HWM = 93/120-1 = -22.5% => DERISK
    eq = pd.Series([100_000.0, 120_000.0, 93_000.0])
    s = rr.drawdown_stats(eq, initial_capital=100_000.0)
    assert s["max_dd"] == pytest.approx(93_000.0 / 120_000.0 - 1.0)
    assert s["flag"] == "DERISK"


# ---------- synthetic end-to-end fixtures ----------------------------------------

def _write_fixtures(tmp_path, s1_path, s2_path):
    """Synthetic accounts + comparison + rebalance log; returns file paths."""
    accounts = tmp_path / "accounts.yaml"
    accounts.write_text(
        "initial_capital: 100000\n"
        "strategies:\n"
        "  arm_halted:\n    name: ARM_HALTED\n    slot: 1\n"
        "  arm_derisk:\n    name: ARM_DERISK\n    slot: 2\n",
        encoding="utf-8",
    )
    dates = ["2026-08-31", "2026-09-30", "2026-10-30"]
    comparison = tmp_path / "monthly_comparison.csv"
    rows = ["date,s1_equity,s2_equity,spy_return,spy_equity"]
    for d, e1, e2, se in zip(dates, s1_path, s2_path, [100000, 101000, 102000]):
        rows.append(f"{d},{e1},{e2},0.0,{se}")
    comparison.write_text("\n".join(rows) + "\n", encoding="utf-8")
    rlog = tmp_path / "rebalance_log.json"
    rlog.write_text(json.dumps([
        {"date": dates[0], "executed": True, "strategies": {
            "arm_halted": {"error": None, "success": True, "submit_errors": []},
            "arm_derisk": {"error": "http 403: boom", "success": False,
                           "submit_errors": [{"ticker": "XLE", "error_message": "x"}]},
        }, "data_warnings": []},
    ]), encoding="utf-8")
    return accounts, comparison, rlog


def test_tripwires_fire_on_synthetic_drawdowns(tmp_path):
    # s1 falls to 74k (-26% => HALT); s2 to 79k (-21% => DERISK).
    accounts, comparison, rlog = _write_fixtures(
        tmp_path, [100_000, 90_000, 74_000], [100_000, 95_000, 79_000]
    )
    out = tmp_path / "report.md"
    rc = rr.main([
        "--out", str(out), "--comparison", str(comparison),
        "--rebalance-log", str(rlog), "--accounts", str(accounts),
        "--race-start", "2026-08-01",
    ])
    assert rc == 0
    text = out.read_text(encoding="utf-8")
    dd_section = text.split("## Drawdown vs tripwires")[1].split("## ")[0]
    halted_row = next(l for l in dd_section.splitlines() if l.startswith("| ARM_HALTED |"))
    derisk_row = next(l for l in dd_section.splitlines() if l.startswith("| ARM_DERISK |"))
    assert "**HALT**" in halted_row
    assert "**DERISK**" in derisk_row
    assert "Tripwire action required: YES" in text
    # race clock: 3 distinct months elapsed of 12
    assert "Months elapsed: 3 / 12" in text
    assert "Months remaining: 9" in text
    # error tally: 1 strategy error + 1 submit error = 2
    assert "**2**" in text
    # race started => no voided-era label
    assert "PRE-RELAUNCH / VOIDED ERA" not in text


def test_no_tripwire_on_healthy_synthetic(tmp_path):
    accounts, comparison, rlog = _write_fixtures(
        tmp_path, [100_000, 104_000, 103_000], [100_000, 99_000, 101_000]
    )
    out = tmp_path / "report.md"
    rc = rr.main([
        "--out", str(out), "--comparison", str(comparison),
        "--rebalance-log", str(rlog), "--accounts", str(accounts),
        "--race-start", "2026-08-01",
    ])
    assert rc == 0
    text = out.read_text(encoding="utf-8")
    assert "Tripwire action required: none." in text
    assert "**HALT**" not in text and "**DERISK**" not in text
