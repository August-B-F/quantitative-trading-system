from datetime import datetime, date, timedelta
from typing import List, Tuple
import pandas as pd
import pytz


NY_TZ = pytz.timezone("America/New_York")


def now_ny() -> datetime:
    return datetime.now(NY_TZ)


def today_str() -> str:
    return now_ny().strftime("%Y-%m-%d")


def is_market_hours() -> bool:
    now = now_ny()
    if now.weekday() >= 5:
        return False
    market_open = now.replace(hour=9, minute=30, second=0, microsecond=0)
    market_close = now.replace(hour=16, minute=0, second=0, microsecond=0)
    return market_open <= now <= market_close


def walk_forward_windows(
    start_date: str,
    end_date: str,
    train_months: int,
    val_months: int,
    test_months: int,
    step_months: int,
) -> List[Tuple[str, str, str, str, str, str]]:
    """
    Generate (train_start, train_end, val_start, val_end, test_start, test_end)
    date tuples for walk-forward validation.
    """
    windows = []
    start = pd.Timestamp(start_date)
    end = pd.Timestamp(end_date)

    cursor = start
    while True:
        train_start = cursor
        train_end = cursor + pd.DateOffset(months=train_months) - timedelta(days=1)
        val_start = train_end + timedelta(days=1)
        val_end = val_start + pd.DateOffset(months=val_months) - timedelta(days=1)
        test_start = val_end + timedelta(days=1)
        test_end = test_start + pd.DateOffset(months=test_months) - timedelta(days=1)

        if test_end > end:
            break

        windows.append((
            train_start.strftime("%Y-%m-%d"),
            train_end.strftime("%Y-%m-%d"),
            val_start.strftime("%Y-%m-%d"),
            val_end.strftime("%Y-%m-%d"),
            test_start.strftime("%Y-%m-%d"),
            test_end.strftime("%Y-%m-%d"),
        ))
        cursor += pd.DateOffset(months=step_months)

    return windows


def trading_days_between(start: str, end: str) -> List[str]:
    """
    Returns list of NYSE trading day strings between start and end (inclusive).
    """
    idx = pd.bdate_range(start=start, end=end, freq="C",
                         holidays=[])
    return [d.strftime("%Y-%m-%d") for d in idx]
