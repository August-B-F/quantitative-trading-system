"""Turnover and cost-sensitivity validation for the ROBUST CHAMPION.

Reconstructs monthly portfolio weights following the exact Robust stack logic
(L1,L3,L4,L5,L6,L9) and then:
  1. Computes average one-way turnover per rebalance.
  2. Re-simulates net returns with per-side execution costs: 0, 2, 5, 10, 20, 40 bps.
  3. Reports CAGR / Sharpe / MaxDD vs baseline canonical.

Run from tests/autonomous/:
    py -3 purge/_validate_turnover.py
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
SIG_GATE = 0.40
UNI_TIER = 0.50
RANK_W = [(42, 1), (63, 3), (126, 1)]
W_NORM = 0.50
W_FULL = 0.82
BOOST_LB_M = 9
BOOST_THR = 0.30
SPY_FAST_LB = 63
SPY_FAST_THR = 0.12
FOMC_PRE, FOMC_POST, FOMC_DEFER = 0, 2, 3


def _signal():
    b = _STATE["bundle"]
    cm = None; ranks = None; total = sum(w for _, w in RANK_W)
    for lb, w in RANK_W:
        r = b.returns[lb]
        if cm is None: cm = list(r.columns)
        else: r = r[cm]
        rk = r.rank(axis=1, method="average") * w
        ranks = rk if ranks is None else ranks + rk
    return ranks / total


def _mk_engine(uni, w1, gated, sig):
    b = _STATE["bundle"]
    cfg = copy.deepcopy(_STATE["cfg"])
    cfg.update({"universe": uni, "top1_weight": w1, "top3_weight": 1.0 - w1,
                "fomc_window_pre": FOMC_PRE, "fomc_window_after": FOMC_POST,
                "fomc_defer_days": FOMC_DEFER})
    shim = types.SimpleNamespace(**{k: getattr(b, k) for k in (
        "df", "dates", "atr21", "fwd21", "spy_dist_sma200", "is_fomc_day")})
    nr = dict(b.returns); nr[cfg["lookback_stable"]] = sig; shim.returns = nr
    return PortfolioEngine(shim, gated, cfg)


def run_robust_weights():
    """Run the Robust stack and capture monthly weights + gross returns per rebalance."""
    _load(); b = _STATE["bundle"]
    with open(HERE.parent / "cache" / "pred_proba_p46.pkl", "rb") as f:
        pr, mp = pickle.load(f)
    cur = np.asarray(_cr(b.df).index)
    gated = pr.copy()
    want = (pr != cur) & (pr >= 0)
    low = np.nan_to_num(mp, nan=0.0) < SIG_GATE
    gated[want & low] = cur[want & low]
    sig = _signal()
    spy_63 = b.returns[SPY_FAST_LB]["SPY"].values

    engines = {}
    for uni_n, uni in [("s", STABLE), ("t", TRANS)]:
        for w1 in (W_NORM, W_FULL):
            engines[(uni_n, w1)] = _mk_engine(uni, w1, gated, sig)

    td = _STATE["test_dates"]
    eng0 = engines[("s", W_NORM)]
    td_positions = pd.Series(eng0.dates.get_indexer(td), index=td)
    month_last = td_positions.groupby(td.to_period("M")).tail(1)
    fomc_idx = np.where(b.is_fomc_day)[0]
    event_mask = fomc_window_mask(eng0.n_days, fomc_idx, pre_days=FOMC_PRE, post_days=FOMC_POST)

    all_tickers = sorted(set(STABLE) | set(TRANS) | {"SHY"})
    rows = []; rets_gross = []; dates = []
    history = []
    for rd, pos in month_last.items():
        i, _ = resolve_rebalance_index(int(pos), FOMC_DEFER, event_mask, eng0.n_days)

        use_t = (pr[i] != cur[i]) and (pr[i] >= 0) and \
                (not np.isnan(mp[i])) and (mp[i] >= UNI_TIER)

        if len(history) >= BOOST_LB_M:
            cum9 = np.prod([1 + h for h in history[-BOOST_LB_M:]]) - 1
        else:
            cum9 = 0.05
        spy_v = spy_63[i] if not np.isnan(spy_63[i]) else -1.0
        boost = (cum9 > BOOST_THR) or (spy_v > SPY_FAST_THR)
        w1 = W_FULL if boost else W_NORM
        uni_n = "t" if use_t else "s"
        eng = engines[(uni_n, w1)]

        # Weight vector
        t1, tk = eng.pick_at(i)
        w_row = {t: 0.0 for t in all_tickers}
        if eng.spy_dist[i] > eng.sma_buffer:
            w_row[eng.universe[t1]] += eng.top1_w
        else:
            w_row[eng.cash] += eng.top1_w

        # top-k inverse-ATR
        sel_atr = eng.atr_arr[i, tk]
        inv = 1.0 / np.where(sel_atr > 0, sel_atr, np.nan)
        if np.isnan(inv).all():
            wk = np.ones_like(inv) / len(inv)
        else:
            wk = inv / np.nansum(inv)
        for j, kk in enumerate(tk):
            if not np.isnan(wk[j]):
                w_row[eng.universe[kk]] += eng.topk_w * wk[j]

        # Gross fwd return for this month
        r1 = eng.fwd_arr[i, t1] if eng.spy_dist[i] > eng.sma_buffer else eng.cash_fwd[i]
        if np.isnan(inv).all():
            rk = np.nanmean(eng.fwd_arr[i, tk])
        else:
            rk = np.nansum(eng.fwd_arr[i, tk] * wk)
        r_g = eng.top1_w * r1 + eng.topk_w * rk

        rows.append(w_row)
        rets_gross.append(r_g)
        history.append(r_g)
        dates.append(rd)

    W = pd.DataFrame(rows, index=pd.Index(dates), columns=all_tickers).fillna(0.0)
    gross = pd.Series(rets_gross, index=pd.Index(dates))
    return W, gross


def turnover_series(W):
    prev = W.shift(1).fillna(0.0)
    # one-way turnover per rebalance = 0.5 * sum(|new - old|)
    return 0.5 * (W - prev).abs().sum(axis=1)


def net_returns(gross, turnover, cost_bps_per_side):
    cost = (cost_bps_per_side / 10_000.0) * 2.0 * turnover  # round-trip each side
    return gross - cost


def main():
    W, gross = run_robust_weights()
    to = turnover_series(W)
    print(f"Rebalances: {len(W)}")
    print(f"Avg 1-way turnover: {to.mean():.3f}")
    print(f"Median:              {to.median():.3f}")
    print(f"Max:                 {to.max():.3f}")
    print(f"Annualized turnover: {to.mean()*12:.2f}x")
    print()
    print(f"{'cost_bps':>10} {'CAGR':>8} {'Sharpe':>8} {'MaxDD':>8} {'dCAGR_vs_0':>12}")
    base0 = None
    for bps in [0, 1, 2, 5, 10, 20, 40]:
        nr = net_returns(gross, to, bps).values
        s = compute_stats(nr)
        if base0 is None:
            base0 = s["cagr"]
        print(f"{bps:>10}bps {s['cagr']*100:>7.2f}% {s['sharpe']:>8.2f} {s['max_dd']*100:>7.2f}% {(s['cagr']-base0)*100:>11.2f}")

    # Breakdown of turnover drivers
    print()
    print("Top-5 highest turnover months:")
    for d, t in to.sort_values(ascending=False).head(5).items():
        print(f"  {d}: {t:.3f}")


if __name__ == "__main__":
    main()
