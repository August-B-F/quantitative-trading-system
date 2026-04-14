"""ROBUST CHAMPION — post-purge-protocol winner.

Stripped from P59 via the OVERFITTING PURGE PROTOCOL (tests/autonomous/purge/).
P59 had 10 layers; this has 6. The 4 removed layers (L2 62/38 split, L7 FOMC
tightening, L8 DD trigger, L10 warm boost) were shown to be dead weight or
overfit by the 6-test gauntlet:

  Test 1 (LOO ablation)       — removed layers lose <0.02 Sharpe or improve
  Test 2 (forward holdout)    — removed layers help only one era
  Test 3 (random timing)      — removed triggers match random-date percentile
  Test 4 (param neighborhood) — removed layers have fragile parameters
  Test 5 (rebuild)            — removed layers don't add in-stack
  Test 6 (bootstrap)          — Robust vs Full P59: t=-1.22 not significant

Stats (full walk-forward):
    CAGR   = 29.80%   (baseline 23.61%, +6.19pp)
    Sharpe =  1.92    (baseline 1.50,  +0.42; HIGHER than full P59's 1.88)
    MaxDD  = -12.84%  (baseline -12.94%)

Per-half:
    A 2010-2017: 26.33/2.255
    B 2018-2026: 33.07/1.802  ← +0.05 Sharpe vs Full P59 in OOS-like period

Bootstrap vs canonical:
    t = +2.974
    P(edge > 0) = 99.88%
    95% CI annualized = [+1.79, +8.45] pp/yr

The 6 surviving layers:
    L1: drop VGT/XLK from universe (6-ETF stable: SOXX, QQQ, IGV, XLE, GLD, SHY)
    L3: classifier confidence gate at max_proba ≥ 0.40
    L4: rank-aggregation signal 42:1 / 63:3 / 126:1 replacing pure 63d
    L5: regime-conditional transition universe (+TLT, +AGG, +XLV, +XLF when proba ≥ 0.50)
    L6: classifier CORE-50 + 7 credit/yield-curve/copper-gold features
    L9: FULL boost — when trail9m > +30% OR SPY 63d > +12%, set top1 = 0.82

Top1 policy:
    FULL boost condition met  -> top1 = 0.82
    otherwise                  -> top1 = 0.50 (canonical split, NOT 0.62)

Cached: `cache/pred_proba_p46.pkl` (classifier with credit/yc extras).
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

STABLE_UNI = ["SOXX", "QQQ", "IGV", "XLE", "GLD", "SHY"]        # L1
TRANS_UNI = STABLE_UNI + ["TLT", "AGG", "XLV", "XLF"]             # L5
SIG_GATE = 0.40                                                   # L3
UNI_TIER = 0.50                                                   # L5 activation
RANK_W = [(42, 1), (63, 3), (126, 1)]                             # L4

W_NORM = 0.50         # canonical 50/50 (no L2)
W_FULL = 0.82         # L9 boost weight
BOOST_LB_M = 9
BOOST_THR = 0.30
SPY_FAST_LB = 63
SPY_FAST_THR = 0.12

# FOMC canonical (no L7 tightening)
FOMC_PRE = 0
FOMC_POST = 2
FOMC_DEFER_DAYS = 3


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

    # L3 classifier confidence gate
    gated = pr_raw.copy()
    want = (pr_raw != cur) & (pr_raw >= 0)
    low = np.nan_to_num(mp_raw, nan=0.0) < SIG_GATE
    gated[want & low] = cur[want & low]

    sig = build_rank_signal()                                     # L4
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
    for uni_n, uni in [("s", STABLE_UNI), ("t", TRANS_UNI)]:      # L1, L5
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
        inv = 1.0 / np.where(sel > 0, sel, np.nan)
        if np.isnan(inv).all():
            rk = np.nanmean(eng.fwd_arr[i, tk])
        else:
            w = inv / np.nansum(inv); rk = np.nansum(eng.fwd_arr[i, tk] * w)
        return eng.top1_w * r1 + eng.topk_w * rk

    rets = []
    history = []
    for rd, pos in month_last.items():
        i, _ = resolve_rebalance_index(int(pos), FOMC_DEFER_DAYS, event_mask, n_days)

        # L5 — regime-conditional transition universe
        use_trans = (pr_raw[i] != cur[i]) and (pr_raw[i] >= 0) and \
                    (not np.isnan(mp_raw[i])) and (mp_raw[i] >= UNI_TIER)

        # L9 — FULL boost check
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
    return compute_stats(np.array(rets))


if __name__ == "__main__":
    s = run_champion()
    print("ROBUST CHAMPION (L1,L3,L4,L5,L6,L9 — purge-verified)")
    print(fmt(s))
