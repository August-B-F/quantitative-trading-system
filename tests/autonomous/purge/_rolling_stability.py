"""Rolling-window stability for Robust-VAR and canonical.

For each 5-year window, compute CAGR, Sharpe, MaxDD of both strategies.
Measure the consistency of the Robust-VAR edge. A stable edge across windows
is strong evidence of genuine alpha; a concentrated edge is a warning sign.
"""
from __future__ import annotations
import sys, copy, types, warnings
from pathlib import Path
import numpy as np, pandas as pd
warnings.filterwarnings("ignore")
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
from _explore_batch2 import run as run_b2  # noqa: E402
from backtest.engine import compute_stats  # noqa: E402
from utils.base_test import _load, _STATE  # noqa: E402
from strategy.portfolio import PortfolioEngine  # noqa: E402
from strategy.rebalance import fomc_window_mask, resolve_rebalance_index  # noqa: E402

CANON = ["SOXX","QQQ","XLK","VGT","IGV","XLE","GLD","SHY"]


def run_canonical():
    _load(); b = _STATE["bundle"]
    cfg = copy.deepcopy(_STATE["cfg"])
    cfg.update({"universe":CANON,"top1_weight":0.50,"top3_weight":0.50,
                "fomc_window_pre":0,"fomc_window_after":2,"fomc_defer_days":3})
    shim = types.SimpleNamespace(**{k:getattr(b,k) for k in ("df","dates","atr21","fwd21","spy_dist_sma200","is_fomc_day")})
    shim.returns = b.returns
    eng = PortfolioEngine(shim, _STATE["pred_reg"], cfg)
    td = _STATE["test_dates"]
    pos = pd.Series(eng.dates.get_indexer(td), index=td)
    ml = pos.groupby(td.to_period("M")).tail(1)
    fomc_idx = np.where(b.is_fomc_day)[0]
    evm = fomc_window_mask(eng.n_days, fomc_idx, pre_days=0, post_days=2)
    rets=[]; dts=[]
    for rd,p in ml.items():
        i,_=resolve_rebalance_index(int(p),3,evm,eng.n_days)
        t1,tk=eng.pick_at(i)
        r1=eng.fwd_arr[i,t1] if eng.spy_dist[i]>eng.sma_buffer else eng.cash_fwd[i]
        sel=eng.atr_arr[i,tk]
        inv=1.0/np.where(sel>0,sel,np.nan)
        if np.isnan(inv).all():
            rk=np.nanmean(eng.fwd_arr[i,tk])
        else:
            w=inv/np.nansum(inv); rk=np.nansum(eng.fwd_arr[i,tk]*w)
        rets.append(eng.top1_w*r1 + eng.topk_w*rk); dts.append(rd)
    return pd.Series(rets,index=pd.Index(dts)).dropna()


def window_stats(ser, y_start, y_end):
    s = ser[(ser.index.year >= y_start) & (ser.index.year < y_end)]
    if len(s) < 12:
        return None
    return compute_stats(s.values)


def main():
    canon = run_canonical()
    rvar = run_b2(wscheme="inv_var")
    rob = run_b2(wscheme="inv_atr")
    print(f"Full sample:  canon Sh {compute_stats(canon.dropna().values)['sharpe']:.3f}  "
          f"robust Sh {compute_stats(rob.dropna().values)['sharpe']:.3f}  "
          f"robust-var Sh {compute_stats(rvar.dropna().values)['sharpe']:.3f}")
    print()

    windows = [(y, y+5) for y in range(2010, 2022)]
    print(f"{'window':<12}  {'canon':>18}  {'robust':>18}  {'robust-var':>18}  {'r-v edge':>10}")
    for y1, y2 in windows:
        a = window_stats(canon, y1, y2)
        b = window_stats(rob, y1, y2)
        c = window_stats(rvar, y1, y2)
        if a and b and c:
            print(f"{y1}-{y2-1}   "
                  f"{a['cagr']*100:>7.2f}% Sh{a['sharpe']:>6.2f}  "
                  f"{b['cagr']*100:>7.2f}% Sh{b['sharpe']:>6.2f}  "
                  f"{c['cagr']*100:>7.2f}% Sh{c['sharpe']:>6.2f}  "
                  f"{c['sharpe']-a['sharpe']:+.2f}")

    # rolling 3-year too for finer resolution
    print()
    print("=== 3-year windows ===")
    print(f"{'window':<12}  {'canon':>12}  {'r-var':>12}  {'r-v edge':>10}")
    for y in range(2010, 2024):
        a = window_stats(canon, y, y+3)
        c = window_stats(rvar, y, y+3)
        if a and c:
            print(f"{y}-{y+2}   Sh{a['sharpe']:>6.2f}        Sh{c['sharpe']:>6.2f}        {c['sharpe']-a['sharpe']:+.2f}")


if __name__ == "__main__":
    main()
