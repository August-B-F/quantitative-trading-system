"""Phase 46: validate P45 + copper_gold_ratio classifier feature."""
from __future__ import annotations
import sys, copy, types, pickle
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import numpy as np, pandas as pd
from utils.base_test import _load, _STATE, fmt
from strategy.portfolio import PortfolioEngine
from backtest.engine import run_backtest, compute_stats
from strategy.rebalance import fomc_window_mask, resolve_rebalance_index
from features.regime_labels import current_regime as _cr, REGIME_CLASSES
from features.engineer import load_core_feature_list, select_core_features
from model.walk_forward import ExpandingSplitter
from model.preprocessing import FeaturePreprocessor
from sklearn.ensemble import HistGradientBoostingClassifier

R = Path(__file__).resolve().parents[3]
STABLE = ["SOXX","QQQ","IGV","XLE","GLD","SHY"]; TRANS = STABLE + ["TLT","AGG","XLV"]
P46_EXTRAS = [
    "cross_asset_credit_appetite__hyg_minus_tlt_21d","credit_features__hy_ig_spread",
    "credit_features__hy_ig_spread_z252","yield_curve_features__yc_slope_10y_2y",
    "yield_curve_features__yc_slope_10y_2y_chg63","yield_curve_features__real_rate_10y",
    "cross_asset_copper_gold__copper_gold_ratio",
]

def wf(feats):
    _load(); cfg = _STATE["cfg"]; df = _STATE["bundle"].df
    dates = df.index; n = len(dates); s = cfg["splitter"]
    sp = ExpandingSplitter(
        min_train_months=s["min_train_months"], val_months=s["val_months"],
        test_months=s["test_months"], step_months=s["step_months"],
        sample_every_n_days=s["sample_every_n_days"], embargo_days=s["embargo_days"],
        target_horizon=s["target_horizon"], decay_halflife_months=s["decay_halflife_months"])
    folds = sp.split(dates)
    target = cfg["classifier"]["target_col"]; cls_to_idx = {c:i for i,c in enumerate(REGIME_CLASSES)}
    pred = np.full(n,-1,dtype=int); maxp = np.full(n,np.nan); accs=[]
    for fold in folds:
        tr,te = fold["train_dates"], fold["test_dates"]
        if len(tr)<30 or len(te)<1: continue
        sw = np.asarray(fold["train_sample_weights"])
        Xtr = df.loc[tr, feats]; ytr_raw = df.loc[tr, target]; Xte = df.loc[te, feats]; yte_raw = df.loc[te, target]
        mtr = ytr_raw.notna(); Xtr,ytr_raw,sw = Xtr[mtr],ytr_raw[mtr],sw[mtr.to_numpy()]
        if len(Xtr)<50: continue
        ytr = ytr_raw.map(cls_to_idx).astype(int).to_numpy()
        pp = FeaturePreprocessor()
        Xtr_z = pp.fit_transform(Xtr, sample_weights=sw).to_numpy(); Xte_z = pp.transform(Xte).to_numpy()
        c = cfg["classifier"]
        clf = HistGradientBoostingClassifier(max_iter=c["max_iter"],max_depth=c["max_depth"],
            learning_rate=c["learning_rate"],min_samples_leaf=c["min_samples_leaf"],
            l2_regularization=c["l2_regularization"],random_state=c["random_state"])
        try: clf.fit(Xtr_z, ytr, sample_weight=sw)
        except Exception: continue
        proba = clf.predict_proba(Xte_z)
        full = np.zeros((len(Xte_z),4))
        for j,cls in enumerate(clf.classes_): full[:,int(cls)]=proba[:,j]
        pr_ = np.argmax(full,axis=1); mx = full.max(axis=1)
        pos = dates.get_indexer(te); pred[pos]=pr_; maxp[pos]=mx
        yte_m = yte_raw.map(cls_to_idx)
        if yte_m.notna().any():
            yv = yte_m.dropna().astype(int).to_numpy()
            accs.append(float((pr_[:len(yv)]==yv[:len(pr_)]).mean()))
    return pred, maxp, (float(np.mean(accs)) if accs else 0.0)


def main():
    _load(); df = _STATE["bundle"].df
    cp = select_core_features(df, load_core_feature_list(R, _STATE["cfg"]["classifier"]["feature_set"]))
    feats = cp + P46_EXTRAS
    pred, maxp, acc = wf(feats)
    print(f"n feats: {len(feats)}  WF acc: {acc:.3f}")
    with open(HERE.parent / "cache" / "pred_proba_p46.pkl", "wb") as f:
        pickle.dump((pred, maxp), f)

    b = _STATE["bundle"]
    cur = np.asarray(_cr(b.df).index)
    gated = pred.copy(); w=(pred!=cur)&(pred>=0); lc = np.nan_to_num(maxp,nan=0)<0.40
    gated[w&lc]=cur[w&lc]
    cm = list(b.returns[63].columns); ranks=None
    for lb,wt in [(42,1),(63,3),(126,1)]:
        r = b.returns[lb][cm].rank(axis=1,method="average")
        ranks = r*wt if ranks is None else ranks+r*wt
    sig = ranks/5

    def mk_eng(uni):
        cfg2 = copy.deepcopy(_STATE["cfg"])
        cfg2.update({"universe":uni,"top1_weight":0.62,"top3_weight":0.38,
                     "fomc_window_pre":0,"fomc_window_after":1,"fomc_defer_days":4})
        shim = types.SimpleNamespace(**{k:getattr(b,k) for k in ("df","dates","atr21","fwd21","spy_dist_sma200","is_fomc_day")})
        nr = dict(b.returns); nr[63]=sig; shim.returns=nr
        return PortfolioEngine(shim, gated, cfg2)
    eng_s = mk_eng(STABLE); eng_t = mk_eng(TRANS)

    def run_period(st,en):
        td = _STATE["test_dates"]
        if st: td = td[td >= pd.Timestamp(st)]
        if en: td = td[td <= pd.Timestamp(en)]
        td_positions = pd.Series(eng_s.dates.get_indexer(td), index=td)
        month_last = td_positions.groupby(td.to_period("M")).tail(1)
        fomc_idx = np.where(b.is_fomc_day)[0]
        event_mask = fomc_window_mask(eng_s.n_days, fomc_idx, pre_days=0, post_days=1)
        def ret_at(eng, i):
            t1,tk = eng.pick_at(i)
            r1 = eng.fwd_arr[i,t1] if eng.spy_dist[i]>eng.sma_buffer else eng.cash_fwd[i]
            sel = eng.atr_arr[i,tk]; inv = 1.0/np.where(sel>0,sel,np.nan)
            if np.isnan(inv).all(): rk = np.nanmean(eng.fwd_arr[i,tk])
            else: ww=inv/np.nansum(inv); rk=np.nansum(eng.fwd_arr[i,tk]*ww)
            return eng.top1_w*r1 + eng.topk_w*rk
        rets = []
        for rd, pos in month_last.items():
            i, _ = resolve_rebalance_index(int(pos), 4, event_mask, eng_s.n_days)
            use_t = (pred[i]!=cur[i]) and (pred[i]>=0) and (not np.isnan(maxp[i])) and (maxp[i]>=0.50)
            rets.append(ret_at(eng_t if use_t else eng_s, i))
        return compute_stats(np.array(rets)), rets

    # Sub-period stats
    print("\nSub-period breakdown:")
    for p, st, en in [("full",None,None),("2010_15","2010-01-01","2015-12-31"),
                      ("2016_20","2016-01-01","2020-12-31"),("2021_26","2021-01-01","2026-12-31")]:
        s, _ = run_period(st, en)
        print(f"  {p}: {fmt(s)}")

    # Bootstrap robustness
    _, p46_rets = run_period(None, None)
    td = _STATE["test_dates"]
    td_positions = pd.Series(eng_s.dates.get_indexer(td), index=td)
    month_last = td_positions.groupby(td.to_period("M")).tail(1)
    p46_series = pd.Series(p46_rets, index=list(month_last.index))
    eng_base = PortfolioEngine(b, _STATE["pred_reg"], _STATE["cfg"])
    base_mr = run_backtest(eng_base, _STATE["test_dates"], _STATE["cfg"]).monthly_returns
    df_ = pd.DataFrame({"p46": p46_series, "base": base_mr}).dropna()
    diff = (df_["p46"] - df_["base"]).values
    t = diff.mean() / (diff.std(ddof=1) / np.sqrt(len(diff)))
    rng = np.random.default_rng(42)
    n = len(diff); bs = np.array([diff[rng.integers(0,n,n)].mean() for _ in range(10000)])
    lo, hi = np.percentile(bs, [2.5, 97.5])
    print(f"\nBootstrap: t={t:.3f}  P(edge>0)={(bs>0).mean()*100:.2f}%")
    print(f"95% CI annualized: [{((1+lo)**12-1)*100:+.2f}, {((1+hi)**12-1)*100:+.2f}] pp/yr")

    def rsh(s, w=36):
        return (s.rolling(w).mean() / s.rolling(w).std()) * np.sqrt(12)
    rp = rsh(df_["p46"]); rb = rsh(df_["base"])
    v = ~rp.isna()
    wr = ((rp > rb)[v]).mean() * 100
    print(f"Rolling 36m Sharpe: P46 wins {wr:.1f}% of windows  median {rp[v].median():.2f} vs {rb[v].median():.2f}")


if __name__ == "__main__":
    main()
