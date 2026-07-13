"""Phase 3 PART A: build calendar event flags parquet.

No scraping. Pure rule-based + a hardcoded list of historical FOMC meetings
(federalreserve.gov is the source of truth; meetings rarely change).
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.data.utils import get_trading_calendar, save_clean, log_to_catalog, CATALOG_PATH

OUT = Path(__file__).resolve().parents[1] / "data" / "clean" / "calendar" / "events.parquet"
START = "2005-01-01"
END = "2027-12-31"


# Historical + scheduled FOMC meetings (last day of each meeting).
# Source: federalreserve.gov/monetarypolicy/fomccalendars.htm
FOMC_MEETINGS = [
    # 2005
    "2005-02-02", "2005-03-22", "2005-05-03", "2005-06-30", "2005-08-09",
    "2005-09-20", "2005-11-01", "2005-12-13",
    # 2006
    "2006-01-31", "2006-03-28", "2006-05-10", "2006-06-29", "2006-08-08",
    "2006-09-20", "2006-10-25", "2006-12-12",
    # 2007
    "2007-01-31", "2007-03-21", "2007-05-09", "2007-06-28", "2007-08-07",
    "2007-09-18", "2007-10-31", "2007-12-11",
    # 2008
    "2008-01-22", "2008-01-30", "2008-03-18", "2008-04-30", "2008-06-25",
    "2008-08-05", "2008-09-16", "2008-10-08", "2008-10-29", "2008-12-16",
    # 2009
    "2009-01-28", "2009-03-18", "2009-04-29", "2009-06-24", "2009-08-12",
    "2009-09-23", "2009-11-04", "2009-12-16",
    # 2010
    "2010-01-27", "2010-03-16", "2010-04-28", "2010-06-23", "2010-08-10",
    "2010-09-21", "2010-11-03", "2010-12-14",
    # 2011
    "2011-01-26", "2011-03-15", "2011-04-27", "2011-06-22", "2011-08-09",
    "2011-09-21", "2011-11-02", "2011-12-13",
    # 2012
    "2012-01-25", "2012-03-13", "2012-04-25", "2012-06-20", "2012-08-01",
    "2012-09-13", "2012-10-24", "2012-12-12",
    # 2013
    "2013-01-30", "2013-03-20", "2013-05-01", "2013-06-19", "2013-07-31",
    "2013-09-18", "2013-10-30", "2013-12-18",
    # 2014
    "2014-01-29", "2014-03-19", "2014-04-30", "2014-06-18", "2014-07-30",
    "2014-09-17", "2014-10-29", "2014-12-17",
    # 2015
    "2015-01-28", "2015-03-18", "2015-04-29", "2015-06-17", "2015-07-29",
    "2015-09-17", "2015-10-28", "2015-12-16",
    # 2016
    "2016-01-27", "2016-03-16", "2016-04-27", "2016-06-15", "2016-07-27",
    "2016-09-21", "2016-11-02", "2016-12-14",
    # 2017
    "2017-02-01", "2017-03-15", "2017-05-03", "2017-06-14", "2017-07-26",
    "2017-09-20", "2017-11-01", "2017-12-13",
    # 2018
    "2018-01-31", "2018-03-21", "2018-05-02", "2018-06-13", "2018-08-01",
    "2018-09-26", "2018-11-08", "2018-12-19",
    # 2019
    "2019-01-30", "2019-03-20", "2019-05-01", "2019-06-19", "2019-07-31",
    "2019-09-18", "2019-10-30", "2019-12-11",
    # 2020
    "2020-01-29", "2020-03-03", "2020-03-15", "2020-04-29", "2020-06-10",
    "2020-07-29", "2020-09-16", "2020-11-05", "2020-12-16",
    # 2021
    "2021-01-27", "2021-03-17", "2021-04-28", "2021-06-16", "2021-07-28",
    "2021-09-22", "2021-11-03", "2021-12-15",
    # 2022
    "2022-01-26", "2022-03-16", "2022-05-04", "2022-06-15", "2022-07-27",
    "2022-09-21", "2022-11-02", "2022-12-14",
    # 2023
    "2023-02-01", "2023-03-22", "2023-05-03", "2023-06-14", "2023-07-26",
    "2023-09-20", "2023-11-01", "2023-12-13",
    # 2024
    "2024-01-31", "2024-03-20", "2024-05-01", "2024-06-12", "2024-07-31",
    "2024-09-18", "2024-11-07", "2024-12-18",
    # 2025
    "2025-01-29", "2025-03-19", "2025-05-07", "2025-06-18", "2025-07-30",
    "2025-09-17", "2025-10-29", "2025-12-10",
    # 2026 (scheduled)
    "2026-01-28", "2026-03-18", "2026-04-29", "2026-06-17", "2026-07-29",
    "2026-09-16", "2026-10-28", "2026-12-09",
]

# ECB Governing Council monetary policy meeting dates (rate decision day).
# Source: ecb.europa.eu — partial list, kept rules-based for forward.
ECB_MEETINGS = [
    "2005-01-13","2005-02-03","2005-03-03","2005-04-07","2005-05-04","2005-06-02",
    "2005-07-07","2005-09-01","2005-10-06","2005-11-03","2005-12-01",
    "2006-01-12","2006-02-02","2006-03-02","2006-04-06","2006-05-04","2006-06-08",
    "2006-07-06","2006-08-03","2006-09-07","2006-10-05","2006-11-02","2006-12-07",
    "2007-01-11","2007-02-08","2007-03-08","2007-04-12","2007-05-10","2007-06-06",
    "2007-07-05","2007-08-02","2007-09-06","2007-10-04","2007-11-08","2007-12-06",
    "2008-01-10","2008-02-07","2008-03-06","2008-04-10","2008-05-08","2008-06-05",
    "2008-07-03","2008-08-07","2008-09-04","2008-10-02","2008-10-08","2008-11-06","2008-12-04",
    "2009-01-15","2009-02-05","2009-03-05","2009-04-02","2009-05-07","2009-06-04",
    "2009-07-02","2009-08-06","2009-09-03","2009-10-08","2009-11-05","2009-12-03",
    "2010-01-14","2010-02-04","2010-03-04","2010-04-08","2010-05-06","2010-06-10",
    "2010-07-08","2010-08-05","2010-09-02","2010-10-07","2010-11-04","2010-12-02",
    "2011-01-13","2011-02-03","2011-03-03","2011-04-07","2011-05-05","2011-06-09",
    "2011-07-07","2011-08-04","2011-09-08","2011-10-06","2011-11-03","2011-12-08",
    "2012-01-12","2012-02-09","2012-03-08","2012-04-04","2012-05-03","2012-06-06",
    "2012-07-05","2012-08-02","2012-09-06","2012-10-04","2012-11-08","2012-12-06",
    "2013-01-10","2013-02-07","2013-03-07","2013-04-04","2013-05-02","2013-06-06",
    "2013-07-04","2013-08-01","2013-09-05","2013-10-02","2013-11-07","2013-12-05",
    "2014-01-09","2014-02-06","2014-03-06","2014-04-03","2014-05-08","2014-06-05",
    "2014-07-03","2014-08-07","2014-09-04","2014-10-02","2014-11-06","2014-12-04",
    "2015-01-22","2015-03-05","2015-04-15","2015-06-03","2015-07-16","2015-09-03",
    "2015-10-22","2015-12-03",
    "2016-01-21","2016-03-10","2016-04-21","2016-06-02","2016-07-21","2016-09-08",
    "2016-10-20","2016-12-08",
    "2017-01-19","2017-03-09","2017-04-27","2017-06-08","2017-07-20","2017-09-07",
    "2017-10-26","2017-12-14",
    "2018-01-25","2018-03-08","2018-04-26","2018-06-14","2018-07-26","2018-09-13",
    "2018-10-25","2018-12-13",
    "2019-01-24","2019-03-07","2019-04-10","2019-06-06","2019-07-25","2019-09-12",
    "2019-10-24","2019-12-12",
    "2020-01-23","2020-03-12","2020-04-30","2020-06-04","2020-07-16","2020-09-10",
    "2020-10-29","2020-12-10",
    "2021-01-21","2021-03-11","2021-04-22","2021-06-10","2021-07-22","2021-09-09",
    "2021-10-28","2021-12-16",
    "2022-02-03","2022-03-10","2022-04-14","2022-06-09","2022-07-21","2022-09-08",
    "2022-10-27","2022-12-15",
    "2023-02-02","2023-03-16","2023-05-04","2023-06-15","2023-07-27","2023-09-14",
    "2023-10-26","2023-12-14",
    "2024-01-25","2024-03-07","2024-04-11","2024-06-06","2024-07-18","2024-09-12",
    "2024-10-17","2024-12-12",
    "2025-01-30","2025-03-06","2025-04-17","2025-06-05","2025-07-24","2025-09-11",
    "2025-10-30","2025-12-18",
    "2026-01-29","2026-03-12","2026-04-23","2026-06-04","2026-07-23","2026-09-10",
    "2026-10-29","2026-12-17",
]


def third_friday(year: int, month: int) -> pd.Timestamp:
    first = pd.Timestamp(year=year, month=month, day=1)
    # 0=Mon, 4=Fri
    days_to_first_fri = (4 - first.weekday()) % 7
    return first + pd.Timedelta(days=days_to_first_fri + 14)


def first_friday(year: int, month: int) -> pd.Timestamp:
    first = pd.Timestamp(year=year, month=month, day=1)
    return first + pd.Timedelta(days=(4 - first.weekday()) % 7)


def last_friday(year: int, month: int) -> pd.Timestamp:
    last = pd.Timestamp(year=year, month=month, day=1) + pd.offsets.MonthEnd(0)
    back = (last.weekday() - 4) % 7
    return last - pd.Timedelta(days=back)


def election_day(year: int) -> pd.Timestamp:
    """First Tuesday after first Monday of November."""
    first = pd.Timestamp(year=year, month=11, day=1)
    first_mon = first + pd.Timedelta(days=(0 - first.weekday()) % 7)
    return first_mon + pd.Timedelta(days=1)


def to_trading_day(date: pd.Timestamp, cal: pd.DatetimeIndex) -> pd.Timestamp | None:
    """Snap a date forward to the next trading day (within ~7 days)."""
    if date in cal:
        return date
    fwd = cal[cal >= date]
    return fwd[0] if len(fwd) > 0 else None


def week_window(date: pd.Timestamp, cal: pd.DatetimeIndex, window: int = 5) -> list:
    """Return up to `window` trading days centered on `date`."""
    if len(cal) == 0:
        return []
    snapped = to_trading_day(date, cal)
    if snapped is None:
        return []
    pos = cal.get_loc(snapped)
    half = window // 2
    lo = max(0, pos - half)
    hi = min(len(cal), pos + half + 1)
    return list(cal[lo:hi])


def main():
    cal = get_trading_calendar(START, END)
    df = pd.DataFrame(index=cal)

    # FOMC
    fomc_dates = [pd.Timestamp(d) for d in FOMC_MEETINGS]
    fomc_trading = sorted({to_trading_day(d, cal) for d in fomc_dates if to_trading_day(d, cal) is not None})
    df["is_fomc_day"] = df.index.isin(fomc_trading).astype(np.int8)

    fomc_week_days = set()
    for d in fomc_trading:
        for x in week_window(d, cal, window=5):
            fomc_week_days.add(x)
    df["is_fomc_week"] = df.index.isin(fomc_week_days).astype(np.int8)

    fomc_arr = pd.Series(fomc_trading).sort_values().reset_index(drop=True)
    days_since = []
    days_to = []
    for d in df.index:
        prior = fomc_arr[fomc_arr <= d]
        nxt = fomc_arr[fomc_arr > d]
        days_since.append((d - prior.iloc[-1]).days if len(prior) else np.nan)
        days_to.append((nxt.iloc[0] - d).days if len(nxt) else np.nan)
    df["days_since_last_fomc"] = days_since
    df["days_to_next_fomc"] = days_to

    # Economic releases (rules-based; precise days vary, week flags are robust)
    # NFP: first Friday of each month
    nfp_dates = []
    for y in range(2005, 2028):
        for m in range(1, 13):
            nfp_dates.append(first_friday(y, m))
    nfp_trading = [to_trading_day(d, cal) for d in nfp_dates]
    nfp_trading = [d for d in nfp_trading if d is not None]
    nfp_week_days = set()
    for d in nfp_trading:
        for x in week_window(d, cal, 5):
            nfp_week_days.add(x)
    df["is_nfp_week"] = df.index.isin(nfp_week_days).astype(np.int8)

    # CPI: typically released 10th-15th of month, weekday
    cpi_dates = []
    for y in range(2005, 2028):
        for m in range(1, 13):
            for day in (12, 13, 14, 15, 11, 10):
                t = pd.Timestamp(year=y, month=m, day=day)
                if t.weekday() < 5:
                    cpi_dates.append(t)
                    break
    cpi_trading = [to_trading_day(d, cal) for d in cpi_dates if to_trading_day(d, cal)]
    cpi_week_days = set()
    for d in cpi_trading:
        for x in week_window(d, cal, 5):
            cpi_week_days.add(x)
    df["is_cpi_week"] = df.index.isin(cpi_week_days).astype(np.int8)

    # GDP advance release: ~end of month following quarter end (Jan, Apr, Jul, Oct)
    gdp_week_days = set()
    for y in range(2005, 2028):
        for m in (1, 4, 7, 10):
            t = pd.Timestamp(year=y, month=m, day=28)
            snap = to_trading_day(t, cal)
            if snap is not None:
                for x in week_window(snap, cal, 5):
                    gdp_week_days.add(x)
    df["is_gdp_week"] = df.index.isin(gdp_week_days).astype(np.int8)

    # Earnings season: weeks 3-6 after quarter end
    earnings = pd.Series(0, index=df.index, dtype=np.int8)
    for y in range(2005, 2028):
        for qm in (1, 4, 7, 10):  # month after quarter end
            qstart = pd.Timestamp(year=y, month=qm, day=1)
            mask = (df.index >= qstart + pd.Timedelta(days=14)) & (df.index < qstart + pd.Timedelta(days=42))
            earnings[mask] = 1
    df["is_earnings_season"] = earnings.values

    # Options expiration
    opex_dates = []
    quad_dates = []
    for y in range(2005, 2028):
        for m in range(1, 13):
            d = third_friday(y, m)
            opex_dates.append(d)
            if m in (3, 6, 9, 12):
                quad_dates.append(d)
    opex_trading = [to_trading_day(d, cal) for d in opex_dates if to_trading_day(d, cal)]
    quad_trading = [to_trading_day(d, cal) for d in quad_dates if to_trading_day(d, cal)]
    opex_week = set()
    for d in opex_trading:
        for x in week_window(d, cal, 5):
            opex_week.add(x)
    quad_week = set()
    for d in quad_trading:
        for x in week_window(d, cal, 5):
            quad_week.add(x)
    df["is_opex_week"] = df.index.isin(opex_week).astype(np.int8)
    df["is_quad_witching_week"] = df.index.isin(quad_week).astype(np.int8)

    # Russell reconstitution: last Friday of June
    russell_dates = [last_friday(y, 6) for y in range(2005, 2028)]
    russell_trading = [to_trading_day(d, cal) for d in russell_dates if to_trading_day(d, cal)]
    russell_week = set()
    for d in russell_trading:
        for x in week_window(d, cal, 5):
            russell_week.add(x)
    df["is_russell_recon_week"] = df.index.isin(russell_week).astype(np.int8)

    # S&P quarterly rebalance = quad witching dates
    df["is_sp_rebalance_week"] = df["is_quad_witching_week"].values

    # Cyclical encodings
    moy = df.index.month
    df["month_sin"] = np.sin(2 * np.pi * moy / 12)
    df["month_cos"] = np.cos(2 * np.pi * moy / 12)
    dom = df.index.day
    df["dom_sin"] = np.sin(2 * np.pi * dom / 31)
    df["dom_cos"] = np.cos(2 * np.pi * dom / 31)
    woy = df.index.isocalendar().week.astype(int).values
    df["woy_sin"] = np.sin(2 * np.pi * woy / 52)
    df["woy_cos"] = np.cos(2 * np.pi * woy / 52)

    # Elections
    elec_months = set()
    for y in range(2004, 2030):
        ed = election_day(y)
        # presidential every 4: 2004, 2008, ...
        elec_months.add((ed.year, ed.month))
    df["is_election_month"] = [
        (1 if (d.year, d.month) in elec_months else 0) for d in df.index
    ]
    df["is_election_month"] = df["is_election_month"].astype(np.int8)

    # ECB
    ecb_dates = [pd.Timestamp(d) for d in ECB_MEETINGS]
    ecb_trading = [to_trading_day(d, cal) for d in ecb_dates if to_trading_day(d, cal)]
    df["is_ecb_day"] = df.index.isin(ecb_trading).astype(np.int8)

    # BOJ: ~8 meetings/year, rule approximation: mid Jan/Mar/Apr/Jun/Jul/Sep/Oct/Dec
    boj_week = set()
    for y in range(2005, 2028):
        for m in (1, 3, 4, 6, 7, 9, 10, 12):
            t = pd.Timestamp(year=y, month=m, day=18)
            snap = to_trading_day(t, cal)
            if snap is not None:
                for x in week_window(snap, cal, 5):
                    boj_week.add(x)
    df["is_boj_week"] = df.index.isin(boj_week).astype(np.int8)

    # China NBS PMI: released 1st of month
    cn_pmi_week = set()
    for y in range(2005, 2028):
        for m in range(1, 13):
            t = pd.Timestamp(year=y, month=m, day=1)
            snap = to_trading_day(t, cal)
            if snap is not None:
                for x in week_window(snap, cal, 5):
                    cn_pmi_week.add(x)
    df["is_cn_pmi_week"] = df.index.isin(cn_pmi_week).astype(np.int8)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    save_clean(df, OUT, metadata={
        "source": "rule-based + hardcoded FOMC/ECB",
        "columns": list(df.columns),
        "rows": len(df),
    })

    log_to_catalog(CATALOG_PATH, {
        "source": "rule-based",
        "series_name": "calendar_events",
        "frequency": "daily",
        "date_range": f"{df.index.min().date()}..{df.index.max().date()}",
        "file_path": "data/clean/calendar/events.parquet",
        "status": "OK",
        "notes": f"{len(df.columns)} flags: FOMC/CPI/NFP/GDP/OpEx/quad/Russell/election/ECB/BOJ/cyclical encodings",
    })

    print(f"Wrote {OUT} with {len(df)} rows x {len(df.columns)} columns")
    print(df.head(3))
    print("Sums (count of flagged days):")
    for c in df.columns:
        if c.startswith("is_"):
            print(f"  {c}: {int(df[c].sum())}")


if __name__ == "__main__":
    main()
