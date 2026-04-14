"""Phase 4: robustness check on champion across sub-periods.

Critical anti-overfitting test: does the champion edge survive when we split the
walk-forward window into halves and evaluate each independently?
"""
from __future__ import annotations
import sys, datetime as dt, copy
from pathlib import Path
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from utils.base_test import run, fmt  # noqa: E402
from backtest.engine import compute_stats  # noqa: E402

BASE = {}
CHAMP = {"universe": ["SOXX","QQQ","IGV","XLE","GLD","SHY"], "top1_weight":0.60, "top3_weight":0.40}

SUBPERIODS = [
    ("full",  None, None),
    ("2010_2015", "2010-01-01", "2015-12-31"),
    ("2016_2020", "2016-01-01", "2020-12-31"),
    ("2021_2026", "2021-01-01", "2026-12-31"),
    ("first_half", "2010-01-01", "2017-12-31"),
    ("second_half","2018-01-01", "2026-12-31"),
]


def run_window(ov, start, end):
    from utils.base_test import _load, _STATE
    from strategy.portfolio import PortfolioEngine
    from backtest.engine import run_backtest
    _load()
    cfg = copy.deepcopy(_STATE["cfg"]); cfg.update(ov or {})
    engine = PortfolioEngine(_STATE["bundle"], _STATE["pred_reg"], cfg)
    res = run_backtest(engine, _STATE["test_dates"], cfg, start=start, end=end)
    return res.stats


def main():
    log_path = HERE.parent / "LOG.md"
    ts = dt.datetime.now().isoformat(timespec="seconds")
    lines = [f"\n### phase4_robustness  {ts}\n",
             "Champion vs baseline across sub-periods (walk-forward windowed):\n",
             "| period | baseline | champion | Δ CAGR | Δ Sharpe | Δ MaxDD |",
             "|---|---|---|---|---|---|"]
    for pname, st, en in SUBPERIODS:
        b = run_window(BASE, st, en); c = run_window(CHAMP, st, en)
        dc = (c["cagr"]-b["cagr"])*100
        ds = c["sharpe"]-b["sharpe"]
        dd = (c["max_dd"]-b["max_dd"])*100
        print(pname, "base", fmt(b), "| champ", fmt(c))
        lines.append(f"| {pname} | {b['cagr']*100:.2f}/{b['sharpe']:.2f}/{b['max_dd']*100:.2f} | {c['cagr']*100:.2f}/{c['sharpe']:.2f}/{c['max_dd']*100:.2f} | {dc:+.2f}pp | {ds:+.2f} | {dd:+.2f}pp |")
    with open(log_path, "a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

if __name__ == "__main__":
    main()
