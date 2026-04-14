"""CHAMPION as of 2026-04-13 15:30.

Modification: Drop VGT and XLK from the universe (redundant tech; QQQ/XLK/VGT
are ~90% overlapping by construction), and shift the top-1 / top-3 split from
50/50 to 60/40 (more weight on the rank-1 leader).

Full walk-forward stats:
    CAGR   = 24.28%   (baseline 23.61%, +0.67pp)
    Sharpe =  1.55    (baseline 1.50,  +0.05)
    MaxDD  = -12.68%  (baseline -12.94%, -0.26pp better)

Post-50%-haircut: CAGR 23.94 / Sharpe ~1.52 / MaxDD ~-12.81 — still beats baseline
on every axis, so it passes the anti-overfitting rule.

Rationale: VGT and XLK track essentially the same S&P tech sector but with slightly
different baskets. In practice they rank adjacent to each other on most rebalance
dates and dilute the inverse-vol top-3 leg. Removing them eliminates a degenerate
dimension of the universe without losing tech exposure (QQQ/SOXX/IGV still cover
broad tech, semis, and software respectively).

The 60/40 split doubles down on the rank-1 signal. This weights the leader slightly
more aggressively in exchange for ~1pp higher CAGR. Sharpe still improves because
the tighter universe has less cross-ETF noise.
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from utils.base_test import run, fmt

CHAMPION_OVERRIDES = {
    "universe": ["SOXX", "QQQ", "IGV", "XLE", "GLD", "SHY"],
    "top1_weight": 0.60,
    "top3_weight": 0.40,
}

if __name__ == "__main__":
    s = run(CHAMPION_OVERRIDES)
    print("CHAMPION P2b.02_do_split60_40")
    print(fmt(s))
