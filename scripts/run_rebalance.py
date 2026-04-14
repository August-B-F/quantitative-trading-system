"""Monthly rebalance orchestrator — 9 strategies, 9 Alpaca paper accounts.

Each strategy trades in its own dedicated paper account. There is no
aggregation; per-strategy P&L comes directly from Alpaca account equity.

Flags:
    --force         run even if today is not a rebalance day
    --execute       actually submit orders (otherwise dry run)
    --no-refresh    skip live data refresh
    --strategy N    run only strategy N (1..9)
    --status        print current status of all 9 accounts and exit
    --kill-all      liquidate all positions in all 9 accounts
    --date YYYY-MM-DD  override "today" (testing)
"""
from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import sys
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))


def _load_dotenv() -> None:
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())

_load_dotenv()

from data.pipeline import load_config, load_panel, refresh_and_rebuild  # noqa: E402
from features.engineer import load_core_feature_list, select_core_features  # noqa: E402
from model.classifier import walk_forward_predict  # noqa: E402
from strategy.portfolio import StrategyRunner  # noqa: E402
from execution.alpaca_client import AlpacaPaperClient  # noqa: E402
from execution.executor import StrategyExecutor, DEFAULT_INITIAL_CAPITAL  # noqa: E402

REBAL_LOG_PATH = ROOT / "logs" / "rebalance_log.json"
MONTHLY_CSV = ROOT / "logs" / "monthly_comparison.csv"
ACCOUNTS_PATH = ROOT / "configs" / "accounts.yaml"

log = logging.getLogger("rebalance")


def load_accounts_cfg() -> dict:
    with open(ACCOUNTS_PATH, "r") as f:
        return yaml.safe_load(f)


def build_client_for(entry: dict) -> tuple[AlpacaPaperClient | None, str | None]:
    key = os.environ.get(entry["alpaca_key_env"], "").strip()
    sec = os.environ.get(entry["alpaca_secret_env"], "").strip()
    if not key or not sec:
        return None, f"missing {entry['alpaca_key_env']}/{entry['alpaca_secret_env']}"
    return AlpacaPaperClient(key, sec), None


def assert_paper_mode_or_exit() -> None:
    val = os.environ.get("ALPACA_PAPER_MODE", "").strip().lower()
    if val != "true":
        print("ERROR: ALPACA_PAPER_MODE must be 'true' in .env to submit orders.")
        sys.exit(2)


# ---------- NYSE calendar ---------------------------------------------------

def _nyse():
    import pandas_market_calendars as mcal
    return mcal.get_calendar("NYSE")


def trading_days(start, end) -> pd.DatetimeIndex:
    sched = _nyse().schedule(start_date=start, end_date=end)
    return pd.DatetimeIndex(sched.index).tz_localize(None).normalize()


def last_trading_day_of_month(today: pd.Timestamp) -> pd.Timestamp:
    first = today.replace(day=1)
    last_cal = (first + pd.offsets.MonthEnd(0)).normalize()
    return trading_days(first, last_cal)[-1]


def next_rebalance_date(today: pd.Timestamp) -> pd.Timestamp:
    ltd = last_trading_day_of_month(today)
    if today <= ltd:
        return ltd
    nxt = (today + pd.offsets.MonthBegin(1)).normalize()
    return last_trading_day_of_month(nxt)


# ---------- shared compute --------------------------------------------------

def _load_shared_state():
    cfg = load_config(ROOT)
    bundle = load_panel(ROOT, cfg)
    cache = ROOT / "tests" / "autonomous" / "cache" / "pred_reg.pkl"
    if cache.exists():
        import pickle
        with open(cache, "rb") as f:
            pred_reg, test_dates = pickle.load(f)
    else:
        core = load_core_feature_list(ROOT, cfg["classifier"]["feature_set"])
        core_present = select_core_features(bundle.df, core)
        pred_reg, test_dates, _ = walk_forward_predict(bundle.df, core_present, cfg)
    # Extend test_dates with the latest panel date so each strategy's
    # weights_history includes today's signal (cached pred_reg covers full panel).
    latest = bundle.dates.max()
    if latest not in set(test_dates):
        test_dates = pd.DatetimeIndex(list(test_dates) + [latest]).sort_values()
    return cfg, bundle, pred_reg, test_dates


def compute_target_weights(runner, bundle, pred_reg, test_dates, cfg_global, as_of):
    runner.run(bundle, pred_reg, test_dates, cfg_global)
    return runner.compute_signal(as_of)


# ---------- log writers -----------------------------------------------------

def append_rebalance_log(entry: dict) -> None:
    REBAL_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    records = []
    if REBAL_LOG_PATH.exists():
        try:
            records = json.loads(REBAL_LOG_PATH.read_text())
        except (json.JSONDecodeError, ValueError):
            records = []
    records.append(entry)
    REBAL_LOG_PATH.write_text(json.dumps(records, indent=2, default=str))


def write_monthly_comparison_row(date_iso: str, equities: dict, spy_return: float | None) -> None:
    MONTHLY_CSV.parent.mkdir(parents=True, exist_ok=True)
    headers = ["date"] + [f"s{i}_equity" for i in range(1, 10)] + ["spy_return"]
    rows: list[dict] = []
    if MONTHLY_CSV.exists():
        with open(MONTHLY_CSV, "r", newline="") as f:
            rows = list(csv.DictReader(f))
        rows = [r for r in rows if r.get("date") != date_iso]
    new_row = {"date": date_iso, "spy_return": "" if spy_return is None else f"{spy_return:.6f}"}
    for i in range(1, 10):
        v = equities.get(i)
        new_row[f"s{i}_equity"] = "" if v is None else f"{v:.2f}"
    rows.append(new_row)
    rows.sort(key=lambda r: r["date"])
    with open(MONTHLY_CSV, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=headers)
        w.writeheader()
        w.writerows(rows)


# ---------- report ----------------------------------------------------------

TIER_TITLE = {
    "confident": "CONFIDENT TIER",
    "neutral":   "NEUTRAL TIER",
    "skeptical": "SKEPTICAL TIER",
}


def _fmt_weights(w: dict) -> str:
    items = sorted(((t, v) for t, v in w.items() if v > 1e-4), key=lambda x: -x[1])[:4]
    return " / ".join(f"{t} {v*100:.1f}%" for t, v in items)


def print_rebalance_report(today, results: list[dict]) -> None:
    bar = "=" * 70
    print(bar)
    print(f"  MONTHLY REBALANCE - {today.date()}")
    print(bar)
    by_tier: dict[str, list[dict]] = {"confident": [], "neutral": [], "skeptical": []}
    for r in results:
        by_tier.setdefault(r["tier"], []).append(r)
    for tier, items in by_tier.items():
        if not items:
            continue
        title = TIER_TITLE[tier]
        print(f"\n  +-- {title} " + "-" * (52 - len(title)) + "+")
        for r in sorted(items, key=lambda x: x["slot"]):
            equity = r.get("equity")
            eq_str = f"${equity:,.0f}" if isinstance(equity, (int, float)) else "-"
            print(f"  | S{r['slot']} {r['name']:<18} Equity: {eq_str}")
            if "error" in r and not r.get("target_weights"):
                print(f"  |   ERROR: {r['error']}")
                continue
            if r.get("target_weights"):
                print(f"  |   Signal: {_fmt_weights(r['target_weights'])}")
            orders = r.get("orders", [])
            if orders:
                trade_str = ", ".join(f"{o['side'].upper()} {o['ticker']}" for o in orders[:6])
                print(f"  |   Trades: {trade_str}")
            else:
                print("  |   Trades: (none)")
            if "error" in r:
                print(f"  |   Note:   {r['error']}")
            submit_errs = r.get("submit_errors") or []
            if submit_errs:
                print(f"  |   SUBMIT ERRORS ({len(submit_errs)}):")
                for se in submit_errs:
                    print(
                        f"  |     - {se['side'].upper()} {se['ticker']} "
                        f"${se['notional']:.2f}: {se['error_message']}"
                    )
            status = "DRY RUN" if r.get("dry_run") else (
                "EXECUTED" if r.get("success") else "PARTIAL/FAILED"
            )
            print(f"  |   Status: {status}")
        print("  +" + "-" * 68 + "+")

    print("\n  SUMMARY:")
    print("  | # | Strategy        | Top hold        | Turnover | Est cost |")
    print("  |---|-----------------|-----------------|----------|----------|")
    for r in sorted(results, key=lambda x: x["slot"]):
        tw = r.get("target_weights", {}) or {}
        top = max(tw.items(), key=lambda x: x[1]) if tw else ("—", 0.0)
        equity = r.get("equity") or DEFAULT_INITIAL_CAPITAL
        turnover = sum(abs(o["notional"]) for o in r.get("orders", []))
        turnover_pct = turnover / equity if equity else 0.0
        cost = turnover * 10 / 1e4
        print(f"  | {r['slot']} | {r['name']:<15} | {top[0]:<5} {top[1]*100:5.1f}%     "
              f"| {turnover_pct*100:6.1f}% | ${cost:7.2f} |")
    print(bar)


def print_status_report(today, statuses: list[dict]) -> None:
    bar = "=" * 70
    print(bar)
    print(f"  PORTFOLIO STATUS - {today.date()}")
    print(bar)
    print("  | # | Strategy        | Equity     | P&L       | Return | Top Hold      |")
    print("  |---|-----------------|------------|-----------|--------|---------------|")
    for s in sorted(statuses, key=lambda x: x["slot"]):
        if "error" in s:
            print(f"  | {s['slot']} | {s['name']:<15} | (error: {s['error'][:40]})")
            continue
        eq = s["equity"]; pnl = s["total_pnl"]; ret = s["return_pct"] * 100
        weights = s.get("weights", {})
        top = max(weights.items(), key=lambda x: x[1]) if weights else ("CASH", 0.0)
        print(f"  | {s['slot']} | {s['name']:<15} | ${eq:9,.0f} | ${pnl:+8,.0f} "
              f"| {ret:+5.1f}% | {top[0]:<5} {top[1]*100:4.1f}% |")
    nxt = next_rebalance_date(today)
    print(f"\n  Next rebalance: {nxt.date()}  ({(nxt - today).days} days)")
    print(bar)


# ---------- subcommands -----------------------------------------------------

def cmd_status() -> int:
    accounts_cfg = load_accounts_cfg()
    initial = float(accounts_cfg.get("initial_capital", DEFAULT_INITIAL_CAPITAL))
    today = pd.Timestamp.utcnow().normalize().tz_localize(None)
    statuses = []
    for slug, entry in accounts_cfg["strategies"].items():
        client, err = build_client_for(entry)
        if err:
            statuses.append({"slot": entry["slot"], "name": entry["name"], "error": err})
            continue
        execu = StrategyExecutor(entry["name"], client, initial_capital=initial)
        s = execu.get_status()
        s["slot"] = entry["slot"]
        s["name"] = entry["name"]
        statuses.append(s)
    print_status_report(today, statuses)
    return 0


def cmd_kill_all() -> int:
    assert_paper_mode_or_exit()
    accounts_cfg = load_accounts_cfg()
    print("This will liquidate ALL 9 paper accounts.")
    confirm = input("Type CONFIRM to proceed: ").strip()
    if confirm != "CONFIRM":
        print("Aborted.")
        return 1
    results = []
    for slug, entry in accounts_cfg["strategies"].items():
        client, err = build_client_for(entry)
        if err:
            print(f"  S{entry['slot']} {entry['name']}: skip ({err})")
            continue
        execu = StrategyExecutor(entry["name"], client)
        r = execu.kill_all()
        results.append({"slot": entry["slot"], "name": entry["name"], **r})
        print(f"  S{entry['slot']} {entry['name']}: closed {len(r['closed'])} positions")
    append_rebalance_log({
        "date": pd.Timestamp.utcnow().date().isoformat(),
        "event": "kill_all",
        "results": results,
    })
    return 0


def cmd_rebalance(args) -> int:
    accounts_cfg = load_accounts_cfg()
    initial = float(accounts_cfg.get("initial_capital", DEFAULT_INITIAL_CAPITAL))
    today = pd.Timestamp(args.date) if args.date else pd.Timestamp.utcnow().normalize().tz_localize(None)
    today = today.normalize()

    ltd = last_trading_day_of_month(today)
    if today.normalize() != ltd.normalize() and not args.force:
        nxt = next_rebalance_date(today)
        print(f"Not a rebalance day ({today.date()}). Next: {nxt.date()}")
        return 0

    if args.execute:
        assert_paper_mode_or_exit()

    warnings: list[str] = []
    if not args.no_refresh:
        print("Refreshing data ...")
        status = refresh_and_rebuild(ROOT)
        if status.get("prices", {}).get("status") == "error":
            print("!! Yahoo prices unavailable. Defer.")
            return 2
        for k in ("prices", "macro", "fomc"):
            s = status.get(k, {})
            if s.get("status") == "degraded":
                warnings.append(f"{k}: degraded ({s.get('stale') or s.get('errors')})")

    print("Loading panel + classifier ...")
    cfg_global, bundle, pred_reg, test_dates = _load_shared_state()
    as_of = bundle.dates.max()

    items = list(accounts_cfg["strategies"].items())
    if args.strategy is not None:
        items = [(slug, e) for slug, e in items if e["slot"] == args.strategy]
        if not items:
            print(f"No strategy with slot {args.strategy}")
            return 1

    results: list[dict] = []
    log_strategies: dict[str, dict] = {}

    for slug, entry in items:
        print(f"\n>> S{entry['slot']} {entry['name']}: computing signal ...")
        runner = StrategyRunner(ROOT / entry["config"])
        try:
            target = compute_target_weights(runner, bundle, pred_reg, test_dates, cfg_global, as_of)
        except Exception as exc:
            log.exception("signal failed for %s", entry["name"])
            results.append({
                "slot": entry["slot"], "name": entry["name"], "tier": entry["tier"],
                "error": f"signal: {exc}", "target_weights": {}, "dry_run": not args.execute,
            })
            continue

        client, err = build_client_for(entry)
        if err:
            results.append({
                "slot": entry["slot"], "name": entry["name"], "tier": entry["tier"],
                "target_weights": target, "orders": [], "dry_run": True,
                "equity": None, "error": err,
            })
            log_strategies[slug] = {"target_weights": target, "error": err}
            continue

        execu = StrategyExecutor(entry["name"], client, initial_capital=initial)
        rb = execu.execute_rebalance(target, dry_run=not args.execute)
        rb["slot"] = entry["slot"]
        rb["name"] = entry["name"]
        rb["tier"] = entry["tier"]
        results.append(rb)
        log_strategies[slug] = {
            "target_weights": target,
            "current_weights": rb.get("current_weights", {}),
            "orders": rb.get("orders", []),
            "post_rebalance_weights": rb.get("post_rebalance_weights"),
            "post_rebalance_equity": rb.get("post_rebalance_equity"),
            "slippage_bps": rb.get("slippage_bps"),
            "executed": not rb.get("dry_run", True),
            "success": rb.get("success", False),
            "error": rb.get("error"),
            "submit_errors": rb.get("submit_errors", []),
        }

    print_rebalance_report(today, results)

    append_rebalance_log({
        "date": today.date().isoformat(),
        "executed": bool(args.execute),
        "strategies": log_strategies,
        "data_warnings": warnings,
    })

    equities = {r["slot"]: r.get("equity") for r in results if r.get("equity") is not None}
    if equities:
        write_monthly_comparison_row(today.date().isoformat(), equities, spy_return=None)

    if not args.execute:
        print("\nDRY RUN — pass --execute to submit orders.")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="9-strategy paper rebalance orchestrator")
    p.add_argument("--force", action="store_true")
    p.add_argument("--execute", action="store_true")
    p.add_argument("--no-refresh", action="store_true")
    p.add_argument("--strategy", type=int, default=None, help="slot 1..9")
    p.add_argument("--status", action="store_true")
    p.add_argument("--kill-all", action="store_true")
    p.add_argument("--date", default=None)
    args = p.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    if args.status:
        return cmd_status()
    if args.kill_all:
        return cmd_kill_all()
    return cmd_rebalance(args)


if __name__ == "__main__":
    raise SystemExit(main())
