"""Walk-forward splitters for daily-sampled panel data.

Both splitters:
- Operate on a sorted DatetimeIndex of trading days.
- Emit overlapping daily sample dates with purging + embargo so the forward
  return window of any train sample cannot leak into val/test.
- Report per-fold window boundaries alongside the actual purged sample dates.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Dict, Optional

import numpy as np
import pandas as pd


def _as_sorted_dti(panel_dates) -> pd.DatetimeIndex:
    idx = pd.DatetimeIndex(panel_dates).sort_values().unique()
    return pd.DatetimeIndex(idx)


def _sample_every_n(dates: pd.DatetimeIndex, n: int) -> pd.DatetimeIndex:
    if n <= 1:
        return dates
    return dates[:: int(n)]


def _purge_and_embargo(
    candidate: pd.DatetimeIndex,
    protected_start: pd.Timestamp,
    target_horizon: int,
    embargo_days: int,
    all_dates: pd.DatetimeIndex,
) -> pd.DatetimeIndex:
    """Drop candidate samples whose [t, t+H] overlaps protected_start, plus embargo."""
    if len(candidate) == 0:
        return candidate
    # horizon in trading days: find date at position +H
    pos = all_dates.get_indexer(candidate)
    horizon_end_pos = np.minimum(pos + target_horizon, len(all_dates) - 1)
    horizon_end = all_dates[horizon_end_pos]
    # Also embargo: remove samples whose sample_date + embargo >= protected_start
    embargo_pos = np.minimum(pos + target_horizon + embargo_days, len(all_dates) - 1)
    embargo_end = all_dates[embargo_pos]
    keep = embargo_end < protected_start
    # horizon check is strictly weaker than embargo check, keep only for clarity
    keep = keep & (horizon_end < protected_start)
    return candidate[keep]


def _month_offset(ts: pd.Timestamp, months: int) -> pd.Timestamp:
    return ts + pd.DateOffset(months=months)


class OverlappingSplitter:
    """Walk-forward with overlapping daily samples, purging, and embargo."""

    def __init__(
        self,
        train_months: int = 60,
        val_months: int = 6,
        test_months: int = 3,
        step_months: int = 3,
        sample_every_n_days: int = 5,
        embargo_days: int = 5,
        target_horizon: int = 21,
    ):
        self.train_months = train_months
        self.val_months = val_months
        self.test_months = test_months
        self.step_months = step_months
        self.sample_every_n_days = sample_every_n_days
        self.embargo_days = embargo_days
        self.target_horizon = target_horizon

    def split(self, panel_dates) -> List[Dict]:
        all_dates = _as_sorted_dti(panel_dates)
        folds: List[Dict] = []

        first = all_dates[0]
        last = all_dates[-1]

        train_start = first
        fold_id = 0
        while True:
            train_end = _month_offset(train_start, self.train_months)
            val_start = train_end
            val_end = _month_offset(val_start, self.val_months)
            test_start = val_end
            test_end = _month_offset(test_start, self.test_months)
            if test_end > last:
                break

            train_win = all_dates[(all_dates >= train_start) & (all_dates < train_end)]
            val_win = all_dates[(all_dates >= val_start) & (all_dates < val_end)]
            test_win = all_dates[(all_dates >= test_start) & (all_dates < test_end)]

            train_samp = _sample_every_n(train_win, self.sample_every_n_days)
            val_samp = _sample_every_n(val_win, self.sample_every_n_days)
            test_samp = _sample_every_n(test_win, self.sample_every_n_days)

            # Purge train against val_start; purge train+val against test_start.
            train_samp = _purge_and_embargo(
                train_samp, val_start, self.target_horizon, self.embargo_days, all_dates
            )
            train_samp = _purge_and_embargo(
                train_samp, test_start, self.target_horizon, self.embargo_days, all_dates
            )
            val_samp = _purge_and_embargo(
                val_samp, test_start, self.target_horizon, self.embargo_days, all_dates
            )

            folds.append(
                dict(
                    fold_id=fold_id,
                    train_dates=train_samp,
                    val_dates=val_samp,
                    test_dates=test_samp,
                    train_start=train_start,
                    train_end=train_end,
                    val_start=val_start,
                    val_end=val_end,
                    test_start=test_start,
                    test_end=test_end,
                )
            )

            fold_id += 1
            train_start = _month_offset(train_start, self.step_months)

        return folds


class ExpandingSplitter:
    """Expanding walk-forward with exponential decay weights for old samples."""

    def __init__(
        self,
        min_train_months: int = 60,
        val_months: int = 6,
        test_months: int = 3,
        step_months: int = 3,
        sample_every_n_days: int = 5,
        embargo_days: int = 5,
        target_horizon: int = 21,
        decay_halflife_months: float = 36.0,
    ):
        self.min_train_months = min_train_months
        self.val_months = val_months
        self.test_months = test_months
        self.step_months = step_months
        self.sample_every_n_days = sample_every_n_days
        self.embargo_days = embargo_days
        self.target_horizon = target_horizon
        self.decay_halflife_months = decay_halflife_months

    def split(self, panel_dates) -> List[Dict]:
        all_dates = _as_sorted_dti(panel_dates)
        folds: List[Dict] = []

        first = all_dates[0]
        last = all_dates[-1]

        # Anchor: initial train_end after min_train_months
        init_train_end = _month_offset(first, self.min_train_months)
        train_end = init_train_end
        fold_id = 0
        while True:
            val_start = train_end
            val_end = _month_offset(val_start, self.val_months)
            test_start = val_end
            test_end = _month_offset(test_start, self.test_months)
            if test_end > last:
                break

            train_win = all_dates[(all_dates >= first) & (all_dates < train_end)]
            val_win = all_dates[(all_dates >= val_start) & (all_dates < val_end)]
            test_win = all_dates[(all_dates >= test_start) & (all_dates < test_end)]

            train_samp = _sample_every_n(train_win, self.sample_every_n_days)
            val_samp = _sample_every_n(val_win, self.sample_every_n_days)
            test_samp = _sample_every_n(test_win, self.sample_every_n_days)

            train_samp = _purge_and_embargo(
                train_samp, val_start, self.target_horizon, self.embargo_days, all_dates
            )
            train_samp = _purge_and_embargo(
                train_samp, test_start, self.target_horizon, self.embargo_days, all_dates
            )
            val_samp = _purge_and_embargo(
                val_samp, test_start, self.target_horizon, self.embargo_days, all_dates
            )

            # Sample weights: exp(-age / (2 * halflife)) with age measured in months
            # from test_start back to each train sample.
            ref = test_start
            age_days = (ref - train_samp).days.to_numpy().astype(float)
            age_months = age_days / 30.4375
            tau = 2.0 * float(self.decay_halflife_months)
            weights = np.exp(-age_months / tau) if tau > 0 else np.ones_like(age_months)

            folds.append(
                dict(
                    fold_id=fold_id,
                    train_dates=train_samp,
                    val_dates=val_samp,
                    test_dates=test_samp,
                    train_sample_weights=weights,
                    train_start=first,
                    train_end=train_end,
                    val_start=val_start,
                    val_end=val_end,
                    test_start=test_start,
                    test_end=test_end,
                )
            )

            fold_id += 1
            train_end = _month_offset(train_end, self.step_months)

        return folds


def cross_sectional_expand(
    X_row: pd.Series,
    etf_tickers: List[str],
    shared_feature_cols: List[str],
    etf_feature_templates: List[str],
    fwd_target_template: str = "TARGET_FWD21_{ticker}",
) -> pd.DataFrame:
    """Expand a single panel row into one row per ETF.

    etf_feature_templates: list of column-name templates containing ``{ticker}``
    (e.g. ``"returns_63d__{ticker}"``). Shared features are copied verbatim.
    Returns a DataFrame indexed by ticker with feature columns + ``y`` target.
    """
    rows = []
    for tk in etf_tickers:
        row = {c: X_row.get(c, np.nan) for c in shared_feature_cols}
        for tmpl in etf_feature_templates:
            col = tmpl.format(ticker=tk)
            row[tmpl] = X_row.get(col, np.nan)
        row["ticker"] = tk
        row["y"] = X_row.get(fwd_target_template.format(ticker=tk), np.nan)
        rows.append(row)
    return pd.DataFrame(rows).set_index("ticker")
