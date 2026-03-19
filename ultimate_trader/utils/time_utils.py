import datetime
import pandas as pd
from zoneinfo import ZoneInfo

NY_TZ = ZoneInfo("America/New_York")


def now_ny() -> datetime.datetime:
    return datetime.datetime.now(NY_TZ)


def today_str() -> str:
    return now_ny().strftime("%Y-%m-%d")


def date_range(start: str, end: str | None = None) -> pd.DatetimeIndex:
    end = end or today_str()
    return pd.bdate_range(start=start, end=end)


def n_business_days_ago(n: int) -> str:
    dt = now_ny()
    count = 0
    while count < n:
        dt -= datetime.timedelta(days=1)
        if dt.weekday() < 5:  # Mon–Fri
            count += 1
    return dt.strftime("%Y-%m-%d")


def is_market_open() -> bool:
    now = now_ny()
    if now.weekday() >= 5:
        return False
    market_open = now.replace(hour=9, minute=30, second=0, microsecond=0)
    market_close = now.replace(hour=16, minute=0, second=0, microsecond=0)
    return market_open <= now <= market_close
