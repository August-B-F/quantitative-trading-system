"""Date/time helpers for market-aware operations."""
import pandas as pd
from datetime import date, timedelta
from typing import List

try:
    import pandas_market_calendars as mcal
    _NYSE = mcal.get_calendar("NYSE")
except ImportError:
    _NYSE = None


def trading_days_between(start: str, end: str) -> List[str]:
    """Return list of NYSE trading day strings (YYYY-MM-DD) between start and end."""
    if _NYSE is None:
        dates = pd.bdate_range(start, end)
        return [str(d.date()) for d in dates]
    schedule = _NYSE.schedule(start_date=start, end_date=end)
    return [str(d.date()) for d in schedule.index]


def last_n_trading_days(n: int, reference_date: str = None) -> List[str]:
    """Return the last n trading days ending on reference_date (or today)."""
    end = reference_date or str(date.today())
    # start far enough back to guarantee n trading days
    start = str((pd.Timestamp(end) - pd.DateOffset(days=n * 2)).date())
    days = trading_days_between(start, end)
    return days[-n:]


def walk_forward_windows(start: str, end: str,
                         train_months: int = 18,
                         val_months: int = 3,
                         test_months: int = 1,
                         step_months: int = 1) -> List[dict]:
    """
    Generate walk-forward windows as list of dicts with keys:
        train_start, train_end, val_start, val_end, test_start, test_end
    """
    windows = []
    cursor = pd.Timestamp(start)
    end_ts = pd.Timestamp(end)

    while True:
        train_start = cursor
        train_end   = cursor + pd.DateOffset(months=train_months) - pd.DateOffset(days=1)
        val_start   = train_end + pd.DateOffset(days=1)
        val_end     = val_start + pd.DateOffset(months=val_months) - pd.DateOffset(days=1)
        test_start  = val_end + pd.DateOffset(days=1)
        test_end    = test_start + pd.DateOffset(months=test_months) - pd.DateOffset(days=1)

        if test_end > end_ts:
            break

        windows.append({
            "train_start": str(train_start.date()),
            "train_end":   str(train_end.date()),
            "val_start":   str(val_start.date()),
            "val_end":     str(val_end.date()),
            "test_start":  str(test_start.date()),
            "test_end":    str(test_end.date()),
        })
        cursor += pd.DateOffset(months=step_months)

    return windows
