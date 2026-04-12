# ARCHIVED: early E00 experiment runner — superseded by run_tier1/run_tier2
"""E00 label-shuffle diagnostic.

Runs HistGradientBoosting (xgboost-style) on MINIMAL features for T1
(winner classification) and T4 (drawdown_gt_5pct) using:
    E00a: OverlappingSplitter (rolling, daily sampling every 5)
    E00b: ExpandingSplitter (with exponential decay weights)
    E00c: OverlappingSplitter with sample_every_n_days=21 (monthly-only)

For each variant we compare real labels to shuffled labels (shuffle within
each training fold). Signal = real_monthly_acc - shuffled_monthly_acc.
A larger positive gap means more genuine signal is being extracted.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from sklearn.ensemble import HistGradientBoostingClassifier

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from model.walk_forward import OverlappingSplitter, ExpandingSplitter  # noqa: E402
from model.preprocessing import FeaturePreprocessor  # noqa: E402
from model.metrics import monthly_aggregate  # noqa: E402

ETFS = ["SOXX", "QQQ", "XLK", "VGT", "IGV", "XLE", "GLD", "SHY"]


def load_panel() -> pd.DataFrame:
    return pd.read_parquet(ROOT / "data/features/master_panel.parquet")


def load_features() -> list[str]:
    y = yaml.safe_load(open(ROOT / "configs/feature_sets.yaml"))
    return list(y["minimal"])


def fwd_return_matrix(df: pd.DataFrame) -> pd.DataFrame:
    cols = [f"TARGET_FWD21_{tk}" for tk in ETFS]
    return df[cols].rename(columns={f"TARGET_FWD21_{tk}": tk for tk in ETFS})


def run_variant(df, feature_cols, splitter, target_col, seed=0):
    folds = splitter.split(df.index)
    preds_real, preds_shuf, true_all, dates_all = [], [], [], []

    for fold in folds:
        tr = fold["train_dates"]
        te = fold["test_dates"]
        if len(tr) < 30 or len(te) < 2:
            continue

        X_tr = df.loc[tr, feature_cols]
        y_tr = df.loc[tr, target_col]
        X_te = df.loc[te, feature_cols]
        y_te = df.loc[te, target_col]

        # drop rows with missing target
        mtr = y_tr.notna()
        X_tr, y_tr = X_tr[mtr], y_tr[mtr]
        mte = y_te.notna()
        X_te, y_te = X_te[mte], y_te[mte]
        te_used = te[mte.to_numpy()]
        if len(X_tr) < 30 or len(X_te) < 1:
            continue

        sw = fold.get("train_sample_weights")
        if sw is not None:
            sw = np.asarray(sw)[mtr.to_numpy()]

        pp = FeaturePreprocessor()
        Xtr_z = pp.fit_transform(X_tr, sample_weights=sw)
        Xte_z = pp.transform(X_te)

        # real
        clf = HistGradientBoostingClassifier(
            max_iter=120, max_depth=4, learning_rate=0.05, random_state=seed
        )
        clf.fit(Xtr_z.to_numpy(), y_tr.astype(int).to_numpy(),
                sample_weight=sw)
        pr = clf.predict(Xte_z.to_numpy())

        # shuffled
        rng = np.random.default_rng(seed + fold["fold_id"])
        y_shuf = rng.permutation(y_tr.astype(int).to_numpy())
        clf2 = HistGradientBoostingClassifier(
            max_iter=120, max_depth=4, learning_rate=0.05, random_state=seed
        )
        clf2.fit(Xtr_z.to_numpy(), y_shuf, sample_weight=sw)
        ps = clf2.predict(Xte_z.to_numpy())

        preds_real.extend(pr.tolist())
        preds_shuf.extend(ps.tolist())
        true_all.extend(y_te.astype(int).to_numpy().tolist())
        dates_all.extend(list(te_used))

    if not dates_all:
        return {"real_monthly_acc": None, "shuf_monthly_acc": None,
                "gap": None, "n_monthly": 0}

    d = pd.DatetimeIndex(dates_all)
    mr = monthly_aggregate(d, preds_real, true_all)
    ms = monthly_aggregate(d, preds_shuf, true_all)
    real_acc = float((mr["y_pred"] == mr["y_true"]).mean())
    shuf_acc = float((ms["y_pred"] == ms["y_true"]).mean())
    return {
        "real_monthly_acc": real_acc,
        "shuf_monthly_acc": shuf_acc,
        "gap": real_acc - shuf_acc,
        "n_monthly": int(len(mr)),
    }


def run():
    df = load_panel()
    feats = load_features()
    feats = [c for c in feats if c in df.columns]
    print(f"Using {len(feats)} minimal features")

    variants = {
        "E00a_overlapping_rolling": OverlappingSplitter(sample_every_n_days=5),
        "E00b_expanding_decay": ExpandingSplitter(sample_every_n_days=5),
        "E00c_monthly_only": OverlappingSplitter(sample_every_n_days=21),
    }

    results = {}
    for vname, sp in variants.items():
        results[vname] = {}
        for tgt in ["TARGET_T1_winner_idx", "TARGET_T4_drawdown_gt_5pct"]:
            print(f"running {vname} / {tgt}")
            res = run_variant(df, feats, sp, tgt)
            results[vname][tgt] = res
            print("  ", res)

    out = ROOT / "results/diagnostics/E00_results.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, indent=2))
    print("wrote", out)
    return results


if __name__ == "__main__":
    run()
