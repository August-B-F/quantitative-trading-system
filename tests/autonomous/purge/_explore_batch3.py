"""Round-3 explorations on top of ROBUST-VAR (inv-var baseline).

H11: L9 boost param neighborhood (boost_lb, boost_thr, spy_thr, w_full)
H12: Different boost triggers (price/drawdown based)
H13: Additional cash sleeve during high-vol regimes (SPY 63d vol gate)
H14: Rank-agg signal augmented with |signal| magnitude (strong rank leader-gap amp)
H15: Variable top1 weight proportional to classifier confidence
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
W_NORM=0.50; W_FULL_DEF=0.82
BOOST_LB_M=9; BOOST_THR=0.30; SPY_FAST_LB=63; SPY_FAST_THR=0.12
FOMC_PRE,FOMC_POST,FOMC_DEFER = 0,2,3
P_EXP = 2.0


def build_sig():
    b=_STATE["bundle"]; cm=None; ranks=None
    for lb,w in [(42,1),(63,3),(126,1)]:
        r=b.returns[lb]
        if cm is None: cm=list(r.columns)
        else: r=r[cm]
        rk=r.rank(axis=1,method="average")*w
        ranks = rk if ranks is None else ranks+rk
    return ranks/5.0


def run(boost_lb=BOOST_LB_M, boost_thr=BOOST_THR, spy_thr=SPY_FAST_THR,
        w_full=W_FULL_DEF, w_norm=W_NORM,
        prop_gate=False, vol_gate_thr=None, vol_gate_lb=63,
        amp_sig=False):
    _load(); b=_STATE["bundle"]
    with open(HERE.parent/"cache"/"pred_proba_p46.pkl","rb") as f:
        pr,mp = pickle.load(f)
    cur=np.asarray(_cr(b.df).index)
    gated=pr.copy()
    want=(pr!=cur)&(pr>=0); low=np.nan_to_num(mp,nan=0)<0.40
    gated[want&low]=cur[want&low]
    sig = build_sig()
    if amp_sig:
        # Emphasize leader gap: square the ranks
        sig = sig ** 1.5
    spy_63=b.returns[SPY_FAST_LB]["SPY"].values
    vol_gate = None
    if vol_gate_thr is not None:
        # realized vol proxy: std of daily returns proxied by 1d returns if available
        if 1 in b.returns:
            r1 = b.returns[1]["SPY"].fillna(0).values
            vol_gate = pd.Series(r1).rolling(vol_gate_lb,min_periods=vol_gate_lb).std().values * np.sqrt(252)

    def mk(uni,w1):
        cfg=copy.deepcopy(_STATE["cfg"])
        cfg.update({"universe":uni,"top1_weight":w1,"top3_weight":1-w1,
                    "fomc_window_pre":FOMC_PRE,"fomc_window_after":FOMC_POST,"fomc_defer_days":FOMC_DEFER})
        shim=types.SimpleNamespace(**{k:getattr(b,k) for k in ("df","dates","atr21","fwd21","spy_dist_sma200","is_fomc_day")})
        nr=dict(b.returns); nr[cfg["lookback_stable"]]=sig; shim.returns=nr
        return PortfolioEngine(shim,gated,cfg)

    # Weight set
    weights_needed = {w_norm, w_full}
    if prop_gate:
        weights_needed.update({0.40, 0.55, 0.60, 0.65, 0.70, 0.75, 0.82})
    engs={}
    for uni_n,uni in [("s",STABLE),("t",TRANS)]:
        for w1 in weights_needed:
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
        w=1.0/(v**P_EXP)
        if np.isnan(w).all():
            rk=np.nanmean(eng.fwd_arr[i,tk])
        else:
            w=w/np.nansum(w); rk=np.nansum(eng.fwd_arr[i,tk]*w)
        return eng.top1_w*r1 + eng.topk_w*rk

    rets=[]; hist=[]; dts=[]
    for rd,p in ml.items():
        i,_=resolve_rebalance_index(int(p),FOMC_DEFER,evm,eng0.n_days)
        use_t=(pr[i]!=cur[i])and(pr[i]>=0)and(not np.isnan(mp[i]))and(mp[i]>=0.50)
        c9 = (np.prod([1+h for h in hist[-boost_lb:]])-1) if len(hist)>=boost_lb else 0.05
        sv = spy_63[i] if not np.isnan(spy_63[i]) else -1.0
        boost = (c9>boost_thr) or (sv>spy_thr)

        if prop_gate and not np.isnan(mp[i]):
            # Scale top1 by classifier confidence (proba of chosen regime)
            p_conf = mp[i]
            if p_conf < 0.40:
                w1 = 0.40
            elif p_conf < 0.50: w1 = 0.55
            elif p_conf < 0.60: w1 = 0.60
            elif p_conf < 0.70: w1 = 0.65
            elif p_conf < 0.80: w1 = 0.70
            elif p_conf < 0.90: w1 = 0.75
            else: w1 = 0.82
        elif boost:
            w1 = w_full
        else:
            w1 = w_norm

        # High-vol cash gate override (defensive)
        if vol_gate is not None and not np.isnan(vol_gate[i]) and vol_gate[i] > vol_gate_thr:
            w1 = 0.40  # defensive

        uni_n="t" if use_t else "s"
        # ensure engine exists
        if (uni_n,w1) not in engs:
            engs[(uni_n,w1)] = mk(STABLE if uni_n=="s" else TRANS, w1)
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
    print(f"{label:<44}  {f['cagr']*100:>6.2f}%  Sh {f['sharpe']:.3f}  "
          f"A {a['sharpe']:.3f}  B {b_['sharpe']:.3f}  dSh {dSh:+.3f}{tag}")


def main():
    base = per_half(run())
    print(f"baseline (Robust-VAR): CAGR {base[0]['cagr']*100:.2f}%  Sh {base[0]['sharpe']:.3f}  A {base[1]['sharpe']:.3f}  B {base[2]['sharpe']:.3f}")
    print()

    print("=== H11a: boost_lb (month lookback) ===")
    for lb in [3,6,9,12,15,18,24]:
        show(f"boost_lb={lb}", run(boost_lb=lb), base)

    print()
    print("=== H11b: boost_thr (trail return threshold) ===")
    for th in [0.15,0.20,0.25,0.30,0.35,0.40]:
        show(f"boost_thr={th:.2f}", run(boost_thr=th), base)

    print()
    print("=== H11c: spy_thr (SPY63d threshold) ===")
    for th in [0.06,0.08,0.10,0.12,0.14,0.16,0.20]:
        show(f"spy_thr={th:.2f}", run(spy_thr=th), base)

    print()
    print("=== H11d: w_full (boost top1 weight) ===")
    for wf in [0.70,0.75,0.78,0.82,0.85,0.88,0.92]:
        show(f"w_full={wf}", run(w_full=wf), base)

    print()
    print("=== H11e: w_norm (default top1) ===")
    for wn in [0.40,0.45,0.50,0.55,0.60,0.62]:
        show(f"w_norm={wn}", run(w_norm=wn), base)

    print()
    print("=== H15: proportional (confidence-scaled top1) ===")
    show("prop_gate (confidence ladder)", run(prop_gate=True), base)

    print()
    print("=== H13: realized-vol gate (SPY vol > thr => defensive) ===")
    for thr in [0.15,0.20,0.25,0.30,0.35]:
        show(f"vol_gate={thr}", run(vol_gate_thr=thr), base)

    print()
    print("=== H14: amp_sig (rank power 1.5) ===")
    show("amp_sig (rank^1.5)", run(amp_sig=True), base)


if __name__ == "__main__":
    main()
