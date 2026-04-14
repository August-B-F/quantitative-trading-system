"""Round-8 architectural changes:
H39: full-basket risk parity across top_k=4 names (no top1 vs topk split)
H40: dynamic basket — include top1 inversely-weighted with rest
H41: pick top_k based on signal strength (narrow when strong, wide when weak) — already did dyn
H42: classifier proba as top1 weight tilt (all regimes, continuous)
H43: take top2 NOT top1 as the flagship pick (robustness check)
H44: keep top1 AND top2 as co-flagships (weighted 0.35 each)
"""
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


def run(mode="baseline", **kwargs):
    _load(); b=_STATE["bundle"]
    with open(HERE.parent/"cache"/"pred_proba_p46.pkl","rb") as f:
        pr,mp = pickle.load(f)
    cur=np.asarray(_cr(b.df).index)
    gated=pr.copy()
    want=(pr!=cur)&(pr>=0); low=np.nan_to_num(mp,nan=0)<0.40
    gated[want&low]=cur[want&low]
    sig = build_sig()
    spy_63=b.returns[SPY_FAST_LB]["SPY"].values

    def mk(uni,w1,tk=3):
        cfg=copy.deepcopy(_STATE["cfg"])
        cfg.update({"universe":uni,"top1_weight":w1,"top3_weight":1-w1,"top_k":tk,
                    "fomc_window_pre":FOMC_PRE,"fomc_window_after":FOMC_POST,"fomc_defer_days":FOMC_DEFER})
        shim=types.SimpleNamespace(**{k:getattr(b,k) for k in ("df","dates","atr21","fwd21","spy_dist_sma200","is_fomc_day")})
        nr=dict(b.returns); nr[cfg["lookback_stable"]]=sig; shim.returns=nr
        return PortfolioEngine(shim,gated,cfg)

    engs={}
    ws = {W_NORM, W_FULL}
    if mode == "rp_full": tks = [4]
    elif mode in ("co_flagship","top2_pick"): tks = [3]
    else: tks = [3]
    for uni_n,uni in [("s",STABLE),("t",TRANS)]:
        for w1 in ws:
            for tk in tks:
                engs[(uni_n,w1,tk)] = mk(uni,w1,tk)
    td=_STATE["test_dates"]; eng0=engs[("s",W_NORM,tks[0])]
    ps=pd.Series(eng0.dates.get_indexer(td),index=td)
    ml=ps.groupby(td.to_period("M")).tail(1)
    fomc_idx=np.where(b.is_fomc_day)[0]
    evm=fomc_window_mask(eng0.n_days,fomc_idx,pre_days=FOMC_PRE,post_days=FOMC_POST)

    rets=[]; hist=[]; dts=[]
    for rd,p in ml.items():
        i,_=resolve_rebalance_index(int(p),FOMC_DEFER,evm,eng0.n_days)
        use_t=(pr[i]!=cur[i])and(pr[i]>=0)and(not np.isnan(mp[i]))and(mp[i]>=0.50)
        c9 = (np.prod([1+h for h in hist[-BOOST_LB_M:]])-1) if len(hist)>=BOOST_LB_M else 0.05
        sv = spy_63[i] if not np.isnan(spy_63[i]) else -1.0
        w1 = W_FULL if (c9>BOOST_THR or sv>SPY_FAST_THR) else W_NORM
        uni_n="t" if use_t else "s"
        eng = engs[(uni_n, w1, tks[0])]
        t1, tk = eng.pick_at(i)

        if mode == "rp_full":
            # Full inv-var across top1 + topk
            all_idx = np.concatenate([[t1], tk])
            all_idx = np.unique(all_idx)
            sel = eng.atr_arr[i, all_idx]
            v = np.where(sel>0, sel, np.nan)
            w = 1.0 / (v**P_EXP)
            fwds = eng.fwd_arr[i, all_idx]
            # Apply SMA gate to top1 slot (treat top1 component specially)
            if eng.spy_dist[i] <= eng.sma_buffer:
                t1_pos = np.where(all_idx == t1)[0][0]
                fwds = fwds.copy()
                fwds[t1_pos] = eng.cash_fwd[i]
            if np.isnan(w).all():
                r = np.nanmean(fwds)
            else:
                w = w / np.nansum(w)
                r = np.nansum(fwds * w)

        elif mode == "co_flagship":
            # top1 and top2 both at half weight
            if len(tk) > 0:
                top2 = tk[0]
            else:
                top2 = t1
            rest = tk[1:] if len(tk) > 1 else np.array([], dtype=int)
            f1 = eng.fwd_arr[i, t1] if eng.spy_dist[i]>eng.sma_buffer else eng.cash_fwd[i]
            f2 = eng.fwd_arr[i, top2] if eng.spy_dist[i]>eng.sma_buffer else eng.cash_fwd[i]
            if len(rest) > 0:
                sel = eng.atr_arr[i, rest]
                v = np.where(sel>0, sel, np.nan)
                w = 1.0/(v**P_EXP)
                if np.isnan(w).all():
                    rk = np.nanmean(eng.fwd_arr[i, rest])
                else:
                    w = w/np.nansum(w); rk = np.nansum(eng.fwd_arr[i, rest]*w)
            else:
                rk = 0.0
            w_co = 0.35
            w_rest = 1 - 2*w_co
            r = w_co*f1 + w_co*f2 + w_rest*rk

        elif mode == "top2_pick":
            # Use top2 as the flagship pick instead of top1
            if len(tk) > 0:
                t1_use = tk[0]
            else:
                t1_use = t1
            r1 = eng.fwd_arr[i,t1_use] if eng.spy_dist[i]>eng.sma_buffer else eng.cash_fwd[i]
            # basket is original top1 + remaining
            rest = np.concatenate([[t1], tk[1:]]) if len(tk) > 1 else np.array([t1])
            sel = eng.atr_arr[i, rest]
            v = np.where(sel>0, sel, np.nan); w = 1.0/(v**P_EXP)
            if np.isnan(w).all():
                rk = np.nanmean(eng.fwd_arr[i, rest])
            else:
                w = w/np.nansum(w); rk = np.nansum(eng.fwd_arr[i,rest]*w)
            r = eng.top1_w*r1 + eng.topk_w*rk

        elif mode == "proba_tilt":
            # Scale top1 weight by mp continuously
            top1_p = np.clip(mp[i] if not np.isnan(mp[i]) else 0.40, 0.30, 0.90)
            w1_new = 0.35 + 0.55 * (top1_p - 0.30) / 0.60  # maps 0.30->0.35, 0.90->0.90
            # Need engine with this weight
            key = (uni_n, round(w1_new,2), 3)
            if key not in engs:
                engs[key] = mk(STABLE if uni_n=="s" else TRANS, round(w1_new,2), 3)
            eng2 = engs[key]
            t1_b, tk_b = eng2.pick_at(i)
            r1 = eng2.fwd_arr[i,t1_b] if eng2.spy_dist[i]>eng2.sma_buffer else eng2.cash_fwd[i]
            sel = eng2.atr_arr[i,tk_b]
            v = np.where(sel>0,sel,np.nan); w = 1.0/(v**P_EXP)
            if np.isnan(w).all():
                rk = np.nanmean(eng2.fwd_arr[i,tk_b])
            else:
                w = w/np.nansum(w); rk = np.nansum(eng2.fwd_arr[i,tk_b]*w)
            r = eng2.top1_w*r1 + eng2.topk_w*rk

        else:  # baseline
            r1 = eng.fwd_arr[i,t1] if eng.spy_dist[i]>eng.sma_buffer else eng.cash_fwd[i]
            sel = eng.atr_arr[i,tk]
            v = np.where(sel>0,sel,np.nan); w = 1.0/(v**P_EXP)
            if np.isnan(w).all():
                rk = np.nanmean(eng.fwd_arr[i,tk])
            else:
                w = w/np.nansum(w); rk = np.nansum(eng.fwd_arr[i,tk]*w)
            r = eng.top1_w*r1 + eng.topk_w*rk

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
    base = per_half(run("baseline"))
    print(f"baseline (Robust-VAR): Sh {base[0]['sharpe']:.3f}  A {base[1]['sharpe']:.3f}  B {base[2]['sharpe']:.3f}")
    print()
    show("H39 full-basket risk parity (top1+topk)", run("rp_full"), base)
    show("H44 co-flagship (top1+top2 at 0.35 each)", run("co_flagship"), base)
    show("H43 top2 pick (flagship = top2)", run("top2_pick"), base)
    show("H42 proba-tilt continuous top1", run("proba_tilt"), base)


if __name__ == "__main__":
    main()
