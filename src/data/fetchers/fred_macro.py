"""FRED macro fetcher — requests-only, no pandas_datareader.

Live refresh path used by `src.data.pipeline.refresh_all_data`. Hits the
public FRED observations API when `FRED_API_KEY` is set, falls back to
the unauthenticated `fredgraph.csv` endpoint, and finally to a cached
parquet on /data/clean/macro/ if the network is unavailable.
"""
from __future__ import annotations

import io
import logging
import os
import time
from collections import deque
from pathlib import Path
from typing import Optional

import pandas as pd
import requests

log = logging.getLogger(__name__)

FRED_API_URL = "https://api.stlouisfed.org/fred/series/observations"
FRED_CSV_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}"

# Rate limit: FRED allows 120 req/min. We track call timestamps and sleep
# if the trailing-60s window would exceed 110 (10-call safety margin).
_MAX_PER_MIN = 110
_CALL_TIMES: deque[float] = deque()


def _throttle() -> None:
    now = time.monotonic()
    while _CALL_TIMES and now - _CALL_TIMES[0] > 60.0:
        _CALL_TIMES.popleft()
    if len(_CALL_TIMES) >= _MAX_PER_MIN:
        sleep_for = 60.0 - (now - _CALL_TIMES[0]) + 0.05
        log.info("fred rate-limit pause %.1fs", sleep_for)
        time.sleep(max(sleep_for, 0))
    _CALL_TIMES.append(time.monotonic())


def _fetch_via_api(
    series_id: str, start: Optional[str], end: Optional[str], api_key: str, timeout: int = 30
) -> pd.DataFrame:
    params = {
        "series_id": series_id,
        "api_key": api_key,
        "file_type": "json",
    }
    if start:
        params["observation_start"] = start
    if end:
        params["observation_end"] = end
    _throttle()
    r = requests.get(FRED_API_URL, params=params, timeout=timeout)
    if r.status_code != 200:
        raise RuntimeError(f"FRED API HTTP {r.status_code}: {r.text[:120]}")
    obs = r.json().get("observations", [])
    if not obs:
        return pd.DataFrame()
    df = pd.DataFrame(obs)
    df["date"] = pd.to_datetime(df["date"])
    df["value"] = pd.to_numeric(df["value"].replace(".", pd.NA), errors="coerce")
    df = df.dropna(subset=["value"]).set_index("date")[["value"]]
    df.columns = [series_id]
    return df.astype("float64")


def _fetch_via_csv(
    series_id: str, start: Optional[str], end: Optional[str], timeout: int = 30
) -> pd.DataFrame:
    _throttle()
    url = FRED_CSV_URL.format(sid=series_id)
    r = requests.get(url, headers={"User-Agent": "Mozilla/5.0 (quant-data-fetcher)"}, timeout=timeout)
    if r.status_code != 200:
        raise RuntimeError(f"FRED CSV HTTP {r.status_code}")
    df = pd.read_csv(io.BytesIO(r.content))
    date_col = "observation_date" if "observation_date" in df.columns else "DATE"
    df[date_col] = pd.to_datetime(df[date_col])
    df = df.set_index(date_col).sort_index()
    df.index.name = None
    for c in df.columns:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(how="all")
    df.columns = [series_id]
    if start:
        df = df[df.index >= pd.Timestamp(start)]
    if end:
        df = df[df.index <= pd.Timestamp(end)]
    return df.astype("float64")


def _load_cached_for_series(cache_dir: Path, series_id: str) -> Optional[pd.DataFrame]:
    """Look up a cached parquet for a FRED series id by either series_id or its
    descriptive_name (catalog mapping in fred.py SERIES table)."""
    p = Path(cache_dir) / f"{series_id.lower()}.parquet"
    if p.exists():
        return pd.read_parquet(p)
    try:
        from src.data.fetchers import fred as _fred_catalog
        for sid, name, _freq, _cat in _fred_catalog.SERIES:
            if sid == series_id:
                p2 = Path(cache_dir) / f"{name}.parquet"
                if p2.exists():
                    return pd.read_parquet(p2)
                break
    except Exception:
        pass
    return None


def fetch_fred_series(
    series_id: str,
    start: Optional[str] = None,
    end: Optional[str] = None,
    api_key: Optional[str] = None,
    cache_dir: Optional[Path] = None,
) -> pd.DataFrame:
    """Fetch a single FRED series.

    Tries: JSON API (if `api_key`) -> public CSV endpoint -> cached parquet.
    Always returns a DataFrame with a DatetimeIndex and one float64 column
    named `series_id`. On total failure returns an empty DataFrame and
    logs a warning rather than raising.
    """
    api_key = api_key or os.environ.get("FRED_API_KEY")

    if api_key:
        try:
            df = _fetch_via_api(series_id, start, end, api_key)
            if not df.empty:
                return df
        except Exception as e:
            log.warning("fred api failed for %s: %s", series_id, e)

    try:
        df = _fetch_via_csv(series_id, start, end)
        if not df.empty:
            return df
    except Exception as e:
        log.warning("fred csv failed for %s: %s", series_id, e)

    if cache_dir is not None:
        cached = _load_cached_for_series(cache_dir, series_id)
        if cached is not None and not cached.empty:
            log.warning("fred %s served from STALE cache", series_id)
            cached.columns = [series_id]
            return cached.astype("float64")

    log.error("fred %s: no data from api/csv/cache", series_id)
    return pd.DataFrame()


def refresh_series(series_ids: list[str], out_dir: Path) -> dict[str, pd.DataFrame]:
    """Fetch a list of FRED series; falls back to the cached parquet on failure."""
    out: dict[str, pd.DataFrame] = {}
    for sid in series_ids:
        df = fetch_fred_series(sid, cache_dir=out_dir)
        if df.empty:
            log.error("no data for %s; leaving empty", sid)
        out[sid] = df
    return out


def load_cached(macro_dir: Path, name: str) -> pd.DataFrame:
    """Load a cached macro series by catalog file name (e.g. 'cpi_all_urban')."""
    p = Path(macro_dir) / f"{name}.parquet"
    if not p.exists():
        raise FileNotFoundError(p)
    return pd.read_parquet(p)


def health_check(series_ids: list[str], stale_days_threshold: int = 60) -> list[dict]:
    """Fetch each series and report (id, latest_date, days_stale, flagged)."""
    today = pd.Timestamp.utcnow().normalize().tz_localize(None)
    rows = []
    for sid in series_ids:
        df = fetch_fred_series(sid)
        if df.empty:
            rows.append({"series_id": sid, "latest": None, "days_stale": None, "flagged": True, "note": "no_data"})
            continue
        latest = df.index.max()
        days_stale = int((today - latest).days)
        rows.append({
            "series_id": sid,
            "latest": latest.date().isoformat(),
            "days_stale": days_stale,
            "flagged": days_stale > stale_days_threshold,
            "note": "",
        })
    return rows
