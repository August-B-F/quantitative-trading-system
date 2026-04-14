"""Re-test the 4 layers that were PURGED (L2, L7, L8, L10) on the new
Robust-VAR baseline. Maybe inv-variance weighting changes the interaction.
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


def run(L2=False, L7=False, L8=False, L10=False,
        w_norm=0.50, w_full=0.82, w_dd=0.40, w_warm=0.70,
        fomc_p=0, fomc_q=2, fomc_d=3,
        dd_lb=3, dd_thr=-0.02, boost_lb=9, boost_thr=0.30,
        spy_lb=63, spy_thr=0.12, warm_lb=6, warm_thr=0.25,
        spy_warm_lb=21, spy_warm_thr=0.10):
    _load(); b=_STATE["bundle"]
    with open(HERE.parent/"cache"/"pred_proba_p46.pkl","rb") as f:
        pr,mp = pickle.load(f)
    cur=np.asarray(_cr(b.df).index)
    gated=pr.copy()
    want=(pr!=cur)&(pr>=0); low=np.nan_to_num(mp,nan=0)<0.40
    gated[want&low]=cur[want&low]
    sig = build_sig()
    spy_63=b.returns[spy_lb]["SPY"].values
    spy_21=b.returns[spy_warm_lb]["SPY"].values

    # L2: if on, use 62/38 split as w_norm
    if L2:
        w_norm = 0.62
    # L7: if on, tighten FOMC window
    if L7:
        fomc_p, fomc_q, fomc_d = 0, 1, 4

    def mk(uni,w1):
        cfg=copy.deepcopy(_STATE["cfg"])
        cfg.update({"universe":uni,"top1_weight":w1,"top3_weight":1-w1,
                    "fomc_window_pre":fomc_p,"fomc_window_after":fomc_q,"fomc_defer_days":fomc_d})
        shim=types.SimpleNamespace(**{k:getattr(b,k) for k in ("df","dates","atr21","fwd21","spy_dist_sma200","is_fomc_day")})
        nr=dict(b.returns); nr[cfg["lookback_stable"]]=sig; shim.returns=nr
        return PortfolioEngine(shim,gated,cfg)

    ws = {w_norm, w_full}
    if L8: ws.add(w_dd)
    if L10: ws.add(w_warm)
    engs={}
    for uni_n,uni in [("s",STABLE),("t",TRANS)]:
        for w1 in ws:
            engs[(uni_n,w1)] = mk(uni,w1)
    td=_STATE["test_dates"]; eng0=engs[("s",w_norm)]
    ps=pd.Series(eng0.dates.get_indexer(td),index=td)
    ml=ps.groupby(td.to_period("M")).tail(1)
    fomc_idx=np.where(b.is_fomc_day)[0]
    evm=fomc_window_mask(eng0.n_days,fomc_idx,pre_days=fomc_p,post_days=fomc_q)

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
    for rd,p in ml.items():
        i,_=resolve_rebalance_index(int(p),fomc_d,evm,eng0.n_days)
        use_t=(pr[i]!=cur[i])and(pr[i]>=0)and(not np.isnan(mp[i]))and(mp[i]>=0.50)

        # State feedback
        cum_dd = (np.prod([1+h for h in hist[-dd_lb:]])-1) if len(hist)>=dd_lb else 0.05
        cum_full = (np.prod([1+h for h in hist[-boost_lb:]])-1) if len(hist)>=boost_lb else 0.05
        cum_warm = (np.prod([1+h for h in hist[-warm_lb:]])-1) if len(hist)>=warm_lb else 0.05
        sv_full = spy_63[i] if not np.isnan(spy_63[i]) else -1.0
        sv_warm = spy_21[i] if not np.isnan(spy_21[i]) else -1.0

        if L8 and cum_dd < dd_thr:
            w1 = w_dd
        elif cum_full > boost_thr or sv_full > spy_thr:
            w1 = w_full
        elif L10 and (cum_warm > warm_thr or sv_warm > spy_warm_thr):
            w1 = w_warm
        else:
            w1 = w_norm

        uni_n="t" if use_t else "s"
        if (uni_n,w1) not in engs:
            engs[(uni_n,w1)] = mk(STABLE if uni_n=="s" else TRANS, w1)
        r=ret_at(engs[(uni_n,w1)],i)
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
    print(f"baseline (Robust-VAR): CAGR {base[0]['cagr']*100:.2f}%  Sh {base[0]['sharpe']:.3f}  A {base[1]['sharpe']:.3f}  B {base[2]['sharpe']:.3f}")
    print()
    print("=== Re-test purged layers on Robust-VAR ===")
    show("+L2 (62/38 split)", run(L2=True), base)
    show("+L7 (tight FOMC)", run(L7=True), base)
    show("+L8 (DD trigger)", run(L8=True), base)
    show("+L10 (warm boost)", run(L10=True), base)
    show("+L2+L7", run(L2=True,L7=True), base)
    show("+L8+L10", run(L8=True,L10=True), base)
    show("+L2+L7+L8+L10 (full P59 on inv-var)", run(L2=True,L7=True,L8=True,L10=True), base)

    print()
    print("=== L8 parameter neighborhood (with inv-var) ===")
    for lb in [2,3,4,6]:
        for thr in [-0.01,-0.02,-0.03,-0.05]:
            show(f"L8 lb={lb} thr={thr}", run(L8=True,dd_lb=lb,dd_thr=thr), base)

    print()
    print("=== L10 parameter neighborhood (with inv-var) ===")
    for lb in [4,6,8,12]:
        for thr in [0.15,0.20,0.25,0.30]:
            show(f"L10 lb={lb} thr={thr}", run(L10=True,warm_lb=lb,warm_thr=thr), base)


if __name__ == "__main__":
    main()
