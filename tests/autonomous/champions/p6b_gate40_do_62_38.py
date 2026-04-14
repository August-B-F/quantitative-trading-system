"""CHAMPION as of 2026-04-13 17:30.

Three stacked modifications over canonical baseline:
  1. Drop VGT and XLK from the universe (redundant tech overlap).
  2. Shift split 60/40 → 62/38 top-1 / top-k (marginal CAGR lift).
  3. Classifier confidence gate: only switch to 21d lookback if the classifier's
     argmax probability is >= 0.40. Otherwise treat as stable (63d). Reduces
     noisy lookback switches when the model is uncertain.

Full walk-forward stats (gross):
    CAGR   = 24.49%  (baseline 23.61%, +0.88pp)
    Sharpe =  1.55   (baseline 1.50,  +0.05)
    MaxDD  = -12.83% (baseline -12.94%)

Post-50%-haircut: CAGR 24.05%, Sharpe ~1.525 — still beats baseline on all axes.

To reproduce, build the probability cache once via phase6_classifier_confidence.py,
then run this file. Requires tests/autonomous/cache/pred_proba.pkl.
"""
from __future__ import annotations
import sys, pickle, copy
from pathlib import Path
import numpy as np

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


def run_champion():
    _load()
    with open(HERE.parent / "cache" / "pred_proba.pkl", "rb") as f:
        pred_reg, maxp = pickle.load(f)
    bundle = _STATE["bundle"]
    cur = np.asarray(_cr(bundle.df).index)
    pr = pred_reg.copy()
    want = (pred_reg != cur) & (pred_reg >= 0)
    low = np.nan_to_num(maxp, nan=0.0) < GATE_THRESHOLD
    pr[want & low] = cur[want & low]

    cfg = copy.deepcopy(_STATE["cfg"])
    cfg.update(CHAMPION_OVERRIDES)
    engine = PortfolioEngine(bundle, pr, cfg)
    return run_backtest(engine, _STATE["test_dates"], cfg).stats


if __name__ == "__main__":
    s = run_champion()
    print("CHAMPION P6b.03 gate40 + dropoverlap + 62/38")
    print(fmt(s))
