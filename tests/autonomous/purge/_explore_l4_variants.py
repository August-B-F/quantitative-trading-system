"""H3: explore alternative L4 rank-aggregation recipes under OOS discipline.

Baseline Robust uses (42:1, 63:3, 126:1). The purge tested this param neighborhood
and found it smooth, but never tested *different window sets*. Here we try:
  - wider window sets including 10d, 21d
  - equal weighting across windows
  - geometric-mean aggregation of ranks
  - vol-adjusted rank (mom/vol21)
  - long-only (63+126)
  - add skip-month signal (needs raw prices)

For each variant, require: (a) total Sharpe >= baseline - 0.02,
(b) Period A AND Period B Sharpe both >= baseline - 0.03 (OOS discipline),
(c) 50% haircut on any improvement.
"""
from __future__ import annotations
import sys, pickle, copy, types
from pathlib import Path
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from utils.base_test import _load, _STATE  # noqa: E402
from strategy.portfolio import PortfolioEngine  # noqa: E402
from backtest.engine import compute_stats  # noqa: E402
from strategy.rebalance import fomc_window_mask, resolve_rebalance_index  # noqa: E402
from features.regime_labels import current_regime as _cr  # noqa: E402

STABLE = ["SOXX", "QQQ", "IGV", "XLE", "GLD", "SHY"]
TRANS = STABLE + ["TLT", "AGG", "XLV", "XLF"]
SIG_GATE = 0.40; UNI_TIER = 0.50
W_NORM = 0.50; W_FULL = 0.82
BOOST_LB_M = 9; BOOST_THR = 0.30
SPY_FAST_LB = 63; SPY_FAST_THR = 0.12
FOMC_PRE, FOMC_POST, FOMC_DEFER = 0, 2, 3


def build_sig_weighted(weight_pairs):
    """(lb, w) list — weighted-rank sum."""
    b = _STATE["bundle"]
    cm = None; ranks = None; total = sum(w for _, w in weight_pairs)
    for lb, w in weight_pairs:
        r = b.returns[lb]
        if cm is None: cm = list(r.columns)
        else: r = r[cm]
        rk = r.rank(axis=1, method="average") * w
        ranks = rk if ranks is None else ranks + rk
    return ranks / total


def build_sig_geomean(lbs):
    """Geometric mean of ranks."""
    b = _STATE["bundle"]
    cm = None; log_ranks = None
    for lb in lbs:
        r = b.returns[lb]
        if cm is None: cm = list(r.columns)
        else: r = r[cm]
        rk = np.log(r.rank(axis=1, method="average"))
        log_ranks = rk if log_ranks is None else log_ranks + rk
    return np.exp(log_ranks / len(lbs))


def build_sig_vol_adj(lb_mom, lb_vol):
    """Rank of (momentum / rolling vol)."""
    b = _STATE["bundle"]
    mom = b.returns[lb_mom]
    vol = b.returns[lb_vol]  # hack: use returns as proxy for vol magnitude
    # Better: compute rolling std from 1d returns if available
    if 1 in b.returns:
        r1 = b.returns[1]
        vol_series = r1.rolling(lb_vol).std()
    else:
        # fallback: use abs short returns as proxy
        vol_series = b.returns[lb_vol].abs()
    ratio = mom / (vol_series + 1e-9)
    return ratio.rank(axis=1, method="average")


def build_sig_long_skip(lb_full, lb_skip):
    """Simulate skip-month by (full - skip)."""
    b = _STATE["bundle"]
    return (b.returns[lb_full] - b.returns[lb_skip]).rank(axis=1, method="average")


def run_with_sig(sig):
    _load(); b = _STATE["bundle"]
    with open(HERE.parent / "cache" / "pred_proba_p46.pkl", "rb") as f:
        pr, mp = pickle.load(f)
    cur = np.asarray(_cr(b.df).index)
    gated = pr.copy()
    want = (pr != cur) & (pr >= 0)
    low = np.nan_to_num(mp, nan=0.0) < SIG_GATE
    gated[want & low] = cur[want & low]
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
        inv = 1.0 / np.where(sel > 0, sel, np.nan)
        if np.isnan(inv).all():
            rk = np.nanmean(eng.fwd_arr[i, tk])
        else:
            w = inv / np.nansum(inv); rk = np.nansum(eng.fwd_arr[i, tk] * w)
        return eng.top1_w * r1 + eng.topk_w * rk

    rets = []; hist = []; dts = []
    for rd, p in month_last.items():
        i, _ = resolve_rebalance_index(int(p), FOMC_DEFER, evm, eng0.n_days)
        use_t = (pr[i] != cur[i]) and (pr[i] >= 0) and \
                (not np.isnan(mp[i])) and (mp[i] >= UNI_TIER)
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
    return ser


def per_half(ser):
    sA = ser[ser.index.map(lambda d: d.year < 2018)]
    sB = ser[ser.index.map(lambda d: d.year >= 2018)]
    a = compute_stats(sA.values); b_ = compute_stats(sB.values)
    full = compute_stats(ser.values)
    return full, a, b_


VARIANTS = [
    ("baseline 42:1/63:3/126:1", build_sig_weighted, [(42,1),(63,3),(126,1)]),
    ("equal 42/63/126",          build_sig_weighted, [(42,1),(63,1),(126,1)]),
    ("equal 21/42/63/126",       build_sig_weighted, [(21,1),(42,1),(63,1),(126,1)]),
    ("equal 10/21/42/63/126",    build_sig_weighted, [(10,1),(21,1),(42,1),(63,1),(126,1)]),
    ("long 63/126",              build_sig_weighted, [(63,1),(126,1)]),
    ("long 63:1/126:2",          build_sig_weighted, [(63,1),(126,2)]),
    ("heavy-short 42:2/63:2/126:1", build_sig_weighted, [(42,2),(63,2),(126,1)]),
    ("heavy-short 21:1/42:2/63:2/126:1", build_sig_weighted, [(21,1),(42,2),(63,2),(126,1)]),
    ("3win geomean 42/63/126",   build_sig_geomean,  [42,63,126]),
    ("4win geomean 21/42/63/126",build_sig_geomean,  [21,42,63,126]),
    ("skip-mom 126-21",          build_sig_long_skip, (126,21)),
    ("skip-mom 63-21",           build_sig_long_skip, (63,21)),
]


def main():
    _load()
    base_sig = build_sig_weighted([(42,1),(63,3),(126,1)])
    base_ser = run_with_sig(base_sig)
    b_full, b_a, b_b = per_half(base_ser)
    print(f"baseline (robust L4):           CAGR {b_full['cagr']*100:.2f}%  "
          f"Sh {b_full['sharpe']:.3f}  A {b_a['sharpe']:.3f}  B {b_b['sharpe']:.3f}")
    print()
    print(f"{'variant':<38} {'CAGR':>7} {'Sh':>6} {'A':>6} {'B':>6} {'verdict':>12}")

    for name, fn, arg in VARIANTS:
        if fn is build_sig_weighted:
            sig = fn(arg)
        elif fn is build_sig_geomean:
            sig = fn(arg)
        elif fn is build_sig_long_skip:
            sig = fn(arg[0], arg[1])
        ser = run_with_sig(sig)
        full, a, bh = per_half(ser)
        dSh = full['sharpe'] - b_full['sharpe']
        dA = a['sharpe'] - b_a['sharpe']
        dB = bh['sharpe'] - b_b['sharpe']
        # OOS rule: must not regress in either half by >0.03 AND must lift total by >0.02 after 50% haircut
        passes_oos = dA >= -0.03 and dB >= -0.03
        is_better = dSh >= 0.04  # pre-haircut gate; after 50% haircut = +0.02
        if passes_oos and is_better:
            verdict = "PASS"
        elif passes_oos:
            verdict = "neutral"
        else:
            verdict = "FAIL"
        print(f"{name:<38} {full['cagr']*100:>6.2f}% {full['sharpe']:>6.3f} "
              f"{a['sharpe']:>6.3f} {bh['sharpe']:>6.3f} {verdict:>12}")


if __name__ == "__main__":
    main()
