import pandas as pd
import datetime
from typing import Optional


def today_str() -> str:
    """Return today's date as YYYY-MM-DD string."""
    return datetime.datetime.now().strftime("%Y-%m-%d")


def to_eastern(dt: datetime.datetime) -> datetime.datetime:
    """Convert any datetime to US Eastern time."""
    import pytz
    eastern = pytz.timezone("America/New_York")
    if dt.tzinfo is None:
        return eastern.localize(dt)
    return dt.astimezone(eastern)


def is_market_open() -> bool:
    """Rough check if NYSE market is currently open."""
    now = to_eastern(datetime.datetime.now())
    if now.weekday() >= 5:  # Saturday / Sunday
        return False
    open_time = now.replace(hour=9, minute=30, second=0, microsecond=0)
    close_time = now.replace(hour=16, minute=0, second=0, microsecond=0)
    return open_time <= now <= close_time


def walk_forward_splits(
    start: str,
    end: str,
    train_months: int,
    val_months: int,
    test_months: int,
    step_months: int,
) -> list[dict]:
    """
    Generate walk-forward time splits.

    Returns:
        List of dicts with keys: train_start, train_end, val_start,
        val_end, test_start, test_end  (all as pandas Timestamps)
    """
    splits = []
    cursor = pd.Timestamp(start)
    end_ts = pd.Timestamp(end) if end else pd.Timestamp(today_str())

    while True:
        train_start = cursor
        train_end = train_start + pd.DateOffset(months=train_months)
        val_start = train_end
        val_end = val_start + pd.DateOffset(months=val_months)
        test_start = val_end
        test_end = test_start + pd.DateOffset(months=test_months)

        if test_end > end_ts:
            break

        splits.append({
            "train_start": train_start,
            "train_end": train_end,
            "val_start": val_start,
            "val_end": val_end,
            "test_start": test_start,
            "test_end": test_end,
        })
        cursor += pd.DateOffset(months=step_months)

    return splits
