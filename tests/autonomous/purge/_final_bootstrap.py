"""Final bootstrap: Robust-VAR vs canonical, and Robust-VAR vs Robust (inv-atr)."""
from __future__ import annotations
import sys, copy, types, warnings
from pathlib import Path
import numpy as np, pandas as pd

warnings.filterwarnings("ignore")
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from utils.base_test import _load, _STATE  # noqa: E402
from strategy.portfolio import PortfolioEngine  # noqa: E402
from backtest.engine import compute_stats  # noqa: E402
from strategy.rebalance import fomc_window_mask, resolve_rebalance_index  # noqa: E402
sys.path.insert(0, str(HERE))
from _explore_batch2 import run as run_batch2  # noqa: E402

CANON = ["SOXX","QQQ","XLK","VGT","IGV","XLE","GLD","SHY"]


def run_canonical():
    _load(); b = _STATE["bundle"]
    cfg = copy.deepcopy(_STATE["cfg"])
    cfg.update({"universe": CANON, "top1_weight": 0.50, "top3_weight": 0.50,
                "fomc_window_pre": 0, "fomc_window_after": 2, "fomc_defer_days": 3})
    shim = types.SimpleNamespace(**{k: getattr(b, k) for k in (
        "df","dates","atr21","fwd21","spy_dist_sma200","is_fomc_day")})
    shim.returns = b.returns
    eng = PortfolioEngine(shim, _STATE["pred_reg"], cfg)
    td = _STATE["test_dates"]
    pos = pd.Series(eng.dates.get_indexer(td), index=td)
    ml = pos.groupby(td.to_period("M")).tail(1)
    fomc_idx = np.where(b.is_fomc_day)[0]
    evm = fomc_window_mask(eng.n_days, fomc_idx, pre_days=0, post_days=2)

    rets=[]; dts=[]
    for rd,p in ml.items():
        i,_ = resolve_rebalance_index(int(p), 3, evm, eng.n_days)
        t1,tk = eng.pick_at(i)
        r1 = eng.fwd_arr[i,t1] if eng.spy_dist[i]>eng.sma_buffer else eng.cash_fwd[i]
        sel = eng.atr_arr[i,tk]
        inv = 1.0/np.where(sel>0,sel,np.nan)
        if np.isnan(inv).all():
            rk = np.nanmean(eng.fwd_arr[i,tk])
        else:
            w = inv/np.nansum(inv); rk = np.nansum(eng.fwd_arr[i,tk]*w)
        r = eng.top1_w*r1 + eng.topk_w*rk
        rets.append(r); dts.append(rd)
    return pd.Series(rets, index=pd.Index(dts)).dropna()


def bootstrap_edge(a,b,n=10000,seed=42):
    rng = np.random.default_rng(seed)
    d = a-b; n_obs=len(d); means=np.empty(n)
    for i in range(n):
        idx = rng.integers(0,n_obs,n_obs)
        means[i] = d[idx].mean()
    ann = ((1+means)**12-1)*100
    t = d.mean()/(d.std(ddof=1)/np.sqrt(n_obs))
    return dict(t=float(t), p=(means>0).mean()*100,
                ann_mean=float(((1+d.mean())**12-1)*100),
                ci=(float(np.percentile(ann,2.5)), float(np.percentile(ann,97.5))))


def main():
    canon = run_canonical()
    rob = run_batch2(wscheme="inv_atr")
    var_ = run_batch2(wscheme="inv_var")

    for name, s in [("canonical", canon), ("Robust (inv-atr)", rob), ("Robust-VAR (inv-var)", var_)]:
        st = compute_stats(s.dropna().values)
        print(f"{name:<22}  CAGR {st['cagr']*100:6.2f}%  Sharpe {st['sharpe']:.3f}  MaxDD {st['max_dd']*100:.2f}%")

    print()
    # Align on common index
    idx = canon.index.intersection(var_.index)
    a = var_.reindex(idx).dropna().values
    b = canon.reindex(idx).dropna().values
    # Align lengths
    m = min(len(a), len(b))
    print("=== Robust-VAR vs canonical ===")
    res = bootstrap_edge(a[-m:], b[-m:])
    print(f"  t = {res['t']:+.3f}  P(edge>0) = {res['p']:.2f}%  ann = +{res['ann_mean']:.2f}pp  CI [+{res['ci'][0]:.2f}, +{res['ci'][1]:.2f}]")

    idx2 = rob.index.intersection(var_.index)
    a = var_.reindex(idx2).dropna().values
    b = rob.reindex(idx2).dropna().values
    m = min(len(a), len(b))
    print("=== Robust-VAR vs Robust (inv-atr) ===")
    res = bootstrap_edge(a[-m:], b[-m:])
    print(f"  t = {res['t']:+.3f}  P(edge>0) = {res['p']:.2f}%  ann = {res['ann_mean']:+.2f}pp  CI [{res['ci'][0]:+.2f}, {res['ci'][1]:+.2f}]")


if __name__ == "__main__":
    main()
