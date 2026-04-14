"""Attribute Robust-VAR returns to each predicted regime.

For each month, what regime was predicted? Group monthly returns by regime and
compute per-regime Sharpe and CAGR contribution.
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

REGIME_NAMES = {0:"growth+low_infl", 1:"growth+high_infl", 2:"bust+low_infl", 3:"bust+high_infl", -1:"unknown"}


def build_sig():
    b=_STATE["bundle"]; cm=None; ranks=None
    for lb,w in [(42,1),(63,3),(126,1)]:
        r=b.returns[lb]
        if cm is None: cm=list(r.columns)
        else: r=r[cm]
        rk=r.rank(axis=1,method="average")*w
        ranks = rk if ranks is None else ranks+rk
    return ranks/5.0


def run_with_regime():
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
        r1=eng.fwd_arr[i,t1] if eng.spy_dist[i]>eng.sma_buffer else eng.cash_fwd[i]
        sel=eng.atr_arr[i,tk]
        v=np.where(sel>0,sel,np.nan); w=1.0/(v**P_EXP)
        if np.isnan(w).all():
            rk=np.nanmean(eng.fwd_arr[i,tk])
        else:
            w=w/np.nansum(w); rk=np.nansum(eng.fwd_arr[i,tk]*w)
        return eng.top1_w*r1 + eng.topk_w*rk, eng.universe[t1]

    rows=[]; hist=[]
    for rd,p in ml.items():
        i,_=resolve_rebalance_index(int(p),FOMC_DEFER,evm,eng0.n_days)
        use_t=(pr[i]!=cur[i])and(pr[i]>=0)and(not np.isnan(mp[i]))and(mp[i]>=0.50)
        c9 = (np.prod([1+h for h in hist[-BOOST_LB_M:]])-1) if len(hist)>=BOOST_LB_M else 0.05
        sv = spy_63[i] if not np.isnan(spy_63[i]) else -1.0
        boost = (c9>BOOST_THR or sv>SPY_FAST_THR)
        w1 = W_FULL if boost else W_NORM
        uni_n="t" if use_t else "s"
        r, top1_name = ret_at(engs[(uni_n,w1)],i)
        rows.append(dict(date=rd, ret=r, current_regime=cur[i], predicted_regime=pr[i],
                         boost=boost, use_t=use_t, top1=top1_name, proba=mp[i]))
        hist.append(r)
    return pd.DataFrame(rows).set_index("date")


def main():
    df = run_with_regime()
    df = df.dropna(subset=["ret"])
    print(f"Total months: {len(df)}")
    print()

    # Per current regime
    print("=== By current regime ===")
    for reg, sub in df.groupby("current_regime"):
        if len(sub) < 3: continue
        s = compute_stats(sub["ret"].values)
        print(f"  {REGIME_NAMES.get(reg, reg):<20}  n={len(sub):3d}  CAGR {s['cagr']*100:6.2f}%  Sh {s['sharpe']:.3f}")

    print()
    print("=== Boost state ===")
    for b_state, sub in df.groupby("boost"):
        s = compute_stats(sub["ret"].values)
        print(f"  boost={b_state}  n={len(sub):3d}  CAGR {s['cagr']*100:6.2f}%  Sh {s['sharpe']:.3f}")

    print()
    print("=== Transition universe usage ===")
    for t_state, sub in df.groupby("use_t"):
        s = compute_stats(sub["ret"].values)
        print(f"  use_t={t_state}  n={len(sub):3d}  CAGR {s['cagr']*100:6.2f}%  Sh {s['sharpe']:.3f}")

    print()
    print("=== Top 10 top1 picks (by months held) ===")
    top_counts = df["top1"].value_counts().head(10)
    for name, n in top_counts.items():
        sub = df[df["top1"] == name]
        s = compute_stats(sub["ret"].values)
        print(f"  {name:<8}  n={n:3d}  CAGR {s['cagr']*100:6.2f}%  Sh {s['sharpe']:.3f}  mean {sub['ret'].mean()*100:+.2f}%")


if __name__ == "__main__":
    main()
