"""Tests for the literature-parameterized sleeves (src/strategy/sleeves.py).

Real-data tests run against the on-disk parquets under data/clean/prices
(offline, like tests/test_ledger.py); the GEM and vol-target behavior
tests use deterministic synthetic fixtures.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from backtest.ledger import load_prices
from strategy.sleeves import (
    CASH,
    GEM_FALLBACK,
    TSMOM_UNIVERSE,
    build_schedule,
    gem_weights,
    tsmom_weights,
    two_sleeve_weights,
)

ROOT = Path(__file__).resolve().parents[1]
REAL_TICKERS = sorted(set(TSMOM_UNIVERSE) | {CASH, GEM_FALLBACK})


@pytest.fixture(scope="module")
def real_prices():
    return load_prices(ROOT, REAL_TICKERS)


# ---------- synthetic fixtures ------------------------------------------------

def _frame_from_rets(rets: np.ndarray, start: str = "2019-01-01") -> pd.DataFrame:
    """Price frame from a daily-return array; first bar is 100.0."""
    steps = np.concatenate([[0.0], np.asarray(rets, dtype=float)])
    path = 100.0 * np.cumprod(1.0 + steps)
    idx = pd.bdate_range(start, periods=len(path))
    return pd.DataFrame({"adj_close": path}, index=idx)


def _const_ret_prices(rets_by_ticker: dict[str, float], n: int = 320) -> dict:
    return {t: _frame_from_rets(np.full(n - 1, r)) for t, r in rets_by_ticker.items()}


def _alternating_prices(drift: float, amp: float, n: int = 320) -> dict:
    """All 9 TSMOM assets share one path: drift + amp*(-1)^t (in phase, so
    the portfolio vol does not diversify away). SHV/AGG grow smoothly."""
    t = np.arange(n - 1)
    risky = drift + amp * np.where(t % 2 == 0, 1.0, -1.0)
    prices = {tk: _frame_from_rets(risky) for tk in TSMOM_UNIVERSE}
    prices[CASH] = _frame_from_rets(np.full(n - 1, 0.0001))
    prices[GEM_FALLBACK] = _frame_from_rets(np.full(n - 1, 0.0002))
    return prices


# ---------- no-lookahead ------------------------------------------------------

@pytest.mark.parametrize("as_of", ["2019-06-28", "2021-12-31"])
def test_no_lookahead_truncation_invariance(real_prices, as_of) -> None:
    """Weights on full data == weights on data truncated at as_of."""
    ts = pd.Timestamp(as_of)
    truncated = {t: df.loc[:ts] for t, df in real_prices.items()}
    for fn in (tsmom_weights, gem_weights, two_sleeve_weights):
        full = fn(real_prices, ts)
        trunc = fn(truncated, ts)
        assert full == trunc, f"{fn.__name__} sees data after {as_of}"
        assert full, f"{fn.__name__} degenerate at {as_of}"


# ---------- weight sanity on real month-ends ----------------------------------

def test_weights_sum_to_one_and_nonnegative_on_month_ends(real_prices) -> None:
    """12 sampled month-ends: every sleeve's weights sum to 1 +- 1e-9, all >= 0."""
    schedule = build_schedule(real_prices, "2015-01-01", "2015-12-31", two_sleeve_weights)
    assert len(schedule) == 12
    for d, w in schedule:
        for weights in (w, tsmom_weights(real_prices, d), gem_weights(real_prices, d)):
            assert weights is not None
            assert abs(sum(weights.values()) - 1.0) <= 1e-9, f"sum != 1 at {d.date()}"
            assert all(x >= 0.0 for x in weights.values()), f"negative weight at {d.date()}"


# ---------- GEM behavior (synthetic) ------------------------------------------

def test_gem_picks_dominant_efa() -> None:
    """EFA outruns SPY and both beat cash -> GEM holds EFA."""
    prices = _const_ret_prices(
        {"SPY": 0.0005, "EFA": 0.0012, CASH: 0.00005, GEM_FALLBACK: 0.0001}
    )
    as_of = prices["SPY"].index[-1]
    assert gem_weights(prices, as_of) == {"EFA": 1.0}


def test_gem_falls_back_to_agg_when_both_below_cash() -> None:
    """Both risk legs below the cash return -> GEM parks in AGG."""
    prices = _const_ret_prices(
        {"SPY": -0.0005, "EFA": -0.0010, CASH: 0.0001, GEM_FALLBACK: 0.0001}
    )
    as_of = prices["SPY"].index[-1]
    assert gem_weights(prices, as_of) == {GEM_FALLBACK: 1.0}


def test_gem_insufficient_history_returns_none() -> None:
    """Fewer than lookback+1 bars -> None (build_schedule skips the date)."""
    prices = _const_ret_prices(
        {"SPY": 0.0005, "EFA": 0.0012, CASH: 0.00005, GEM_FALLBACK: 0.0001}, n=100
    )
    assert gem_weights(prices, prices["SPY"].index[-1]) is None


def test_tsmom_all_off_parks_in_cash() -> None:
    """Every asset below the cash hurdle -> the whole sleeve sits in SHV."""
    rets = {t: -0.0005 for t in TSMOM_UNIVERSE}
    rets[CASH] = 0.0001
    rets[GEM_FALLBACK] = 0.0001
    prices = _const_ret_prices(rets)
    assert tsmom_weights(prices, prices["SPY"].index[-1]) == {CASH: 1.0}


# ---------- vol targeting (synthetic) ------------------------------------------

def test_vol_target_scales_down_in_high_vol_regime() -> None:
    """~63% realized vol >> 10% target -> a single scale < 1, excess to SHV."""
    prices = _alternating_prices(drift=0.002, amp=0.04)
    as_of = prices["SPY"].index[-1]
    ts = tsmom_weights(prices, as_of)
    gem = gem_weights(prices, as_of)
    combined: dict[str, float] = {}
    for t, w in ts.items():
        combined[t] = combined.get(t, 0.0) + 0.6 * w
    for t, w in gem.items():
        combined[t] = combined.get(t, 0.0) + 0.4 * w
    assert CASH not in combined  # all assets ON, GEM in a risk leg

    out = two_sleeve_weights(prices, as_of)
    scales = {t: out[t] / combined[t] for t in combined}
    scale = next(iter(scales.values()))
    assert all(abs(s - scale) < 1e-12 for s in scales.values()), "scale not uniform"
    assert 0.0 < scale < 1.0, f"expected de-risking, got scale={scale}"
    assert out[CASH] == pytest.approx(1.0 - scale * sum(combined.values()), abs=1e-9)
    assert out[CASH] > 0.5  # ~63% vol vs 10% target -> mostly cash


def test_vol_target_capped_at_one_in_low_vol_regime() -> None:
    """~1.6% realized vol < 10% target -> scale == 1 (no leverage), weights
    equal the unscaled 0.6/0.4 combination exactly."""
    prices = _alternating_prices(drift=0.0004, amp=0.001)
    as_of = prices["SPY"].index[-1]
    ts = tsmom_weights(prices, as_of)
    gem = gem_weights(prices, as_of)
    combined: dict[str, float] = {}
    for t, w in ts.items():
        combined[t] = combined.get(t, 0.0) + 0.6 * w
    for t, w in gem.items():
        combined[t] = combined.get(t, 0.0) + 0.4 * w

    out = two_sleeve_weights(prices, as_of)
    for t, w in combined.items():
        assert out[t] == pytest.approx(w, abs=1e-12), f"{t} rescaled despite low vol"
    assert out[CASH] == pytest.approx(1.0 - sum(combined.values()), abs=1e-9)
