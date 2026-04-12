import pandas as pd
from datetime import datetime, timedelta
from typing import List, Tuple


def market_date_range(start: str, end: str = None) -> pd.DatetimeIndex:
    """
    Returns business-day date range between start and end (inclusive).
    """
    if end is None:
        end = datetime.today().strftime("%Y-%m-%d")
    return pd.bdate_range(start=start, end=end)


def walk_forward_windows(
    dates: pd.DatetimeIndex,
    train_months: int = 18,
    val_months: int = 3,
    test_months: int = 1,
    step_months: int = 1,
) -> List[Tuple[pd.DatetimeIndex, pd.DatetimeIndex, pd.DatetimeIndex]]:
    """
    Generates (train_dates, val_dates, test_dates) tuples for walk-forward training.
    Each window slides forward by step_months.
    """
    windows = []
    start = dates[0]
    total_months = train_months + val_months + test_months

    while True:
        train_end = start + pd.DateOffset(months=train_months)
        val_end = train_end + pd.DateOffset(months=val_months)
        test_end = val_end + pd.DateOffset(months=test_months)

        if test_end > dates[-1]:
            break

        train_idx = dates[(dates >= start) & (dates < train_end)]
        val_idx = dates[(dates >= train_end) & (dates < val_end)]
        test_idx = dates[(dates >= val_end) & (dates < test_end)]

        if len(train_idx) > 0 and len(val_idx) > 0 and len(test_idx) > 0:
            windows.append((train_idx, val_idx, test_idx))

        start += pd.DateOffset(months=step_months)

    return windows


def is_market_open() -> bool:
    """
    Returns True if current time is within regular US market hours (Mon-Fri 9:30-16:00 ET).
    """
    import pytz
    tz = pytz.timezone("America/New_York")
    now = datetime.now(tz)
    if now.weekday() >= 5:
        return False
    market_open = now.replace(hour=9, minute=30, second=0, microsecond=0)
    market_close = now.replace(hour=16, minute=0, second=0, microsecond=0)
    return market_open <= now <= market_close


def next_market_open() -> datetime:
    """
    Returns datetime of the next market open (9:30 ET).
    """
    import pytz
    tz = pytz.timezone("America/New_York")
    now = datetime.now(tz)
    candidate = now.replace(hour=9, minute=30, second=0, microsecond=0)
    if now >= candidate:
        candidate += timedelta(days=1)
    while candidate.weekday() >= 5:
        candidate += timedelta(days=1)
    return candidate
