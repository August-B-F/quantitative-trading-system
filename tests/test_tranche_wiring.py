"""Spec tests: wiring the tranched blend rotation candidate into the live
orchestrator (scripts/run_rebalance.py rotation-engine path).

Covers: (a) account_target_from_state math, (b) tranche decision-day
selection and k mapping, (c) tranche-state JSON round-trip with atomic
write, (d) integration-lite compute_rotation_target on synthetic prices.
All offline — no network, no broker calls.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from strategy.rotation import (
    ROTATION_UNIVERSE,
    TRANCHE_OFFSETS,
    account_target_from_state,
    tranche_decision_days,
)

import run_rebalance as rr


# ---- (a) account_target_from_state math -------------------------------------

def test_fresh_state_all_shy_average() -> None:
    """Fresh (empty) state + a pure-SHY decision -> pure SHY account target."""
    target = account_target_from_state({}, 0, {"SHY": 1.0}, TRANCHE_OFFSETS)
    assert set(target) == {"SHY"}
    assert target["SHY"] == pytest.approx(1.0)


def test_one_tranche_updated_is_quarter_new_rest_shy() -> None:
    """One updated tranche on fresh state -> 25% new weights + 75% SHY."""
    new_w = {"QQQ": 0.5, "GLD": 0.5}
    target = account_target_from_state({}, 5, new_w, TRANCHE_OFFSETS)
    assert target["QQQ"] == pytest.approx(0.125)
    assert target["GLD"] == pytest.approx(0.125)
    assert target["SHY"] == pytest.approx(0.75)
    assert sum(target.values()) == pytest.approx(1.0)


def test_persisted_tranches_are_kept_and_replaced_tranche_is_dropped() -> None:
    state = {
        "tranches": {
            "0": {"QQQ": 1.0},
            "5": {"XLE": 1.0},
            "10": {"SHY": 1.0},
            "15": {"GLD": 1.0},
        },
        "updated": {"0": "2026-05-29"},
    }
    target = account_target_from_state(state, 10, {"SOXX": 1.0}, TRANCHE_OFFSETS)
    assert target == {
        "QQQ": pytest.approx(0.25),
        "XLE": pytest.approx(0.25),
        "SOXX": pytest.approx(0.25),
        "GLD": pytest.approx(0.25),
    }
    assert "SHY" not in target  # the replaced tranche's old SHY leg is gone


def test_unknown_tranche_k_raises() -> None:
    with pytest.raises(ValueError):
        account_target_from_state({}, 7, {"SHY": 1.0}, TRANCHE_OFFSETS)


# ---- (b) tranche decision-day selection --------------------------------------

def test_exactly_four_offset_days_trigger_with_right_k() -> None:
    """On a synthetic calendar, month-end + 0/5/10/15 td are the ONLY decision
    days in the [month_end, month_end+15] window, each mapped to its k."""
    cal = pd.DatetimeIndex(pd.bdate_range("2024-01-01", "2024-06-28"))
    decision = tranche_decision_days(cal, TRANCHE_OFFSETS)

    month_ends = cal.to_series().groupby(cal.to_period("M")).last()
    march_end = pd.Timestamp(month_ends[pd.Period("2024-03", freq="M")])
    p = cal.get_loc(march_end)

    for k in TRANCHE_OFFSETS:
        assert decision[cal[p + k]] == k, f"offset +{k} maps to wrong tranche"

    window = set(cal[p:p + 16])                      # month-end .. +15 td
    hits = sorted(d for d in decision if d in window)
    assert len(hits) == 4, f"expected exactly 4 decision days, got {hits}"
    # non-offset days inside the window must NOT trigger
    assert cal[p + 3] not in decision
    assert cal[p + 8] not in decision


def test_decision_days_cover_every_month() -> None:
    cal = pd.DatetimeIndex(pd.bdate_range("2024-01-01", "2024-12-31"))
    decision = tranche_decision_days(cal, TRANCHE_OFFSETS)
    k0_days = [d for d, k in decision.items() if k == 0]
    # one k=0 decision (the month-end itself) per calendar month
    assert len(k0_days) == 12
    month_ends = cal.to_series().groupby(cal.to_period("M")).last()
    assert set(k0_days) == set(pd.DatetimeIndex(month_ends.values))


def test_rotation_tranche_for_today_nyse() -> None:
    """Live helper agrees with the pure mapping on the real NYSE calendar."""
    # 2026-06-30 was the last NYSE trading day of June 2026 -> tranche 0.
    assert rr.rotation_tranche_for_today(
        pd.Timestamp("2026-06-30"), TRANCHE_OFFSETS) == 0

    cal = rr.trading_days("2026-04-01", "2026-06-30")
    decision = tranche_decision_days(cal, TRANCHE_OFFSETS)
    non_days = [d for d in cal
                if d not in decision and d > pd.Timestamp("2026-06-01")]
    day = non_days[-1]
    assert rr.rotation_tranche_for_today(day, TRANCHE_OFFSETS) is None
    # --force falls back to the most recent decision day's tranche
    most_recent = max(d for d in decision if d <= day)
    assert rr.rotation_tranche_for_today(
        day, TRANCHE_OFFSETS, force=True) == decision[most_recent]


# ---- (c) tranche-state round-trip (atomic write) ------------------------------

def test_state_roundtrip_atomic(tmp_path) -> None:
    path = tmp_path / "tranche_state.json"
    state = {
        "candidate_blend_rotation": {
            "tranches": {"0": {"QQQ": 0.6, "GLD": 0.4}},
            "updated": {"0": "2026-06-30"},
        }
    }
    rr.save_tranche_state(state, path)
    assert rr.load_tranche_state(path) == state
    # atomic write: the temp file was replaced, not left behind
    assert [p.name for p in tmp_path.iterdir()] == [path.name]
    # a rewrite fully replaces the previous content
    state2 = {"x": {"tranches": {"5": {"SHY": 1.0}}, "updated": {"5": "2026-07-08"}}}
    rr.save_tranche_state(state2, path)
    assert rr.load_tranche_state(path) == state2
    assert [p.name for p in tmp_path.iterdir()] == [path.name]


def test_missing_state_file_is_fresh_empty_state(tmp_path) -> None:
    assert rr.load_tranche_state(tmp_path / "does_not_exist.json") == {}


def test_corrupt_state_file_raises_not_resets(tmp_path) -> None:
    """A corrupt state file must raise (recorded as a signal error), never be
    silently treated as a fresh all-SHY book."""
    path = tmp_path / "tranche_state.json"
    path.write_text("{this is not json")
    with pytest.raises(ValueError):
        rr.load_tranche_state(path)


# ---- (d) integration-lite: compute_rotation_target ----------------------------

def _synthetic_prices(n_days: int = 700, seed: int = 7) -> dict:
    """Deterministic OHLC dict for the universe + SPY with distinct drifts
    (same construction as tests/test_rotation.py)."""
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2020-01-01", periods=n_days)
    drifts = {
        "SOXX": 0.0012, "QQQ": 0.0008, "XLK": 0.0007, "VGT": 0.0006,
        "IGV": 0.0002, "XLE": -0.0004, "GLD": 0.0001, "SHY": 0.00005,
        "SPY": 0.0006,
    }
    out = {}
    for t, mu in drifts.items():
        rets = mu + rng.normal(0, 0.01, n_days)
        px = 100 * np.cumprod(1 + rets)
        out[t] = pd.DataFrame(
            {"open": px, "close": px, "adj_close": px}, index=idx
        )
    return out


def test_compute_rotation_target_valid_weights() -> None:
    prices = _synthetic_prices()
    as_of = prices["SPY"].index[-1]
    target, new_w = rr.compute_rotation_target(
        prices, as_of, {}, 0, TRANCHE_OFFSETS
    )
    assert sum(new_w.values()) == pytest.approx(1.0, abs=1e-9)
    assert sum(target.values()) == pytest.approx(1.0, abs=1e-9)
    assert all(v >= 0 for v in target.values())
    assert set(target) <= set(ROTATION_UNIVERSE)
    # fresh state: the 3 untouched tranches stay 100% SHY -> at least 75% SHY
    assert target.get("SHY", 0.0) >= 0.75 - 1e-9


def test_compute_rotation_target_with_persisted_state() -> None:
    prices = _synthetic_prices()
    as_of = prices["SPY"].index[-1]
    state = {"tranches": {"0": {"QQQ": 1.0}, "5": {"XLE": 1.0}}}
    target, new_w = rr.compute_rotation_target(
        prices, as_of, state, 10, TRANCHE_OFFSETS
    )
    assert sum(target.values()) == pytest.approx(1.0, abs=1e-9)
    # persisted tranches contribute exactly 1/4 each
    assert target["QQQ"] >= 0.25 - 1e-9
    assert target["XLE"] >= 0.25 - 1e-9
    # missing tranche 15 defaults to SHY (1/4)
    assert target.get("SHY", 0.0) >= 0.25 - 1e-9
