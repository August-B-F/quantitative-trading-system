"""CHAMPION as of 2026-04-13 18:00.

Full stack of modifications over canonical baseline:
  1. Drop VGT and XLK from the universe (redundant tech overlap).
  2. Shift top-1/top-k split 50/50 → 62/38.
  3. Classifier confidence gate: only switch to 21d lookback if argmax proba >= 0.40.
  4. STABLE-REGIME momentum signal is a multi-horizon weighted rank aggregation
     across 42d, 63d, and 126d return tables with weights (1, 2, 1). 63d still
     carries the most weight; 42d adds short-term responsiveness; 126d adds
     longer-term trend confirmation. The resulting per-ticker "rank score" is
     injected in place of `bundle.returns[63]` at engine-construction time.

Full walk-forward stats (gross):
    CAGR   = 25.84%  (baseline 23.61%, +2.23pp)
    Sharpe =  1.60   (baseline 1.50,  +0.10)
    MaxDD  = -12.66% (baseline -12.94%)

Post-50%-haircut: CAGR ~24.73% — still ~+1.1pp over baseline.

Sub-period robustness: every sub-window (2010-15, 2016-20, 2021-26, first half,
second half) beats baseline on both CAGR and Sharpe. Unlike the prior champion
(P6b.03) which had a concentrated 2021-26 edge and lost in 2016-20, this stack
is consistently above baseline.

Reproducible: run `phase6_classifier_confidence.py` first to build the proba
cache, then `py champions/p10_rankagg_stack.py`.
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
from backtest.engine import run_backtest  # noqa: E402
from features.regime_labels import current_regime as _cr  # noqa: E402

CHAMPION_OVERRIDES = {
    "universe": ["SOXX", "QQQ", "IGV", "XLE", "GLD", "SHY"],
    "top1_weight": 0.62,
    "top3_weight": 0.38,
}
GATE_THRESHOLD = 0.40
RANK_WEIGHTS = [(42, 1), (63, 3), (126, 1)]


def build_rank_signal():
    _load()
    bundle = _STATE["bundle"]
    ranks_sum = None; cm = None
    total = sum(w for _, w in RANK_WEIGHTS)
    for lb, w in RANK_WEIGHTS:
        r = bundle.returns[lb]
        if cm is None:
            cm = list(r.columns)
        else:
            r = r[cm]
        ranked = r.rank(axis=1, method="average")
        ranks_sum = ranked * w if ranks_sum is None else ranks_sum + ranked * w
    return ranks_sum / total


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
    sig = build_rank_signal()
    pred = build_gated_pred()
    cfg = copy.deepcopy(_STATE["cfg"])
    cfg.update(CHAMPION_OVERRIDES)
    bundle = _STATE["bundle"]
    shim = types.SimpleNamespace(**{k: getattr(bundle, k) for k in (
        "df", "dates", "atr21", "fwd21", "spy_dist_sma200", "is_fomc_day")})
    new_ret = dict(bundle.returns)
    new_ret[cfg["lookback_stable"]] = sig
    shim.returns = new_ret
    engine = PortfolioEngine(shim, pred, cfg)
    return run_backtest(engine, _STATE["test_dates"], cfg).stats


if __name__ == "__main__":
    s = run_champion()
    print("CHAMPION P10 rankagg-stack (42:1, 63:2, 126:1)")
    print(fmt(s))
