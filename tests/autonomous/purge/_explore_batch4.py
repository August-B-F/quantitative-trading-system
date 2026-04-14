"""Round-4 explorations — fundamentally different angles on Robust-VAR.

H16: Vol-adjusted rank-agg signal (rank(ret/vol))
H17: Use classifier proba as a continuous regime-mix weight
H18: Bi-weekly rebalance cadence
H19: MaxDD soft cap (scale top1 down after recent drawdown, differently than L9)
H20: Universe subsetting by rank-agg percentile (skip holdings ranked bottom)
"""
from __future__ import annotations
import sys, pickle, copy, types, warnings
from pathlib import Path
import numpy as np
import pandas as pd

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


def std_rank_sig():
    b=_STATE["bundle"]; cm=None; ranks=None
    for lb,w in [(42,1),(63,3),(126,1)]:
        r=b.returns[lb]
        if cm is None: cm=list(r.columns)
        else: r=r[cm]
        rk=r.rank(axis=1,method="average")*w
        ranks = rk if ranks is None else ranks+rk
    return ranks/5.0


def vol_adj_sig():
    """rank((ret/realized_vol) weighted across windows)."""
    b=_STATE["bundle"]
    # realized vol via std of 1d returns
    r1 = b.returns.get(1)
    if r1 is None:
        return std_rank_sig()
    cm=None; ranks=None
    for lb,w in [(42,1),(63,3),(126,1)]:
        r=b.returns[lb]
        if cm is None: cm=list(r.columns)
        else: r=r[cm]
        vol = r1[cm].rolling(lb, min_periods=lb).std() + 1e-9
        adj = r / vol
        rk = adj.rank(axis=1, method="average") * w
        ranks = rk if ranks is None else ranks+rk
    return ranks/5.0


def run(variant="baseline", biweekly=False):
    _load(); b=_STATE["bundle"]
    with open(HERE.parent/"cache"/"pred_proba_p46.pkl","rb") as f:
        pr,mp = pickle.load(f)
    cur=np.asarray(_cr(b.df).index)
    gated=pr.copy()
    want=(pr!=cur)&(pr>=0); low=np.nan_to_num(mp,nan=0)<0.40
    gated[want&low]=cur[want&low]
    if variant=="vol_adj_sig":
        sig = vol_adj_sig()
    else:
        sig = std_rank_sig()
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
    if biweekly:
        # every ~10 business days
        keep_positions = pd.Series(ps.values, index=ps.index)
        keep = keep_positions.iloc[::10]
    else:
        keep = ps.groupby(td.to_period("M")).tail(1)
    fomc_idx=np.where(b.is_fomc_day)[0]
    evm=fomc_window_mask(eng0.n_days,fomc_idx,pre_days=FOMC_PRE,post_days=FOMC_POST)

    def ret_at(eng,i):
        t1,tk=eng.pick_at(i)
        r1=eng.fwd_arr[i,t1] if eng.spy_dist[i]>eng.sma_buffer else eng.cash_fwd[i]
        sel=eng.atr_arr[i,tk]
        v=np.where(sel>0,sel,np.nan)
        w=1.0/(v**P_EXP)
        if np.isnan(w).all():
            rk=np.nanmean(eng.fwd_arr[i,tk])
        else:
            w=w/np.nansum(w); rk=np.nansum(eng.fwd_arr[i,tk]*w)
        return eng.top1_w*r1 + eng.topk_w*rk

    rets=[]; hist=[]; dts=[]
    for rd,p in keep.items():
        i,_=resolve_rebalance_index(int(p),FOMC_DEFER,evm,eng0.n_days)
        use_t=(pr[i]!=cur[i])and(pr[i]>=0)and(not np.isnan(mp[i]))and(mp[i]>=0.50)
        c9 = (np.prod([1+h for h in hist[-BOOST_LB_M:]])-1) if len(hist)>=BOOST_LB_M else 0.05
        sv = spy_63[i] if not np.isnan(spy_63[i]) else -1.0
        boost = (c9>BOOST_THR) or (sv>SPY_FAST_THR)
        w1 = W_FULL if boost else W_NORM
        uni_n="t" if use_t else "s"
        r=ret_at(engs[(uni_n,w1)],i)
        hist.append(r); rets.append(r); dts.append(rd)
    s = pd.Series(rets,index=pd.Index(dts)).dropna()
    return s


def per_half(ser):
    sA=ser[ser.index.map(lambda d:d.year<2018)]
    sB=ser[ser.index.map(lambda d:d.year>=2018)]
    return compute_stats(ser.values), compute_stats(sA.values), compute_stats(sB.values)


def show(label, ser, base):
    f,a,b_=per_half(ser)
    f0,a0,b0=base
    dSh=f['sharpe']-f0['sharpe']; dA=a['sharpe']-a0['sharpe']; dB=b_['sharpe']-b0['sharpe']
    tag=""
    if dA>=-0.02 and dB>=-0.02 and dSh>=0.04: tag="  PASS"
    elif dA>=-0.02 and dB>=-0.02 and dSh>=0:  tag="  +"
    print(f"{label:<44}  {f['cagr']*100:>6.2f}%  Sh {f['sharpe']:.3f}  A {a['sharpe']:.3f}  B {b_['sharpe']:.3f}  dSh {dSh:+.3f}{tag}")


def main():
    base = per_half(run())
    print(f"baseline (Robust-VAR): CAGR {base[0]['cagr']*100:.2f}%  Sh {base[0]['sharpe']:.3f}  A {base[1]['sharpe']:.3f}  B {base[2]['sharpe']:.3f}")
    print()
    print("=== H16: vol-adjusted rank signal ===")
    show("vol_adj_sig", run(variant="vol_adj_sig"), base)
    print()
    print("=== H18: bi-weekly rebalance cadence ===")
    show("bi-weekly (every ~10d)", run(biweekly=True), base)


if __name__ == "__main__":
    main()
