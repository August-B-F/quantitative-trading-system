import datetime
import pytz


def now_eastern() -> datetime.datetime:
    tz = pytz.timezone("America/New_York")
    return datetime.datetime.now(tz)


def to_eastern(dt: datetime.datetime) -> datetime.datetime:
    tz = pytz.timezone("America/New_York")
    if dt.tzinfo is None:
        return tz.localize(dt)
    return dt.astimezone(tz)


def date_range(start: str, end: str):
    """Yield date strings from start to end inclusive (YYYY-MM-DD)."""
    s = datetime.date.fromisoformat(start)
    e = datetime.date.fromisoformat(end)
    delta = datetime.timedelta(days=1)
    while s <= e:
        yield s.isoformat()
        s += delta


def trading_days_ago(n: int) -> str:
    """Return approximate date n calendar days ago (rough, not calendar-exact)."""
    d = datetime.date.today() - datetime.timedelta(days=n)
    return d.isoformat()
