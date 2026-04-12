"""Evaluation metrics with monthly aggregation for overlapping samples."""

from __future__ import annotations

from typing import Dict, Optional

import numpy as np
import pandas as pd


def monthly_aggregate(
    dates: pd.DatetimeIndex,
    y_pred,
    y_true,
    fwd_returns: Optional[pd.Series] = None,
) -> pd.DataFrame:
    """Collapse daily predictions to one observation per month (last sample).

    Returns a DataFrame indexed by month-end with y_pred, y_true, fwd_ret columns.
    """
    df = pd.DataFrame(
        {"y_pred": np.asarray(y_pred), "y_true": np.asarray(y_true)},
        index=pd.DatetimeIndex(dates),
    )
    if fwd_returns is not None:
        df["fwd_ret"] = np.asarray(fwd_returns)
    df = df.sort_index()
    # last sample per calendar month
    df["__month"] = df.index.to_period("M")
    monthly = df.groupby("__month").tail(1).drop(columns="__month")
    monthly.index = monthly.index.to_period("M").to_timestamp("M")
    return monthly


def classification_metrics(y_true, y_pred) -> Dict[str, float]:
    """Return accuracy / precision / recall / F1 for classification labels."""
    y_true = np.asarray(y_true)
    y_pred = np.asarray(y_pred)
    acc = float((y_true == y_pred).mean()) if len(y_true) else float("nan")
    return {"accuracy": acc, "n": int(len(y_true))}


def strategy_metrics(monthly_returns: np.ndarray) -> Dict[str, float]:
    """Return CAGR, Sharpe, MaxDD, etc. from a series of monthly returns."""
    r = np.asarray(monthly_returns, dtype=float)
    r = r[~np.isnan(r)]
    if len(r) == 0:
        return {"mean_monthly": float("nan"), "sharpe_ann": float("nan"),
                "cagr": float("nan"), "max_dd": float("nan"), "n_months": 0}
    mean = r.mean()
    sd = r.std(ddof=1) if len(r) > 1 else 0.0
    sharpe = (mean / sd * np.sqrt(12)) if sd > 0 else float("nan")
    eq = np.cumprod(1.0 + r)
    years = len(r) / 12.0
    cagr = float(eq[-1] ** (1.0 / years) - 1.0) if years > 0 else float("nan")
    peak = np.maximum.accumulate(eq)
    dd = eq / peak - 1.0
    return {
        "mean_monthly": float(mean),
        "sharpe_ann": float(sharpe),
        "cagr": float(cagr),
        "max_dd": float(dd.min()),
        "n_months": int(len(r)),
    }
