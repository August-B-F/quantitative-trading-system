"""STUDY 3 dev-window runner — the 10 pre-registered configs of HYPOTHESIS.md."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(r"c:\Users\august\Documents\GitHub\quantitative-trading-system")
DROP = ROOT / "research" / "droplets" / "study3_no_trade_bands"
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(DROP))

from backtest.ledger import load_prices, run_ledger_backtest  # noqa: E402
from strategy.sleeves import TSMOM_UNIVERSE, build_schedule, two_sleeve_weights  # noqa: E402
import bands_lib as bl  # noqa: E402

UNIVERSE_A = ["SOXX", "QQQ", "XLK", "VGT", "IGV", "XLE", "GLD", "SHY"]
DEV_A = ("2005-01-01", "2017-12-31")
DEV_B = ("2007-01-01", "2017-12-31")


def run_configs(configs: dict, prices: dict, end: str, out_rows: list):
    for name, sched in configs.items():
        for bps in (10.0, 20.0):
            res = run_ledger_backtest(sched, prices, cost_bps=bps,
                                      cash_ticker="SHV", end=end, benchmarks=())
            s = res.stats
            out_rows.append({
                "config": name, "cost_bps": bps,
                "start": str(s["start"].date()), "end": str(s["end"].date()),
                "sharpe": round(s["sharpe"], 4), "cagr": round(s["cagr"], 6),
                "vol": round(s["vol"], 6), "max_dd": round(s["max_dd"], 6),
                "ann_turnover": round(s["ann_turnover"], 4),
                "ann_cost_drag_bps": round(s["ann_cost_drag"] * 1e4, 2),
                "n_rebalances": s["n_rebalances"],
            })
            print(f"{name:>4} @{bps:>4.0f}bps  Sharpe={s['sharpe']:.3f}  "
                  f"CAGR={s['cagr']*100:6.2f}%  MaxDD={s['max_dd']*100:6.2f}%  "
                  f"TO={s['ann_turnover']:5.2f}x  drag={s['ann_cost_drag']*1e4:5.1f}bps  "
                  f"reb={s['n_rebalances']}")


def main():
    rows: list[dict] = []

    # ---- Rule A ----
    prices_a = load_prices(ROOT, UNIVERSE_A + ["SHV"])
    px_a = bl.adj_close_frame(prices_a, UNIVERSE_A + ["SHV"])
    a_base = bl.build_rotation_targets(prices_a, UNIVERSE_A, *DEV_A, m=0)
    a_h1 = bl.build_rotation_targets(prices_a, UNIVERSE_A, *DEV_A, m=1)
    a_h2 = bl.build_rotation_targets(prices_a, UNIVERSE_A, *DEV_A, m=2)
    configs_a = {
        "A0": a_base,
        "A1": a_h1,
        "A2": a_h2,
        "A3": bl.apply_position_band(a_base, px_a, 0.05),
        "A4": bl.apply_position_band(a_h2, px_a, 0.05),
    }
    print("== Rule A: 63d top-3 inverse-vol rotation, dev 2005..2017 ==")
    run_configs(configs_a, prices_a, DEV_A[1], rows)

    # ---- Rule B ----
    tickers_b = sorted(set(TSMOM_UNIVERSE) | {"SHV", "AGG"})
    prices_b = load_prices(ROOT, tickers_b)
    px_b = bl.adj_close_frame(prices_b, tickers_b)
    b_base = build_schedule(prices_b, DEV_B[0], DEV_B[1], two_sleeve_weights)
    configs_b = {
        "B0": b_base,
        "B1": bl.apply_position_band(b_base, px_b, 0.02),
        "B2": bl.apply_position_band(b_base, px_b, 0.05),
        "B3": bl.apply_position_band(b_base, px_b, 0.10),
        "B4": bl.apply_portfolio_skip(b_base, px_b, 0.10),
    }
    print("== Rule B: two-sleeve, dev 2007..2017 ==")
    run_configs(configs_b, prices_b, DEV_B[1], rows)

    df = pd.DataFrame(rows)
    df.to_csv(DROP / "dev_results.csv", index=False)
    print(f"\nwrote {DROP / 'dev_results.csv'}")


if __name__ == "__main__":
    main()
