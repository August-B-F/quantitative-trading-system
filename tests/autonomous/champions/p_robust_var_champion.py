"""ROBUST-VAR CHAMPION — post-purge Robust stack with inverse-variance basket.

Identical to p_robust_champion.py except the top-k basket weights use
    w_i proportional to 1 / sigma_i^2  (inv-variance)
instead of
    w_i proportional to 1 / sigma_i    (inv-ATR).

Discovered and validated in purge/_explore_batch2.py + _validate_inv_var*.py.

Evidence:
    Full walk-forward:
        inv-ATR (Robust):  CAGR 29.80% / Sharpe 1.925 / MaxDD -12.84%
        inv-VAR (this):    CAGR 30.96% / Sharpe 1.989 / MaxDD -12.79%
        Net of 10bps/side: CAGR 29.49% / Sharpe 1.910 (vs 28.38/1.847)

    Per-half (A 2010-2017 / B 2018-2026):
        inv-ATR: A 2.255 / B 1.802
        inv-VAR: A 2.251 / B 1.890     <- period B improves cleanly, A flat

    Bootstrap vs inv-ATR Robust (paired, 10k iter, trailing-NaN dropped):
        t = +2.024    P(edge>0) = 98.23%
        Mean ann = +0.90 pp/yr    95% CI ann = [+0.06, +1.80] pp/yr

    Parameter neighborhood (exponent p in w = 1/vol^p):
        p=0.00 -> 1.776    p=1.00 -> 1.925    p=2.00 -> 1.989
        p=0.50 -> 1.856    p=1.50 -> 1.958    p=2.50 -> 1.998
        Monotone and smooth across the entire [0, 4] range. No spike.

The layer is promoted over inv-ATR because:
  1. Pre-haircut Sharpe lift >= 0.04 (purge criterion).
  2. Period B (OOS-like) Sharpe improves by +0.088 with Period A flat.
  3. Full-sample bootstrap t=+2.02 (p~0.02) paired vs Robust.
  4. Parameter neighborhood is globally smooth.
  5. Cost-resilient: edge preserved at 10-20 bps/side execution.
  6. Turnover unchanged (5.78x vs 5.62x annualized, within noise).

Intuition: inverse-variance concentrates the non-top1 basket toward low-vol
defenders (GLD, SHY) relative to inverse-ATR, which already under-weights
high-vol names but less aggressively. The extra concentration shaves volatility
from the basket without meaningfully hurting the winners.
"""
from __future__ import annotations
import sys, pickle, copy, types
from pathlib import Path
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from utils.base_test import _load, _STATE, fmt  # noqa: E402
from strategy.portfolio import PortfolioEngine  # noqa: E402
from backtest.engine import compute_stats  # noqa: E402
from strategy.rebalance import fomc_window_mask, resolve_rebalance_index  # noqa: E402
from features.regime_labels import current_regime as _cr  # noqa: E402

STABLE_UNI = ["SOXX", "QQQ", "IGV", "XLE", "GLD", "SHY"]
TRANS_UNI = STABLE_UNI + ["TLT", "AGG", "XLV", "XLF"]
SIG_GATE = 0.40
UNI_TIER = 0.50
RANK_W = [(42, 1), (63, 3), (126, 1)]

W_NORM = 0.50
W_FULL = 0.82
BOOST_LB_M = 9
BOOST_THR = 0.30
SPY_FAST_LB = 63
SPY_FAST_THR = 0.12

FOMC_PRE = 0
FOMC_POST = 2
FOMC_DEFER_DAYS = 3

BASKET_VOL_EXP = 2.0  # <-- the only delta vs p_robust_champion.py (was 1.0)


def build_rank_signal():
    _load(); b = _STATE["bundle"]
    cm = None; ranks = None; total = sum(w for _, w in RANK_W)
    for lb, w in RANK_W:
        r = b.returns[lb]
        if cm is None: cm = list(r.columns)
        else: r = r[cm]
        ranked = r.rank(axis=1, method="average") * w
        ranks = ranked if ranks is None else ranks + ranked
    return ranks / total


def run_champion():
    _load()
    b = _STATE["bundle"]
    with open(HERE.parent / "cache" / "pred_proba_p46.pkl", "rb") as f:
        pr_raw, mp_raw = pickle.load(f)
    cur = np.asarray(_cr(b.df).index)

    gated = pr_raw.copy()
    want = (pr_raw != cur) & (pr_raw >= 0)
    low = np.nan_to_num(mp_raw, nan=0.0) < SIG_GATE
    gated[want & low] = cur[want & low]

    sig = build_rank_signal()
    spy_63 = b.returns[SPY_FAST_LB]["SPY"].values

    def make_engine(uni, w1):
        cfg = copy.deepcopy(_STATE["cfg"])
        cfg.update({
            "universe": uni, "top1_weight": w1, "top3_weight": 1.0 - w1,
            "fomc_window_pre": FOMC_PRE, "fomc_window_after": FOMC_POST,
            "fomc_defer_days": FOMC_DEFER_DAYS,
        })
        shim = types.SimpleNamespace(**{k: getattr(b, k) for k in (
            "df", "dates", "atr21", "fwd21", "spy_dist_sma200", "is_fomc_day")})
        nr = dict(b.returns); nr[cfg["lookback_stable"]] = sig; shim.returns = nr
        return PortfolioEngine(shim, gated, cfg)

    engines = {}
    for uni_n, uni in [("s", STABLE_UNI), ("t", TRANS_UNI)]:
        for w1 in (W_NORM, W_FULL):
            engines[(uni_n, w1)] = make_engine(uni, w1)

    td = _STATE["test_dates"]
    td_positions = pd.Series(engines[("s", W_NORM)].dates.get_indexer(td), index=td)
    month_last = td_positions.groupby(td.to_period("M")).tail(1)
    fomc_idx = np.where(b.is_fomc_day)[0]
    n_days = engines[("s", W_NORM)].n_days
    event_mask = fomc_window_mask(n_days, fomc_idx, pre_days=FOMC_PRE, post_days=FOMC_POST)

    def ret_at(eng, i):
        t1, tk = eng.pick_at(i)
        r1 = eng.fwd_arr[i, t1] if eng.spy_dist[i] > eng.sma_buffer else eng.cash_fwd[i]
        sel = eng.atr_arr[i, tk]
        v = np.where(sel > 0, sel, np.nan)
        w = 1.0 / (v ** BASKET_VOL_EXP)
        if np.isnan(w).all():
            rk = np.nanmean(eng.fwd_arr[i, tk])
        else:
            w = w / np.nansum(w); rk = np.nansum(eng.fwd_arr[i, tk] * w)
        return eng.top1_w * r1 + eng.topk_w * rk

    rets = []; history = []
    for rd, pos in month_last.items():
        i, _ = resolve_rebalance_index(int(pos), FOMC_DEFER_DAYS, event_mask, n_days)

        use_trans = (pr_raw[i] != cur[i]) and (pr_raw[i] >= 0) and \
                    (not np.isnan(mp_raw[i])) and (mp_raw[i] >= UNI_TIER)

        if len(history) >= BOOST_LB_M:
            cum_9 = np.prod([1 + h for h in history[-BOOST_LB_M:]]) - 1
        else:
            cum_9 = 0.05
        spy_v = spy_63[i] if not np.isnan(spy_63[i]) else -1.0
        boost = (cum_9 > BOOST_THR) or (spy_v > SPY_FAST_THR)

        w1 = W_FULL if boost else W_NORM
        uni_n = "t" if use_trans else "s"
        r = ret_at(engines[(uni_n, w1)], i)
        history.append(r)
        rets.append(r)
    arr = np.array(rets)
    arr = arr[~np.isnan(arr)]
    return compute_stats(arr)


if __name__ == "__main__":
    s = run_champion()
    print("ROBUST-VAR CHAMPION (Robust stack + inverse-variance basket, p=2)")
    print(fmt(s))
