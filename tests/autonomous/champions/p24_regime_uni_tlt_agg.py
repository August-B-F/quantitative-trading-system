"""CHAMPION as of 2026-04-13 20:45.

Full stack of modifications:
  1. Drop VGT and XLK (6-ETF dropoverlap universe for stable regime).
  2. Regime-conditional universe expansion: in transition regime (classifier proba
     >= 0.40 AND predicted != current), expand to 8 ETFs by adding TLT and AGG.
  3. 62/38 top-1/top-k split.
  4. Classifier confidence gate at 0.40.
  5. Stable-regime momentum signal: weighted rank aggregation across 42d, 63d, 126d
     with weights (1, 3, 1).

Full walk-forward stats:
    CAGR   = 27.28%  (baseline 23.61%, +3.67pp)
    Sharpe =  1.72   (baseline 1.50,  +0.22)
    MaxDD  = -12.66% (baseline -12.94%)

Post-50%-haircut: CAGR ~25.45% — still +1.84pp over baseline.

Sub-period robustness: every period wins on both CAGR and Sharpe. 2010-2015
MaxDD improved from baseline -10.11% to -8.25%.
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
TRANSITION_UNI = STABLE_UNI + ["TLT", "AGG"]
GATE_THRESHOLD = 0.40
RANK_WEIGHTS = [(42, 1), (63, 3), (126, 1)]
SPLIT = (0.62, 0.38)


def build_rank_signal():
    _load()
    b = _STATE["bundle"]
    cm = None; ranks = None; total = sum(w for _, w in RANK_WEIGHTS)
    for lb, w in RANK_WEIGHTS:
        r = b.returns[lb]
        if cm is None: cm = list(r.columns)
        else: r = r[cm]
        ranked = r.rank(axis=1, method="average") * w
        ranks = ranked if ranks is None else ranks + ranked
    return ranks / total


def build_gated_pred():
    with open(HERE.parent / "cache" / "pred_proba.pkl", "rb") as f:
        pred_reg, maxp = pickle.load(f)
    _load()
    cur = np.asarray(_cr(_STATE["bundle"].df).index)
    out = pred_reg.copy()
    want = (pred_reg != cur) & (pred_reg >= 0)
    low = np.nan_to_num(maxp, nan=0.0) < GATE_THRESHOLD
    out[want & low] = cur[want & low]
    return out


def run_champion():
    _load()
    b = _STATE["bundle"]
    sig = build_rank_signal()
    gated = build_gated_pred()
    cur = np.asarray(_cr(b.df).index)

    def make_engine(uni):
        cfg = copy.deepcopy(_STATE["cfg"])
        cfg.update({"universe": uni, "top1_weight": SPLIT[0], "top3_weight": SPLIT[1]})
        shim = types.SimpleNamespace(**{k: getattr(b, k) for k in (
            "df", "dates", "atr21", "fwd21", "spy_dist_sma200", "is_fomc_day")})
        nr = dict(b.returns); nr[cfg["lookback_stable"]] = sig; shim.returns = nr
        return PortfolioEngine(shim, gated, cfg)

    eng_s = make_engine(STABLE_UNI)
    eng_t = make_engine(TRANSITION_UNI)
    td = _STATE["test_dates"]
    td_positions = pd.Series(eng_s.dates.get_indexer(td), index=td)
    month_last = td_positions.groupby(td.to_period("M")).tail(1)
    fomc_idx = np.where(b.is_fomc_day)[0]
    event_mask = fomc_window_mask(eng_s.n_days, fomc_idx, pre_days=0, post_days=2)

    def ret_at(eng, i):
        t1, tk = eng.pick_at(i)
        r1 = eng.fwd_arr[i, t1] if eng.spy_dist[i] > eng.sma_buffer else eng.cash_fwd[i]
        sel = eng.atr_arr[i, tk]
        inv = 1.0 / np.where(sel > 0, sel, np.nan)
        if np.isnan(inv).all():
            rk = np.nanmean(eng.fwd_arr[i, tk])
        else:
            w = inv / np.nansum(inv)
            rk = np.nansum(eng.fwd_arr[i, tk] * w)
        return eng.top1_w * r1 + eng.topk_w * rk

    rets = []
    for rd, pos in month_last.items():
        i, _ = resolve_rebalance_index(int(pos), 3, event_mask, eng_s.n_days)
        is_stable = (gated[i] == cur[i]) or (gated[i] < 0)
        rets.append(ret_at(eng_s if is_stable else eng_t, i))
    return compute_stats(np.array(rets))


if __name__ == "__main__":
    s = run_champion()
    print("CHAMPION P24 regime-universe +TLT+AGG")
    print(fmt(s))
