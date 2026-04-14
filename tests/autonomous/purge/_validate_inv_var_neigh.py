"""Parameter neighborhood test for the basket weight exponent.

weight = 1 / vol^p, for p in {0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0}.
p=0 is equal-weight, p=1 is inv-ATR (baseline), p=2 is inv-variance.
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

STABLE = ["SOXX", "QQQ", "IGV", "XLE", "GLD", "SHY"]
TRANS = STABLE + ["TLT", "AGG", "XLV", "XLF"]
W_NORM = 0.50; W_FULL = 0.82
BOOST_LB_M = 9; BOOST_THR = 0.30; SPY_FAST_LB = 63; SPY_FAST_THR = 0.12
FOMC_PRE, FOMC_POST, FOMC_DEFER = 0, 2, 3


def build_sig():
    b = _STATE["bundle"]
    cm = None; ranks = None
    for lb, w in [(42,1),(63,3),(126,1)]:
        r = b.returns[lb]
        if cm is None: cm = list(r.columns)
        else: r = r[cm]
        rk = r.rank(axis=1, method="average") * w
        ranks = rk if ranks is None else ranks + rk
    return ranks / 5.0


def run(p_exp):
    _load(); b = _STATE["bundle"]
    with open(HERE.parent / "cache" / "pred_proba_p46.pkl", "rb") as f:
        pr, mp = pickle.load(f)
    cur = np.asarray(_cr(b.df).index)
    gated = pr.copy()
    want = (pr != cur) & (pr >= 0)
    low = np.nan_to_num(mp, nan=0.0) < 0.40
    gated[want & low] = cur[want & low]
    sig = build_sig()
    spy_63 = b.returns[SPY_FAST_LB]["SPY"].values

    def mk(uni, w1):
        cfg = copy.deepcopy(_STATE["cfg"])
        cfg.update({"universe": uni, "top1_weight": w1, "top3_weight": 1 - w1,
                    "fomc_window_pre": FOMC_PRE, "fomc_window_after": FOMC_POST,
                    "fomc_defer_days": FOMC_DEFER})
        shim = types.SimpleNamespace(**{k: getattr(b, k) for k in (
            "df", "dates", "atr21", "fwd21", "spy_dist_sma200", "is_fomc_day")})
        nr = dict(b.returns); nr[cfg["lookback_stable"]] = sig; shim.returns = nr
        return PortfolioEngine(shim, gated, cfg)

    engs = {}
    for uni_n, uni in [("s", STABLE), ("t", TRANS)]:
        for w1 in (W_NORM, W_FULL):
            engs[(uni_n, w1)] = mk(uni, w1)
    td = _STATE["test_dates"]
    eng0 = engs[("s", W_NORM)]
    pos = pd.Series(eng0.dates.get_indexer(td), index=td)
    month_last = pos.groupby(td.to_period("M")).tail(1)
    fomc_idx = np.where(b.is_fomc_day)[0]
    evm = fomc_window_mask(eng0.n_days, fomc_idx, pre_days=FOMC_PRE, post_days=FOMC_POST)

    def ret_at(eng, i):
        t1, tk = eng.pick_at(i)
        r1 = eng.fwd_arr[i, t1] if eng.spy_dist[i] > eng.sma_buffer else eng.cash_fwd[i]
        sel = eng.atr_arr[i, tk]
        v = np.where(sel > 0, sel, np.nan)
        if p_exp == 0:
            w = np.ones_like(v)
        else:
            w = 1.0 / (v ** p_exp)
        if np.isnan(w).all():
            rk = np.nanmean(eng.fwd_arr[i, tk])
        else:
            w = w / np.nansum(w)
            rk = np.nansum(eng.fwd_arr[i, tk] * w)
        return eng.top1_w * r1 + eng.topk_w * rk

    rets = []; hist = []; dts = []
    for rd, p in month_last.items():
        i, _ = resolve_rebalance_index(int(p), FOMC_DEFER, evm, eng0.n_days)
        use_t = (pr[i] != cur[i]) and (pr[i] >= 0) and \
                (not np.isnan(mp[i])) and (mp[i] >= 0.50)
        if len(hist) >= BOOST_LB_M:
            c9 = np.prod([1 + h for h in hist[-BOOST_LB_M:]]) - 1
        else:
            c9 = 0.05
        sv = spy_63[i] if not np.isnan(spy_63[i]) else -1.0
        w1 = W_FULL if (c9 > BOOST_THR or sv > SPY_FAST_THR) else W_NORM
        uni_n = "t" if use_t else "s"
        r = ret_at(engs[(uni_n, w1)], i)
        hist.append(r); rets.append(r); dts.append(rd)
    ser = pd.Series(rets, index=pd.Index(dts))
    return ser.dropna()


def per_half(ser):
    sA = ser[ser.index.map(lambda d: d.year < 2018)]
    sB = ser[ser.index.map(lambda d: d.year >= 2018)]
    return compute_stats(ser.values), compute_stats(sA.values), compute_stats(sB.values)


def main():
    print(f"{'p_exp':>6}  {'CAGR':>8}  {'Sharpe':>8}  {'MaxDD':>8}  {'A-Sh':>8}  {'B-Sh':>8}")
    for p in [0.0, 0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0, 2.25, 2.5, 3.0, 4.0]:
        ser = run(p)
        f, a, b_ = per_half(ser)
        print(f"{p:>6.2f}  {f['cagr']*100:>7.2f}%  {f['sharpe']:>8.3f}  "
              f"{f['max_dd']*100:>7.2f}%  {a['sharpe']:>8.3f}  {b_['sharpe']:>8.3f}")


if __name__ == "__main__":
    main()
