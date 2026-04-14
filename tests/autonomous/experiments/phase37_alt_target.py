"""Phase 37: retrain classifier on alternative target (VIX regime or drawdown).

Test whether these targets produce better switch timing than growth/inflation.
"""
from __future__ import annotations
import sys, datetime as dt, copy, types
from pathlib import Path
import numpy as np
import pandas as pd
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from utils.base_test import _load, _STATE, fmt, haircut_verdict  # noqa: E402
from strategy.portfolio import PortfolioEngine  # noqa: E402
from backtest.engine import run_backtest, compute_stats  # noqa: E402
from strategy.rebalance import fomc_window_mask, resolve_rebalance_index  # noqa: E402
from features.engineer import load_core_feature_list, select_core_features  # noqa: E402
from model.walk_forward import ExpandingSplitter  # noqa: E402
from model.preprocessing import FeaturePreprocessor  # noqa: E402
from features.regime_labels import current_regime as _cr  # noqa: E402
from sklearn.ensemble import HistGradientBoostingClassifier  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
STABLE = ["SOXX","QQQ","IGV","XLE","GLD","SHY"]
TRANS  = STABLE + ["TLT","AGG","XLV"]


def wf_retrain_target(target_col, core_feats):
    """WF retrain with alternative target. Returns pred (class idx), proba (max)."""
    _load(); cfg = _STATE["cfg"]; df = _STATE["bundle"].df
    dates = df.index; n = len(dates)
    s = cfg["splitter"]
    sp = ExpandingSplitter(
        min_train_months=s["min_train_months"], val_months=s["val_months"],
        test_months=s["test_months"], step_months=s["step_months"],
        sample_every_n_days=s["sample_every_n_days"], embargo_days=s["embargo_days"],
        target_horizon=s["target_horizon"], decay_halflife_months=s["decay_halflife_months"])
    folds = sp.split(dates)
    # Build class index mapping from unique values in target
    t_raw = df[target_col]
    if t_raw.dtype == object or hasattr(t_raw, 'cat'):
        vals = sorted(t_raw.dropna().unique().tolist())
    else:
        vals = sorted(t_raw.dropna().unique().tolist())
    cls_to_idx = {v: i for i, v in enumerate(vals)}
    n_classes = len(vals)
    print(f"target={target_col}  classes={vals}")
    pred = np.full(n, -1, dtype=int); maxp = np.full(n, np.nan)
    for fold in folds:
        tr = fold["train_dates"]; te = fold["test_dates"]
        if len(tr)<30 or len(te)<1: continue
        sw = np.asarray(fold["train_sample_weights"])
        Xtr = df.loc[tr, core_feats]; ytr_raw = df.loc[tr, target_col]
        Xte = df.loc[te, core_feats]
        mtr = ytr_raw.notna(); Xtr, ytr_raw, sw = Xtr[mtr], ytr_raw[mtr], sw[mtr.to_numpy()]
        if len(Xtr) < 50: continue
        ytr = ytr_raw.map(cls_to_idx).astype(int).to_numpy()
        pp = FeaturePreprocessor()
        Xtr_z = pp.fit_transform(Xtr, sample_weights=sw).to_numpy()
        Xte_z = pp.transform(Xte).to_numpy()
        c = cfg["classifier"]
        clf = HistGradientBoostingClassifier(max_iter=c["max_iter"],max_depth=c["max_depth"],
            learning_rate=c["learning_rate"],min_samples_leaf=c["min_samples_leaf"],
            l2_regularization=c["l2_regularization"],random_state=c["random_state"])
        try: clf.fit(Xtr_z, ytr, sample_weight=sw)
        except Exception: continue
        proba = clf.predict_proba(Xte_z)
        full = np.zeros((len(Xte_z), n_classes))
        for j, cls in enumerate(clf.classes_):
            full[:, int(cls)] = proba[:, j]
        pr_ = np.argmax(full, axis=1); mx = full.max(axis=1)
        pos = dates.get_indexer(te)
        pred[pos] = pr_; maxp[pos] = mx
    return pred, maxp, vals


def rankagg(weights):
    _load(); b = _STATE["bundle"]
    cm=None; total=sum(w for _,w in weights); ranks=None
    for lb,w in weights:
        r = b.returns[lb]
        if cm is None: cm = list(r.columns)
        else: r = r[cm]
        ranks = r.rank(axis=1,method="average")*w if ranks is None else ranks+r.rank(axis=1,method="average")*w
    return ranks/total


def run_alt_classifier(pred, maxp, vals, sig, high_regime_set):
    """high_regime_set: set of class indices that should trigger transition."""
    _load(); b = _STATE["bundle"]
    def mk_eng(uni):
        cfg = copy.deepcopy(_STATE["cfg"])
        cfg.update({"universe":uni,"top1_weight":0.62,"top3_weight":0.38})
        shim = types.SimpleNamespace(**{k:getattr(b,k) for k in ("df","dates","atr21","fwd21","spy_dist_sma200","is_fomc_day")})
        nr = dict(b.returns); nr[cfg["lookback_stable"]]=sig; shim.returns=nr
        # Build a fake pred_reg vector for the engine: if prediction in high_regime_set → use transition
        fake_pred = np.full(len(pred), -1, dtype=int)
        # Engine will switch to 21d when pred != current_regime. We want switch when pred in high_regime_set.
        # Use a trick: set fake_pred = 99 (unseen) when prediction hits high regime, else match current.
        from features.regime_labels import current_regime as _cr
        cur = np.asarray(_cr(b.df).index)
        fake_pred[:] = cur  # default to current (so use_trans=False → 63d)
        is_switch = np.isin(pred, list(high_regime_set)) & (maxp >= 0.40)
        # Set different from current
        fake_pred[is_switch] = (cur[is_switch] + 1) % 4
        return PortfolioEngine(shim, fake_pred, cfg), fake_pred
    eng_s, fp = mk_eng(STABLE); eng_t, _ = mk_eng(TRANS)
    td = _STATE["test_dates"]
    td_positions = pd.Series(eng_s.dates.get_indexer(td), index=td)
    month_last = td_positions.groupby(td.to_period("M")).tail(1)
    fomc_idx = np.where(b.is_fomc_day)[0]
    event_mask = fomc_window_mask(eng_s.n_days, fomc_idx, pre_days=0, post_days=2)
    def ret_at(eng, i):
        t1,tk = eng.pick_at(i)
        r1 = eng.fwd_arr[i,t1] if eng.spy_dist[i]>eng.sma_buffer else eng.cash_fwd[i]
        sel = eng.atr_arr[i,tk]; inv = 1.0/np.where(sel>0,sel,np.nan)
        if np.isnan(inv).all(): rk = np.nanmean(eng.fwd_arr[i,tk])
        else: ww=inv/np.nansum(inv); rk=np.nansum(eng.fwd_arr[i,tk]*ww)
        return eng.top1_w*r1 + eng.topk_w*rk
    rets = []
    for rd, pos in month_last.items():
        i, _ = resolve_rebalance_index(int(pos), 3, event_mask, eng_s.n_days)
        use_t = (np.isin(pred[i], list(high_regime_set))) and (not np.isnan(maxp[i])) and (maxp[i] >= 0.50)
        rets.append(ret_at(eng_t if use_t else eng_s, i))
    return compute_stats(np.array(rets))


def main():
    _load(); df = _STATE["bundle"].df
    cfg = _STATE["cfg"]
    core = load_core_feature_list(ROOT, cfg["classifier"]["feature_set"])
    cp = select_core_features(df, core)
    sig = rankagg([(42,1),(63,3),(126,1)])

    log_path = HERE.parent / "LOG.md"
    ts = dt.datetime.now().isoformat(timespec="seconds")
    lines = [f"\n### phase37_alt_target  {ts}\n",
             "| name | CAGR | Sharpe | MaxDD | verdict |","|---|---|---|---|---|"]

    # VIX regime target
    try:
        pr_v, mp_v, v_vals = wf_retrain_target("TARGET_TREG_vix_regime_fwd21", cp)
        # "high" = the highest-vix class (index = last in vals)
        print("VIX class vals:", v_vals)
        # Try high-index classes (high/extreme)
        for hs_name, hs in [("topclass", {len(v_vals)-1}), ("top2class", {len(v_vals)-2, len(v_vals)-1})]:
            s = run_alt_classifier(pr_v, mp_v, v_vals, sig, hs)
            passes, _ = haircut_verdict(s)
            v = "PASS" if passes else "fail"
            name = f"P37.01_vix_{hs_name}"
            print(name, fmt(s), v)
            lines.append(f"| {name} | {s['cagr']*100:.2f}% | {s['sharpe']:.2f} | {s['max_dd']*100:.2f}% | {v} |")
    except Exception as e:
        print("vix fail:", e)

    # Drawdown target (5pct)
    for col in ("TARGET_T4_drawdown_gt_3pct", "TARGET_T4_drawdown_gt_5pct", "TARGET_T4_drawdown_gt_7pct"):
        if col not in df.columns: continue
        try:
            pr_d, mp_d, d_vals = wf_retrain_target(col, cp)
            # "high" = class 1 (drawdown occurred)
            hi = {len(d_vals)-1} if len(d_vals) > 1 else set()
            s = run_alt_classifier(pr_d, mp_d, d_vals, sig, hi)
            passes, _ = haircut_verdict(s)
            v = "PASS" if passes else "fail"
            name = f"P37.02_{col.split('__')[-1] if '__' in col else col.split('_')[-1]}"
            print(name, fmt(s), v)
            lines.append(f"| {name} | {s['cagr']*100:.2f}% | {s['sharpe']:.2f} | {s['max_dd']*100:.2f}% | {v} |")
        except Exception as e:
            print(f"{col} fail:", e)

    with open(log_path,"a",encoding="utf-8") as f: f.write("\n".join(lines)+"\n")


if __name__ == "__main__":
    main()
