"""H4: rank-gap conviction sizing on top of Robust.

When the top1 ETF outranks top2 by a large margin, we're more certain. Test:
  gap_norm = (rank1 - rank2) / n_names   # in [0, 1]
  if FULL boost fires -> ignore (L9 takes precedence)
  elif gap_norm > hi -> top1 = w_hi
  elif gap_norm < lo -> top1 = w_lo
  else               -> top1 = W_NORM (0.50)

Require: both halves improve Sharpe >= 0.02 vs Robust baseline.
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


def mk_engine(uni, w1, gated, sig):
    b = _STATE["bundle"]
    cfg = copy.deepcopy(_STATE["cfg"])
    cfg.update({"universe": uni, "top1_weight": w1, "top3_weight": 1 - w1,
                "fomc_window_pre": FOMC_PRE, "fomc_window_after": FOMC_POST,
                "fomc_defer_days": FOMC_DEFER})
    shim = types.SimpleNamespace(**{k: getattr(b, k) for k in (
        "df", "dates", "atr21", "fwd21", "spy_dist_sma200", "is_fomc_day")})
    nr = dict(b.returns); nr[cfg["lookback_stable"]] = sig; shim.returns = nr
    return PortfolioEngine(shim, gated, cfg)


def run(hi_thr=None, lo_thr=None, w_hi=0.65, w_lo=0.40):
    """If hi_thr/lo_thr are None, run pure Robust baseline."""
    _load(); b = _STATE["bundle"]
    with open(HERE.parent / "cache" / "pred_proba_p46.pkl", "rb") as f:
        pr, mp = pickle.load(f)
    cur = np.asarray(_cr(b.df).index)
    gated = pr.copy()
    want = (pr != cur) & (pr >= 0)
    low = np.nan_to_num(mp, nan=0.0) < SIG_GATE
    gated[want & low] = cur[want & low]
    sig = build_sig()
    spy_63 = b.returns[SPY_FAST_LB]["SPY"].values

    weights_needed = {W_NORM, W_FULL, w_hi, w_lo}
    engs = {}
    for uni_n, uni in [("s", STABLE), ("t", TRANS)]:
        for w1 in weights_needed:
            engs[(uni_n, w1)] = mk_engine(uni, w1, gated, sig)

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

    def gap_at(eng, i):
        """Compute normalized rank gap between top1 and top2 within the active universe."""
        uni_vals = sig.iloc[i].reindex(eng.universe).values
        if np.isnan(uni_vals).all():
            return 0.0
        n = len(eng.universe)
        # rank the universe subset
        r = pd.Series(uni_vals).rank(method="average").values
        top1 = np.nanargmax(r)
        r_top1 = r[top1]
        r_rest = np.delete(r, top1)
        r_top2 = np.nanmax(r_rest) if len(r_rest) else r_top1
        return float((r_top1 - r_top2) / n)

    rets = []; hist = []; dts = []; gaps = []
    for rd, p in month_last.items():
        i, _ = resolve_rebalance_index(int(p), FOMC_DEFER, evm, eng0.n_days)
        use_t = (pr[i] != cur[i]) and (pr[i] >= 0) and \
                (not np.isnan(mp[i])) and (mp[i] >= UNI_TIER)
        if len(hist) >= BOOST_LB_M:
            c9 = np.prod([1 + h for h in hist[-BOOST_LB_M:]]) - 1
        else:
            c9 = 0.05
        sv = spy_63[i] if not np.isnan(spy_63[i]) else -1.0
        boost = (c9 > BOOST_THR) or (sv > SPY_FAST_THR)

        uni_n = "t" if use_t else "s"
        ref_eng = engs[(uni_n, W_NORM)]
        g = gap_at(ref_eng, i)

        if boost:
            w1 = W_FULL
        elif hi_thr is not None and g > hi_thr:
            w1 = w_hi
        elif lo_thr is not None and g < lo_thr:
            w1 = w_lo
        else:
            w1 = W_NORM

        r = ret_at(engs[(uni_n, w1)], i)
        hist.append(r); rets.append(r); dts.append(rd); gaps.append(g)
    ser = pd.Series(rets, index=pd.Index(dts))
    return ser, gaps


def per_half(ser):
    sA = ser[ser.index.map(lambda d: d.year < 2018)]
    sB = ser[ser.index.map(lambda d: d.year >= 2018)]
    a = compute_stats(sA.values); b_ = compute_stats(sB.values)
    full = compute_stats(ser.values)
    return full, a, b_


def main():
    base_ser, base_gaps = run(None, None)
    f0, a0, b0 = per_half(base_ser)
    print(f"Robust baseline:                CAGR {f0['cagr']*100:.2f}%  Sh {f0['sharpe']:.3f}  A {a0['sharpe']:.3f}  B {b0['sharpe']:.3f}")
    g_arr = np.array(base_gaps)
    print(f"Gap stats:  mean {g_arr.mean():.3f}  median {np.median(g_arr):.3f}  p25 {np.percentile(g_arr,25):.3f}  p75 {np.percentile(g_arr,75):.3f}")
    print()
    print(f"{'hi_thr':>7} {'lo_thr':>7} {'w_hi':>5} {'w_lo':>5}  {'CAGR':>7} {'Sh':>6} {'A':>6} {'B':>6} {'verdict':>12}")

    grid = []
    for hi in [0.10, 0.15, 0.20, 0.25, 0.30, None]:
        for lo in [0.05, 0.10, None]:
            for w_hi_v in [0.60, 0.65, 0.70]:
                for w_lo_v in [0.35, 0.40, 0.45]:
                    if hi is None and lo is None:
                        continue
                    grid.append((hi, lo, w_hi_v, w_lo_v))

    results = []
    for hi, lo, w_hi_v, w_lo_v in grid:
        ser, _ = run(hi, lo, w_hi_v, w_lo_v)
        f, a, b_ = per_half(ser)
        dA = a['sharpe'] - a0['sharpe']
        dB = b_['sharpe'] - b0['sharpe']
        dSh = f['sharpe'] - f0['sharpe']
        # haircut: require pre-haircut dSh >= 0.04
        passes_oos = dA >= -0.02 and dB >= -0.02
        is_better = dSh >= 0.04 and passes_oos
        verdict = "PASS" if is_better else ("neutral" if passes_oos else "FAIL")
        results.append((hi, lo, w_hi_v, w_lo_v, f, a, b_, verdict, dSh))
        if verdict != "FAIL":
            hi_s = f"{hi:.2f}" if hi is not None else "--"
            lo_s = f"{lo:.2f}" if lo is not None else "--"
            print(f"{hi_s:>7} {lo_s:>7} {w_hi_v:>5} {w_lo_v:>5}  {f['cagr']*100:>6.2f}% "
                  f"{f['sharpe']:>6.3f} {a['sharpe']:>6.3f} {b_['sharpe']:>6.3f} {verdict:>12}")

    # Best pass
    passes = [r for r in results if r[7] == "PASS"]
    if passes:
        passes.sort(key=lambda x: -x[8])
        print()
        print("BEST PASS:")
        hi, lo, wh, wl, f, a, b_, v, dSh = passes[0]
        print(f"  hi={hi} lo={lo} w_hi={wh} w_lo={wl}  dSharpe=+{dSh:.3f}")
    else:
        print()
        print("No PASS variant.")


if __name__ == "__main__":
    main()
