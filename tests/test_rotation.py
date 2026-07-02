"""Spec tests for the blend_126_252 rotation candidate (src/strategy/rotation.py)."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from strategy.rotation import (
    ROTATION_UNIVERSE,
    blend_rotation_weights,
    blend_scores,
    build_tranched_schedules,
    gate_risk_off,
    month_end_offset_dates,
)


def _synthetic_prices(n_days: int = 700, seed: int = 7) -> dict:
    """Deterministic OHLC dict for the universe + SPY with distinct drifts."""
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


def test_truncation_invariance_no_lookahead() -> None:
    prices = _synthetic_prices()
    as_of = prices["SPY"].index[500]
    full = blend_rotation_weights(prices, as_of)
    truncated = {t: df[df.index <= as_of] for t, df in prices.items()}
    assert blend_rotation_weights(truncated, as_of) == full


def test_weights_sum_to_one_and_nonnegative() -> None:
    prices = _synthetic_prices()
    for i in (400, 450, 500, 550, 600, 650):
        w = blend_rotation_weights(prices, prices["SPY"].index[i])
        assert sum(w.values()) == pytest.approx(1.0, abs=1e-9)
        assert all(v >= 0 for v in w.values())
        assert set(w) <= set(ROTATION_UNIVERSE)


def test_scores_rank_best_asset_highest() -> None:
    # Near-zero noise so the drift ordering is deterministic.
    rng = np.random.default_rng(1)
    idx = pd.bdate_range("2020-01-01", periods=700)
    drifts = {
        "SOXX": 0.0012, "QQQ": 0.0008, "XLK": 0.0007, "VGT": 0.0006,
        "IGV": 0.0002, "XLE": -0.0004, "GLD": 0.0001, "SHY": 0.00005,
        "SPY": 0.0006,
    }
    prices = {}
    for t, mu in drifts.items():
        px = 100 * np.cumprod(1 + mu + rng.normal(0, 1e-5, 700))
        prices[t] = pd.DataFrame(
            {"open": px, "close": px, "adj_close": px}, index=idx
        )
    scores = blend_scores(prices, idx[600]).dropna()
    # SOXX has the strongest drift — it must carry the top blend rank.
    assert scores.idxmax() == "SOXX"
    assert scores.idxmin() == "XLE"
    # ranks average two legs over 8 assets: scores live in [1, 8]
    assert scores.between(1.0, 8.0).all()


def test_gate_sends_everything_to_shy() -> None:
    prices = _synthetic_prices()
    as_of = prices["SPY"].index[-1]
    # Crash SPY 30% below its SMA200 by scaling the recent tail.
    spy = prices["SPY"].copy()
    spy.loc[spy.index[-30]:, ["open", "close", "adj_close"]] *= 0.6
    prices["SPY"] = spy
    assert gate_risk_off(prices, as_of) is True
    assert blend_rotation_weights(prices, as_of) == {"SHY": 1.0}


def test_short_history_defaults_risk_off() -> None:
    prices = _synthetic_prices(n_days=120)  # < SMA200 window
    as_of = prices["SPY"].index[-1]
    assert blend_rotation_weights(prices, as_of) == {"SHY": 1.0}


def test_month_end_offsets_stagger_and_stay_on_calendar() -> None:
    prices = _synthetic_prices()
    cal = prices["SPY"].index
    d0 = month_end_offset_dates(cal, 0)
    d5 = month_end_offset_dates(cal, 5)
    assert d0.isin(cal).all() and d5.isin(cal).all()
    # Each offset-5 date is exactly 5 trading days after its month-end twin.
    for a, b in zip(d0[:-1], d5[:-1]):
        assert cal.get_loc(b) - cal.get_loc(a) == 5


def test_tranched_schedules_shape() -> None:
    prices = _synthetic_prices()
    schedules = build_tranched_schedules(
        prices, prices["SPY"].index[400], prices["SPY"].index[-1]
    )
    assert set(schedules) == {0, 5, 10, 15}
    for k, sched in schedules.items():
        assert len(sched) > 5
        for d, w in sched:
            assert sum(w.values()) == pytest.approx(1.0, abs=1e-9)
