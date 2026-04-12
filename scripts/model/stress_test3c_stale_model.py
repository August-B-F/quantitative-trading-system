# NOT EXECUTED IN-SESSION — run offline. Estimated runtime: ~20 minutes
# (3 partial walk-forward retrains with frozen cutoffs @ ~6 min each).
#
# Trains the regime classifier on data through end of 2018 / 2020 / 2022 only,
# then applies that frozen classifier forward to all subsequent test dates
# (no re-training). Measures performance degradation from model staleness.
"""Stale-model stress test (NOT EXECUTED IN-SESSION)."""
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
    run_strategy_from_cache, stats, load_cache, SPLIT_KW, REGIME_CLASSES,
)

OUT = ROOT / "results/stress"
OUT.mkdir(parents=True, exist_ok=True)

FREEZE_CUTOFFS = ["2018-12-31", "2020-12-31", "2022-12-31"]


def freeze_and_eval(cutoff: str):
    from sklearn.ensemble import HistGradientBoostingClassifier
    from model.walk_forward import ExpandingSplitter
    from model.preprocessing import FeaturePreprocessor

    print(f"[freeze] cutoff = {cutoff}")
    df = pd.read_parquet(ROOT / "data/features/master_panel.parquet")
    fs = yaml.safe_load(open(ROOT / "configs/feature_sets.yaml"))
    core_feats = [c for c in fs["core"] if c in df.columns]
    DATES = df.index
    NDAYS = len(df)

    splitter = ExpandingSplitter(**SPLIT_KW)
    folds = splitter.split(DATES)
    target_col = "TARGET_TREG_growth_inflation_fwd21"
    cls_to_idx = {c: i for i, c in enumerate(REGIME_CLASSES)}
    pred_reg = np.full(NDAYS, -1, dtype=int)

    cutoff_ts = pd.Timestamp(cutoff)
    last_clf = None
    last_pp = None
    for fold in folds:
        tr = fold["train_dates"]; te = fold["test_dates"]
        if len(tr) < 30 or len(te) < 1:
            continue
        # Only retrain if training data ends before cutoff
        train_end = pd.Timestamp(max(tr))
        if train_end <= cutoff_ts:
            sw = np.asarray(fold["train_sample_weights"])
            Xtr = df.loc[tr, core_feats]; ytr_raw = df.loc[tr, target_col]
            mtr = ytr_raw.notna()
            Xtr, ytr_raw, sw = Xtr[mtr], ytr_raw[mtr], sw[mtr.to_numpy()]
            if len(Xtr) < 50:
                continue
            ytr = ytr_raw.map(cls_to_idx).astype(int).to_numpy()
            pp = FeaturePreprocessor()
            Xtr_z = pp.fit_transform(Xtr, sample_weights=sw).to_numpy()
            clf = HistGradientBoostingClassifier(max_iter=200, max_depth=4, learning_rate=0.05,
                                                 min_samples_leaf=20, l2_regularization=1.0, random_state=0)
            clf.fit(Xtr_z, ytr, sample_weight=sw)
            last_clf = clf
            last_pp = pp
        if last_clf is None:
            continue
        Xte = df.loc[te, core_feats]
        Xte_z = last_pp.transform(Xte).to_numpy()
        proba = last_clf.predict_proba(Xte_z)
        full = np.zeros((len(Xte_z), 4))
        for j, c in enumerate(last_clf.classes_):
            full[:, int(c)] = proba[:, j]
        pr = np.argmax(full, axis=1)
        pred_reg[DATES.get_indexer(te)] = pr

    cache = load_cache()
    r = run_strategy_from_cache(cache, pred_reg_override=pred_reg)
    # Forward-only window: from cutoff+1d to end of data
    fwd_start = (cutoff_ts + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    end_s = pd.Timestamp(cache["DATES"][-1]).strftime("%Y-%m-%d")
    r_fwd = run_strategy_from_cache(cache, pred_reg_override=pred_reg,
                                    date_range=(fwd_start, end_s))
    # Regime accuracy on forward window
    DATES = cache["DATES"]
    current_reg = cache["current_reg"]
    fwd_mask = (DATES > cutoff_ts) & (pred_reg != -1)
    acc = float((pred_reg[fwd_mask] == current_reg[fwd_mask]).mean()) if fwd_mask.any() else float("nan")
    return {"full_stats": r["stats"], "forward_stats": r_fwd["stats"],
            "forward_regime_acc": acc, "forward_n_days": int(fwd_mask.sum())}


def main():
    t0 = time.time()
    out = {"baseline": run_strategy_from_cache(load_cache())["stats"]}
    for co in FREEZE_CUTOFFS:
        res = freeze_and_eval(co)
        out[co] = res
        fs = res["forward_stats"]
        print(f"  freeze {co}: FWD CAGR {fs['cagr']*100:.2f}%  Sharpe {fs['sharpe']:.2f}  "
              f"MaxDD {fs['max_dd']*100:.2f}%  regime_acc {res['forward_regime_acc']:.3f}")
    out["wall_seconds"] = time.time() - t0
    (OUT / "test3c.json").write_text(json.dumps(out, indent=2, default=str))
    print(f"Wrote {OUT / 'test3c.json'}")


if __name__ == "__main__":
    main()
