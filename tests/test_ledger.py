"""Acceptance tests for the compounded-ledger backtester (src/backtest/ledger.py).

Run against the REAL on-disk parquets under data/clean/prices (offline).
The SPY replication test is the canary — it would have caught the old
engine's tiling bug by comparing engine NAV compounding against the raw
adj_close total return.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from backtest.ledger import LedgerResult, load_prices, run_ledger_backtest

ROOT = Path(__file__).resolve().parents[1]

STATS_KEYS = {
    "cagr", "vol", "sharpe", "max_dd", "ann_turnover",
    "ann_cost_drag", "n_rebalances", "start", "end",
}


@pytest.fixture(scope="module")
def prices():
    return load_prices(ROOT, ["SPY", "SHY", "SHV", "AGG"])


def _alternating_schedule(prices) -> list[tuple[pd.Timestamp, dict[str, float]]]:
    """100% SPY / 100% SHY alternating at every month-end, 2019-2021 (3 years)."""
    cal = prices["SPY"].index
    cal = cal[(cal >= pd.Timestamp("2019-01-01")) & (cal <= pd.Timestamp("2021-12-31"))]
    month_ends = cal.to_series().groupby(cal.to_period("M")).last()
    return [
        (pd.Timestamp(d), {"SPY": 1.0} if i % 2 == 0 else {"SHY": 1.0})
        for i, d in enumerate(month_ends)
    ]


def test_spy_replication_canary(prices) -> None:
    """Buy-and-hold SPY at 0 bps must match SPY adj_close total return within 10 bps/yr."""
    spy = prices["SPY"]["adj_close"]
    first = spy.index[0]
    res = run_ledger_backtest([(first, {"SPY": 1.0})], prices, cost_bps=0.0, benchmarks=())
    nav = res.nav
    assert isinstance(res, LedgerResult)
    assert nav.iloc[0] == 1.0
    assert nav.index[0] == first
    years = (nav.index[-1] - nav.index[0]).days / 365.25
    assert years > 15  # full history, not a truncated/tiled span
    engine_ann = nav.iloc[-1] ** (1.0 / years) - 1.0
    spy_aligned = spy.reindex(nav.index).ffill()
    spy_ann = (spy_aligned.iloc[-1] / spy_aligned.iloc[0]) ** (1.0 / years) - 1.0
    assert abs(engine_ann - spy_ann) < 0.0010, (
        f"engine {engine_ann:.4%}/yr vs SPY adj_close {spy_ann:.4%}/yr — drift > 10 bps/yr"
    )
    assert set(res.stats) == STATS_KEYS
    assert res.stats["n_rebalances"] == 1


def test_cost_sanity_alternating(prices) -> None:
    """NAV gap between 0 and 10 bps must be ~ 2 * 0.001 * n_rebalances (25% tol)."""
    sched = _alternating_schedule(prices)
    kwargs = dict(prices=prices, end="2021-12-31", benchmarks=())
    res0 = run_ledger_backtest(sched, cost_bps=0.0, **kwargs)
    res10 = run_ledger_backtest(sched, cost_bps=10.0, **kwargs)
    n_reb = res10.stats["n_rebalances"]
    assert n_reb >= 30
    gap = res0.nav.iloc[-1] / res10.nav.iloc[-1] - 1.0
    expected = 2 * 0.001 * n_reb
    assert abs(gap - expected) / expected < 0.25, (
        f"cost gap {gap:.4f} vs expected {expected:.4f} for {n_reb} rebalances"
    )
    assert res10.stats["ann_cost_drag"] > 0
    assert res0.stats["ann_cost_drag"] == 0.0


def test_drift_matches_hand_computed(prices) -> None:
    """50/50 SPY/AGG with no further rebalances drifts by relative adjusted performance."""
    d0 = pd.Timestamp("2015-01-30")
    res = run_ledger_backtest(
        [(d0, {"SPY": 0.5, "AGG": 0.5})], prices,
        cost_bps=0.0, start=d0, end="2016-12-30", benchmarks=(),
    )
    fill_date = res.trades["date"].min()
    assert fill_date > d0

    def adj_open(t: str) -> float:
        row = prices[t].loc[fill_date]
        return float(row["open"] * row["adj_close"] / row["close"])

    sampled = pd.Timestamp("2016-06-30")
    v_spy = 0.5 * float(prices["SPY"].loc[sampled, "adj_close"]) / adj_open("SPY")
    v_agg = 0.5 * float(prices["AGG"].loc[sampled, "adj_close"]) / adj_open("AGG")
    expected_w_spy = v_spy / (v_spy + v_agg)
    assert abs(res.weights.loc[sampled, "SPY"] - expected_w_spy) < 1e-9
    assert abs(res.weights.loc[sampled, "AGG"] - (1.0 - expected_w_spy)) < 1e-9
    # only the initial fill — no phantom rebalancing between decisions
    assert res.stats["n_rebalances"] == 1


def test_no_nan_and_weights_sum_to_one(prices) -> None:
    """No NaN anywhere in NAV; every daily weights row sums to 1 +- 1e-6."""
    res = run_ledger_backtest(_alternating_schedule(prices), prices, cost_bps=10.0, end="2021-12-31", benchmarks=())
    assert res.nav.notna().all()
    assert res.weights.notna().all().all()
    row_sums = res.weights.sum(axis=1)
    assert (row_sums - 1.0).abs().max() < 1e-6
    assert list(res.trades.columns) == ["date", "ticker", "side", "notional_frac", "cost_frac"]
    assert set(res.trades["side"].unique()) <= {"buy", "sell"}


def test_determinism(prices) -> None:
    """Same inputs -> identical NAV twice."""
    sched = _alternating_schedule(prices)
    nav_a = run_ledger_backtest(sched, prices, cost_bps=10.0, end="2021-12-31", benchmarks=()).nav
    nav_b = run_ledger_backtest(sched, prices, cost_bps=10.0, end="2021-12-31", benchmarks=()).nav
    pd.testing.assert_series_equal(nav_a, nav_b, check_exact=True)


def test_benchmarks_through_same_engine(prices) -> None:
    """Default benchmarks come back aligned to nav.index and start at ~1.0."""
    res = run_ledger_backtest(
        [(pd.Timestamp("2020-01-31"), {"SPY": 1.0})], prices,
        cost_bps=10.0, start="2020-01-31", end="2022-12-30",
    )
    assert set(res.benchmarks) == {"SPY", "60_40"}
    for name, bnav in res.benchmarks.items():
        assert bnav.index.equals(res.nav.index), f"benchmark '{name}' not aligned to nav.index"
        assert bnav.iloc[0] == pytest.approx(1.0), f"benchmark '{name}' does not start at 1.0"
        assert bnav.notna().all()
    # 60/40 rebalances monthly, so it must differ from buy-and-hold SPY
    assert not np.allclose(res.benchmarks["SPY"].values, res.benchmarks["60_40"].values)


def test_schedule_validation(prices) -> None:
    """Negative weight -> ValueError; unknown ticker -> KeyError naming it; sum > 1 -> ValueError."""
    d = pd.Timestamp("2020-01-31")
    with pytest.raises(ValueError):
        run_ledger_backtest([(d, {"SPY": -0.5, "SHY": 1.5})], prices, benchmarks=())
    with pytest.raises(KeyError, match="NOPE"):
        run_ledger_backtest([(d, {"NOPE": 1.0})], prices, benchmarks=())
    with pytest.raises(ValueError):
        run_ledger_backtest([(d, {"SPY": 0.8, "SHY": 0.8})], prices, benchmarks=())


def test_partial_weights_remainder_to_cash(prices) -> None:
    """Weights summing to < 1 leave the remainder in the cash ticker (SHV)."""
    res = run_ledger_backtest(
        [(pd.Timestamp("2020-01-31"), {"SPY": 0.7})], prices,
        cost_bps=0.0, end="2020-06-30", benchmarks=(),
    )
    fill_date = res.trades["date"].min()
    assert res.weights.loc[fill_date, "SHV"] == pytest.approx(0.3, abs=0.01)
    assert (res.weights.sum(axis=1) - 1.0).abs().max() < 1e-6
