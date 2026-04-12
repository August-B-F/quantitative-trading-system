# NOT EXECUTED IN-SESSION — run offline. Estimated runtime: ~35 minutes
# (5 retrains of the full walk-forward regime classifier @ ~7 min each).
#
# Removes each top-5 SHAP feature individually, retrains the classifier,
# re-simulates the OPTIMIZED (M26_post_3d) strategy, and records CAGR/Sharpe/MaxDD.
#
# Top-5 features from results/FEATURE_IMPORTANCE_REPORT.md:
#   1. inflation_features__cpi_yoy
#   2. activity_features__ism_pmi
#   3. activity_rail_traffic__rail_traffic_ma4w
#   4. cross_asset_oil_gold__oil_gold_ratio
#   5. activity_features__capacity_utilization
"""Feature ablation stress test (NOT EXECUTED IN-SESSION)."""
from __future__ import annotations
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts/model"))

from stress_harness import (  # noqa: E402
    run_strategy_from_cache,
    load_cache,
    SPLIT_KW,
    REGIME_CLASSES,
)

OUT = ROOT / "results/stress"
OUT.mkdir(parents=True, exist_ok=True)

TOP5 = [
    "inflation_features__cpi_yoy",
    "activity_features__ism_pmi",
    "activity_rail_traffic__rail_traffic_ma4w",
    "cross_asset_oil_gold__oil_gold_ratio",
    "activity_features__capacity_utilization",
]


def retrain_and_eval(drop_feat: str):
    from sklearn.ensemble import HistGradientBoostingClassifier
    from model.walk_forward import ExpandingSplitter
    from model.preprocessing import FeaturePreprocessor

    print(f"[ablate] drop = {drop_feat}")
    df = pd.read_parquet(ROOT / "data/features/master_panel.parquet")
    fs = yaml.safe_load(open(ROOT / "configs/feature_sets.yaml"))
    core_feats = [c for c in fs["core"] if c in df.columns and c != drop_feat]
    DATES = df.index
    NDAYS = len(df)

    splitter = ExpandingSplitter(**SPLIT_KW)
    folds = splitter.split(DATES)
    target_col = "TARGET_TREG_growth_inflation_fwd21"
    cls_to_idx = {c: i for i, c in enumerate(REGIME_CLASSES)}
    pred_reg = np.full(NDAYS, -1, dtype=int)

    for fold in folds:
        tr = fold["train_dates"]; te = fold["test_dates"]
        if len(tr) < 30 or len(te) < 1:
            continue
        sw = np.asarray(fold["train_sample_weights"])
        Xtr = df.loc[tr, core_feats]; ytr_raw = df.loc[tr, target_col]
        Xte = df.loc[te, core_feats]
        mtr = ytr_raw.notna()
        Xtr, ytr_raw, sw = Xtr[mtr], ytr_raw[mtr], sw[mtr.to_numpy()]
        if len(Xtr) < 50:
            continue
        ytr = ytr_raw.map(cls_to_idx).astype(int).to_numpy()
        pp = FeaturePreprocessor()
        Xtr_z = pp.fit_transform(Xtr, sample_weights=sw).to_numpy()
        Xte_z = pp.transform(Xte).to_numpy()
        clf = HistGradientBoostingClassifier(max_iter=200, max_depth=4, learning_rate=0.05,
                                             min_samples_leaf=20, l2_regularization=1.0, random_state=0)
        clf.fit(Xtr_z, ytr, sample_weight=sw)
        proba = clf.predict_proba(Xte_z)
        full = np.zeros((len(Xte_z), 4))
        for j, c in enumerate(clf.classes_):
            full[:, int(c)] = proba[:, j]
        pr = np.argmax(full, axis=1)
        pred_reg[DATES.get_indexer(te)] = pr

    # Run strategy with overridden pred_reg
    cache = load_cache()
    r = run_strategy_from_cache(cache, pred_reg_override=pred_reg)
    return r["stats"]


def main():
    t0 = time.time()
    results = {}
    base = run_strategy_from_cache(load_cache())["stats"]
    results["baseline"] = base
    for feat in TOP5:
        st = retrain_and_eval(feat)
        results[feat] = {
            "stats": st,
            "d_cagr_pp": (st["cagr"] - base["cagr"]) * 100,
            "d_sharpe": st["sharpe"] - base["sharpe"],
            "d_maxdd_pp": (st["max_dd"] - base["max_dd"]) * 100,
        }
        print(f"  {feat}: CAGR {st['cagr']*100:.2f}% dCAGR {(st['cagr']-base['cagr'])*100:+.2f}pp")
    results["wall_seconds"] = time.time() - t0
    (OUT / "test3a.json").write_text(json.dumps(results, indent=2, default=str))
    print(f"\nWrote {OUT / 'test3a.json'}")


if __name__ == "__main__":
    main()
