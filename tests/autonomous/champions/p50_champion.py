"""CHAMPION as of 2026-04-13 18:10 local.

Extends P49 with a symmetric Kelly response — adds a HOT-STREAK boost mode to
complement the DD defensive mode. Three-state position sizing keyed off the
strategy's own trailing 6-month return:

   trail6m return      | top1 weight | top3 weight | months active
   --------------------|-------------|-------------|--------------
   < 0%   (DD)         |    0.45     |    0.55     |    ~9
   0% to 25% (normal)  |    0.62     |    0.38     |   ~156
   > 25%  (hot streak) |    0.75     |    0.25     |    ~25

This is the full Kelly-like response: when the strategy is winning, press the
top-1 bet harder; when losing, diversify into top-3. The asymmetry of the
thresholds (0% vs 25%) reflects that drawdowns warrant immediate response while
hot streaks need confirmation (sustained 25%+ rolling return).

Mechanism intuition: hot-streak periods are when the rank-1 momentum signal is
working most strongly — concentration captures more of that. Drawdown periods
are when the rank-1 pick is more likely to be wrong (signal in flux) — diversification
reduces single-leader risk.

Full walk-forward stats:
    CAGR   = 29.58%   (baseline 23.61%, +5.97pp)
    Sharpe =  1.86    (baseline 1.50,  +0.36)
    MaxDD  = -12.66%  (baseline -12.94%)

Post-50%-haircut: CAGR ~26.59%.

Sub-period (every window beats baseline on both CAGR and Sharpe):
  2010-2015: 23.76/1.94/-5.75 vs baseline 13.74/1.18/-10.11
  2016-2020: 24.57/1.46/-12.66 vs baseline 20.54/1.24/-12.94
  2021-2026: 40.56/2.21/-5.91 vs baseline 38.37/2.06/-10.22

Robustness (strictly stronger than P49):
  - Paired bootstrap t = 3.008 (P49 was 2.915)
  - P(edge > 0) = 99.96%
  - 95% CI annualized = [+1.80, +8.26] pp/yr (P49 lower bound was +1.58)
  - Rolling 36m Sharpe: wins 90.2% of 188 windows

Note: this is a STATEFUL backtest — the rule depends on the strategy's own
prior monthly returns. In production, maintain a rolling 6-month return buffer
and check before each rebalance which sizing mode to apply.

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

W_DD = 0.45     # top1 weight when in DD
W_NORM = 0.62   # top1 weight in normal mode
W_BOOST = 0.75  # top1 weight in hot streak
DD_THRESHOLD = 0.0      # trail6m return < 0% → DD mode
BOOST_THRESHOLD = 0.25  # trail6m return > 25% → hot streak mode
LOOKBACK_MONTHS = 6

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
    history = []  # rolling history of own monthly returns
    for rd, pos in month_last.items():
        i, _ = resolve_rebalance_index(int(pos), FOMC_DEFER_DAYS, event_mask, n_days)
        use_trans = (pr_raw[i] != cur[i]) and (pr_raw[i] >= 0) and \
                    (not np.isnan(mp_raw[i])) and (mp_raw[i] >= UNI_TIER)
        if len(history) >= LOOKBACK_MONTHS:
            recent_cum = np.prod([1 + h for h in history[-LOOKBACK_MONTHS:]]) - 1
        else:
            recent_cum = 0.05  # neutral default during warm-up
        # 3-state Kelly response
        if recent_cum < DD_THRESHOLD:
            w1 = W_DD
        elif recent_cum > BOOST_THRESHOLD:
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
    print("CHAMPION P50 (P47 + 3-state Kelly self-equity sizing)")
    print(fmt(s))
