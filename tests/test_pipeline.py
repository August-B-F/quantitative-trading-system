"""Smoke test: data pipeline loads the master panel bundle."""
from __future__ import annotations

from pathlib import Path

from data.pipeline import load_config, load_panel

ROOT = Path(__file__).resolve().parents[1]


def test_load_panel() -> None:
    """Panel loads with expected arrays and coverage."""
    cfg = load_config(ROOT)
    b = load_panel(ROOT, cfg)
    assert len(b.dates) > 5000
    assert 63 in b.returns and 21 in b.returns
    assert "SOXX" in b.fwd21 and "SHY" in b.fwd21
    assert b.spy_dist_sma200.shape == (len(b.dates),)
    assert b.is_fomc_day.dtype == bool
