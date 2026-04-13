"""Smoke tests: fetcher wrappers import and have the expected API surface."""
from __future__ import annotations

from data.fetchers import yahoo_prices, fred_macro, fomc_calendar


def test_yahoo_module_api() -> None:
    """Module exposes fetch_adj_close and load_cached."""
    assert callable(yahoo_prices.fetch_adj_close)
    assert callable(yahoo_prices.load_cached)


def test_fred_module_api() -> None:
    """Module exposes refresh_series and load_cached."""
    assert callable(fred_macro.refresh_series)
    assert callable(fred_macro.load_cached)


def test_fomc_module_api() -> None:
    """Module exposes load_fomc_dates and tolerates missing files."""
    assert callable(fomc_calendar.load_fomc_dates)
    # missing file -> empty list, not crash
    assert fomc_calendar.load_fomc_dates("/no/such/path.parquet") == []
