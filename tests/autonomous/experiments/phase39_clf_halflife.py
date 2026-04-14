"""Phase 39: classifier walk-forward with alternate decay halflife.

Current: decay_halflife_months=36. Try 12, 24, 48, 60, and None.
"""
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
STABLE = ["SOXX","QQQ","IGV","XLE","GLD","SHY"]
TRANS  = STABLE + ["TLT","AGG","XLV"]


def wf_alt_halflife(halflife):
    _load(); cfg = _STATE["cfg"]; df = _STATE["bundle"].df
    core = load_core_feature_list(ROOT, cfg["classifier"]["feature_set"])
    core_feats = select_core_features(df, core)
    dates = df.index; n = len(dates)
    s = cfg["splitter"]
    sp = ExpandingSplitter(
        min_train_months=s["min_train_months"], val_months=s["val_months"],
        test_months=s["test_months"], step_months=s["step_months"],
        sample_every_n_days=s["sample_every_n_days"], embargo_days=s["embargo_days"],
        target_horizon=s["target_horizon"], decay_halflife_months=halflife)
    folds = sp.split(dates)
    target = cfg["classifier"]["target_col"]
    cls_to_idx = {c:i for i,c in enumerate(REGIME_CLASSES)}
    pred = np.full(n,-1,dtype=int); maxp = np.full(n,np.nan); accs=[]
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
        c = cfg["classifier"]
        clf = HistGradientBoostingClassifier(max_iter=c["max_iter"],max_depth=c["max_depth"],
            learning_rate=c["learning_rate"],min_samples_leaf=c["min_samples_leaf"],
            l2_regularization=c["l2_regularization"],random_state=c["random_state"])
        try: clf.fit(Xtr_z, ytr, sample_weight=sw)
        except Exception: continue
        proba = clf.predict_proba(Xte_z)
        full = np.zeros((len(Xte_z), 4))
        for j,c2 in enumerate(clf.classes_): full[:,int(c2)] = proba[:,j]
        pr_ = np.argmax(full,axis=1); mx = full.max(axis=1)
        pos = dates.get_indexer(te); pred[pos]=pr_; maxp[pos]=mx
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
        ranks = r.rank(axis=1,method="average")*w if ranks is None else ranks+r.rank(axis=1,method="average")*w
    return ranks/total


def run_full(pred, mp, sig):
    _load(); b = _STATE["bundle"]
    cur = np.asarray(_cr(b.df).index)
    gated = pred.copy(); w=(pred!=cur)&(pred>=0); lc = np.nan_to_num(mp,nan=0)<0.40
    gated[w&lc]=cur[w&lc]
    from strategy.rebalance import fomc_window_mask, resolve_rebalance_index
    from backtest.engine import compute_stats
    def mk_eng(uni):
        cfg = copy.deepcopy(_STATE["cfg"])
        cfg.update({"universe":uni,"top1_weight":0.62,"top3_weight":0.38})
        shim = types.SimpleNamespace(**{k:getattr(b,k) for k in ("df","dates","atr21","fwd21","spy_dist_sma200","is_fomc_day")})
        nr = dict(b.returns); nr[cfg["lookback_stable"]]=sig; shim.returns=nr
        return PortfolioEngine(shim, gated, cfg)
    eng_s = mk_eng(STABLE); eng_t = mk_eng(TRANS)
    import pandas as pd
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
        use_t = (pred[i]!=cur[i]) and (pred[i]>=0) and (not np.isnan(mp[i])) and (mp[i]>=0.50)
        rets.append(ret_at(eng_t if use_t else eng_s, i))
    return compute_stats(np.array(rets))


def main():
    sig = rankagg([(42,1),(63,3),(126,1)])
    log_path = HERE.parent / "LOG.md"
    ts = dt.datetime.now().isoformat(timespec="seconds")
    lines = [f"\n### phase39_clf_halflife  {ts}\n",
             "| name | CAGR | Sharpe | MaxDD | accuracy | verdict |","|---|---|---|---|---|---|"]

    for hl in (12, 24, 36, 48, 60, 120):
        pr_, mp_, acc = wf_alt_halflife(hl)
        s = run_full(pr_, mp_, sig)
        passes,_ = haircut_verdict(s)
        v = "PASS" if passes else "fail"
        name = f"P39_halflife_{hl}"
        print(name, fmt(s), f"acc={acc:.3f}", v)
        lines.append(f"| {name} | {s['cagr']*100:.2f}% | {s['sharpe']:.2f} | {s['max_dd']*100:.2f}% | {acc:.3f} | {v} |")
    with open(log_path,"a",encoding="utf-8") as f: f.write("\n".join(lines)+"\n")

if __name__ == "__main__":
    main()
