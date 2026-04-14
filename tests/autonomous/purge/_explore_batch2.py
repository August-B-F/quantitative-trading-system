"""Round-2 hypothesis batch on top of Robust:

H6: Top-k composition     — vary top1/topk split structure
H7: Classifier gate thr   — sweep L3 proba gate wider
H8: SMA defense window    — try 50/100/150/200/250 and none
H9: Weight scheme         — equal vs inverse-ATR vs inverse-vol
H10: Trans universe tier  — sweep L5 classifier proba threshold

For each variant: recompute per-half Sharpe. PASS requires full Sharpe >= 1.96
(baseline 1.925 + 0.035 haircut gate) AND both halves Sharpe >= baseline - 0.02.
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
W_NORM = 0.50; W_FULL = 0.82
BOOST_LB_M = 9; BOOST_THR = 0.30
SPY_FAST_LB = 63; SPY_FAST_THR = 0.12
FOMC_PRE, FOMC_POST, FOMC_DEFER = 0, 2, 3

# baseline defaults (Robust)
DEF_GATE = 0.40
DEF_TIER = 0.50
DEF_TOPK = 2          # top1 + 2 extras = 3-name basket (matches champion)
DEF_SMA  = 200
DEF_WSCHEME = "inv_atr"


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


def run(gate=DEF_GATE, tier=DEF_TIER, topk=DEF_TOPK,
        sma_lb=DEF_SMA, wscheme=DEF_WSCHEME, top1_w=W_NORM, full_w=W_FULL):
    _load(); b = _STATE["bundle"]
    with open(HERE.parent / "cache" / "pred_proba_p46.pkl", "rb") as f:
        pr, mp = pickle.load(f)
    cur = np.asarray(_cr(b.df).index)
    gated = pr.copy()
    want = (pr != cur) & (pr >= 0)
    low = np.nan_to_num(mp, nan=0.0) < gate
    gated[want & low] = cur[want & low]
    sig = build_sig()
    spy_63 = b.returns[SPY_FAST_LB]["SPY"].values

    # SMA defense: recompute spy_dist for the requested lookback
    if sma_lb == 200:
        spy_dist_override = None
    else:
        spy_close_col = None
        # Use SPY cumulative returns to back into an SMA proxy
        # NOTE: panel's canonical spy_dist_sma200 is the 200d version; for
        # other lookbacks we approximate from returns[1] if available, else
        # use returns[21] rolling mean as a proxy.
        if 1 in b.returns:
            spy_r1 = b.returns[1]["SPY"].fillna(0).values
            cum = np.cumprod(1 + spy_r1)
            sma = pd.Series(cum).rolling(sma_lb, min_periods=sma_lb).mean().values
            spy_dist_override = cum / sma - 1
        else:
            spy_dist_override = b.spy_dist_sma200  # fallback

    def mk(uni, w1, topk_override):
        cfg = copy.deepcopy(_STATE["cfg"])
        topk_w = 1 - w1
        cfg.update({"universe": uni, "top1_weight": w1, "top3_weight": topk_w,
                    "top_k": topk_override + 1,  # incl top1
                    "fomc_window_pre": FOMC_PRE, "fomc_window_after": FOMC_POST,
                    "fomc_defer_days": FOMC_DEFER})
        shim = types.SimpleNamespace(**{k: getattr(b, k) for k in (
            "df", "dates", "atr21", "fwd21", "is_fomc_day")})
        if spy_dist_override is not None:
            shim.spy_dist_sma200 = spy_dist_override
        else:
            shim.spy_dist_sma200 = b.spy_dist_sma200
        nr = dict(b.returns); nr[cfg["lookback_stable"]] = sig; shim.returns = nr
        return PortfolioEngine(shim, gated, cfg)

    try:
        engs = {}
        for uni_n, uni in [("s", STABLE), ("t", TRANS)]:
            for w1 in {top1_w, full_w}:
                engs[(uni_n, w1)] = mk(uni, w1, topk)
    except Exception as e:
        return None

    td = _STATE["test_dates"]
    eng0 = engs[("s", top1_w)]
    pos = pd.Series(eng0.dates.get_indexer(td), index=td)
    month_last = pos.groupby(td.to_period("M")).tail(1)
    fomc_idx = np.where(b.is_fomc_day)[0]
    evm = fomc_window_mask(eng0.n_days, fomc_idx, pre_days=FOMC_PRE, post_days=FOMC_POST)

    def ret_at(eng, i):
        t1, tk = eng.pick_at(i)
        r1 = eng.fwd_arr[i, t1] if eng.spy_dist[i] > eng.sma_buffer else eng.cash_fwd[i]
        sel = eng.atr_arr[i, tk]
        if wscheme == "inv_atr":
            inv = 1.0 / np.where(sel > 0, sel, np.nan)
            if np.isnan(inv).all():
                rk = np.nanmean(eng.fwd_arr[i, tk])
            else:
                w = inv / np.nansum(inv); rk = np.nansum(eng.fwd_arr[i, tk] * w)
        elif wscheme == "equal":
            rk = np.nanmean(eng.fwd_arr[i, tk])
        elif wscheme == "inv_var":
            v = np.where(sel > 0, sel, np.nan) ** 2
            inv = 1.0 / v
            if np.isnan(inv).all():
                rk = np.nanmean(eng.fwd_arr[i, tk])
            else:
                w = inv / np.nansum(inv); rk = np.nansum(eng.fwd_arr[i, tk] * w)
        else:
            rk = np.nanmean(eng.fwd_arr[i, tk])
        return eng.top1_w * r1 + eng.topk_w * rk

    rets = []; hist = []; dts = []
    for rd, p in month_last.items():
        i, _ = resolve_rebalance_index(int(p), FOMC_DEFER, evm, eng0.n_days)
        use_t = (pr[i] != cur[i]) and (pr[i] >= 0) and \
                (not np.isnan(mp[i])) and (mp[i] >= tier)
        if len(hist) >= BOOST_LB_M:
            c9 = np.prod([1 + h for h in hist[-BOOST_LB_M:]]) - 1
        else:
            c9 = 0.05
        sv = spy_63[i] if not np.isnan(spy_63[i]) else -1.0
        w1 = full_w if (c9 > BOOST_THR or sv > SPY_FAST_THR) else top1_w
        uni_n = "t" if use_t else "s"
        r = ret_at(engs[(uni_n, w1)], i)
        hist.append(r); rets.append(r); dts.append(rd)
    return pd.Series(rets, index=pd.Index(dts))


def per_half(ser):
    sA = ser[ser.index.map(lambda d: d.year < 2018)]
    sB = ser[ser.index.map(lambda d: d.year >= 2018)]
    a = compute_stats(sA.values); b_ = compute_stats(sB.values)
    f = compute_stats(ser.values)
    return f, a, b_


def show(label, ser, base):
    if ser is None:
        print(f"{label:<40}  FAILED")
        return None
    f, a, b_ = per_half(ser)
    f0, a0, b0 = base
    dSh = f['sharpe'] - f0['sharpe']
    dA = a['sharpe'] - a0['sharpe']
    dB = b_['sharpe'] - b0['sharpe']
    tag = ""
    if dA >= -0.02 and dB >= -0.02 and dSh >= 0.04:
        tag = "  PASS"
    elif dA >= -0.02 and dB >= -0.02 and dSh >= 0:
        tag = "  +"
    print(f"{label:<40}  {f['cagr']*100:>6.2f}%  Sh {f['sharpe']:.3f}  "
          f"A {a['sharpe']:.3f}  B {b_['sharpe']:.3f}  dSh {dSh:+.3f}{tag}")
    return f, a, b_


def main():
    base_ser = run()
    base = per_half(base_ser)
    print(f"baseline (Robust):                        "
          f"{base[0]['cagr']*100:>6.2f}%  Sh {base[0]['sharpe']:.3f}  "
          f"A {base[1]['sharpe']:.3f}  B {base[2]['sharpe']:.3f}")
    print()

    print("=== H6 topk composition ===")
    for k in [1, 2, 3, 4, 5]:
        show(f"topk={k} (top1+{k})", run(topk=k), base)

    print()
    print("=== H7 classifier gate threshold (L3) ===")
    for g in [0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60]:
        show(f"gate={g:.2f}", run(gate=g), base)

    print()
    print("=== H8 SMA defense window ===")
    for sma in [50, 100, 150, 200, 250]:
        show(f"SMA={sma}", run(sma_lb=sma), base)

    print()
    print("=== H9 weight scheme (basket) ===")
    for w in ["inv_atr", "equal", "inv_var"]:
        show(f"weight={w}", run(wscheme=w), base)

    print()
    print("=== H10 trans-universe tier (L5) ===")
    for t in [0.35, 0.40, 0.45, 0.50, 0.55, 0.60, 0.65]:
        show(f"tier={t:.2f}", run(tier=t), base)


if __name__ == "__main__":
    main()
