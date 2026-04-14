"""Bureau of Labor Statistics CPI fetcher — third fallback for FRED CPI.

Only covers CPI-U (series CUUR0000SA0 / CUSR0000SA0). PMI has no free
BLS equivalent; per MASTER_ARCHITECTURE the PMI fallback stays
"forward-fill from cache".

v1 API is keyless but capped at 25 req/day / 10yr history per call.
That is plenty for a single monthly series refresh.
"""
from __future__ import annotations

import logging
from typing import Optional

import pandas as pd
import requests

log = logging.getLogger(__name__)

BLS_V1_URL = "https://api.bls.gov/publicAPI/v1/timeseries/data/{series}"

# CPI-U, U.S. city average, all items
CPI_SA = "CUSR0000SA0"   # seasonally adjusted (matches FRED CPIAUCSL)
CPI_NSA = "CUUR0000SA0"  # not seasonally adjusted (matches FRED CPIAUCNS)

_MONTH_TO_NUM = {
    "M01": 1, "M02": 2, "M03": 3, "M04": 4, "M05": 5, "M06": 6,
    "M07": 7, "M08": 8, "M09": 9, "M10": 10, "M11": 11, "M12": 12,
}


def fetch_cpi(
    series_id: str = CPI_SA,
    start_year: Optional[int] = None,
    end_year: Optional[int] = None,
    timeout: int = 20,
) -> Optional[pd.DataFrame]:
    """Fetch monthly CPI from BLS v1 keyless endpoint.

    Returns DataFrame indexed by month-end date with a single column named
    `series_id`, or `None` on failure. v1 is limited to ~10 years per call
    without registration — we accept that window.
    """
    params = {}
    if start_year is not None:
        params["startyear"] = str(start_year)
    if end_year is not None:
        params["endyear"] = str(end_year)

    url = BLS_V1_URL.format(series=series_id)
    try:
        r = requests.get(url, params=params or None, timeout=timeout)
    except Exception as e:
        log.error("bls request failed: %s", e)
        return None

    if r.status_code != 200:
        log.error("bls HTTP %s: %s", r.status_code, r.text[:120])
        return None

    try:
        payload = r.json()
    except Exception as e:
        log.error("bls json decode failed: %s", e)
        return None

    if payload.get("status") != "REQUEST_SUCCEEDED":
        log.error("bls error: %s", payload.get("message", payload.get("status")))
        return None

    series = payload.get("Results", {}).get("series", [])
    if not series:
        return None
    rows = series[0].get("data", [])
    if not rows:
        return None

    records = []
    for row in rows:
        period = row.get("period", "")
        year = row.get("year")
        value = row.get("value")
        if period not in _MONTH_TO_NUM or year is None:
            continue
        try:
            month_num = _MONTH_TO_NUM[period]
            dt = pd.Timestamp(year=int(year), month=month_num, day=1) + pd.offsets.MonthEnd(0)
            records.append((dt, float(value)))
        except (TypeError, ValueError):
            continue

    if not records:
        return None

    df = pd.DataFrame(records, columns=["date", series_id]).set_index("date").sort_index()
    df.index.name = None
    return df.astype("float64")


def fetch_cpi_yoy(series_id: str = CPI_SA, start_year: Optional[int] = None) -> Optional[pd.DataFrame]:
    """Convenience: return YoY percent change of the CPI level series."""
    df = fetch_cpi(series_id, start_year=start_year)
    if df is None or df.empty:
        return None
    out = df.pct_change(12) * 100.0
    out.columns = [f"{series_id}_yoy"]
    return out.dropna()
