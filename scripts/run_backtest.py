"""Run the full production backtest and print CAGR / Sharpe / MaxDD.

Usage:
    py scripts/run_backtest.py --start 2011-01-01 --end 2025-12-31 --cost-bps 0

The canonical research result is gross (cost_bps=0); pass --cost-bps 10
to apply a 10bps round-trip haircut per rebalance for the degradation
budget check.
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from data.pipeline import load_config, load_panel  # noqa: E402
from features.engineer import load_core_feature_list, select_core_features  # noqa: E402
from model.classifier import walk_forward_predict  # noqa: E402
from strategy.portfolio import PortfolioEngine  # noqa: E402
from backtest.engine import run_backtest  # noqa: E402


def main() -> int:
    """Entry point."""
    parser = argparse.ArgumentParser()
    # Defaults = full walk-forward test window (matches canonical 23.61/1.50/-12.94).
    # The canonical research run covers ~2010-04 -> 2026-03 (188 months).
    # Passing a narrower window (e.g. 2011-2025) will trim the series and
    # therefore return slightly different stats; see tests/test_backtest_canary.py.
    parser.add_argument("--start", default=None)
    parser.add_argument("--end", default=None)
    parser.add_argument("--cost-bps", type=float, default=0.0)
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    cfg = load_config(ROOT)
    bundle = load_panel(ROOT, cfg)
    core = load_core_feature_list(ROOT, cfg["classifier"]["feature_set"])
    core_present = select_core_features(bundle.df, core)
    print(f"core features present: {len(core_present)} / {len(core)}")

    pred_reg, test_dates, accs = walk_forward_predict(bundle.df, core_present, cfg)
    print(f"WF test dates: {len(test_dates)}  WF accuracy: {sum(accs)/max(len(accs),1):.3f}")

    engine = PortfolioEngine(bundle, pred_reg, cfg)
    res = run_backtest(
        engine, test_dates, cfg,
        cost_bps=args.cost_bps, start=args.start, end=args.end,
    )
    s = res.stats
    print(f"\nCAGR  : {s['cagr']*100:6.2f}%")
    print(f"Sharpe: {s['sharpe']:6.2f}")
    print(f"MaxDD : {s['max_dd']*100:6.2f}%")
    print(f"n     : {s['n']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
