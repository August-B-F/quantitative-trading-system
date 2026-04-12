"""Shared data utilities. Imported by every fetcher and feature builder."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

try:
    import pandas_market_calendars as mcal
    _HAS_MCAL = True
except ImportError:
    _HAS_MCAL = False


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
CATALOG_PATH = DATA_DIR / "DATA_CATALOG.md"
HEALTH_PATH = DATA_DIR / "DATA_HEALTH.md"
FAILED_PATH = DATA_DIR / "FAILED_SOURCES.md"


def get_trading_calendar(start_date, end_date) -> pd.DatetimeIndex:
    """Return NYSE trading days between start and end (tz-naive)."""
    start = pd.Timestamp(start_date)
    end = pd.Timestamp(end_date)
    if _HAS_MCAL:
        nyse = mcal.get_calendar("NYSE")
        sched = nyse.schedule(start_date=start, end_date=end)
        idx = pd.DatetimeIndex(sched.index)
    else:
        idx = pd.bdate_range(start, end)
    return idx.tz_localize(None) if idx.tz is not None else idx


def align_to_trading_days(
    df: pd.DataFrame,
    method: str = "ffill",
    limit: int = 5,
    source_freq: str = "daily",
    start: Optional[str] = None,
    end: Optional[str] = None,
) -> pd.DataFrame:
    """Reindex dataframe to NYSE trading day calendar.

    source_freq controls fill limit when method='ffill':
      daily -> limit (default 5)
      weekly -> 5
      monthly -> 22
    """
    if df.empty:
        return df
    df = df.copy()
    if df.index.tz is not None:
        df.index = df.index.tz_localize(None)
    df = df.sort_index()
    df = df[~df.index.duplicated(keep="last")]

    s = pd.Timestamp(start) if start else df.index.min()
    e = pd.Timestamp(end) if end else df.index.max()
    cal = get_trading_calendar(s, e)

    fill_limit = {"daily": limit, "weekly": 5, "monthly": 22, "quarterly": 66}.get(source_freq, limit)
    if method == "ffill":
        # Reindex to UNION of original dates + trading days so values whose dates
        # aren't trading days (Sat-dated weekly, 1st-of-quarter) survive the
        # reindex via ffill, then drop back to the trading-day calendar.
        union = cal.union(df.index)
        out = df.reindex(union).ffill(limit=fill_limit).reindex(cal)
    else:
        out = df.reindex(cal)
    return out


def save_clean(df: pd.DataFrame, path, metadata: Optional[dict] = None) -> None:
    """Save df as parquet with float64 values + datetime index, plus optional sidecar JSON."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    out = df.copy()
    if not isinstance(out.index, pd.DatetimeIndex):
        out.index = pd.to_datetime(out.index)
    out.index.name = "date"
    for c in out.columns:
        if pd.api.types.is_numeric_dtype(out[c]):
            out[c] = out[c].astype("float64")
    out.to_parquet(path)
    if metadata is not None:
        meta = dict(metadata)
        meta.setdefault("saved_at", datetime.utcnow().isoformat() + "Z")
        meta.setdefault("rows", len(out))
        meta.setdefault("columns", list(out.columns))
        with open(path.with_suffix(".json"), "w") as f:
            json.dump(meta, f, indent=2, default=str)


def load_clean(path) -> pd.DataFrame:
    df = pd.read_parquet(path)
    if not isinstance(df.index, pd.DatetimeIndex):
        df.index = pd.to_datetime(df.index)
    return df


def validate_data(df: pd.DataFrame, name: str = "") -> dict:
    """Print summary stats and return dict with date range, NaNs, gaps, outliers."""
    report: dict = {"name": name}
    if df.empty:
        report["empty"] = True
        print(f"[{name}] EMPTY")
        return report

    report["start"] = str(df.index.min().date())
    report["end"] = str(df.index.max().date())
    report["rows"] = int(len(df))
    nan_counts = df.isna().sum().to_dict()
    nan_pct = (df.isna().mean() * 100).round(2).to_dict()
    report["nan_counts"] = {k: int(v) for k, v in nan_counts.items()}
    report["nan_pct"] = {k: float(v) for k, v in nan_pct.items()}

    # gaps > 5 trading days
    cal = get_trading_calendar(df.index.min(), df.index.max())
    missing = cal.difference(df.index)
    gaps = []
    if len(missing) > 0:
        runs = []
        cur = [missing[0]]
        for d in missing[1:]:
            if (d - cur[-1]).days <= 7:
                cur.append(d)
            else:
                runs.append(cur)
                cur = [d]
        runs.append(cur)
        for run in runs:
            if len(run) > 5:
                gaps.append((str(run[0].date()), str(run[-1].date()), len(run)))
    report["gaps_gt_5d"] = gaps

    # outliers > 5 sigma from rolling 252d mean
    outliers = {}
    for c in df.select_dtypes(include=[np.number]).columns:
        s = df[c].dropna()
        if len(s) < 50:
            continue
        roll_mean = s.rolling(252, min_periods=20).mean()
        roll_std = s.rolling(252, min_periods=20).std()
        z = (s - roll_mean).abs() / roll_std.replace(0, np.nan)
        n = int((z > 5).sum())
        if n:
            outliers[c] = n
    report["outliers_5sigma"] = outliers

    print(
        f"[{name}] {report['start']}..{report['end']}  rows={report['rows']}  "
        f"nan%={nan_pct}  gaps>5d={len(gaps)}  outliers={outliers}"
    )
    return report


def log_to_catalog(catalog_path, entry: dict) -> None:
    """Append a markdown table row to DATA_CATALOG.md (creates header if missing)."""
    catalog_path = Path(catalog_path)
    catalog_path.parent.mkdir(parents=True, exist_ok=True)
    header = (
        "# Data Catalog\n\n"
        "| Source | Series | Frequency | Date Range | File Path | Status | Notes |\n"
        "|--------|--------|-----------|------------|-----------|--------|-------|\n"
    )
    if not catalog_path.exists():
        catalog_path.write_text(header)
    fields = ["source", "series_name", "frequency", "date_range", "file_path", "status", "notes"]
    row = "| " + " | ".join(str(entry.get(f, "")) for f in fields) + " |\n"
    with open(catalog_path, "a") as f:
        f.write(row)


def log_failure(failed_path, source: str, reason: str, attempted: str = "") -> None:
    """Append failure entry to FAILED_SOURCES.md."""
    failed_path = Path(failed_path)
    failed_path.parent.mkdir(parents=True, exist_ok=True)
    if not failed_path.exists():
        failed_path.write_text("# Failed Sources\n\n| Date | Source | Attempted | Reason |\n|------|--------|-----------|--------|\n")
    ts = datetime.utcnow().strftime("%Y-%m-%d")
    with open(failed_path, "a") as f:
        f.write(f"| {ts} | {source} | {attempted} | {reason} |\n")
