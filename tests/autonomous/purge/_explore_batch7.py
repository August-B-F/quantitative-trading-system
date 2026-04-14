"""Round-7 creative angles:
H32: log-inverse vol weights  w = -log(vol)
H33: signal-rank-weighted basket (higher rank → more weight)
H34: hybrid w = (rank * inv_var)
H35: 10-day momentum as tie-breaker for top1 pick
H36: exponential weight kernel w = exp(-vol/scale)
H37: blend inv-var with equal weight (0.5 each)
H38: inv-var with min-weight floor (no holding < 5%)
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


def build_sig():
    b=_STATE["bundle"]; cm=None; ranks=None
    for lb,w in [(42,1),(63,3),(126,1)]:
        r=b.returns[lb]
        if cm is None: cm=list(r.columns)
        else: r=r[cm]
        rk=r.rank(axis=1,method="average")*w
        ranks = rk if ranks is None else ranks+rk
    return ranks/5.0


def basket_weights(sel_atr, scheme, sig_vals=None, floor=0.05, p=2.0, blend=0.5, scale=0.02):
    v = np.where(sel_atr > 0, sel_atr, np.nan)
    if scheme == "inv_var":
        w = 1.0 / (v**2)
    elif scheme == "inv_var_floor":
        w = 1.0 / (v**2)
        if not np.isnan(w).all():
            w_norm = w / np.nansum(w)
            w_norm = np.maximum(w_norm, floor)
            w = w_norm / w_norm.sum()
            return w
    elif scheme == "log_inv":
        w = -np.log(v)  # negative log: lower vol → bigger number
        if not np.isnan(w).all():
            w = np.maximum(w, 0) + 0.001  # positive
    elif scheme == "sig_weighted":
        w = sig_vals if sig_vals is not None else np.ones_like(v)
    elif scheme == "rank_inv_var":
        w = (sig_vals if sig_vals is not None else np.ones_like(v)) * (1.0 / (v**2))
    elif scheme == "exp_kernel":
        w = np.exp(-v / scale)
    elif scheme == "blend_eq":
        inv_var = 1.0 / (v**2)
        if np.isnan(inv_var).all():
            return None
        inv_var_norm = inv_var / np.nansum(inv_var)
        eq = np.ones_like(v) / len(v)
        w = blend * inv_var_norm + (1 - blend) * eq
        return w
    else:
        w = 1.0 / (v**p)
    if np.isnan(w).all():
        return None
    w = w / np.nansum(w)
    return w


def run(scheme="inv_var", **kwargs):
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
        uni_tk_names = [eng.universe[k] for k in tk]
        sig_row = sig.iloc[i].reindex(uni_tk_names).values
        w = basket_weights(sel, scheme, sig_vals=sig_row, **kwargs)
        if w is None or np.isnan(w).all():
            rk = np.nanmean(eng.fwd_arr[i,tk])
        else:
            rk = np.nansum(eng.fwd_arr[i,tk] * w)
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


def show(label, ser, base):
    f,a,b_=per_half(ser)
    f0,a0,b0=base
    dSh=f['sharpe']-f0['sharpe']; dA=a['sharpe']-a0['sharpe']; dB=b_['sharpe']-b0['sharpe']
    tag=""
    if dA>=-0.02 and dB>=-0.02 and dSh>=0.04: tag="  PASS"
    elif dA>=-0.02 and dB>=-0.02 and dSh>=0:  tag="  +"
    print(f"{label:<44}  {f['cagr']*100:>6.2f}%  Sh {f['sharpe']:.3f}  A {a['sharpe']:.3f}  B {b_['sharpe']:.3f}  dSh {dSh:+.3f}{tag}")


def main():
    base = per_half(run(scheme="inv_var"))
    print(f"baseline (inv_var p=2): Sh {base[0]['sharpe']:.3f}  A {base[1]['sharpe']:.3f}  B {base[2]['sharpe']:.3f}")
    print()

    print("=== H32: log-inverse vol ===")
    show("log_inv", run(scheme="log_inv"), base)
    print()
    print("=== H33: signal-rank weighted basket ===")
    show("sig_weighted", run(scheme="sig_weighted"), base)
    print()
    print("=== H34: rank × inv_var hybrid ===")
    show("rank_inv_var", run(scheme="rank_inv_var"), base)
    print()
    print("=== H36: exponential kernel w = exp(-vol/scale) ===")
    for scale in [0.005, 0.010, 0.015, 0.020, 0.030]:
        show(f"exp_kernel scale={scale}", run(scheme="exp_kernel", scale=scale), base)
    print()
    print("=== H37: blend inv_var with equal weight ===")
    for blend in [0.3, 0.5, 0.7, 0.8, 0.9]:
        show(f"blend_eq {blend}", run(scheme="blend_eq", blend=blend), base)
    print()
    print("=== H38: inv_var with min-weight floor ===")
    for floor in [0.02, 0.05, 0.08, 0.10]:
        show(f"inv_var_floor {floor}", run(scheme="inv_var_floor", floor=floor), base)


if __name__ == "__main__":
    main()
