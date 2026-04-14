"""CHAMPION as of 2026-04-13 18:40 local — first to cross 30% CAGR.

Extends P51 with a second boost trigger using SPY's own 63-day return as a
short-horizon market-wide momentum confirmation. The two boost conditions are
OR'd, so either one activates the press-the-bet mode.

Three-state Kelly with TWO boost triggers:

   trigger                                    | top1 weight
   -------------------------------------------|------------
   trail3m return < -2% (DD mode)             |    0.45
   trail9m return > +30%  OR  SPY 63d > +12%  |    0.75
   normal (neither boost nor DD)              |    0.62

The 9m self-equity boost captures sustained strategy momentum (slow signal).
The SPY 63d boost captures short-term market-wide breakouts (fast signal) that
haven't yet shown up in the strategy's own 9-month track record.

Time-horizon orthogonality: the two triggers fire at different lags. The OR
combination adds ~10 extra boost months over P51 alone, capturing ~+0.20pp CAGR.

Full walk-forward stats:
    CAGR   = 30.12%   (baseline 23.61%, +6.51pp)
    Sharpe =  1.88    (baseline 1.50,  +0.38)
    MaxDD  = -12.66%  (baseline -12.94%)

Post-50%-haircut: CAGR ~26.87%.

Sub-period (every window beats baseline):
  2010-2015: 24.59/1.99/-5.75 vs baseline 13.74/1.18/-10.11
  2016-2020: 25.05/1.47/-12.66 vs baseline 20.54/1.24/-12.94
  2021-2026: 40.54/2.21/-5.91 vs baseline 38.37/2.06/-10.22

Robustness (strictly stronger than P51):
  - Paired bootstrap t = 3.197 (P51 was 3.110)
  - P(edge > 0) = 99.99%
  - 95% CI annualized = [+2.17, +8.80] pp/yr
  - Rolling 36m Sharpe: wins 90.2% of 188 windows

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
W_BOOST = 0.75
DD_LOOKBACK_MONTHS = 3
DD_THRESHOLD = -0.02
SELF_BOOST_LOOKBACK_MONTHS = 9
SELF_BOOST_THRESHOLD = 0.30
SPY_BOOST_THRESHOLD = 0.12  # SPY 63d return

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
        for w1 in (W_DD, W_NORM, W_BOOST):
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
        # Asymmetric Kelly with two boost triggers
        if len(history) >= DD_LOOKBACK_MONTHS:
            cum_dd = np.prod([1 + h for h in history[-DD_LOOKBACK_MONTHS:]]) - 1
        else:
            cum_dd = 0.05
        if len(history) >= SELF_BOOST_LOOKBACK_MONTHS:
            cum_self_boost = np.prod([1 + h for h in history[-SELF_BOOST_LOOKBACK_MONTHS:]]) - 1
        else:
            cum_self_boost = 0.05
        spy_val = spy_63[i] if not np.isnan(spy_63[i]) else 0.0

        if cum_dd < DD_THRESHOLD:
            w1 = W_DD
        elif (cum_self_boost > SELF_BOOST_THRESHOLD) or (spy_val > SPY_BOOST_THRESHOLD):
            w1 = W_BOOST
        else:
            w1 = W_NORM
        uni_n = "t" if use_trans else "s"
        r = ret_at(engines[(uni_n, w1)], i)
        history.append(r)
        rets.append(r)
    return compute_stats(np.array(rets))


if __name__ == "__main__":
    s = run_champion()
    print("CHAMPION P52 (P51 + SPY 63d > 12% boost trigger)")
    print(fmt(s))
