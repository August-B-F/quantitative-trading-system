"""Round-5 on top of Robust-VAR:

H21: alternative classifier cache files (pred_proba_v2, p44_05, p45)
H22: absolute momentum filter (skip top1 if its raw return is negative)
H23: dynamic top_k (tighten to k=2 or widen to k=4 based on signal strength)
H24: seasonal effects (sell-in-May, Santa rally)
H25: own-equity trailing drawdown top1 scaling
H26: alternate proba gate definitions (margin instead of abs proba)
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


def build_sig():
    b=_STATE["bundle"]; cm=None; ranks=None
    for lb,w in [(42,1),(63,3),(126,1)]:
        r=b.returns[lb]
        if cm is None: cm=list(r.columns)
        else: r=r[cm]
        rk=r.rank(axis=1,method="average")*w
        ranks = rk if ranks is None else ranks+rk
    return ranks/5.0


def run(cache_file="pred_proba_p46.pkl",
        abs_mom_filter=False, abs_mom_lb=63,
        dyn_topk=None,
        seasonal_filter=None,
        equity_dd_scale=False, dd_thr=-0.05, dd_w=0.35,
        margin_gate=False, margin_thr=0.15):
    _load(); b=_STATE["bundle"]
    with open(HERE.parent/"cache"/cache_file, "rb") as f:
        pr,mp = pickle.load(f)
    cur=np.asarray(_cr(b.df).index)
    gated=pr.copy()

    if margin_gate:
        # Require proba margin vs runner-up: if we have 2d proba, compute margin
        # Approximate via 1 - (1-mp) = just use (mp - 0.25) as proxy for margin
        want=(pr!=cur)&(pr>=0)
        proxy = np.nan_to_num(mp, nan=0.0) - 0.25
        low = proxy < margin_thr
        gated[want&low]=cur[want&low]
    else:
        want=(pr!=cur)&(pr>=0); low=np.nan_to_num(mp,nan=0)<0.40
        gated[want&low]=cur[want&low]

    sig = build_sig()
    spy_63=b.returns[SPY_FAST_LB]["SPY"].values
    abs_mom_ret = b.returns[abs_mom_lb] if abs_mom_filter else None

    def mk(uni,w1,topk):
        cfg=copy.deepcopy(_STATE["cfg"])
        cfg.update({"universe":uni,"top1_weight":w1,"top3_weight":1-w1,
                    "top_k": topk+1,
                    "fomc_window_pre":FOMC_PRE,"fomc_window_after":FOMC_POST,"fomc_defer_days":FOMC_DEFER})
        shim=types.SimpleNamespace(**{k:getattr(b,k) for k in ("df","dates","atr21","fwd21","spy_dist_sma200","is_fomc_day")})
        nr=dict(b.returns); nr[cfg["lookback_stable"]]=sig; shim.returns=nr
        return PortfolioEngine(shim,gated,cfg)

    # Engines per (uni, w1, topk)
    engs={}
    topks_needed = {2}
    ws_needed = {W_NORM, W_FULL}
    if dyn_topk: topks_needed.update(dyn_topk.get("ks",[2]))
    if equity_dd_scale: ws_needed.add(dd_w)
    for uni_n,uni in [("s",STABLE),("t",TRANS)]:
        for w1 in ws_needed:
            for tk in topks_needed:
                engs[(uni_n,w1,tk)] = mk(uni,w1,tk)
    td=_STATE["test_dates"]; eng0=engs[("s",W_NORM,2)]
    ps=pd.Series(eng0.dates.get_indexer(td),index=td)
    ml=ps.groupby(td.to_period("M")).tail(1)
    fomc_idx=np.where(b.is_fomc_day)[0]
    evm=fomc_window_mask(eng0.n_days,fomc_idx,pre_days=FOMC_PRE,post_days=FOMC_POST)

    def ret_at(eng,i):
        t1,tk=eng.pick_at(i)
        # Absolute momentum filter for top1
        if abs_mom_filter:
            t1_name = eng.universe[t1]
            raw = abs_mom_ret[t1_name].iloc[i] if hasattr(abs_mom_ret, "iloc") else None
            if raw is not None and not np.isnan(raw) and raw < 0:
                r1 = eng.cash_fwd[i]  # go to cash
            else:
                r1=eng.fwd_arr[i,t1] if eng.spy_dist[i]>eng.sma_buffer else eng.cash_fwd[i]
        else:
            r1=eng.fwd_arr[i,t1] if eng.spy_dist[i]>eng.sma_buffer else eng.cash_fwd[i]
        sel=eng.atr_arr[i,tk]
        v=np.where(sel>0,sel,np.nan)
        w=1.0/(v**P_EXP)
        if np.isnan(w).all():
            rk=np.nanmean(eng.fwd_arr[i,tk])
        else:
            w=w/np.nansum(w); rk=np.nansum(eng.fwd_arr[i,tk]*w)
        return eng.top1_w*r1 + eng.topk_w*rk

    rets=[]; hist=[]; dts=[]; peak=1.0; eq=1.0
    for rd,p in ml.items():
        # Seasonal filter
        if seasonal_filter == "sell_may" and rd.month in (5,6,7,8,9):
            r = 0.0
            rets.append(r); hist.append(r); dts.append(rd)
            eq *= (1+r); peak=max(peak,eq)
            continue

        i,_=resolve_rebalance_index(int(p),FOMC_DEFER,evm,eng0.n_days)
        use_t=(pr[i]!=cur[i])and(pr[i]>=0)and(not np.isnan(mp[i]))and(mp[i]>=0.50)
        c9 = (np.prod([1+h for h in hist[-BOOST_LB_M:]])-1) if len(hist)>=BOOST_LB_M else 0.05
        sv = spy_63[i] if not np.isnan(spy_63[i]) else -1.0
        boost = (c9>BOOST_THR) or (sv>SPY_FAST_THR)
        w1 = W_FULL if boost else W_NORM

        # Equity-based DD scaling
        if equity_dd_scale:
            dd = eq/peak - 1.0
            if dd < dd_thr:
                w1 = dd_w

        # Dynamic top_k
        tk_use = 2
        if dyn_topk:
            # If signal gap large, concentrate (k=2); if small, diversify (k=4)
            uni = STABLE if not use_t else TRANS
            sig_vals = sig.iloc[i].reindex(uni).values
            if np.isnan(sig_vals).all():
                tk_use = 2
            else:
                r_ranks = pd.Series(sig_vals).rank(method="average").values
                r1 = np.nanmax(r_ranks)
                r2 = np.nanmax(r_ranks[r_ranks < r1]) if np.any(r_ranks < r1) else r1
                gap = (r1 - r2) / len(uni)
                tk_use = 2 if gap > dyn_topk["thr"] else dyn_topk.get("wide", 4)

        uni_n="t" if use_t else "s"
        key = (uni_n, w1, tk_use)
        if key not in engs:
            engs[key] = mk(STABLE if uni_n=="s" else TRANS, w1, tk_use)
        r=ret_at(engs[key],i)
        hist.append(r); rets.append(r); dts.append(rd)
        eq *= (1+r); peak=max(peak,eq)
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

    print("=== H21: alternative classifier caches ===")
    for cache in ["pred_proba_p46.pkl","pred_proba_p45.pkl","pred_proba_p44_05.pkl","pred_proba_v2.pkl","pred_proba.pkl"]:
        try:
            show(cache, run(cache_file=cache), base)
        except Exception as e:
            print(f"{cache}: ERROR {type(e).__name__}")

    print()
    print("=== H22: absolute momentum filter ===")
    for lb in [21, 63, 126]:
        show(f"abs_mom_{lb}d", run(abs_mom_filter=True, abs_mom_lb=lb), base)

    print()
    print("=== H23: dynamic top_k (gap-based) ===")
    for thr in [0.10, 0.15, 0.20]:
        for wide in [3, 4, 5]:
            show(f"dyn_topk thr={thr} wide={wide}", run(dyn_topk={"thr":thr,"wide":wide,"ks":[2,wide]}), base)

    print()
    print("=== H24: seasonal filter (sell May-Sep) ===")
    show("sell_may_sep", run(seasonal_filter="sell_may"), base)

    print()
    print("=== H25: own-equity DD top1 scaling ===")
    for thr in [-0.03,-0.05,-0.08]:
        for wd in [0.30,0.35,0.40]:
            show(f"eq_dd thr={thr} w={wd}", run(equity_dd_scale=True,dd_thr=thr,dd_w=wd), base)

    print()
    print("=== H26: margin gate ===")
    for mt in [0.10, 0.15, 0.20, 0.25]:
        show(f"margin_thr={mt}", run(margin_gate=True, margin_thr=mt), base)


if __name__ == "__main__":
    main()
