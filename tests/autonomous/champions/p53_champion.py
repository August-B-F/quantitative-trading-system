"""CHAMPION as of 2026-04-13 18:55 local.

Extends P52 with a 4-state Kelly: adds an intermediate "warmup boost" tier
between Normal and Full Boost. The warmup state captures partial-confirmation
periods where the strategy is doing well but not yet at full-boost levels.

Four-state Kelly:

   trigger                                                    | top1 weight
   -----------------------------------------------------------|------------
   trail3m return < -2%  (DD mode)                            |    0.45
   trail9m > +30% OR SPY 63d > +12%  (FULL boost)             |    0.75
   trail6m > +25% OR SPY 21d > +10%  (WARM boost — partial)   |    0.70
   normal (none of the above)                                 |    0.62

Marginal +0.08 CAGR over P52 with same Sharpe. 2010-2015 sub-period Sharpe
hits 2.00. Bootstrap t improves from 3.197 to 3.241.

Note: 4-state has 4 thresholds vs P52's 3 — slightly more parameter risk.
P52 is the conservative fallback if this pattern doesn't hold forward.

Full walk-forward stats:
    CAGR   = 30.20%   (baseline 23.61%, +6.59pp)
    Sharpe =  1.88    (baseline 1.50,  +0.38)
    MaxDD  = -12.66%  (baseline -12.94%)

Sub-period:
  2010-2015: 24.70/2.00/-5.75 vs baseline 13.74/1.18/-10.11
  2016-2020: 25.07/1.47/-12.66 vs baseline 20.54/1.24/-12.94
  2021-2026: 40.60/2.21/-5.91 vs baseline 38.37/2.06/-10.22

Robustness:
  - Paired bootstrap t = 3.241
  - P(edge > 0) = 99.99%
  - 95% CI annualized = [+2.22, +8.87] pp/yr

Cached: `cache/pred_proba_p46.pkl` (classifier unchanged from P46/P47).
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

W_DD = 0.45
W_NORM = 0.62
W_WARM = 0.70
W_FULL = 0.75

DD_LB_M = 3
DD_THR = -0.02
SELF_BOOST_LB_M = 9
SELF_BOOST_THR = 0.30
SPY_BOOST_THR = 0.12       # SPY 63d
SELF_WARM_LB_M = 6
SELF_WARM_THR = 0.25
SPY_WARM_THR = 0.10        # SPY 21d

FOMC_PRE = 0
FOMC_POST = 1
FOMC_DEFER_DAYS = 4


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
    spy_63 = b.returns[63]["SPY"].values
    spy_21 = b.returns[21]["SPY"].values

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
        for w1 in (W_DD, W_NORM, W_WARM, W_FULL):
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
        use_trans = (pr_raw[i] != cur[i]) and (pr_raw[i] >= 0) and \
                    (not np.isnan(mp_raw[i])) and (mp_raw[i] >= UNI_TIER)
        # 4-state Kelly
        if len(history) >= DD_LB_M:
            cum_dd = np.prod([1 + h for h in history[-DD_LB_M:]]) - 1
        else:
            cum_dd = 0.05
        if len(history) >= SELF_WARM_LB_M:
            cum_warm = np.prod([1 + h for h in history[-SELF_WARM_LB_M:]]) - 1
        else:
            cum_warm = 0.05
        if len(history) >= SELF_BOOST_LB_M:
            cum_full = np.prod([1 + h for h in history[-SELF_BOOST_LB_M:]]) - 1
        else:
            cum_full = 0.05
        spy_v63 = spy_63[i] if not np.isnan(spy_63[i]) else 0.0
        spy_v21 = spy_21[i] if not np.isnan(spy_21[i]) else 0.0

        if cum_dd < DD_THR:
            w1 = W_DD
        elif (cum_full > SELF_BOOST_THR) or (spy_v63 > SPY_BOOST_THR):
            w1 = W_FULL
        elif (cum_warm > SELF_WARM_THR) or (spy_v21 > SPY_WARM_THR):
            w1 = W_WARM
        else:
            w1 = W_NORM
        uni_n = "t" if use_trans else "s"
        r = ret_at(engines[(uni_n, w1)], i)
        history.append(r)
        rets.append(r)
    return compute_stats(np.array(rets))


if __name__ == "__main__":
    s = run_champion()
    print("CHAMPION P53 (P52 + 4-state warmup boost)")
    print(fmt(s))
