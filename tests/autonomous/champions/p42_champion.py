"""CHAMPION as of 2026-04-13 16:30 local.

Extends P27 (tier-proba50 regime-uni) with a tightened FOMC window:
   pre=0, post=1 (fire only on FOMC day itself), defer 4 trading days.

The canonical M26_post_3d uses pre=0, post=2, defer=3. The tightened (1,4)
variant sub-period-dominates in 2016-2020 (+1.50pp CAGR vs prior) while giving
up a small amount in 2021-2026 (-0.99pp). Net +0.26pp full-period CAGR,
Sharpe essentially flat (-0.01).

Full walk-forward stats:
    CAGR   = 28.03%   (baseline 23.61%, +4.42pp)
    Sharpe =  1.74    (baseline 1.50,  +0.24)
    MaxDD  = -12.66%  (baseline -12.94%)

Post-50%-haircut: CAGR ~25.82% — still +2.21pp over baseline.

Full stack:
  1. Universe (stable) = [SOXX, QQQ, IGV, XLE, GLD, SHY]  (drop VGT, XLK)
  2. Universe (transition, gated by classifier proba>=0.50) adds TLT, AGG, XLV
  3. Classifier signal-level gate: switch to 21d only if argmax proba >= 0.40
  4. Stable momentum signal: rank-aggregation across 42d/63d/126d weights (1,3,1)
  5. Split: 62/38 top-1/top-k
  6. FOMC window: pre=0, post=1, defer=4
  7. SMA200 gate buffer: -4% (unchanged)
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
TRANS_UNI = STABLE_UNI + ["TLT", "AGG", "XLV"]
SIG_GATE = 0.40
UNI_TIER = 0.50
RANK_W = [(42, 1), (63, 3), (126, 1)]
SPLIT = (0.62, 0.38)
FOMC_PRE = 0
FOMC_POST = 1
FOMC_DEFER_DAYS = 4


def build_rank_signal():
    _load()
    b = _STATE["bundle"]
    cm = None; ranks = None; total = sum(w for _, w in RANK_W)
    for lb, w in RANK_W:
        r = b.returns[lb]
        if cm is None: cm = list(r.columns)
        else: r = r[cm]
        ranked = r.rank(axis=1, method="average") * w
        ranks = ranked if ranks is None else ranks + ranked
    return ranks / total


def build_gated_pred():
    with open(HERE.parent / "cache" / "pred_proba.pkl", "rb") as f:
        pr_raw, mp_raw = pickle.load(f)
    _load()
    cur = np.asarray(_cr(_STATE["bundle"].df).index)
    out = pr_raw.copy()
    want = (pr_raw != cur) & (pr_raw >= 0)
    low = np.nan_to_num(mp_raw, nan=0.0) < SIG_GATE
    out[want & low] = cur[want & low]
    return out, pr_raw, mp_raw, cur


def run_champion():
    _load()
    b = _STATE["bundle"]
    sig = build_rank_signal()
    gated, pr_raw, mp_raw, cur = build_gated_pred()

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
    print("CHAMPION P42 (P27 + FOMC 0/1/4)")
    print(fmt(s))
