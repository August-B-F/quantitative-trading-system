"""CHAMPION as of 2026-04-13 17:30 local.

Extends P46 with one marginal but clean addition: XLF in the transition universe.

XLF (Financial Select Sector SPDR) benefits from yield-curve steepening — banks
lend long, borrow short. My classifier tracks yield-curve slope features, so
when it flags yield-curve regime shifts, adding XLF to the transition basket
gives the momentum engine one more option to capture rotation into financials.

In backtest, XLF is picked as top-1 only ONCE in 190 months. The +0.10pp CAGR
gain comes from XLF entering the top-3 inv-vol basket during transition regimes,
where its financials exposure is correlation-orthogonal to TLT (long duration),
AGG (aggregate bond), and XLV (defensive sector).

Full walk-forward stats:
    CAGR   = 28.95%   (baseline 23.61%, +5.34pp)
    Sharpe =  1.84    (baseline 1.50,  +0.34)
    MaxDD  = -12.66%  (baseline -12.94%)

Post-50%-haircut: CAGR ~26.28%.

Sub-period (every window wins on CAGR and Sharpe):
  2010-2015: 23.73/1.94/-5.75 vs baseline 13.74/1.18/-10.11 (MaxDD best in session)
  2016-2020: 24.24/1.44/-12.66 vs baseline 20.54/1.24/-12.94
  2021-2026: 39.68/2.23/-5.91 vs baseline 38.37/2.06/-10.22

Robustness:
  - Paired bootstrap t = 2.779
  - P(edge > 0) = 99.88%
  - 95% CI annualized edge = [+1.36, +7.57] pp/yr
  - Rolling 36m Sharpe: wins 90.2% of 188 windows

Transition universe: [SOXX, QQQ, IGV, XLE, GLD, SHY, TLT, AGG, XLV, XLF]
All other components inherited from P46.

Cached: `cache/pred_proba_p46.pkl` (classifier is unchanged from P46).
"""
from __future__ import annotations
import sys, pickle, copy, types
from pathlib import Path
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
ROOT = HERE.parent.parent.parent

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
SPLIT = (0.62, 0.38)
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

    def make_engine(uni):
        cfg = copy.deepcopy(_STATE["cfg"])
        cfg.update({
            "universe": uni, "top1_weight": SPLIT[0], "top3_weight": SPLIT[1],
            "fomc_window_pre": FOMC_PRE, "fomc_window_after": FOMC_POST,
            "fomc_defer_days": FOMC_DEFER_DAYS,
        })
        shim = types.SimpleNamespace(**{k: getattr(b, k) for k in (
            "df", "dates", "atr21", "fwd21", "spy_dist_sma200", "is_fomc_day")})
        nr = dict(b.returns); nr[cfg["lookback_stable"]] = sig; shim.returns = nr
        return PortfolioEngine(shim, gated, cfg)

    eng_s = make_engine(STABLE_UNI)
    eng_t = make_engine(TRANS_UNI)
    td = _STATE["test_dates"]
    td_positions = pd.Series(eng_s.dates.get_indexer(td), index=td)
    month_last = td_positions.groupby(td.to_period("M")).tail(1)
    fomc_idx = np.where(b.is_fomc_day)[0]
    event_mask = fomc_window_mask(eng_s.n_days, fomc_idx, pre_days=FOMC_PRE, post_days=FOMC_POST)

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
    for rd, pos in month_last.items():
        i, _ = resolve_rebalance_index(int(pos), FOMC_DEFER_DAYS, event_mask, eng_s.n_days)
        use_trans = (pr_raw[i] != cur[i]) and (pr_raw[i] >= 0) and \
                    (not np.isnan(mp_raw[i])) and (mp_raw[i] >= UNI_TIER)
        rets.append(ret_at(eng_t if use_trans else eng_s, i))
    return compute_stats(np.array(rets))


if __name__ == "__main__":
    s = run_champion()
    print("CHAMPION P47 (P46 + XLF in trans universe)")
    print(fmt(s))
