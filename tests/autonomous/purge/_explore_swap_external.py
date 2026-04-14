"""Use externally-fetched tickers to test symbol-swap robustness.

Strategy: construct a modified bundle where one ticker is replaced with its
equivalent from the swap_tickers.pkl cache. Rebuild returns[10,21,42,63,126]
and ATR for that ticker from the new close series.
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


def load_swap_data():
    with open(HERE.parent / "cache" / "swap_tickers.pkl", "rb") as f:
        return pickle.load(f)


def patch_bundle(b, replacements):
    """replacements = {old_ticker: new_ticker_name}. Returns a new bundle-like shim.
    Patches BOTH returns[lb] and atr21 for clean comparison."""
    swap_data = load_swap_data()
    new_returns = {}
    for lb, r_df in b.returns.items():
        new_df = r_df.copy()
        for old, new_name in replacements.items():
            if new_name not in swap_data:
                return None
            if old not in new_df.columns:
                continue
            close = swap_data[new_name]
            lb_ret = close.pct_change(lb)
            lb_ret = lb_ret.reindex(r_df.index)
            new_df[old] = lb_ret.values
        new_returns[lb] = new_df

    # Patch atr21 with a rolling 21d stdev of 1d returns as a clean vol proxy
    new_atr = b.atr21.copy()
    for old, new_name in replacements.items():
        if old not in new_atr.columns:
            continue
        close = swap_data[new_name]
        r1 = close.pct_change()
        atr_proxy = r1.abs().rolling(21, min_periods=21).mean()
        atr_proxy = atr_proxy.reindex(b.atr21.index)
        new_atr[old] = atr_proxy.values

    # Also patch fwd21 with realized 21d forward return
    new_fwd = b.fwd21.copy() if hasattr(b.fwd21, "copy") else b.fwd21
    if hasattr(new_fwd, "columns"):
        for old, new_name in replacements.items():
            if old not in new_fwd.columns:
                continue
            close = swap_data[new_name]
            fwd = close.pct_change(21).shift(-21)
            fwd = fwd.reindex(new_fwd.index)
            new_fwd[old] = fwd.values

    new_b = types.SimpleNamespace(
        df=b.df, dates=b.dates, atr21=new_atr, fwd21=new_fwd,
        spy_dist_sma200=b.spy_dist_sma200, is_fomc_day=b.is_fomc_day,
        returns=new_returns
    )
    return new_b


def build_sig(bundle):
    cm=None; ranks=None
    for lb,w in [(42,1),(63,3),(126,1)]:
        r=bundle.returns[lb]
        if cm is None: cm=list(r.columns)
        else: r=r[cm]
        rk=r.rank(axis=1,method="average")*w
        ranks = rk if ranks is None else ranks+rk
    return ranks/5.0


def run(replacements=None):
    _load(); b=_STATE["bundle"]
    if replacements:
        b = patch_bundle(b, replacements)
        if b is None:
            return None
    with open(HERE.parent/"cache"/"pred_proba_p46.pkl","rb") as f:
        pr,mp = pickle.load(f)
    cur=np.asarray(_cr(_STATE["bundle"].df).index)
    gated=pr.copy()
    want=(pr!=cur)&(pr>=0); low=np.nan_to_num(mp,nan=0)<0.40
    gated[want&low]=cur[want&low]
    sig = build_sig(b)
    spy_63=b.returns[SPY_FAST_LB]["SPY"].values

    def mk(uni,w1):
        cfg=copy.deepcopy(_STATE["cfg"])
        cfg.update({"universe":uni,"top1_weight":w1,"top3_weight":1-w1,
                    "fomc_window_pre":FOMC_PRE,"fomc_window_after":FOMC_POST,"fomc_defer_days":FOMC_DEFER})
        nr=dict(b.returns); nr[cfg["lookback_stable"]]=sig
        shim = types.SimpleNamespace(
            df=b.df, dates=b.dates, atr21=b.atr21, fwd21=b.fwd21,
            spy_dist_sma200=b.spy_dist_sma200, is_fomc_day=b.is_fomc_day,
            returns=nr)
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


def main():
    base = per_half(run(None))
    print(f"baseline (Robust-VAR): CAGR {base[0]['cagr']*100:.2f}%  Sh {base[0]['sharpe']:.3f}  A {base[1]['sharpe']:.3f}  B {base[2]['sharpe']:.3f}")
    print()
    print(f"{'swap':<20}  CAGR    Sh      A       B       dSh")
    swaps = [
        ("SOXX->SMH", {"SOXX":"SMH"}),
        ("GLD->IAU",  {"GLD":"IAU"}),
        ("XLE->VDE",  {"XLE":"VDE"}),
        ("IGV->IGM",  {"IGV":"IGM"}),
        ("SHY->BIL",  {"SHY":"BIL"}),
        ("TLT->IEF",  {"TLT":"IEF"}),
        ("AGG->BND",  {"AGG":"BND"}),
        ("SOXX->SMH + GLD->IAU", {"SOXX":"SMH","GLD":"IAU"}),
        ("All swappable", {"SOXX":"SMH","GLD":"IAU","XLE":"VDE","IGV":"IGM","TLT":"IEF","AGG":"BND"}),
    ]
    for name, rep in swaps:
        ser = run(replacements=rep)
        if ser is None:
            print(f"{name:<20}  SKIPPED")
            continue
        f,a,b_ = per_half(ser)
        dSh = f['sharpe'] - base[0]['sharpe']
        print(f"{name:<20}  {f['cagr']*100:6.2f}%  {f['sharpe']:.3f}  {a['sharpe']:.3f}  {b_['sharpe']:.3f}  {dSh:+.3f}")


if __name__ == "__main__":
    main()
