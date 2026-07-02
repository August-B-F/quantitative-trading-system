"""STUDY 3 — the single validation look (per HYPOTHESIS.md decision rule).

Rule A winner A1 (rank hysteresis m=1) vs its no-band baseline A0,
2018-01-01..latest, fresh state at the first 2018 month-end, 10 and 20 bps.
Rule B: no qualifier on dev -> no validation look (null result stands).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(r"c:\Users\august\Documents\GitHub\quantitative-trading-system")
DROP = ROOT / "research" / "droplets" / "study3_no_trade_bands"
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(DROP))

from backtest.ledger import load_prices, run_ledger_backtest  # noqa: E402
import bands_lib as bl  # noqa: E402

UNIVERSE_A = ["SOXX", "QQQ", "XLK", "VGT", "IGV", "XLE", "GLD", "SHY"]
VAL = ("2018-01-01", "2026-12-31")

prices = load_prices(ROOT, UNIVERSE_A + ["SHV"])
rows = []
for name, m in (("A0_val", 0), ("A1_val", 1)):
    sched = bl.build_rotation_targets(prices, UNIVERSE_A, *VAL, m=m)
    for bps in (10.0, 20.0):
        res = run_ledger_backtest(sched, prices, cost_bps=bps,
                                  cash_ticker="SHV", benchmarks=())
        s = res.stats
        rows.append({
            "config": name, "cost_bps": bps,
            "start": str(s["start"].date()), "end": str(s["end"].date()),
            "sharpe": round(s["sharpe"], 4), "cagr": round(s["cagr"], 6),
            "vol": round(s["vol"], 6), "max_dd": round(s["max_dd"], 6),
            "ann_turnover": round(s["ann_turnover"], 4),
            "ann_cost_drag_bps": round(s["ann_cost_drag"] * 1e4, 2),
            "n_rebalances": s["n_rebalances"],
        })
        print(f"{name} @{bps:.0f}bps  {s['start'].date()}..{s['end'].date()}  "
              f"Sharpe={s['sharpe']:.3f}  CAGR={s['cagr']*100:.2f}%  "
              f"MaxDD={s['max_dd']*100:.2f}%  TO={s['ann_turnover']:.2f}x  "
              f"drag={s['ann_cost_drag']*1e4:.1f}bps")

pd.DataFrame(rows).to_csv(DROP / "validation_results.csv", index=False)
print(f"wrote {DROP / 'validation_results.csv'}")
