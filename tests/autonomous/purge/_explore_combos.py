"""Combine promising-but-marginal ideas: higher p_exp + GLD overlay + finer w_norm.
Each individually was below significance; maybe the stack compounds."""
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
BOOST_LB_M=9; BOOST_THR=0.30; SPY_FAST_LB=63; SPY_FAST_THR=0.12
FOMC_PRE,FOMC_POST,FOMC_DEFER=0,2,3


def build_sig():
    b=_STATE["bundle"]; cm=None; ranks=None
    for lb,w in [(42,1),(63,3),(126,1)]:
        r=b.returns[lb]
        if cm is None: cm=list(r.columns)
        else: r=r[cm]
        rk=r.rank(axis=1,method="average")*w
        ranks = rk if ranks is None else ranks+rk
    return ranks/5.0


def run(p_exp=2.0, w_norm=0.50, w_full=0.82, gld_w=0.0, agg_w=0.0):
    _load(); b=_STATE["bundle"]
    with open(HERE.parent/"cache"/"pred_proba_p46.pkl","rb") as f:
        pr,mp = pickle.load(f)
    cur=np.asarray(_cr(b.df).index)
    gated=pr.copy()
    want=(pr!=cur)&(pr>=0); low=np.nan_to_num(mp,nan=0)<0.40
    gated[want&low]=cur[want&low]
    sig = build_sig()
    spy_63=b.returns[SPY_FAST_LB]["SPY"].values
    gld_fwd = b.returns[21]["GLD"].values
    agg_fwd = b.returns[21]["AGG"].values

    def mk(uni,w1):
        cfg=copy.deepcopy(_STATE["cfg"])
        cfg.update({"universe":uni,"top1_weight":w1,"top3_weight":1-w1,
                    "fomc_window_pre":FOMC_PRE,"fomc_window_after":FOMC_POST,"fomc_defer_days":FOMC_DEFER})
        shim=types.SimpleNamespace(**{k:getattr(b,k) for k in ("df","dates","atr21","fwd21","spy_dist_sma200","is_fomc_day")})
        nr=dict(b.returns); nr[cfg["lookback_stable"]]=sig; shim.returns=nr
        return PortfolioEngine(shim,gated,cfg)

    engs={}
    for uni_n,uni in [("s",STABLE),("t",TRANS)]:
        for w1 in (w_norm, w_full):
            engs[(uni_n,w1)] = mk(uni,w1)
    td=_STATE["test_dates"]; eng0=engs[("s",w_norm)]
    ps=pd.Series(eng0.dates.get_indexer(td),index=td)
    ml=ps.groupby(td.to_period("M")).tail(1)
    fomc_idx=np.where(b.is_fomc_day)[0]
    evm=fomc_window_mask(eng0.n_days,fomc_idx,pre_days=FOMC_PRE,post_days=FOMC_POST)

    def ret_at(eng,i):
        t1,tk=eng.pick_at(i)
        r1=eng.fwd_arr[i,t1] if eng.spy_dist[i]>eng.sma_buffer else eng.cash_fwd[i]
        sel=eng.atr_arr[i,tk]
        v=np.where(sel>0,sel,np.nan)
        w=1.0/(v**p_exp)
        if np.isnan(w).all():
            rk=np.nanmean(eng.fwd_arr[i,tk])
        else:
            w=w/np.nansum(w); rk=np.nansum(eng.fwd_arr[i,tk]*w)
        return eng.top1_w*r1 + eng.topk_w*rk

    rets=[]; hist=[]; dts=[]
    for rd,p in ml.items():
        i,_=resolve_rebalance_index(int(p),FOMC_DEFER,evm,eng0.n_days)
        use_t=(pr[i]!=cur[i])and(pr[i]>=0)and(not np.isnan(mp[i]))and(mp[i]>=0.50)
        c9 = (np.prod([1+h for h in hist[-BOOST_LB_M:]])-1) if len(hist)>=BOOST_LB_M else 0.05
        sv = spy_63[i] if not np.isnan(spy_63[i]) else -1.0
        w1 = w_full if (c9>BOOST_THR or sv>SPY_FAST_THR) else w_norm
        uni_n="t" if use_t else "s"
        r_strat = ret_at(engs[(uni_n,w1)],i)
        overlay_w = gld_w + agg_w
        r = (1-overlay_w)*r_strat + gld_w*gld_fwd[i] + agg_w*agg_fwd[i]
        hist.append(r); rets.append(r); dts.append(rd)
    return pd.Series(rets,index=pd.Index(dts)).dropna()


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
    print(f"baseline (p=2, no overlay): Sh {base[0]['sharpe']:.3f}")
    print()

    print("=== p_exp x gld overlay ===")
    for p in [2.0, 2.5, 3.0]:
        for gw in [0.0, 0.05, 0.08, 0.10]:
            show(f"p={p} gld={gw}", run(p_exp=p, gld_w=gw), base)

    print()
    print("=== p_exp x agg overlay ===")
    for p in [2.0, 2.5, 3.0]:
        for aw in [0.0, 0.05, 0.08, 0.10]:
            show(f"p={p} agg={aw}", run(p_exp=p, agg_w=aw), base)

    print()
    print("=== best combinations (higher-p + small overlay + w_norm tweak) ===")
    combos = [
        dict(p_exp=2.5, gld_w=0.05),
        dict(p_exp=2.5, gld_w=0.08),
        dict(p_exp=2.5, gld_w=0.10),
        dict(p_exp=3.0, gld_w=0.05),
        dict(p_exp=3.0, gld_w=0.08),
        dict(p_exp=2.5, gld_w=0.05, w_norm=0.45),
        dict(p_exp=2.5, agg_w=0.05, w_norm=0.45),
        dict(p_exp=2.5, gld_w=0.05, agg_w=0.05),
    ]
    for c in combos:
        show(str(c), run(**c), base)


if __name__ == "__main__":
    main()
