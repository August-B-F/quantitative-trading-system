"""9-strategy multi-backtest with side-by-side comparison.

Loads all 9 yamls from ``configs/strategies/``, runs each over the shared
walk-forward window, and prints the summary table + annual returns +
correlation matrix + account-level aggregation. Writes a JSON dump to
``results/multi_strategy_backtest.json``.

Usage::

    py scripts/run_multi_backtest.py
"""
from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from data.pipeline import load_config, load_panel  # noqa: E402
from features.engineer import load_core_feature_list, select_core_features  # noqa: E402
from model.classifier import walk_forward_predict  # noqa: E402
from backtest.engine import compute_stats  # noqa: E402
from backtest.multi_engine import MultiStrategyBacktest, _extended_metrics  # noqa: E402

log = logging.getLogger(__name__)


STRATEGY_FILES = [
    "strategy_1_optimized.yaml",
    "strategy_2_robust_stack.yaml",
    "strategy_3_dropoverlap.yaml",
    "strategy_4_t2_balanced.yaml",
    "strategy_5_trend_simple.yaml",
    "strategy_6_dual_momentum.yaml",
    "strategy_7_robust_var.yaml",
    "strategy_8_p59_full_stack.yaml",
    "strategy_9_p57_frontloaded.yaml",
]


def _load_shared_state():
    cfg = load_config(ROOT)
    bundle = load_panel(ROOT, cfg)
    # Use the cached walk-forward predictions if present to keep this fast.
    cache = ROOT / "tests" / "autonomous" / "cache" / "pred_reg.pkl"
    if cache.exists():
        import pickle
        with open(cache, "rb") as f:
            pred_reg, test_dates = pickle.load(f)
        acc = float("nan")
    else:
        core = load_core_feature_list(ROOT, cfg["classifier"]["feature_set"])
        core_present = select_core_features(bundle.df, core)
        pred_reg, test_dates, accs = walk_forward_predict(bundle.df, core_present, cfg)
        acc = sum(accs) / max(len(accs), 1)
    return cfg, bundle, pred_reg, test_dates, acc


def _format_row(i, name, m):
    return (f"| {i} | {name:<17} | "
            f"{m['cagr']*100:6.2f}% | {m['sharpe']:5.2f} | "
            f"{m['max_dd']*100:7.2f}% | {m['sortino']:6.2f} | "
            f"{m['win_pct']*100:5.1f}% | {m['worst_year']*100:7.2f}% |")


def _print_summary(results: dict) -> None:
    print("\nSUMMARY TABLE:")
    print("| # | Name              | CAGR    | Sharpe | MaxDD    | Sortino | Win%  | Worst Yr |")
    print("|---|-------------------|---------|--------|----------|---------|-------|----------|")
    for name, r in sorted(results.items(), key=lambda kv: kv[1]["slot"]):
        print(_format_row(r["slot"], name, r["metrics"]))


def _print_annual(results: dict, spy_annual: pd.Series) -> None:
    print("\nANNUAL RETURNS PER STRATEGY:")
    # gather
    strat_annual = {}
    for name, r in sorted(results.items(), key=lambda kv: kv[1]["slot"]):
        strat_annual[f"S{r['slot']}"] = r["metrics"]["annual_returns"]
    df = pd.DataFrame(strat_annual)
    df["SPY"] = spy_annual
    header = "| Year | " + " | ".join(f"{c:>6}" for c in df.columns) + " |"
    sep = "|------|" + "|".join(["--------"] * len(df.columns)) + "|"
    print(header)
    print(sep)
    for year, row in df.iterrows():
        cells = " | ".join(
            f"{v*100:5.1f}%" if pd.notna(v) else "  -   " for v in row.values
        )
        print(f"| {year} | {cells} |")


def _print_corr(results: dict) -> None:
    print("\nCORRELATION MATRIX (monthly returns):")
    frame = pd.DataFrame({
        f"S{r['slot']}": r["monthly_returns"]
        for _, r in results.items()
    }).sort_index(axis=1)
    corr = frame.corr()
    header = "|    | " + " | ".join(f"{c:>5}" for c in corr.columns) + " |"
    sep = "|----|" + "|".join(["-------"] * len(corr.columns)) + "|"
    print(header)
    print(sep)
    for idx, row in corr.iterrows():
        cells = " | ".join(f"{v:+.2f}" for v in row.values)
        print(f"| {idx} | {cells} |")

    # Diversity metrics
    mask = ~np.eye(len(corr), dtype=bool)
    off = corr.values[mask]
    avg = float(np.nanmean(off))
    low = int(((corr.values < 0.5) & mask).sum() / 2)
    # Most uncorrelated with S1 (OPTIMIZED)
    opt_col = corr["S1"].drop("S1")
    lowest = opt_col.idxmin()
    print(f"\nDIVERSITY:")
    print(f"  avg pairwise corr    : {avg:.3f}")
    print(f"  pairs with corr < 0.5: {low}")
    print(f"  most uncorrelated w/ OPTIMIZED: {lowest} (corr={opt_col.min():.3f})")
    return corr


def _print_accounts(results: dict, accounts_cfg: dict) -> None:
    print("\nACCOUNT GROUPING VALIDATION:")
    print("| Account    | Strategies | Agg CAGR | Agg Sharpe | Agg MaxDD |")
    print("|------------|-----------|----------|------------|-----------|")
    slot_by_file = {}
    for name, r in results.items():
        slot_by_file[r["slot"]] = r
    # Map file stem -> slot
    # Accounts yaml uses strategy file stems like strategy_1_optimized
    slug_to_slot = {
        "strategy_1_optimized": 1,
        "strategy_2_robust_stack": 2,
        "strategy_3_dropoverlap": 3,
        "strategy_4_t2_balanced": 4,
        "strategy_5_trend_simple": 5,
        "strategy_6_dual_momentum": 6,
        "strategy_7_robust_var": 7,
        "strategy_8_p59_full_stack": 8,
        "strategy_9_p57_frontloaded": 9,
    }
    for acct_key, acct in accounts_cfg["accounts"].items():
        slots = [slug_to_slot[s] for s in acct["strategies"]]
        splits = acct["capital_split"]
        series_list = [slot_by_file[s]["monthly_returns"] for s in slots]
        # align on common index
        combined = pd.concat(series_list, axis=1).dropna()
        combined.columns = [f"S{s}" for s in slots]
        agg = (combined * splits).sum(axis=1)
        s = compute_stats(agg.values)
        strat_str = ",".join(str(x) for x in slots)
        print(f"| {acct['name']:<10} | {strat_str:<9} | "
              f"{s['cagr']*100:6.2f}% | {s['sharpe']:6.2f}    | {s['max_dd']*100:7.2f}% |")


def _spy_annual(bundle, test_dates) -> pd.Series:
    """Compute SPY annual returns over the backtest window."""
    # SPY 21d forward return evaluated monthly, compounded to yearly
    import pandas as pd
    positions = pd.Series(bundle.dates.get_indexer(test_dates), index=test_dates)
    month_last = positions.groupby(test_dates.to_period("M")).tail(1)
    spy_fwd = bundle.fwd21["SPY"]
    vals = [(rd, float(spy_fwd[int(p)])) for rd, p in month_last.items()]
    s = pd.Series(dict(vals)).sort_index()
    return (1 + s).groupby(s.index.year).prod() - 1


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    cfg, bundle, pred_reg, test_dates, wf_acc = _load_shared_state()
    print(f"Loaded panel: {len(bundle.dates)} days | WF test dates: {len(test_dates)} | WF acc: {wf_acc:.3f}")

    strat_paths = [ROOT / "configs" / "strategies" / f for f in STRATEGY_FILES]
    mb = MultiStrategyBacktest(strat_paths, cost_bps=0.0)
    results = mb.run(bundle, pred_reg, test_dates, cfg)

    _print_summary(results)
    spy_yr = _spy_annual(bundle, test_dates)
    _print_annual(results, spy_yr)
    corr = _print_corr(results)

    with open(ROOT / "configs" / "accounts.yaml", "r") as f:
        acct_cfg = yaml.safe_load(f)
    _print_accounts(results, acct_cfg)

    # Canary validations
    s1 = results["OPTIMIZED"]["metrics"]
    print(f"\nCANARY: OPTIMIZED CAGR={s1['cagr']*100:.2f}% Sharpe={s1['sharpe']:.2f} MaxDD={s1['max_dd']*100:.2f}%")
    ok = (abs(s1["cagr"] - 0.2361) < 0.005
          and abs(s1["sharpe"] - 1.50) < 0.05
          and abs(s1["max_dd"] + 0.1294) < 0.01)
    print("  canary:", "PASS" if ok else "FAIL")

    # Save JSON
    out = {
        "strategies": {},
        "correlation_matrix": corr.to_dict(),
        "spy_annual": spy_yr.to_dict(),
    }
    for name, r in results.items():
        m = r["metrics"].copy()
        m.pop("annual_returns", None)
        out["strategies"][name] = {
            "slot": r["slot"],
            "metrics": {k: (float(v) if isinstance(v, (int, float, np.floating)) else v)
                        for k, v in m.items() if k != "n"},
            "n": int(r["metrics"]["n"]),
            "annual_returns": {int(y): float(v) for y, v in r["metrics"]["annual_returns"].items()},
            "monthly_returns": {str(d.date()): float(v) for d, v in r["monthly_returns"].items()},
        }

    out_path = ROOT / "results" / "multi_strategy_backtest.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2, default=str)
    print(f"\nSaved: {out_path}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
