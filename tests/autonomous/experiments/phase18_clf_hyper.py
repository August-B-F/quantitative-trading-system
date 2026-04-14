"""Phase 18: classifier hyperparameter variants (max_depth, lr, max_iter, l2)."""
from __future__ import annotations
import sys, datetime as dt, copy, types
from pathlib import Path
import numpy as np
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


def wf_custom(core_feats, hp):
    _load(); cfg = _STATE["cfg"]; df = _STATE["bundle"].df
    dates = df.index; n = len(dates)
    s = cfg["splitter"]
    sp = ExpandingSplitter(
        min_train_months=s["min_train_months"], val_months=s["val_months"],
        test_months=s["test_months"], step_months=s["step_months"],
        sample_every_n_days=s["sample_every_n_days"], embargo_days=s["embargo_days"],
        target_horizon=s["target_horizon"], decay_halflife_months=s["decay_halflife_months"])
    folds = sp.split(dates)
    target = cfg["classifier"]["target_col"]
    cls_to_idx = {c: i for i, c in enumerate(REGIME_CLASSES)}
    pred = np.full(n,-1,dtype=int); maxp = np.full(n,np.nan); accs = []
    for fold in folds:
        tr,te = fold["train_dates"], fold["test_dates"]
        if len(tr)<30 or len(te)<1: continue
        sw = np.asarray(fold["train_sample_weights"])
        Xtr = df.loc[tr, core_feats]; ytr_raw = df.loc[tr, target]
        Xte = df.loc[te, core_feats]; yte_raw = df.loc[te, target]
        mtr = ytr_raw.notna(); Xtr,ytr_raw,sw = Xtr[mtr],ytr_raw[mtr],sw[mtr.to_numpy()]
        if len(Xtr)<50: continue
        ytr = ytr_raw.map(cls_to_idx).astype(int).to_numpy()
        pp = FeaturePreprocessor()
        Xtr_z = pp.fit_transform(Xtr, sample_weights=sw).to_numpy()
        Xte_z = pp.transform(Xte).to_numpy()
        clf = HistGradientBoostingClassifier(random_state=0, **hp)
        try: clf.fit(Xtr_z, ytr, sample_weight=sw)
        except Exception: continue
        proba = clf.predict_proba(Xte_z)
        full = np.zeros((len(Xte_z),4))
        for j,c in enumerate(clf.classes_): full[:,int(c)] = proba[:,j]
        pr_ = np.argmax(full,axis=1); mx = full.max(axis=1)
        pos = dates.get_indexer(te)
        pred[pos]=pr_; maxp[pos]=mx
        yte_m = yte_raw.map(cls_to_idx)
        if yte_m.notna().any():
            yv = yte_m.dropna().astype(int).to_numpy()
            accs.append(float((pr_[:len(yv)]==yv[:len(pr_)]).mean()))
    return pred, maxp, (np.mean(accs) if accs else 0.0)


def rankagg(weights):
    _load(); b = _STATE["bundle"]
    cm=None; total=sum(w for _,w in weights); ranks=None
    for lb,w in weights:
        r = b.returns[lb]
        if cm is None: cm = list(r.columns)
        else: r = r[cm]
        ranks = r.rank(axis=1,method="average")*w if ranks is None else ranks + r.rank(axis=1,method="average")*w
    return ranks/total

def apply_gate(pred, mp, thr=0.40):
    _load(); cur = np.asarray(_cr(_STATE["bundle"].df).index)
    out = pred.copy(); w=(pred!=cur)&(pred>=0); lc = np.nan_to_num(mp,nan=0)<thr
    out[w&lc]=cur[w&lc]; return out

def run_sig(sig, ov, pred):
    _load(); cfg = copy.deepcopy(_STATE["cfg"]); cfg.update(ov or {})
    b = _STATE["bundle"]
    shim = types.SimpleNamespace(**{k:getattr(b,k) for k in ("df","dates","atr21","fwd21","spy_dist_sma200","is_fomc_day")})
    nr = dict(b.returns); nr[cfg["lookback_stable"]]=sig; shim.returns=nr
    eng = PortfolioEngine(shim, pred, cfg)
    return run_backtest(eng, _STATE["test_dates"], cfg).stats


def main():
    _load(); df = _STATE["bundle"].df; cfg = _STATE["cfg"]
    cp = select_core_features(df, load_core_feature_list(ROOT, cfg["classifier"]["feature_set"]))
    sig = rankagg([(42,1),(63,3),(126,1)])

    HP_GRID = [
        ("H0_default",     dict(max_iter=200,max_depth=4,learning_rate=0.05,min_samples_leaf=20,l2_regularization=1.0)),
        ("H1_d3_lr05",     dict(max_iter=200,max_depth=3,learning_rate=0.05,min_samples_leaf=20,l2_regularization=1.0)),
        ("H2_d5_lr05",     dict(max_iter=200,max_depth=5,learning_rate=0.05,min_samples_leaf=20,l2_regularization=1.0)),
        ("H3_d6_lr05",     dict(max_iter=200,max_depth=6,learning_rate=0.05,min_samples_leaf=20,l2_regularization=1.0)),
        ("H4_d4_lr03",     dict(max_iter=300,max_depth=4,learning_rate=0.03,min_samples_leaf=20,l2_regularization=1.0)),
        ("H5_d4_lr10",     dict(max_iter=100,max_depth=4,learning_rate=0.10,min_samples_leaf=20,l2_regularization=1.0)),
        ("H6_d4_leaf10",   dict(max_iter=200,max_depth=4,learning_rate=0.05,min_samples_leaf=10,l2_regularization=1.0)),
        ("H7_d4_leaf40",   dict(max_iter=200,max_depth=4,learning_rate=0.05,min_samples_leaf=40,l2_regularization=1.0)),
        ("H8_d4_l2_5",     dict(max_iter=200,max_depth=4,learning_rate=0.05,min_samples_leaf=20,l2_regularization=5.0)),
        ("H9_d4_l2_0p1",   dict(max_iter=200,max_depth=4,learning_rate=0.05,min_samples_leaf=20,l2_regularization=0.1)),
        ("H10_d4_iter500", dict(max_iter=500,max_depth=4,learning_rate=0.05,min_samples_leaf=20,l2_regularization=1.0)),
    ]

    log_path = HERE.parent / "LOG.md"
    ts = dt.datetime.now().isoformat(timespec="seconds")
    lines = [f"\n### phase18_clf_hyper  {ts}\n",
             "| name | CAGR | Sharpe | MaxDD | accuracy | verdict |","|---|---|---|---|---|---|"]
    for name, hp in HP_GRID:
        pr, mp, acc = wf_custom(cp, hp)
        g = apply_gate(pr, mp, 0.40)
        s = run_sig(sig, CHAMP, g)
        passes,_ = haircut_verdict(s)
        v = "PASS" if passes else "fail"
        print(name, fmt(s), f"acc={acc:.3f}", v)
        lines.append(f"| {name} | {s['cagr']*100:.2f}% | {s['sharpe']:.2f} | {s['max_dd']*100:.2f}% | {acc:.3f} | {v} |")
    with open(log_path,"a",encoding="utf-8") as f: f.write("\n".join(lines)+"\n")


if __name__ == "__main__":
    main()
