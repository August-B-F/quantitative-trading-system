"""Phase 16: retrain classifier with trimmed feature sets.

Compute feature importances across all walk-forward folds, then retrain with
top-N features for various N, test effect on champion.
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
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier  # noqa: E402
from sklearn.inspection import permutation_importance  # noqa: E402
from sklearn.linear_model import LogisticRegression  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
CHAMP = {"universe": ["SOXX","QQQ","IGV","XLE","GLD","SHY"], "top1_weight":0.62, "top3_weight":0.38}


def wf_retrain(core_feats, model_kind="histgb"):
    """Retrain WF classifier and return (pred_reg, max_proba, accuracy)."""
    _load()
    cfg = _STATE["cfg"]
    df = _STATE["bundle"].df
    dates = df.index; n = len(dates)
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
    pred_max = np.full(n, np.nan)
    accs = []
    for fold in folds:
        tr = fold["train_dates"]; te = fold["test_dates"]
        if len(tr) < 30 or len(te) < 1: continue
        sw = np.asarray(fold["train_sample_weights"])
        Xtr = df.loc[tr, core_feats]; ytr_raw = df.loc[tr, target_col]
        Xte = df.loc[te, core_feats]; yte_raw = df.loc[te, target_col]
        mtr = ytr_raw.notna()
        Xtr, ytr_raw, sw = Xtr[mtr], ytr_raw[mtr], sw[mtr.to_numpy()]
        if len(Xtr) < 50: continue
        ytr = ytr_raw.map(cls_to_idx).astype(int).to_numpy()
        pp = FeaturePreprocessor()
        Xtr_z = pp.fit_transform(Xtr, sample_weights=sw).to_numpy()
        Xte_z = pp.transform(Xte).to_numpy()
        c = cfg["classifier"]
        if model_kind == "histgb":
            clf = HistGradientBoostingClassifier(
                max_iter=c["max_iter"], max_depth=c["max_depth"], learning_rate=c["learning_rate"],
                min_samples_leaf=c["min_samples_leaf"], l2_regularization=c["l2_regularization"],
                random_state=c["random_state"])
        elif model_kind == "rf":
            clf = RandomForestClassifier(n_estimators=300, max_depth=6, min_samples_leaf=20, random_state=0, n_jobs=-1)
        elif model_kind == "logreg":
            clf = LogisticRegression(max_iter=500, C=1.0, random_state=0, n_jobs=-1)
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
        pred_max[te_pos] = mx
        yte_m = yte_raw.map(cls_to_idx)
        if yte_m.notna().any():
            yv = yte_m.dropna().astype(int).to_numpy()
            accs.append(float((pr[: len(yv)] == yv[: len(pr)]).mean()))
    return pred_reg, pred_max, (np.mean(accs) if accs else 0.0)


def feature_importance_ranking(core_feats):
    """Train HistGB on all data, permutation importance to rank features."""
    _load()
    cfg = _STATE["cfg"]; df = _STATE["bundle"].df
    target_col = cfg["classifier"]["target_col"]
    cls_to_idx = {c: i for i, c in enumerate(REGIME_CLASSES)}
    m = df[target_col].notna()
    X = df.loc[m, core_feats]; y = df.loc[m, target_col].map(cls_to_idx).astype(int).to_numpy()
    pp = FeaturePreprocessor()
    Xz = pp.fit_transform(X).to_numpy()
    c = cfg["classifier"]
    clf = HistGradientBoostingClassifier(
        max_iter=c["max_iter"], max_depth=c["max_depth"], learning_rate=c["learning_rate"],
        min_samples_leaf=c["min_samples_leaf"], l2_regularization=c["l2_regularization"],
        random_state=c["random_state"])
    clf.fit(Xz, y)
    # HistGB doesn't expose feature_importances_ directly, use permutation on holdout
    # Cheap alternative: train/test split
    n = len(Xz); cut = int(n*0.8)
    clf2 = HistGradientBoostingClassifier(
        max_iter=c["max_iter"], max_depth=c["max_depth"], learning_rate=c["learning_rate"],
        min_samples_leaf=c["min_samples_leaf"], l2_regularization=c["l2_regularization"],
        random_state=c["random_state"])
    clf2.fit(Xz[:cut], y[:cut])
    r = permutation_importance(clf2, Xz[cut:], y[cut:], n_repeats=5, random_state=0, n_jobs=-1)
    imp = pd.Series(r.importances_mean, index=core_feats).sort_values(ascending=False)
    return imp


def rankagg_static(weights):
    _load(); b = _STATE["bundle"]
    cm = None; total = sum(w for _,w in weights); ranks = None
    for lb, w in weights:
        r = b.returns[lb]
        if cm is None: cm = list(r.columns)
        else: r = r[cm]
        ranks = r.rank(axis=1,method="average")*w if ranks is None else ranks + r.rank(axis=1,method="average")*w
    return ranks/total


def apply_gate(pred, maxp, thr=0.40):
    _load(); cur = np.asarray(_cr(_STATE["bundle"].df).index)
    out = pred.copy(); w = (pred != cur) & (pred >= 0); lc = np.nan_to_num(maxp,nan=0)<thr
    out[w&lc]=cur[w&lc]; return out


def run_sig(sig, ov, pred):
    _load(); cfg = copy.deepcopy(_STATE["cfg"]); cfg.update(ov or {})
    b = _STATE["bundle"]
    shim = types.SimpleNamespace(**{k:getattr(b,k) for k in ("df","dates","atr21","fwd21","spy_dist_sma200","is_fomc_day")})
    nr = dict(b.returns); nr[cfg["lookback_stable"]]=sig; shim.returns=nr
    eng = PortfolioEngine(shim, pred, cfg)
    return run_backtest(eng, _STATE["test_dates"], cfg).stats


def main():
    _load()
    cfg = _STATE["cfg"]; df = _STATE["bundle"].df
    core = load_core_feature_list(ROOT, cfg["classifier"]["feature_set"])
    core_present = select_core_features(df, core)
    print(f"CORE features present: {len(core_present)}")

    # Must keep cpi_yoy per non-negotiable
    CPI_COL = "inflation_features__cpi_yoy"
    if CPI_COL not in core_present:
        print("WARNING: cpi_yoy not in core!")

    imp = feature_importance_ranking(core_present)
    imp.to_csv(HERE.parent / "cache" / "feature_importances.csv")
    print("Top-10 features:")
    print(imp.head(10))
    print("...Bottom-5:")
    print(imp.tail(5))

    stable_sig = rankagg_static([(42,1),(63,3),(126,1)])

    log_path = HERE.parent / "LOG.md"
    ts = dt.datetime.now().isoformat(timespec="seconds")
    lines = [f"\n### phase16_classifier_feature_trim  {ts}\n",
             f"Feature importance top: {imp.head(5).index.tolist()}\n",
             "| name | CAGR | Sharpe | MaxDD | accuracy | verdict |",
             "|---|---|---|---|---|---|"]

    # Retrain with top-N features (forcing cpi_yoy in)
    experiments = []
    for N in (10, 15, 20, 30, 40):
        top = list(imp.head(N).index)
        if CPI_COL not in top and CPI_COL in core_present:
            top.append(CPI_COL)
        experiments.append((f"P16.01_top{N}", top, "histgb"))
    # Full set with RF and LogReg
    experiments.append(("P16.02_full_rf", core_present, "rf"))
    experiments.append(("P16.03_full_logreg", core_present, "logreg"))

    for name, feats, kind in experiments:
        try:
            pr, mp, acc = wf_retrain(feats, kind)
            g = apply_gate(pr, mp, 0.40)
            s = run_sig(stable_sig, CHAMP, g)
        except Exception as e:
            print(name, "ERROR", e)
            lines.append(f"| {name} | | | | | ERR |"); continue
        passes,_ = haircut_verdict(s)
        v = "PASS" if passes else "fail"
        print(name, fmt(s), f"acc={acc:.3f}", v)
        lines.append(f"| {name} | {s['cagr']*100:.2f}% | {s['sharpe']:.2f} | {s['max_dd']*100:.2f}% | {acc:.3f} | {v} |")
    with open(log_path,"a",encoding="utf-8") as f: f.write("\n".join(lines)+"\n")


if __name__ == "__main__":
    main()
