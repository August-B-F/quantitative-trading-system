"""H5: dispersion-conditional sizing.

The panel already contains cross_sectional_dispersion_63d__dispersion. Hypothesis:
when cross-sectional dispersion is high the rank-agg signal has more bite (winners
separate clearly from losers), so top1 concentration makes sense. When dispersion
is low, we're essentially picking among near-ties, so spread out.

Stack on top of Robust. Only applies when L9 isn't boosting.
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


def run(disp_hi=None, disp_lo=None, w_hi=0.65, w_lo=0.40):
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
    disp = b.df["cross_sectional_dispersion_63d__dispersion"].values

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
        for w1 in {W_NORM, W_FULL, w_hi, w_lo}:
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

    rets = []; hist = []; dts = []; disp_vals = []
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
        d = disp[i]
        disp_vals.append(d)

        if boost:
            w1 = W_FULL
        elif disp_hi is not None and not np.isnan(d) and d > disp_hi:
            w1 = w_hi
        elif disp_lo is not None and not np.isnan(d) and d < disp_lo:
            w1 = w_lo
        else:
            w1 = W_NORM

        uni_n = "t" if use_t else "s"
        r = ret_at(engs[(uni_n, w1)], i)
        hist.append(r); rets.append(r); dts.append(rd)
    return pd.Series(rets, index=pd.Index(dts)), np.array(disp_vals)


def per_half(ser):
    sA = ser[ser.index.map(lambda d: d.year < 2018)]
    sB = ser[ser.index.map(lambda d: d.year >= 2018)]
    a = compute_stats(sA.values); b_ = compute_stats(sB.values)
    full = compute_stats(ser.values)
    return full, a, b_


def main():
    base, dvals = run()
    f0, a0, b0 = per_half(base)
    print(f"Robust baseline:   CAGR {f0['cagr']*100:.2f}%  Sh {f0['sharpe']:.3f}  A {a0['sharpe']:.3f}  B {b0['sharpe']:.3f}")
    print(f"Dispersion (on rebalance dates):  p25 {np.nanpercentile(dvals,25):.4f}  "
          f"p50 {np.nanmedian(dvals):.4f}  p75 {np.nanpercentile(dvals,75):.4f}")
    print()
    # Use percentile thresholds
    p60 = np.nanpercentile(dvals, 60)
    p70 = np.nanpercentile(dvals, 70)
    p80 = np.nanpercentile(dvals, 80)
    p20 = np.nanpercentile(dvals, 20)
    p30 = np.nanpercentile(dvals, 30)
    p40 = np.nanpercentile(dvals, 40)

    print(f"{'hi_q':>5} {'lo_q':>5} {'w_hi':>5} {'w_lo':>5}  {'CAGR':>7} {'Sh':>6} {'A':>6} {'B':>6}")
    combos = [
        ("p60",p60,"p30",p30), ("p70",p70,"p30",p30), ("p80",p80,"p20",p20),
        ("p60",p60,"p40",p40), ("p70",p70,None,None), (None,None,"p30",p30),
        ("p70",p70,"p40",p40), ("p80",p80,"p40",p40),
    ]
    for hi_n, hi_v, lo_n, lo_v in combos:
        for wh in [0.60, 0.65]:
            for wl in [0.40, 0.45]:
                ser, _ = run(hi_v, lo_v, wh, wl)
                f, a, b_ = per_half(ser)
                dA = a['sharpe'] - a0['sharpe']; dB = b_['sharpe'] - b0['sharpe']
                tag = ""
                if dA >= -0.02 and dB >= -0.02 and f['sharpe'] - f0['sharpe'] >= 0.04:
                    tag = "  PASS"
                elif dA >= -0.02 and dB >= -0.02 and f['sharpe'] - f0['sharpe'] >= 0:
                    tag = "  +"
                hi_s = hi_n if hi_n else "--"
                lo_s = lo_n if lo_n else "--"
                print(f"{hi_s:>5} {lo_s:>5} {wh:>5} {wl:>5}  {f['cagr']*100:>6.2f}% "
                      f"{f['sharpe']:>6.3f} {a['sharpe']:>6.3f} {b_['sharpe']:>6.3f}{tag}")


if __name__ == "__main__":
    main()
