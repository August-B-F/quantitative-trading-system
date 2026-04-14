"""Phase 6: classifier confidence-gated lookback switch.

Build the walk-forward predictions WITH probability output, then test rules like
'only switch to 21d if max_prob > threshold'.

Runs one fresh WF training pass to capture proba (~16s).
"""
from __future__ import annotations
import sys, datetime as dt, copy, pickle
from pathlib import Path
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from utils.base_test import _load, _STATE, fmt, haircut_verdict  # noqa: E402
from strategy.portfolio import PortfolioEngine  # noqa: E402
from backtest.engine import run_backtest  # noqa: E402
from model.walk_forward import ExpandingSplitter  # noqa: E402
from model.preprocessing import FeaturePreprocessor  # noqa: E402
from features.regime_labels import REGIME_CLASSES  # noqa: E402
from sklearn.ensemble import HistGradientBoostingClassifier  # noqa: E402
from features.engineer import load_core_feature_list, select_core_features  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
PROBA_CACHE = HERE.parent / "cache" / "pred_proba.pkl"

CHAMP = {"universe": ["SOXX","QQQ","IGV","XLE","GLD","SHY"], "top1_weight":0.60, "top3_weight":0.40}


def wf_predict_with_proba():
    if PROBA_CACHE.exists():
        with open(PROBA_CACHE, "rb") as f:
            return pickle.load(f)
    _load()
    cfg = _STATE["cfg"]
    df = _STATE["bundle"].df
    core = load_core_feature_list(ROOT, cfg["classifier"]["feature_set"])
    core_feats = select_core_features(df, core)

    dates = df.index
    n = len(dates)
    s = cfg["splitter"]
    splitter = ExpandingSplitter(
        min_train_months=s["min_train_months"], val_months=s["val_months"],
        test_months=s["test_months"], step_months=s["step_months"],
        sample_every_n_days=s["sample_every_n_days"], embargo_days=s["embargo_days"],
        target_horizon=s["target_horizon"], decay_halflife_months=s["decay_halflife_months"],
    )
    folds = splitter.split(dates)
    target_col = cfg["classifier"]["target_col"]
    cls_to_idx = {c: i for i, c in enumerate(REGIME_CLASSES)}

    pred_reg = np.full(n, -1, dtype=int)
    pred_max_prob = np.full(n, np.nan)
    for fold in folds:
        tr = fold["train_dates"]; te = fold["test_dates"]
        if len(tr) < 30 or len(te) < 1:
            continue
        sw = np.asarray(fold["train_sample_weights"])
        Xtr = df.loc[tr, core_feats]; ytr_raw = df.loc[tr, target_col]
        Xte = df.loc[te, core_feats]
        mtr = ytr_raw.notna()
        Xtr, ytr_raw, sw = Xtr[mtr], ytr_raw[mtr], sw[mtr.to_numpy()]
        if len(Xtr) < 50: continue
        ytr = ytr_raw.map(cls_to_idx).astype(int).to_numpy()
        pp = FeaturePreprocessor()
        Xtr_z = pp.fit_transform(Xtr, sample_weights=sw).to_numpy()
        Xte_z = pp.transform(Xte).to_numpy()
        c = cfg["classifier"]
        clf = HistGradientBoostingClassifier(
            max_iter=c["max_iter"], max_depth=c["max_depth"], learning_rate=c["learning_rate"],
            min_samples_leaf=c["min_samples_leaf"], l2_regularization=c["l2_regularization"],
            random_state=c["random_state"])
        try: clf.fit(Xtr_z, ytr, sample_weight=sw)
        except Exception: continue
        proba = clf.predict_proba(Xte_z)
        full = np.zeros((len(Xte_z), 4))
        for j, cls in enumerate(clf.classes_):
            full[:, int(cls)] = proba[:, j]
        pr = np.argmax(full, axis=1)
        mx = full.max(axis=1)
        te_pos = dates.get_indexer(te)
        pred_reg[te_pos] = pr
        pred_max_prob[te_pos] = mx

    PROBA_CACHE.parent.mkdir(parents=True, exist_ok=True)
    with open(PROBA_CACHE, "wb") as f:
        pickle.dump((pred_reg, pred_max_prob), f)
    return pred_reg, pred_max_prob


def make_gated_pred(pred_reg, pred_max_prob, current_reg_arr, threshold):
    """If model confidence < threshold and it would switch, override to current regime (→ 63d)."""
    out = pred_reg.copy()
    want_switch = (pred_reg != current_reg_arr) & (pred_reg >= 0)
    low_conf = np.nan_to_num(pred_max_prob, nan=0.0) < threshold
    override = want_switch & low_conf
    out[override] = current_reg_arr[override]
    return out


def run_with_pred(pred_reg, overrides):
    _load()
    cfg = copy.deepcopy(_STATE["cfg"]); cfg.update(overrides or {})
    engine = PortfolioEngine(_STATE["bundle"], pred_reg, cfg)
    res = run_backtest(engine, _STATE["test_dates"], cfg)
    return res.stats


def main():
    pred_reg, pred_max_prob = wf_predict_with_proba()
    print(f"proba cached. distribution of max_prob:")
    mx = pred_max_prob[~np.isnan(pred_max_prob)]
    print(f"  min={mx.min():.3f} med={np.median(mx):.3f} max={mx.max():.3f}")
    print(f"  pct >0.5: {(mx>0.5).mean():.2f}  >0.6: {(mx>0.6).mean():.2f}  >0.7: {(mx>0.7).mean():.2f}")

    _load()
    from features.regime_labels import current_regime as _cr
    bundle = _STATE["bundle"]
    current_reg = np.asarray(_cr(bundle.df).index)  # ndarray of class codes
    switches = ((pred_reg != current_reg) & (pred_reg >= 0)).sum()
    print(f"total would-switch decisions: {switches}")

    log_path = HERE.parent / "LOG.md"
    ts = dt.datetime.now().isoformat(timespec="seconds")
    lines = [f"\n### phase6_classifier_confidence  {ts}\n",
             "| name | CAGR | Sharpe | MaxDD | verdict |",
             "|---|---|---|---|---|"]

    experiments = []
    # baseline using fresh pred_reg (same argmax)
    experiments.append(("P6.00_argmax_base", pred_reg, {}))
    experiments.append(("P6.00_argmax_champ", pred_reg, CHAMP))

    for thr in (0.30, 0.35, 0.40, 0.45, 0.50, 0.60, 0.70):
        gated = make_gated_pred(pred_reg, pred_max_prob, current_reg, thr)
        experiments.append((f"P6.01_gate{int(thr*100)}_base", gated, {}))
        experiments.append((f"P6.01_gate{int(thr*100)}_champ", gated, CHAMP))

    for name, pr, ov in experiments:
        try: s = run_with_pred(pr, ov)
        except Exception as e: s = {"error": str(e)}
        if "error" in s:
            print(name, "ERROR", s["error"])
            lines.append(f"| {name} | | | | ERR |"); continue
        passes, _ = haircut_verdict(s)
        v = "PASS" if passes else "fail"
        print(name, fmt(s), v)
        lines.append(f"| {name} | {s['cagr']*100:.2f}% | {s['sharpe']:.2f} | {s['max_dd']*100:.2f}% | {v} |")
    with open(log_path, "a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

if __name__ == "__main__":
    main()
