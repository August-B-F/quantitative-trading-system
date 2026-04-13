"""FOMC calendar loader. Reads data/clean/calendar/events.parquet.

Expected schema: DatetimeIndex or 'date' column + an event type column
identifying FOMC decision days. The production panel already has
timing__is_fomc_day — this module exposes both a date list (for audit) and
the boolean mask used by the deferral rule (§2.7).
"""
from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

log = logging.getLogger(__name__)


def load_fomc_dates(path: Path) -> list[pd.Timestamp]:
    """Load all FOMC decision dates from the calendar parquet."""
    p = Path(path)
    if not p.exists():
        log.warning("FOMC calendar not found: %s — deferral rule will not fire", p)
        return []
    df = pd.read_parquet(p)
    # Accept a few schemas
    if "date" in df.columns:
        df = df.set_index("date")
    type_col = next((c for c in df.columns if "type" in c.lower() or "event" in c.lower()), None)
    if type_col is None:
        return list(pd.to_datetime(df.index).unique())
    mask = df[type_col].astype(str).str.lower().str.contains("fomc")
    return list(pd.to_datetime(df.index[mask]).unique())
