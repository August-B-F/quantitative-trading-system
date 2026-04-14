"""Skip IGV as top1 pick — replace with second-best when IGV wins top1."""
from __future__ import annotations
import sys, pickle, copy, types, warnings
from pathlib import Path
import numpy as np, pandas as pd
warnings.filterwarnings("ignore")
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from utils.base_test import _load, _STATE  # noqa: E402
from strategy.portfolio import PortfolioEngine  # noqa: E402
from backtest.engine import compute_stats  # noqa: E402
from strategy.rebalance import fomc_window_mask, resolve_rebalance_index  # noqa: E402
from features.regime_labels import current_regime as _cr  # noqa: E402

STABLE=["SOXX","QQQ","IGV","XLE","GLD","SHY"]
TRANS=STABLE+["TLT","AGG","XLV","XLF"]
W_NORM=0.50; W_FULL=0.82
BOOST_LB_M=9; BOOST_THR=0.30; SPY_FAST_LB=63; SPY_FAST_THR=0.12
FOMC_PRE,FOMC_POST,FOMC_DEFER=0,2,3
P_EXP=2.0


def build_sig():
    b=_STATE["bundle"]; cm=None; ranks=None
    for lb,w in [(42,1),(63,3),(126,1)]:
        r=b.returns[lb]
        if cm is None: cm=list(r.columns)
        else: r=r[cm]
        rk=r.rank(axis=1,method="average")*w
        ranks = rk if ranks is None else ranks+rk
    return ranks/5.0


def run(skip_ticker=None):
    _load(); b=_STATE["bundle"]
    with open(HERE.parent/"cache"/"pred_proba_p46.pkl","rb") as f:
        pr,mp = pickle.load(f)
    cur=np.asarray(_cr(b.df).index)
    gated=pr.copy()
    want=(pr!=cur)&(pr>=0); low=np.nan_to_num(mp,nan=0)<0.40
    gated[want&low]=cur[want&low]
    sig = build_sig()
    spy_63=b.returns[SPY_FAST_LB]["SPY"].values

    def mk(uni,w1):
        cfg=copy.deepcopy(_STATE["cfg"])
        cfg.update({"universe":uni,"top1_weight":w1,"top3_weight":1-w1,
                    "fomc_window_pre":FOMC_PRE,"fomc_window_after":FOMC_POST,"fomc_defer_days":FOMC_DEFER})
        shim=types.SimpleNamespace(**{k:getattr(b,k) for k in ("df","dates","atr21","fwd21","spy_dist_sma200","is_fomc_day")})
        nr=dict(b.returns); nr[cfg["lookback_stable"]]=sig; shim.returns=nr
        return PortfolioEngine(shim,gated,cfg)

    engs={}
    for uni_n,uni in [("s",STABLE),("t",TRANS)]:
        for w1 in (W_NORM,W_FULL):
            engs[(uni_n,w1)] = mk(uni,w1)
    td=_STATE["test_dates"]; eng0=engs[("s",W_NORM)]
    ps=pd.Series(eng0.dates.get_indexer(td),index=td)
    ml=ps.groupby(td.to_period("M")).tail(1)
    fomc_idx=np.where(b.is_fomc_day)[0]
    evm=fomc_window_mask(eng0.n_days,fomc_idx,pre_days=FOMC_PRE,post_days=FOMC_POST)

    def ret_at(eng,i):
        t1,tk=eng.pick_at(i)
        # Skip logic: tk includes t1 as tk[0]. Real runners-up are tk[1:].
        if skip_ticker is not None and eng.universe[t1] == skip_ticker and len(tk) > 1:
            t1_new = tk[1]
            # Build a new basket of size 3 from remaining: [new_top1, tk[2], t1_original]
            rest = [int(tk[1])]
            if len(tk) > 2:
                rest.append(int(tk[2]))
            rest.append(int(t1))
            tk_new = np.array(rest, dtype=int)
        else:
            t1_new, tk_new = t1, tk
        r1=eng.fwd_arr[i,t1_new] if eng.spy_dist[i]>eng.sma_buffer else eng.cash_fwd[i]
        sel=eng.atr_arr[i,tk_new]
        v=np.where(sel>0,sel,np.nan); w=1.0/(v**P_EXP)
        if np.isnan(w).all():
            rk=np.nanmean(eng.fwd_arr[i,tk_new])
        else:
            w=w/np.nansum(w); rk=np.nansum(eng.fwd_arr[i,tk_new]*w)
        return eng.top1_w*r1 + eng.topk_w*rk

    rets=[]; hist=[]; dts=[]
    for rd,p in ml.items():
        i,_=resolve_rebalance_index(int(p),FOMC_DEFER,evm,eng0.n_days)
        use_t=(pr[i]!=cur[i])and(pr[i]>=0)and(not np.isnan(mp[i]))and(mp[i]>=0.50)
        c9 = (np.prod([1+h for h in hist[-BOOST_LB_M:]])-1) if len(hist)>=BOOST_LB_M else 0.05
        sv = spy_63[i] if not np.isnan(spy_63[i]) else -1.0
        w1 = W_FULL if (c9>BOOST_THR or sv>SPY_FAST_THR) else W_NORM
        uni_n="t" if use_t else "s"
        r=ret_at(engs[(uni_n,w1)],i)
        hist.append(r); rets.append(r); dts.append(rd)
    return pd.Series(rets,index=pd.Index(dts)).dropna()


def per_half(ser):
    sA=ser[ser.index.map(lambda d:d.year<2018)]
    sB=ser[ser.index.map(lambda d:d.year>=2018)]
    return compute_stats(ser.values), compute_stats(sA.values), compute_stats(sB.values)


def boot_sh_diff(a,b,n=10000,seed=42):
    rng = np.random.default_rng(seed)
    m = len(a); diffs = np.empty(n)
    def sh(x):
        x = x[~np.isnan(x)]
        if len(x)<2 or x.std(ddof=1)==0: return 0.0
        return float(x.mean()/x.std(ddof=1)*np.sqrt(12))
    for i in range(n):
        idx = rng.integers(0,m,m)
        diffs[i] = sh(a[idx]) - sh(b[idx])
    return dict(mean=float(diffs.mean()), p=float((diffs>0).mean()*100),
                ci=(float(np.percentile(diffs,2.5)), float(np.percentile(diffs,97.5))))


def main():
    base_ser = run()
    base = per_half(base_ser)
    print(f"baseline: Sh {base[0]['sharpe']:.3f}  A {base[1]['sharpe']:.3f}  B {base[2]['sharpe']:.3f}")
    print()
    for skip in ["IGV","QQQ","SOXX","XLE","GLD","SHY"]:
        ser = run(skip_ticker=skip)
        f,a,b_ = per_half(ser)
        valid = ~(base_ser.isna() | ser.isna())
        r = boot_sh_diff(ser[valid].values, base_ser[valid].values)
        tag = "  SIG" if r['ci'][0]>0 else ""
        print(f"skip {skip:<6}  Sh {f['sharpe']:.3f}  A {a['sharpe']:.3f}  B {b_['sharpe']:.3f}  "
              f"dSh {f['sharpe']-base[0]['sharpe']:+.3f}  "
              f"boot[{r['ci'][0]:+.3f},{r['ci'][1]:+.3f}]{tag}")


if __name__ == "__main__":
    main()
