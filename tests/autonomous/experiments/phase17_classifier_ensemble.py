"""Phase 17: classifier ensemble via random seed averaging.

Train 5 HistGB classifiers with different random_state per fold, average probas.
This is a genuine noise-reduction technique with no leakage.
"""
from __future__ import annotations
import sys, datetime as dt, copy, pickle, types
from pathlib import Path
import numpy as np
import pandas as pd
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from utils.base_test import _load, _STATE, fmt, haircut_verdict  # noqa: E402
from strategy.portfolio import PortfolioEngine  # noqa: E402
from backtest.engine import run_backtest  # noqa: E402
from features.regime_labels import current_regime as _cr, REGIME_CLASSES  # noqa: E402
from features.engineer import load_core_feature_list, select_core_features  # noqa: E402
from model.walk_forward import ExpandingSplitter  # noqa: E402
from model.preprocessing import FeaturePreprocessor  # noqa: E402
from sklearn.ensemble import HistGradientBoostingClassifier  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
CHAMP = {"universe": ["SOXX","QQQ","IGV","XLE","GLD","SHY"], "top1_weight":0.62, "top3_weight":0.38}


def wf_ensemble(core_feats, seeds=(0,1,2,3,4)):
    _load()
    cfg = _STATE["cfg"]; df = _STATE["bundle"].df
    dates = df.index; n = len(dates)
    s = cfg["splitter"]
    splitter = ExpandingSplitter(
        min_train_months=s["min_train_months"], val_months=s["val_months"],
        test_months=s["test_months"], step_months=s["step_months"],
        sample_every_n_days=s["sample_every_n_days"], embargo_days=s["embargo_days"],
        target_horizon=s["target_horizon"], decay_halflife_months=s["decay_halflife_months"])
    folds = splitter.split(dates)
    target = cfg["classifier"]["target_col"]
    cls_to_idx = {c: i for i, c in enumerate(REGIME_CLASSES)}

    pred = np.full(n, -1, dtype=int)
    maxp = np.full(n, np.nan)
    accs = []
    for fold in folds:
        tr = fold["train_dates"]; te = fold["test_dates"]
        if len(tr) < 30 or len(te) < 1: continue
        sw = np.asarray(fold["train_sample_weights"])
        Xtr = df.loc[tr, core_feats]; ytr_raw = df.loc[tr, target]
        Xte = df.loc[te, core_feats]; yte_raw = df.loc[te, target]
        mtr = ytr_raw.notna()
        Xtr, ytr_raw, sw = Xtr[mtr], ytr_raw[mtr], sw[mtr.to_numpy()]
        if len(Xtr) < 50: continue
        ytr = ytr_raw.map(cls_to_idx).astype(int).to_numpy()
        pp = FeaturePreprocessor()
        Xtr_z = pp.fit_transform(Xtr, sample_weights=sw).to_numpy()
        Xte_z = pp.transform(Xte).to_numpy()
        c = cfg["classifier"]
        full = np.zeros((len(Xte_z), 4))
        n_models = 0
        for seed in seeds:
            clf = HistGradientBoostingClassifier(
                max_iter=c["max_iter"], max_depth=c["max_depth"], learning_rate=c["learning_rate"],
                min_samples_leaf=c["min_samples_leaf"], l2_regularization=c["l2_regularization"],
                random_state=seed)
            try: clf.fit(Xtr_z, ytr, sample_weight=sw)
            except Exception: continue
            proba = clf.predict_proba(Xte_z)
            for j, cls in enumerate(clf.classes_):
                full[:, int(cls)] += proba[:, j]
            n_models += 1
        if n_models == 0: continue
        full /= n_models
        pr_ = np.argmax(full, axis=1); mx = full.max(axis=1)
        pos = dates.get_indexer(te)
        pred[pos] = pr_; maxp[pos] = mx
        yte_m = yte_raw.map(cls_to_idx)
        if yte_m.notna().any():
            yv = yte_m.dropna().astype(int).to_numpy()
            accs.append(float((pr_[:len(yv)] == yv[:len(pr_)]).mean()))
    return pred, maxp, (np.mean(accs) if accs else 0.0)


def rankagg_static(weights):
    _load(); b = _STATE["bundle"]
    cm=None; total=sum(w for _,w in weights); ranks=None
    for lb,w in weights:
        r = b.returns[lb]
        if cm is None: cm = list(r.columns)
        else: r = r[cm]
        ranks = r.rank(axis=1,method="average")*w if ranks is None else ranks + r.rank(axis=1,method="average")*w
    return ranks/total

def apply_gate(pred, maxp, thr=0.40):
    _load(); cur = np.asarray(_cr(_STATE["bundle"].df).index)
    out = pred.copy(); w = (pred != cur) & (pred >= 0); lc = np.nan_to_num(maxp,nan=0)<thr
    out[w&lc] = cur[w&lc]; return out

def run_sig(sig, ov, pred):
    _load(); cfg = copy.deepcopy(_STATE["cfg"]); cfg.update(ov or {})
    b = _STATE["bundle"]
    shim = types.SimpleNamespace(**{k:getattr(b,k) for k in ("df","dates","atr21","fwd21","spy_dist_sma200","is_fomc_day")})
    nr = dict(b.returns); nr[cfg["lookback_stable"]]=sig; shim.returns=nr
    eng = PortfolioEngine(shim, pred, cfg)
    return run_backtest(eng, _STATE["test_dates"], cfg).stats


def main():
    _load(); cfg = _STATE["cfg"]; df = _STATE["bundle"].df
    core = load_core_feature_list(ROOT, cfg["classifier"]["feature_set"])
    cp = select_core_features(df, core)
    stable_sig = rankagg_static([(42,1),(63,3),(126,1)])

    log_path = HERE.parent / "LOG.md"
    ts = dt.datetime.now().isoformat(timespec="seconds")
    lines = [f"\n### phase17_classifier_ensemble  {ts}\n",
             "| name | CAGR | Sharpe | MaxDD | accuracy | verdict |","|---|---|---|---|---|---|"]

    experiments = [
        ("P17.01_ens_3seeds", (0,1,2)),
        ("P17.02_ens_5seeds", (0,1,2,3,4)),
        ("P17.03_ens_10seeds", tuple(range(10))),
    ]
    for name, seeds in experiments:
        pr, mp, acc = wf_ensemble(cp, seeds)
        for thr_name, thr in [("gate40", 0.40), ("gate35", 0.35), ("gate45", 0.45)]:
            g = apply_gate(pr, mp, thr)
            s = run_sig(stable_sig, CHAMP, g)
            passes,_ = haircut_verdict(s)
            v = "PASS" if passes else "fail"
            full_name = f"{name}_{thr_name}"
            print(full_name, fmt(s), f"acc={acc:.3f}", v)
            lines.append(f"| {full_name} | {s['cagr']*100:.2f}% | {s['sharpe']:.2f} | {s['max_dd']*100:.2f}% | {acc:.3f} | {v} |")

    with open(log_path,"a",encoding="utf-8") as f: f.write("\n".join(lines)+"\n")

if __name__ == "__main__":
    main()
