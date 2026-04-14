"""Cost sensitivity for inv-variance Robust variant."""
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

STABLE = ["SOXX","QQQ","IGV","XLE","GLD","SHY"]
TRANS = STABLE + ["TLT","AGG","XLV","XLF"]
W_NORM=0.50; W_FULL=0.82; BOOST_LB_M=9; BOOST_THR=0.30; SPY_FAST_LB=63; SPY_FAST_THR=0.12
FOMC_PRE, FOMC_POST, FOMC_DEFER = 0, 2, 3


def build_sig():
    b = _STATE["bundle"]; cm=None; ranks=None
    for lb, w in [(42,1),(63,3),(126,1)]:
        r = b.returns[lb]
        if cm is None: cm = list(r.columns)
        else: r = r[cm]
        rk = r.rank(axis=1, method="average") * w
        ranks = rk if ranks is None else ranks + rk
    return ranks / 5.0


def run_weights(p_exp):
    _load(); b = _STATE["bundle"]
    with open(HERE.parent/"cache"/"pred_proba_p46.pkl","rb") as f:
        pr,mp = pickle.load(f)
    cur = np.asarray(_cr(b.df).index)
    gated = pr.copy()
    want = (pr != cur)&(pr>=0); low = np.nan_to_num(mp,nan=0)<0.40
    gated[want&low] = cur[want&low]
    sig = build_sig()
    spy_63 = b.returns[SPY_FAST_LB]["SPY"].values

    def mk(uni, w1):
        cfg = copy.deepcopy(_STATE["cfg"])
        cfg.update({"universe":uni,"top1_weight":w1,"top3_weight":1-w1,
                    "fomc_window_pre":FOMC_PRE,"fomc_window_after":FOMC_POST,"fomc_defer_days":FOMC_DEFER})
        shim = types.SimpleNamespace(**{k:getattr(b,k) for k in ("df","dates","atr21","fwd21","spy_dist_sma200","is_fomc_day")})
        nr = dict(b.returns); nr[cfg["lookback_stable"]] = sig; shim.returns = nr
        return PortfolioEngine(shim, gated, cfg)

    engs={}
    for uni_n,uni in [("s",STABLE),("t",TRANS)]:
        for w1 in (W_NORM,W_FULL):
            engs[(uni_n,w1)] = mk(uni,w1)
    td = _STATE["test_dates"]; eng0 = engs[("s",W_NORM)]
    pos = pd.Series(eng0.dates.get_indexer(td),index=td)
    ml = pos.groupby(td.to_period("M")).tail(1)
    fomc_idx = np.where(b.is_fomc_day)[0]
    evm = fomc_window_mask(eng0.n_days,fomc_idx,pre_days=FOMC_PRE,post_days=FOMC_POST)

    all_t = sorted(set(STABLE)|set(TRANS))
    rows=[]; rets=[]; hist=[]; dts=[]
    for rd,p in ml.items():
        i,_ = resolve_rebalance_index(int(p),FOMC_DEFER,evm,eng0.n_days)
        use_t = (pr[i]!=cur[i])and(pr[i]>=0)and(not np.isnan(mp[i]))and(mp[i]>=0.50)
        c9 = (np.prod([1+h for h in hist[-BOOST_LB_M:]])-1) if len(hist)>=BOOST_LB_M else 0.05
        sv = spy_63[i] if not np.isnan(spy_63[i]) else -1.0
        w1 = W_FULL if (c9>BOOST_THR or sv>SPY_FAST_THR) else W_NORM
        uni_n = "t" if use_t else "s"
        eng = engs[(uni_n,w1)]
        t1, tk = eng.pick_at(i)
        row = {t:0.0 for t in all_t}
        if eng.spy_dist[i] > eng.sma_buffer:
            row[eng.universe[t1]] += eng.top1_w
        else:
            row[eng.cash] += eng.top1_w
        sel = eng.atr_arr[i, tk]
        v = np.where(sel>0,sel,np.nan)
        if p_exp == 0:
            w = np.ones_like(v)
        else:
            w = 1.0 / (v**p_exp)
        if np.isnan(w).all():
            rk = np.nanmean(eng.fwd_arr[i,tk]); w_norm = np.ones(len(tk))/len(tk)
        else:
            w_norm = w / np.nansum(w)
            rk = np.nansum(eng.fwd_arr[i,tk]*w_norm)
        for j,kk in enumerate(tk):
            if not np.isnan(w_norm[j]):
                row[eng.universe[kk]] += eng.topk_w * w_norm[j]
        r1 = eng.fwd_arr[i,t1] if eng.spy_dist[i]>eng.sma_buffer else eng.cash_fwd[i]
        r_g = eng.top1_w*r1 + eng.topk_w*rk
        rows.append(row); rets.append(r_g); hist.append(r_g); dts.append(rd)
    W = pd.DataFrame(rows,index=pd.Index(dts),columns=all_t).fillna(0.0)
    gross = pd.Series(rets,index=pd.Index(dts))
    return W,gross


def main():
    for label, p in [("inv-ATR (p=1)",1.0), ("inv-VAR (p=2)",2.0)]:
        W, gross = run_weights(p)
        to = 0.5*(W - W.shift(1).fillna(0)).abs().sum(axis=1)
        valid = ~gross.isna()
        g2 = gross[valid]; to2 = to[valid]
        print(f"\n=== {label} ===")
        print(f"Avg 1-way turnover: {to2.mean():.3f}  Ann: {to2.mean()*12:.2f}x")
        for bps in [0,2,5,10,20,40]:
            nr = (g2 - (bps/10_000)*2*to2).values
            s = compute_stats(nr)
            print(f"  {bps:>3}bps  CAGR {s['cagr']*100:6.2f}%  Sh {s['sharpe']:.3f}  DD {s['max_dd']*100:.2f}%")


if __name__ == "__main__":
    main()
