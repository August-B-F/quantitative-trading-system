"""Live-freshness regression tests — the live path must never trade stale data.

Uses the real on-disk artifacts under data/features/ (offline, no network):
the master panel is frozen at 2026-04-10 while the nightly-rebuilt price
feature parquets run through late June 2026. ``load_panel(live_extend=True)``
must surface the fresh dates; the research path must stay byte-identical.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from data.pipeline import load_config, load_panel

PANEL_RAW_MAX = pd.Timestamp("2026-04-10")
MIN_LIVE_DATE = pd.Timestamp("2026-06-25")


@pytest.fixture(scope="module")
def cfg() -> dict:
    return load_config(ROOT)


@pytest.fixture(scope="module")
def live_bundle(cfg):
    return load_panel(ROOT, cfg, live_extend=True)


def test_live_extend_reaches_fresh_dates(live_bundle) -> None:
    """Extended panel covers the fresh price-feature dates with a valid SMA gate input."""
    as_of = live_bundle.dates.max()
    assert as_of >= MIN_LIVE_DATE, f"live as_of stuck at {as_of}"

    spy_dist = live_bundle.spy_dist_sma200[-1]
    assert not np.isnan(spy_dist), "quality_dist_sma200__SPY is NaN at as_of"
    assert spy_dist > 0, "SPY should be above its SMA200 in the on-disk data"
    # the panel column itself must match (that is what strategies read)
    assert live_bundle.df["quality_dist_sma200__SPY"].iloc[-1] == pytest.approx(spy_dist)

    fr = live_bundle.freshness
    assert fr is not None
    assert fr["panel_raw_max"] == PANEL_RAW_MAX
    assert fr["as_of"] == as_of
    assert fr["extended_days"] == len(live_bundle.dates) - 5351


def test_momentum_rank_at_live_tail(live_bundle) -> None:
    """63d momentum at the live as_of ranks SOXX above XLE (fresh, not April, data)."""
    r63 = live_bundle.returns[63]
    row = r63.loc[live_bundle.dates.max()]
    assert not np.isnan(row["SOXX"]) and not np.isnan(row["XLE"])
    assert row["SOXX"] > row["XLE"]


def test_research_path_unchanged(cfg) -> None:
    """live_extend=False keeps the raw panel index (byte-identical research path)."""
    b = load_panel(ROOT, cfg)
    assert b.dates.max() == PANEL_RAW_MAX
    assert b.freshness is None


def test_signal_freshness_gate() -> None:
    """The pure gate helper rejects a 5-trading-day-old as_of, accepts 1-day-old."""
    import run_rebalance as rr

    today = pd.Timestamp("2026-07-02")
    tdays = rr.trading_days(today - pd.Timedelta(days=30), today)
    assert len(tdays) >= 7
    stale_as_of = tdays[-6]   # 5 trading days behind the last trading day
    fresh_as_of = tdays[-2]   # 1 trading day behind
    assert not rr.signal_is_fresh(stale_as_of, today, max_lag_td=3)
    assert rr.signal_is_fresh(fresh_as_of, today, max_lag_td=3)
    assert rr.signal_is_fresh(tdays[-1], today, max_lag_td=3)
