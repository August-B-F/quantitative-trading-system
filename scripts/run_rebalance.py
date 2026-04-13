"""Monthly rebalance entry point (MASTER_ARCHITECTURE §2.7, §2.8).

Flow on a rebalance day:
    schedule check -> FOMC deferral -> data refresh -> signal -> trades
    -> report -> state save. Trades are NOT executed; they are printed
    for manual submission. Use --confirm after execution to persist the
    new holdings.

Flags:
    --force      run even if today is not the last trading day of the month
    --confirm    record that the last rebalance's trades were executed
    --status     print current holdings and schedule info, then exit
    --date YYYY-MM-DD  pretend today is this date (testing)
    --no-refresh skip the live data refresh
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import date as _date
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
from strategy.rebalance import fomc_window_mask  # noqa: E402

HOLDINGS_PATH = ROOT / "configs/holdings.json"
REBAL_LOG_PATH = ROOT / "logs/rebalance_log.json"
MIN_TRADE_FRACTION = 0.01  # 1% — skip dust trades (§3.4)

log = logging.getLogger("rebalance")


# ---------- NYSE calendar helpers ------------------------------------------

def _nyse():
    import pandas_market_calendars as mcal
    return mcal.get_calendar("NYSE")


def trading_days(start: pd.Timestamp, end: pd.Timestamp) -> pd.DatetimeIndex:
    sched = _nyse().schedule(start_date=start, end_date=end)
    return pd.DatetimeIndex(sched.index).tz_localize(None).normalize()


def last_trading_day_of_month(today: pd.Timestamp) -> pd.Timestamp:
    first = today.replace(day=1)
    last_cal = (first + pd.offsets.MonthEnd(0)).normalize()
    days = trading_days(first, last_cal)
    return days[-1]


def next_rebalance_date(today: pd.Timestamp) -> pd.Timestamp:
    ltd = last_trading_day_of_month(today)
    if today <= ltd:
        return ltd
    nxt = (today + pd.offsets.MonthBegin(1)).normalize()
    return last_trading_day_of_month(nxt)


def add_trading_days(start: pd.Timestamp, n: int) -> pd.Timestamp:
    days = trading_days(start, start + pd.Timedelta(days=max(10, n * 3)))
    days = days[days > start]
    return days[n - 1] if len(days) >= n else days[-1]


# ---------- FOMC deferral --------------------------------------------------

def fomc_defer_check(today: pd.Timestamp, cfg: dict) -> tuple[bool, pd.Timestamp | None]:
    """Return (in_window, deferred_to) based on FOMC calendar + config."""
    if not cfg.get("fomc_defer_enabled", True):
        return False, None
    cal_path = ROOT / cfg["paths"]["fomc_calendar"]
    if not cal_path.exists():
        return False, None
    df = pd.read_parquet(cal_path)
    if "is_fomc_day" not in df.columns:
        return False, None
    fomc_days = pd.DatetimeIndex(df.index[df["is_fomc_day"] > 0]).normalize()
    post_days = int(cfg.get("fomc_window_after", 2))
    pre_days = int(cfg.get("fomc_window_pre", 0))
    for f in fomc_days:
        lo = f - pd.Timedelta(days=pre_days * 3 + 2)
        hi = f + pd.Timedelta(days=post_days * 3 + 4)
        if lo <= today <= hi:
            window = trading_days(f - pd.Timedelta(days=10), hi + pd.Timedelta(days=10))
            window = window[(window >= f) & (window <= add_trading_days(f, post_days))]
            if today.normalize() in set(window):
                deferred_to = add_trading_days(today, int(cfg.get("fomc_defer_days", 3)))
                return True, deferred_to
    return False, None


# ---------- holdings / log I/O ---------------------------------------------

def load_holdings() -> dict[str, float]:
    if not HOLDINGS_PATH.exists():
        return {"SHY": 1.0}
    with open(HOLDINGS_PATH, "r") as f:
        return json.load(f)


def save_holdings(weights: dict[str, float]) -> None:
    HOLDINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    clean = {k: round(float(v), 6) for k, v in weights.items() if v > 1e-6}
    with open(HOLDINGS_PATH, "w") as f:
        json.dump(clean, f, indent=2, sort_keys=True)


def append_rebalance_log(entry: dict) -> None:
    REBAL_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    records = []
    if REBAL_LOG_PATH.exists():
        try:
            with open(REBAL_LOG_PATH, "r") as f:
                records = json.load(f)
        except (json.JSONDecodeError, ValueError):
            records = []
    records.append(entry)
    with open(REBAL_LOG_PATH, "w") as f:
        json.dump(records, f, indent=2, default=str)


# ---------- trade computation ----------------------------------------------

def compute_trades(
    current: dict[str, float], target: dict[str, float], min_frac: float = MIN_TRADE_FRACTION
) -> dict[str, float]:
    tickers = set(current) | set(target)
    trades = {}
    for t in tickers:
        delta = target.get(t, 0.0) - current.get(t, 0.0)
        if abs(delta) >= min_frac:
            trades[t] = delta
    return trades


# ---------- report ---------------------------------------------------------

def print_report(
    today: pd.Timestamp,
    rec,
    current: dict[str, float],
    trades: dict[str, float],
    cost_bps: float,
    warnings: list[str],
    fomc_deferred: bool,
) -> None:
    bar = "=" * 60
    print(bar)
    print(f"REBALANCE REPORT - {today.date()}")
    print(bar)
    regime_kind = "TRANSITION" if rec.current_regime != rec.predicted_regime else "STABLE"
    print(f"Regime: current={rec.current_regime}, predicted={rec.predicted_regime}  [{regime_kind}]")
    print(f"Lookback: {rec.lookback_used}d")
    print(f"SMA gate: {'ON (CASH)' if rec.sma_gate_fired else 'OFF'}  "
          f"(SPY dist200 = {rec.sma_distance*100:+.2f}%)")
    print(f"FOMC deferral: {'YES' if fomc_deferred else 'NO'}")

    lb = rec.lookback_used
    cfg = rec  # placeholder not used below
    print(f"\nETF Rankings ({lb}d returns):")
    engine_ret = _rank_returns(lb, today)
    if engine_ret is not None:
        for i, (t, r) in enumerate(engine_ret.items(), 1):
            mark = " <- TOP1" if t == rec.top1 else (" *" if t in rec.topk else "")
            print(f"  {i:2d}. {t:5s} {r*100:+7.2f}%{mark}")

    print("\nTarget Weights:")
    for t, w in sorted(rec.target_weights.items(), key=lambda x: -x[1]):
        if w > 1e-6:
            print(f"  {t:6s} {w*100:6.2f}%")

    print("\nCurrent Holdings:")
    if not current:
        print("  (none)")
    for t, w in sorted(current.items(), key=lambda x: -x[1]):
        if w > 1e-6:
            print(f"  {t:6s} {w*100:6.2f}%")

    print("\nNet Trades (|delta| >= 1%):")
    if not trades:
        print("  (no trades needed)")
    else:
        for t, d in sorted(trades.items(), key=lambda x: -abs(x[1])):
            side = "BUY " if d > 0 else "SELL"
            print(f"  {side} {t:5s} {d*100:+6.2f}%")

    turnover = sum(abs(d) for d in trades.values())
    cost_per_100k = turnover * 100_000 * cost_bps / 10_000
    print(f"\nEstimated turnover: {turnover*100:.1f}% of portfolio")
    print(f"Estimated cost at {cost_bps:.0f}bps: ${cost_per_100k:.2f} per $100k")

    print("\nWarnings:")
    if warnings:
        for w in warnings:
            print(f"  - {w}")
    else:
        print("  none")
    print(bar)


def _rank_returns(lookback: int, target_date: pd.Timestamp):
    """Best-effort ranking read-out; returns None if returns file missing."""
    try:
        cfg = load_config(ROOT)
        rpath = ROOT / cfg["paths"]["returns_dir"] / f"returns_{lookback}d.parquet"
        if not rpath.exists():
            return None
        df = pd.read_parquet(rpath)
        uni = cfg["universe"]
        if target_date not in df.index:
            target_date = df.index[df.index <= target_date].max()
        row = df.loc[target_date, [t for t in uni if t in df.columns]]
        return row.sort_values(ascending=False)
    except Exception:
        return None


# ---------- subcommands ----------------------------------------------------

def cmd_status() -> int:
    today = pd.Timestamp.utcnow().normalize().tz_localize(None)
    holdings = load_holdings()
    print(f"Current holdings ({HOLDINGS_PATH.name}):")
    for t, w in sorted(holdings.items(), key=lambda x: -x[1]):
        print(f"  {t:6s} {w*100:6.2f}%")

    last_date = None
    if REBAL_LOG_PATH.exists():
        try:
            with open(REBAL_LOG_PATH, "r") as f:
                records = json.load(f)
            if records:
                last_date = pd.Timestamp(records[-1]["date"])
        except Exception:
            pass
    if last_date is not None:
        print(f"\nLast rebalance: {last_date.date()}  "
              f"({(today - last_date).days} days ago)")
    else:
        print("\nLast rebalance: (never)")
    nxt = next_rebalance_date(today)
    print(f"Next scheduled: {nxt.date()}")
    return 0


def cmd_confirm() -> int:
    if not REBAL_LOG_PATH.exists():
        print("No rebalance_log.json found. Run --force first.")
        return 1
    with open(REBAL_LOG_PATH, "r") as f:
        records = json.load(f)
    if not records:
        print("rebalance_log.json is empty.")
        return 1
    last = records[-1]
    print(f"Most recent rebalance: {last['date']}")
    print("Target weights:")
    for t, w in sorted(last["target_weights"].items(), key=lambda x: -x[1]):
        print(f"  {t:6s} {w*100:6.2f}%")
    ans = input("\nWere these trades executed as reported? (y/n/manual): ").strip().lower()
    if ans == "y":
        save_holdings(last["target_weights"])
        print(f"OK — holdings.json updated to {last['date']} targets.")
        return 0
    if ans == "manual":
        print("Enter weights as 'TICKER WEIGHT' pairs, one per line. Blank to finish.")
        new: dict[str, float] = {}
        while True:
            line = input("> ").strip()
            if not line:
                break
            parts = line.split()
            if len(parts) != 2:
                print("  expected 'TICKER WEIGHT'")
                continue
            try:
                new[parts[0].upper()] = float(parts[1])
            except ValueError:
                print("  weight must be numeric")
        if new:
            save_holdings(new)
            print("holdings.json updated from manual entry.")
            return 0
    print("Aborted — holdings.json unchanged.")
    return 1


# ---------- main rebalance -------------------------------------------------

def cmd_rebalance(args) -> int:
    cfg = load_config(ROOT)
    today = pd.Timestamp(args.date) if args.date else pd.Timestamp.utcnow().normalize().tz_localize(None)
    today = today.normalize()
    warnings: list[str] = []

    # --- STEP 1 — schedule check ------------------------------------------
    ltd = last_trading_day_of_month(today)
    is_rebal_day = today.normalize() == ltd.normalize()
    if not is_rebal_day and not args.force:
        nxt = next_rebalance_date(today)
        print(f"Not a rebalance day ({today.date()}). Next rebalance: {nxt.date()}")
        return 0

    # --- STEP 2 — FOMC deferral -------------------------------------------
    in_fomc, deferred_to = fomc_defer_check(today, cfg)
    if in_fomc and not args.force:
        msg = (
            f"FOMC deferral active. Rebalance deferred to "
            f"{deferred_to.date() if deferred_to is not None else '(unknown)'}. "
            f"Re-run on that date with --force."
        )
        print(msg)
        log.info("fomc_defer: today=%s deferred_to=%s", today.date(),
                 deferred_to.date() if deferred_to is not None else None)
        append_rebalance_log({
            "date": today.date().isoformat(),
            "event": "fomc_defer",
            "deferred_to": deferred_to.date().isoformat() if deferred_to is not None else None,
        })
        return 0

    # --- STEP 3 — refresh data --------------------------------------------
    if args.no_refresh:
        print("(data refresh skipped)")
        status = {}
    else:
        print("Refreshing data ...")
        status = refresh_and_rebuild(ROOT)
        if status.get("prices", {}).get("status") == "error":
            print("!! Yahoo prices unavailable. Defer rebalance 1 trading day. Retry tomorrow.")
            return 2
        for k in ("prices", "macro", "fomc"):
            s = status.get(k, {})
            if s.get("status") == "degraded":
                warnings.append(f"{k}: degraded ({s.get('stale') or s.get('errors')})")
            elif s.get("status") not in ("ok", None):
                warnings.append(f"{k}: {s.get('status')}")
    print(f"Data freshness: "
          f"prices={status.get('prices',{}).get('status','?')}, "
          f"macro={status.get('macro',{}).get('status','?')}, "
          f"fomc={status.get('fomc',{}).get('status','?')}")

    # --- STEP 4 — compute signal ------------------------------------------
    bundle = load_panel(ROOT, cfg)
    target_date = bundle.dates.max() if not args.date else pd.Timestamp(args.date)
    if target_date not in bundle.dates:
        target_date = bundle.dates[bundle.dates <= target_date].max()
        warnings.append(f"target date snapped to panel: {target_date.date()}")

    core = load_core_feature_list(ROOT, cfg["classifier"]["feature_set"])
    core_present = select_core_features(bundle.df, core)
    pred_reg, _, _ = walk_forward_predict(bundle.df, core_present, cfg)
    pos_idx = bundle.dates.get_indexer([target_date])[0]
    if pos_idx >= 0 and pred_reg[pos_idx] < 0:
        live_pred = predict_at(bundle.df, core_present, cfg, target_date)
        if live_pred >= 0:
            pred_reg[pos_idx] = live_pred
    engine = PortfolioEngine(bundle, pred_reg, cfg)
    rec = engine.decide(pos_idx, pos_idx, deferred=in_fomc)

    # --- STEP 5 — current holdings ----------------------------------------
    current = load_holdings()

    # --- STEP 6 — trades ---------------------------------------------------
    trades = compute_trades(current, rec.target_weights, MIN_TRADE_FRACTION)
    cost_bps = float(cfg.get("transaction_cost_bps", 10))

    # --- STEP 7 — report ---------------------------------------------------
    print()
    print_report(today, rec, current, trades, cost_bps, warnings, fomc_deferred=in_fomc)

    # --- STEP 8 — persist --------------------------------------------------
    log_entry = {
        "date": today.date().isoformat(),
        "panel_date": target_date.date().isoformat(),
        "target_weights": {k: float(v) for k, v in rec.target_weights.items() if v > 1e-6},
        "current_weights": {k: float(v) for k, v in current.items()},
        "trades": {k: float(v) for k, v in trades.items()},
        "regime_info": {
            "current": int(rec.current_regime),
            "predicted": int(rec.predicted_regime),
        },
        "lookback": int(rec.lookback_used),
        "sma_gate_fired": bool(rec.sma_gate_fired),
        "sma_distance": float(rec.sma_distance),
        "fomc_deferred": bool(in_fomc),
        "data_warnings": warnings,
        "top1": rec.top1,
        "topk": list(rec.topk),
        "forced": bool(args.force),
    }
    append_rebalance_log(log_entry)

    # --- STEP 9 — hand-off message ----------------------------------------
    print()
    print("Review the report above. Execute trades manually via your broker.")
    print("Run 'python scripts/run_rebalance.py --confirm' after execution")
    print("to update holdings.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Monthly rebalance (MASTER_ARCHITECTURE §2.7/§2.8)")
    parser.add_argument("--force", action="store_true", help="run even if today is not a rebalance day")
    parser.add_argument("--confirm", action="store_true", help="confirm the last rebalance was executed")
    parser.add_argument("--status", action="store_true", help="show current holdings and next rebalance")
    parser.add_argument("--date", default=None, help="override today's date (YYYY-MM-DD)")
    parser.add_argument("--no-refresh", action="store_true", help="skip live data refresh")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    if args.status:
        return cmd_status()
    if args.confirm:
        return cmd_confirm()
    return cmd_rebalance(args)


if __name__ == "__main__":
    raise SystemExit(main())
