"""End-to-end production signal dry-run.

Steps (matches MASTER_ARCHITECTURE.md §2.8):
1. refresh_all_data() — fetch latest prices/macro/FOMC.
2. compute_classifier_features() — build today's CORE row.
3. Load classifier + run the full PortfolioEngine for the latest date.
4. Print regime, lookback, ETF rankings, target weights, gate, deferral, warnings.

NO TRADES ARE PLACED. This is a verification/dry-run script.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from data.pipeline import load_config, load_panel, refresh_and_rebuild  # noqa: E402
from features.engineer import load_core_feature_list, select_core_features  # noqa: E402
from features.live_features import compute_classifier_features  # noqa: E402
from model.classifier import walk_forward_predict, predict_at  # noqa: E402
from strategy.portfolio import PortfolioEngine  # noqa: E402
from strategy.rebalance import month_end_positions, fomc_window_mask  # noqa: E402


def _print_section(title: str) -> None:
    print(f"\n{'=' * 60}\n {title}\n{'=' * 60}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=None, help="optional YYYY-MM-DD; default = latest panel date")
    parser.add_argument("--no-refresh", action="store_true", help="skip live data refresh")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    warnings: list[str] = []

    # ---- STEP 1 — refresh -------------------------------------------------
    _print_section("STEP 1 — refresh_and_rebuild")
    if args.no_refresh:
        print("(skipped)")
        status = {}
    else:
        status = refresh_and_rebuild(ROOT)
        print(json.dumps(status, indent=2, default=str))
        # Auto-defer rule (§4.1.1): if prices are unavailable, do not
        # proceed with stale prices. Defer 1 trading day and exit.
        if status.get("prices", {}).get("status") == "error":
            print("\n!! Yahoo prices unavailable. Defer rebalance 1 trading day. Retry tomorrow.")
            return 2
        for k in ("prices", "macro", "fomc"):
            s = status.get(k, {})
            if s.get("status") not in ("ok",):
                warnings.append(f"{k}: status={s.get('status')} ({s.get('error') or s.get('errors') or s.get('stale')})")

    # ---- STEP 2 — live features ------------------------------------------
    _print_section("STEP 2 — compute_classifier_features")
    cfg = load_config(ROOT)
    bundle = load_panel(ROOT, cfg)

    target_date = pd.Timestamp(args.date) if args.date else bundle.dates.max()
    print(f"target_date = {target_date.date()}")

    live_row = compute_classifier_features(ROOT, as_of=target_date)
    n_nonnull = int(live_row.iloc[0].notna().sum())
    print(f"live CORE row: {live_row.shape[1]} cols, {n_nonnull} non-null")
    if n_nonnull < live_row.shape[1] * 0.9:
        warnings.append(f"only {n_nonnull}/{live_row.shape[1]} live CORE features populated")

    # Cross-check vs panel
    panel_row = bundle.df.loc[[target_date], live_row.columns.intersection(bundle.df.columns)]
    common = panel_row.columns
    diffs = []
    for c in common:
        lv, pv = live_row[c].iloc[0], panel_row[c].iloc[0]
        if pd.isna(lv) and pd.isna(pv):
            continue
        if pd.isna(lv) or pd.isna(pv) or not np.isclose(lv, pv, rtol=1e-6, atol=1e-9):
            diffs.append(c)
    print(f"vs master panel: {len(diffs)} mismatches across {len(common)} shared columns")
    if diffs:
        warnings.append(f"live features diverge from panel: {diffs[:3]}")

    # ---- STEP 3 — classifier ----------------------------------------------
    _print_section("STEP 3 — classifier (walk-forward predict)")
    core = load_core_feature_list(ROOT, cfg["classifier"]["feature_set"])
    core_present = select_core_features(bundle.df, core)
    pred_reg, _, _ = walk_forward_predict(bundle.df, core_present, cfg)
    print(f"classifier WF predictions: {len(pred_reg)} rows")

    # WF emits predictions only on its discrete test dates; if the live
    # rebalance date falls between them, fit a fresh model on all labels
    # available before `target_date - (horizon+embargo)` and overwrite.
    pos_idx = bundle.dates.get_indexer([target_date])[0]
    if pos_idx >= 0 and pred_reg[pos_idx] < 0:
        live_pred = predict_at(bundle.df, core_present, cfg, target_date)
        if live_pred >= 0:
            pred_reg[pos_idx] = live_pred
            print(f"live predict_at({target_date.date()}) -> regime {live_pred}")
        else:
            warnings.append(f"predict_at returned -1 for {target_date.date()} (will use 63d fallback)")

    engine = PortfolioEngine(bundle, pred_reg, cfg)
    pos = bundle.dates.get_indexer([target_date])[0]
    if pos < 0:
        print(f"date {target_date} not in panel; aborting")
        return 1

    # ---- STEP 4 — rebalance schedule + FOMC deferral ----------------------
    _print_section("STEP 4 — rebalance / FOMC deferral check")
    me_positions = month_end_positions(bundle.dates)
    is_rebal_day = pos in set(me_positions.values.tolist())
    fomc_idx = np.where(bundle.is_fomc_day)[0]
    fomc_mask = fomc_window_mask(
        len(bundle.dates),
        fomc_idx,
        pre_days=int(cfg.get("fomc_window_pre", 0)),
        post_days=int(cfg.get("fomc_window_after", 2)),
    )
    in_fomc_window = bool(fomc_mask[pos])
    print(f"is_month_end_rebalance_day = {is_rebal_day}")
    print(f"in_FOMC_post_window[{cfg['fomc_window_pre']}..{cfg['fomc_window_after']}] = {in_fomc_window}")
    if not is_rebal_day:
        print("(NOTE: today is not a scheduled rebalance day — computing signal anyway for verification)")

    # ---- STEP 5 — decide --------------------------------------------------
    _print_section("STEP 5 — decision")
    rec = engine.decide(pos, pos, deferred=in_fomc_window)
    lb = rec.lookback_used
    print(f"date              : {rec.date.date()}")
    print(f"current_regime    : {rec.current_regime}")
    print(f"predicted_regime  : {rec.predicted_regime}")
    print(f"active_lookback   : {lb} trading days")
    print(f"SMA distance      : {rec.sma_distance:+.4f}  gate_fired={rec.sma_gate_fired}")
    print(f"FOMC deferred     : {rec.deferred}")

    # N-day returns for the universe at the active lookback
    print(f"\nETF rankings (return over {lb}d):")
    if lb in bundle.returns:
        ret_row = bundle.returns[lb].loc[target_date, cfg["universe"]]
        ranked = ret_row.sort_values(ascending=False)
        for i, (t, r) in enumerate(ranked.items(), 1):
            mark = " <- TOP1" if t == rec.top1 else (" *" if t in rec.topk else "")
            print(f"  {i:2d}. {t:5s} {r * 100:+7.2f}%{mark}")

    print("\nTarget weights:")
    total = 0.0
    for t, w in sorted(rec.target_weights.items(), key=lambda x: -x[1]):
        if w > 1e-6:
            print(f"  {t:6s} {w * 100:6.2f}%")
            total += w
    print(f"  {'TOTAL':6s} {total * 100:6.2f}%")
    if not np.isclose(total, 1.0, atol=1e-4):
        warnings.append(f"weights sum to {total:.4f}, not 1.0")

    # ---- STEP 6 — warnings ------------------------------------------------
    _print_section("DATA QUALITY WARNINGS")
    if warnings:
        for w in warnings:
            print(f"  ! {w}")
    else:
        print("  none")

    print("\nDRY RUN — no trades placed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
