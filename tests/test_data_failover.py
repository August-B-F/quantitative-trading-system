"""Data pipeline failover tests.

Covers auto-failover from Yahoo → Twelve Data → cache, plus BLS CPI
fallback and the source_health_report() probe surface.

Live-API tests (fetch real SPY from Twelve Data, real CPI from BLS)
are gated on env vars and skip cleanly in CI.
"""
from __future__ import annotations

import os
from pathlib import Path
from unittest import mock

import numpy as np
import pandas as pd
import pytest

from data import pipeline
from data.fetchers import twelve_data, bls as bls_mod

ROOT = Path(__file__).resolve().parents[1]


# ---------- helpers ----------------------------------------------------------


def _fake_panel(tickers, days=30, latest=None):
    """Build a dict[ticker -> OHLCV DataFrame] that looks like yahoo_prices.fetch_ohlcv output."""
    if latest is None:
        latest = pd.Timestamp.utcnow().normalize().tz_localize(None)
    idx = pd.bdate_range(end=latest, periods=days)
    n = len(idx)
    out = {}
    for t in tickers:
        df = pd.DataFrame(
            {
                "open": np.linspace(100, 110, n),
                "high": np.linspace(101, 111, n),
                "low": np.linspace(99, 109, n),
                "close": np.linspace(100, 110, n),
                "adj_close": np.linspace(100, 110, n),
                "volume": np.ones(n) * 1e6,
            },
            index=idx,
        )
        out[t] = df
    return out


def _tiny_cfg(tmp_root: Path) -> dict:
    prices_dir = tmp_root / "data/clean/prices"
    prices_dir.mkdir(parents=True, exist_ok=True)
    return {
        "universe": ["SPY", "QQQ"],
        "reference_index": "SPY",
        "feature_extras": [],
        "paths": {"prices_clean": "data/clean/prices"},
    }


# ---------- fresh-panel helper -----------------------------------------------


def test_panels_are_fresh_true() -> None:
    panels = _fake_panel(["SPY"])
    assert pipeline._panels_are_fresh(panels) is True


def test_panels_are_fresh_false_when_stale() -> None:
    stale = pd.Timestamp.utcnow().normalize().tz_localize(None) - pd.Timedelta(days=60)
    panels = _fake_panel(["SPY"], latest=stale)
    assert pipeline._panels_are_fresh(panels) is False


def test_panels_are_fresh_false_when_empty() -> None:
    assert pipeline._panels_are_fresh({}) is False


# ---------- failover: Yahoo → Twelve Data ------------------------------------


def test_refresh_prices_uses_yahoo_when_fresh(tmp_path: Path) -> None:
    cfg = _tiny_cfg(tmp_path)
    panels = _fake_panel(["SPY", "QQQ", "^VIX"])
    with mock.patch("src.data.fetchers.yahoo_prices.fetch_ohlcv", return_value=panels):
        status = pipeline._refresh_prices(tmp_path, cfg)
    assert status["status"] == "ok"
    assert status["source"] == "yahoo"


def test_refresh_prices_falls_through_to_twelve_data(tmp_path: Path) -> None:
    cfg = _tiny_cfg(tmp_path)
    td_panels = _fake_panel(["SPY", "QQQ", "^VIX"])
    with mock.patch("src.data.fetchers.yahoo_prices.fetch_ohlcv", return_value=None), \
         mock.patch("src.data.fetchers.twelve_data.fetch_ohlcv", return_value=td_panels):
        status = pipeline._refresh_prices(tmp_path, cfg)
    assert status["status"] == "degraded"
    assert status["source"] == "twelve_data"
    assert "backup" in status.get("warning", "")


def test_refresh_prices_stale_yahoo_triggers_backup(tmp_path: Path) -> None:
    """Yahoo returns data but the newest bar is weeks old — treat as failure."""
    cfg = _tiny_cfg(tmp_path)
    stale_date = pd.Timestamp.utcnow().normalize().tz_localize(None) - pd.Timedelta(days=45)
    yahoo_stale = _fake_panel(["SPY", "QQQ", "^VIX"], latest=stale_date)
    td_fresh = _fake_panel(["SPY", "QQQ", "^VIX"])
    with mock.patch("src.data.fetchers.yahoo_prices.fetch_ohlcv", return_value=yahoo_stale), \
         mock.patch("src.data.fetchers.twelve_data.fetch_ohlcv", return_value=td_fresh):
        status = pipeline._refresh_prices(tmp_path, cfg)
    assert status["source"] == "twelve_data"


# ---------- failover: both sources down → cache -----------------------------


def test_refresh_prices_falls_through_to_cache(tmp_path: Path) -> None:
    cfg = _tiny_cfg(tmp_path)
    # Seed the cache with a one-day-old parquet so staleness_days <= 2.
    prices_dir = tmp_path / "data/clean/prices"
    cached_latest = pd.Timestamp.utcnow().normalize().tz_localize(None) - pd.Timedelta(days=1)
    for t in ("SPY", "QQQ", "_VIX"):
        df = _fake_panel([t], latest=cached_latest)[t]
        df.to_parquet(prices_dir / f"{t}.parquet")
    with mock.patch("src.data.fetchers.yahoo_prices.fetch_ohlcv", return_value=None), \
         mock.patch("src.data.fetchers.twelve_data.fetch_ohlcv", return_value=None):
        status = pipeline._refresh_prices(tmp_path, cfg)
    assert status["status"] == "degraded"
    assert status["source"] == "cache"
    assert status["staleness_days"] <= 2


def test_refresh_prices_errors_when_cache_too_stale(tmp_path: Path) -> None:
    cfg = _tiny_cfg(tmp_path)
    prices_dir = tmp_path / "data/clean/prices"
    ancient = pd.Timestamp.utcnow().normalize().tz_localize(None) - pd.Timedelta(days=30)
    df = _fake_panel(["SPY"], latest=ancient)["SPY"]
    df.to_parquet(prices_dir / "SPY.parquet")
    with mock.patch("src.data.fetchers.yahoo_prices.fetch_ohlcv", return_value=None), \
         mock.patch("src.data.fetchers.twelve_data.fetch_ohlcv", return_value=None):
        status = pipeline._refresh_prices(tmp_path, cfg)
    assert status["status"] == "error"
    assert status["source"] == "none"


# ---------- fetcher API surface ---------------------------------------------


def test_twelve_data_module_api() -> None:
    assert callable(twelve_data.fetch_daily)
    assert callable(twelve_data.fetch_ohlcv)


def test_twelve_data_missing_key_returns_none(monkeypatch) -> None:
    monkeypatch.delenv("TWELVE_DATA_KEY", raising=False)
    assert twelve_data.fetch_daily("SPY") is None


def test_bls_module_api() -> None:
    assert callable(bls_mod.fetch_cpi)
    assert callable(bls_mod.fetch_cpi_yoy)


# ---------- source_health_report surface ------------------------------------


def test_source_health_report_returns_expected_keys() -> None:
    """All probes should be heavily mocked — test only the shape."""
    def fake_get(*a, **kw):
        r = mock.Mock()
        r.status_code = 200
        return r

    spy_df = pd.DataFrame(
        {"SPY": np.linspace(400, 410, 5)},
        index=pd.bdate_range(end=pd.Timestamp.utcnow().normalize().tz_localize(None), periods=5),
    )
    cpi_df = pd.DataFrame({"CUSR0000SA0": [300.0, 301.0]}, index=pd.to_datetime(["2026-02-28", "2026-03-31"]))

    with mock.patch("src.data.fetchers.yahoo_prices.fetch_adj_close", return_value=spy_df), \
         mock.patch("src.data.fetchers.bls.fetch_cpi", return_value=cpi_df), \
         mock.patch("requests.get", side_effect=fake_get):
        report = pipeline.source_health_report()

    assert "yahoo" in report
    assert "fred_csv" in report
    assert "bls" in report
    assert report["yahoo"]["status"] == "ok"
    assert report["bls"]["status"] == "ok"
    # twelve_data skipped if TWELVE_DATA_KEY unset
    assert report["twelve_data"]["status"] in ("ok", "down", "skipped")


# ---------- live-API tests (skip without keys) ------------------------------


@pytest.mark.skipif(not os.environ.get("TWELVE_DATA_KEY"), reason="TWELVE_DATA_KEY not set")
def test_live_twelve_data_spy() -> None:
    df = twelve_data.fetch_daily("SPY")
    assert df is not None and not df.empty
    assert "adj_close" in df.columns


@pytest.mark.skipif(not os.environ.get("TWELVE_DATA_KEY"), reason="TWELVE_DATA_KEY not set")
def test_live_twelve_data_matches_yahoo_spy() -> None:
    """Spot-check: SPY adj_close from Twelve Data should be within $0.50 of Yahoo on the same date."""
    from data.fetchers.yahoo_prices import fetch_ohlcv as yahoo_fetch
    start = (pd.Timestamp.utcnow() - pd.Timedelta(days=20)).date().isoformat()
    y = yahoo_fetch(["SPY"], start=start)
    td = twelve_data.fetch_daily("SPY", start=start)
    assert y is not None and "SPY" in y and td is not None
    common = y["SPY"].index.intersection(td.index)
    assert len(common) > 0
    diffs = (y["SPY"].loc[common, "adj_close"] - td.loc[common, "adj_close"]).abs()
    # Adjusted-close sources occasionally differ by vendor corporate-action timing,
    # so we allow a generous $0.50 tolerance on SPY (~$500 per share).
    assert diffs.max() < 0.50, f"max diff {diffs.max():.4f}"


def test_live_bls_cpi() -> None:
    """BLS v1 is keyless; if network is reachable this should work."""
    try:
        df = bls_mod.fetch_cpi(start_year=pd.Timestamp.utcnow().year - 1)
    except Exception:
        pytest.skip("bls unreachable")
    if df is None:
        pytest.skip("bls returned None (network/ratelimit)")
    assert not df.empty
    assert df.index.is_monotonic_increasing
