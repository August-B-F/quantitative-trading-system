"""Compute B0-B3 baselines for T1 (winner selection) on walk-forward test folds.

All baselines are evaluated at the monthly decision cadence (one trade per month)
using the end-of-month sample from each fold's test window.

Baselines:
- B0: uniform random winner (seeded)
- B1: always SPY-proxy (QQQ is the SPY-like core here; we use the ETF whose
      FWD21 realized return matches the index's broad tech/mega-cap exposure:
      we pick QQQ as the static buy-and-hold since SPY is not in the 8-ETF set)
- B2: 12-1 momentum winner (argmax of returns_12_1_mom__<ticker>)
- B3: 3-month momentum winner (argmax of returns_63d__<ticker>)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from model.walk_forward import OverlappingSplitter  # noqa: E402
from model.metrics import monthly_aggregate, strategy_metrics  # noqa: E402

ETFS = ["SOXX", "QQQ", "XLK", "VGT", "IGV", "XLE", "GLD", "SHY"]
IDX2TK = {i: tk for i, tk in enumerate(ETFS)}
TK2IDX = {tk: i for i, tk in enumerate(ETFS)}


def load_panel() -> pd.DataFrame:
    return pd.read_parquet(ROOT / "data/features/master_panel.parquet")


def fwd_return_matrix(df: pd.DataFrame) -> pd.DataFrame:
    cols = [f"TARGET_FWD21_{tk}" for tk in ETFS]
    return df[cols].rename(columns={f"TARGET_FWD21_{tk}": tk for tk in ETFS})


def mom_12_1_matrix(df: pd.DataFrame) -> pd.DataFrame:
    cols = [f"returns_12_1_mom__{tk}" for tk in ETFS]
    out = {}
    for tk in ETFS:
        c = f"returns_12_1_mom__{tk}"
        out[tk] = df[c] if c in df.columns else pd.Series(np.nan, index=df.index)
    return pd.DataFrame(out)


def mom_63d_matrix(df: pd.DataFrame) -> pd.DataFrame:
    out = {}
    for tk in ETFS:
        c = f"returns_63d__{tk}"
        out[tk] = df[c] if c in df.columns else pd.Series(np.nan, index=df.index)
    return pd.DataFrame(out)


def run() -> dict:
    df = load_panel()
    dates = df.index
    splits = OverlappingSplitter().split(dates)

    y_true = df["TARGET_T1_winner_idx"]
    fwd = fwd_return_matrix(df)
    mom121 = mom_12_1_matrix(df)
    mom63 = mom_63d_matrix(df)

    rng = np.random.default_rng(7)
    picks = {"B0": [], "B1": [], "B2": [], "B3": []}

    # Collect all test sample dates across folds, then aggregate monthly.
    all_test_dates: list[pd.Timestamp] = []
    all_true: list[int] = []
    all_b0: list[int] = []
    all_b1: list[int] = []
    all_b2: list[int] = []
    all_b3: list[int] = []

    for fold in splits:
        td = fold["test_dates"]
        if len(td) == 0:
            continue
        yt = y_true.loc[td].to_numpy()
        m121 = mom121.loc[td].to_numpy()
        m63 = mom63.loc[td].to_numpy()

        b0 = rng.integers(0, len(ETFS), size=len(td))
        b1 = np.full(len(td), TK2IDX["QQQ"])
        b2 = np.nanargmax(m121, axis=1)
        b3 = np.nanargmax(m63, axis=1)

        all_test_dates.extend(list(td))
        all_true.extend(list(yt))
        all_b0.extend(list(b0))
        all_b1.extend(list(b1))
        all_b2.extend(list(b2))
        all_b3.extend(list(b3))

    test_idx = pd.DatetimeIndex(all_test_dates)
    results: dict = {}

    for name, preds in [("B0_random", all_b0), ("B1_QQQ", all_b1),
                        ("B2_mom12_1", all_b2), ("B3_mom63d", all_b3)]:
        preds_arr = np.asarray(preds)
        true_arr = np.asarray(all_true)
        mask = ~pd.isna(true_arr)
        preds_arr = preds_arr[mask]
        true_arr = true_arr[mask].astype(int)
        dates_sub = test_idx[mask]

        # realized return of the *predicted* pick for each date
        fwd_sub = fwd.loc[dates_sub].to_numpy()
        realized = fwd_sub[np.arange(len(preds_arr)), preds_arr]

        monthly = monthly_aggregate(dates_sub, preds_arr, true_arr, realized)
        monthly_acc = float((monthly["y_pred"] == monthly["y_true"]).mean())
        strat = strategy_metrics(monthly["fwd_ret"].to_numpy())
        results[name] = {
            "monthly_accuracy": monthly_acc,
            "n_monthly_obs": int(len(monthly)),
            **strat,
        }

    out_path = ROOT / "results/baselines.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(results, indent=2))
    print(json.dumps(results, indent=2))
    return results


if __name__ == "__main__":
    run()
