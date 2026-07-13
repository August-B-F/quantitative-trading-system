"""Monthly rebalance orchestrator — 9 strategies, 9 Alpaca paper accounts.

Each strategy trades in its own dedicated paper account. There is no
aggregation; per-strategy P&L comes directly from Alpaca account equity.

An accounts.yaml strategy entry may additionally set ``engine: rotation``:
that entry is routed through the tranched rotation compute path (signals
from src/strategy/rotation.py on the clean price parquets; rebalances on
month-end + tranche-offset trading days; tranche state persisted at
logs/tranche_state.json) instead of StrategyRunner. See the comment block
in configs/strategies/candidate_blend_rotation.yaml for the entry shape.
No entry uses it until the operator wires one — the path is dormant.

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

import numpy as np
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

from backtest.ledger import load_prices as load_price_frames  # noqa: E402
from data.pipeline import load_config, load_panel, refresh_and_rebuild  # noqa: E402
from features.engineer import load_core_feature_list, select_core_features  # noqa: E402
from model.classifier import walk_forward_predict  # noqa: E402
from strategy import rotation  # noqa: E402
from strategy.portfolio import StrategyRunner  # noqa: E402
from execution.alpaca_client import AlpacaPaperClient  # noqa: E402
from execution.executor import StrategyExecutor, DEFAULT_INITIAL_CAPITAL  # noqa: E402
from risk.notify import send_alert  # noqa: E402

REBAL_LOG_PATH = ROOT / "logs" / "rebalance_log.json"
MONTHLY_CSV = ROOT / "logs" / "monthly_comparison.csv"
ACCOUNTS_PATH = ROOT / "configs" / "accounts.yaml"
LOCK_PATH = ROOT / "logs" / "rebalance.lock"
# Tranche state for rotation-engine strategies (accounts.yaml `engine: rotation`),
# keyed by strategy slug. Written atomically (temp file + os.replace).
TRANCHE_STATE_PATH = ROOT / "logs" / "tranche_state.json"

# Hard freshness gate: refuse to trade when the panel as_of lags the last
# NYSE trading day by more than this many trading days.
MAX_SIGNAL_LAG_TD = 3
# A lock older than this is considered abandoned (crash without cleanup).
LOCK_MAX_AGE_HOURS = 12

log = logging.getLogger("rebalance")


# single-instance lock

def _pid_alive(pid: int) -> bool | None:
    """Tri-state liveness: True=alive, False=dead, None=cannot determine."""
    if pid <= 0:
        return False
    try:
        import psutil
    except ImportError:
        return None
    try:
        return psutil.pid_exists(pid)
    except Exception:
        return None


def acquire_lock() -> bool:
    """Acquire logs/rebalance.lock. Returns False if a live run holds it.

    A verifiably ALIVE owner blocks regardless of lock age — a normal
    scheduled run legitimately holds the lock ~11h+ (04:15 Stockholm start,
    wait for the 15:30 open, then up-to-600s fill waits x 9 strategies), so
    age alone must never justify stealing the lock from a live process.
    Age only breaks ties when liveness cannot be determined.
    """
    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    if LOCK_PATH.exists():
        pid, ts = -1, None
        try:
            payload = json.loads(LOCK_PATH.read_text())
            pid = int(payload.get("pid", -1))
            ts = pd.Timestamp(payload.get("timestamp"))
        except (json.JSONDecodeError, ValueError, TypeError):
            pass
        now = pd.Timestamp.utcnow().tz_localize(None)
        fresh = ts is not None and (now - ts) < pd.Timedelta(hours=LOCK_MAX_AGE_HOURS)
        alive = _pid_alive(pid)
        if alive is True or (alive is None and fresh):
            log.error("lock held by pid=%s since %s (alive=%s)", pid, ts, alive)
            return False
        log.warning("removing stale lock (pid=%s, ts=%s, alive=%s)", pid, ts, alive)
    LOCK_PATH.write_text(json.dumps({
        "pid": os.getpid(),
        "timestamp": pd.Timestamp.utcnow().tz_localize(None).isoformat(),
    }))
    return True


def release_lock() -> None:
    """Delete the lock file (best effort)."""
    try:
        LOCK_PATH.unlink(missing_ok=True)
    except OSError as exc:
        log.warning("could not remove lock: %s", exc)


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


# NYSE calendar

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


def signal_is_fresh(as_of, today, max_lag_td: int = MAX_SIGNAL_LAG_TD) -> bool:
    """True when `as_of` lags the last NYSE trading day <= `today` by at most
    `max_lag_td` trading days.

    Pure function — the hard freshness gate in cmd_rebalance and the tests
    both call this.
    """
    as_of = pd.Timestamp(as_of).normalize()
    today = pd.Timestamp(today).normalize()
    if as_of >= today:
        return True
    tdays = trading_days(today - pd.Timedelta(days=45), today)
    if len(tdays) == 0:
        return True  # calendar unavailable — do not block on gate infrastructure
    lag_td = int((tdays > as_of).sum())
    return lag_td <= max_lag_td


# shared compute

# A retrain cache older than this is discarded (quarterly cadence + margin).
PRED_CACHE_MAX_AGE_DAYS = 100


def _load_pred_cache(cache: Path, bundle):
    """Load and DATE-ALIGN the retrain cache onto the current panel.

    Cache format (written by scripts/run_retrain.py): a 3-tuple
    ``(pred_reg, test_dates, dates)`` where ``dates`` is the panel index the
    predictions were computed on. Alignment is by DATE, so the cache stays
    valid as live_extend grows the panel day over day; dates the cache does
    not cover get -1 (select_momentum's stable/persistence fallback — the
    same value a recompute yields beyond the last completed fold). Legacy
    2-tuple caches carry no dates and are rejected.

    Returns ``(pred_reg, test_dates)`` aligned to ``bundle.dates``, or None.
    """
    import pickle
    import time as _time
    age_days = (_time.time() - cache.stat().st_mtime) / 86400
    if age_days > PRED_CACHE_MAX_AGE_DAYS:
        log.warning("pred_reg cache is %.0f days old (max %d) — recomputing",
                    age_days, PRED_CACHE_MAX_AGE_DAYS)
        return None
    try:
        # Trusted local artifact — written by scripts/run_retrain.py in
        # this repo, never sourced from the network.
        with open(cache, "rb") as f:
            payload = pickle.load(f)
    except (pickle.UnpicklingError, ValueError, EOFError, OSError) as exc:
        log.warning("pred_reg cache unreadable (%s) — recomputing", exc)
        return None
    if not (isinstance(payload, tuple) and len(payload) == 3):
        log.warning("pred_reg cache is the legacy dateless format — recomputing")
        return None
    pred_raw, test_dates, cached_dates = payload
    try:
        cached_dates = pd.DatetimeIndex(cached_dates)
        test_dates = pd.DatetimeIndex(test_dates)
    except (TypeError, ValueError):
        return None
    if len(cached_dates) != len(np.asarray(pred_raw)) or len(test_dates) == 0:
        log.warning("pred_reg cache internally inconsistent — recomputing")
        return None
    overlap = cached_dates.isin(bundle.dates)
    if overlap.mean() < 0.99:
        log.warning("pred_reg cache dates diverge from panel calendar "
                    "(%.1f%% overlap) — recomputing", overlap.mean() * 100)
        return None
    pred = (
        pd.Series(np.asarray(pred_raw), index=cached_dates)
        .reindex(bundle.dates)
        .fillna(-1)
        .astype(int)
        .values
    )
    test_dates = test_dates[test_dates.isin(bundle.dates)]
    log.info("pred_reg cache (age %.0fd) date-aligned onto panel: "
             "%d cached dates -> %d panel rows", age_days,
             len(cached_dates), len(bundle.dates))
    return pred, test_dates


def _load_shared_state():
    cfg = load_config(ROOT)
    bundle = load_panel(ROOT, cfg, live_extend=True)
    cache = ROOT / "tests" / "autonomous" / "cache" / "pred_reg.pkl"
    use_cache = False
    pred_reg = test_dates = None
    if cache.exists():
        loaded = _load_pred_cache(cache, bundle)
        if loaded is not None:
            pred_reg, test_dates = loaded
            use_cache = True
    if not use_cache:
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
    weights = runner.compute_signal(as_of)
    # Belt-and-braces: assert the decision actually served is fresh. The
    # panel-level gate can pass while a strategy's weights_history ends
    # earlier (e.g. a walk-forward change drops the test_dates extension) —
    # that failure mode is exactly the 2026-Q2 freeze, so it must raise, not
    # silently serve an old decision.
    _, weights_history = runner._cached_run
    as_of_ts = pd.Timestamp(as_of)
    decision_date = max(
        (rd for rd, _ in weights_history if rd <= as_of_ts), default=None
    )
    if decision_date is None or not signal_is_fresh(decision_date, as_of_ts):
        raise RuntimeError(
            f"stale decision for {runner.name}: last weights date "
            f"{decision_date} lags as_of {as_of_ts.date()} beyond "
            f"{MAX_SIGNAL_LAG_TD} trading days"
        )
    return weights


# rotation-engine compute path (tranched candidate)
#
# An accounts.yaml strategy entry with `engine: rotation` is NOT run through
# StrategyRunner. Its signal comes from strategy.rotation.blend_rotation_weights
# on the clean price parquets, it rebalances on month-end + tranche-offset
# trading days (offsets from the strategy yaml's rebalance.tranches), and the
# account-level target is the equal-weight average of the 4 tranches' weights
# (state persisted at logs/tranche_state.json). The target then feeds the
# EXISTING StrategyExecutor unchanged.

def _load_strategy_yaml(entry: dict) -> dict:
    with open(ROOT / entry["config"], "r") as f:
        return yaml.safe_load(f) or {}


def _rotation_offsets(strategy_cfg: dict) -> tuple[int, ...]:
    """Tranche offsets from the strategy yaml (rebalance.tranches), else spec default."""
    tranches = (strategy_cfg.get("rebalance") or {}).get("tranches")
    if not tranches:
        return tuple(rotation.TRANCHE_OFFSETS)
    return tuple(int(k) for k in tranches)


def rotation_tranche_for_today(today, offsets, force: bool = False) -> int | None:
    """Which tranche offset k a rotation-engine strategy updates on `today`.

    Decision days are month-end + k NYSE trading days for each k in
    `offsets` (strategy.rotation.tranche_decision_days). Returns the matching
    k, or None when today is not a decision day. Under `force`, falls back to
    the tranche of the MOST RECENT decision day at or before today, so a
    forced run refreshes the tranche whose decision is newest.
    """
    today = pd.Timestamp(today).normalize()
    # 70 calendar days back always covers every month-end whose +15-trading-day
    # offset could land on `today`; extending to the calendar month end keeps
    # the final month complete so its true month-end (not a partial-month last
    # row) anchors the offsets.
    start = (today - pd.Timedelta(days=70)).date()
    end = (today + pd.offsets.MonthEnd(0)).date()
    cal = trading_days(start, end)
    decision = rotation.tranche_decision_days(cal, offsets)
    if today in decision:
        return int(decision[today])
    if not force:
        return None
    past = [d for d in decision if d <= today]
    if not past:
        return int(offsets[0])
    return int(decision[max(past)])


def load_tranche_state(path: Path = TRANCHE_STATE_PATH) -> dict:
    """Read the tranche-state JSON. Missing file -> {} (fresh state is a
    legitimate first run: every tranche defaults to 100% SHY). A CORRUPT file
    raises ValueError — silently resetting live tranche weights to SHY would
    trade the account toward a fabricated target."""
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def save_tranche_state(state: dict, path: Path = TRANCHE_STATE_PATH) -> None:
    """Atomic write: serialize to a temp file in the same dir, then os.replace."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(state, indent=2, sort_keys=True))
    os.replace(tmp, path)


def compute_rotation_target(
    prices: dict,
    as_of,
    state: dict,
    tranche_k: int,
    offsets,
    universe: list | None = None,
) -> tuple[dict, dict]:
    """(account_target, new_tranche_weights) for a rotation-engine strategy.

    Tranche `tranche_k` is recomputed at `as_of` via the frozen blend_126_252
    spec; the account-level target is the equal-weight average of all
    tranches with tranche_k replaced (rotation.account_target_from_state).
    """
    new_w = rotation.blend_rotation_weights(
        prices, pd.Timestamp(as_of), universe=universe
    )
    target = rotation.account_target_from_state(state, tranche_k, new_w, offsets)
    return target, new_w


def _run_rotation_entry(
    slug: str,
    entry: dict,
    rotation_active: dict,
    today: pd.Timestamp,
    initial: float,
    args,
    results: list,
    log_strategies: dict,
) -> None:
    """Signal + execution for one rotation-engine strategy (appends to
    results/log_strategies in the same shapes the classic path uses; the
    account-level target feeds the existing StrategyExecutor unchanged)."""
    tier = entry.get("tier", "candidate")
    if slug not in rotation_active:
        print(f"\n>> S{entry['slot']} {entry['name']}: rotation engine — "
              f"not a tranche decision day, skipped")
        return
    ctx = rotation_active[slug]
    k = ctx["tranche_k"]
    print(f"\n>> S{entry['slot']} {entry['name']}: rotation engine — "
          f"updating tranche +{k} (of offsets {ctx['offsets']}, "
          f"prices as_of {pd.Timestamp(ctx['as_of']).date()}) ...")
    try:
        state_all = load_tranche_state()
        strat_state = state_all.get(slug, {})
        target, new_w = compute_rotation_target(
            ctx["prices"], ctx["as_of"], strat_state, k, ctx["offsets"],
            universe=ctx["universe"],
        )
    except Exception as exc:
        log.exception("rotation signal failed for %s", entry["name"])
        results.append({
            "slot": entry["slot"], "name": entry["name"], "tier": tier,
            "error": f"signal: {exc}", "target_weights": {},
            "dry_run": not args.execute,
        })
        return
    print(f"   tranche +{k} new weights: {_fmt_weights(new_w) or 'SHY 100.0%'}")
    print(f"   account target ({len(ctx['offsets'])}-tranche average): "
          f"{_fmt_weights(target)}")

    client, err = build_client_for(entry)
    if err:
        results.append({
            "slot": entry["slot"], "name": entry["name"], "tier": tier,
            "target_weights": target, "orders": [], "dry_run": True,
            "equity": None, "error": err,
        })
        log_strategies[slug] = {
            "target_weights": target, "error": err,
            "engine": "rotation", "tranche_updated": k,
        }
        return

    execu = StrategyExecutor(entry["name"], client, initial_capital=initial)
    rb = execu.execute_rebalance(target, dry_run=not args.execute)
    rb["slot"] = entry["slot"]
    rb["name"] = entry["name"]
    rb["tier"] = tier
    results.append(rb)

    # Persist the tranche's new weights ONLY after a successful live
    # execution — a dry run or a failed run must not mark the tranche as
    # holding weights the account never traded into.
    executed_ok = (not rb.get("dry_run", True)) and rb.get("success", False)
    if executed_ok:
        strat_state.setdefault("tranches", {})[str(int(k))] = new_w
        strat_state.setdefault("updated", {})[str(int(k))] = today.date().isoformat()
        state_all[slug] = strat_state
        save_tranche_state(state_all)
        print(f"   tranche state saved: {TRANCHE_STATE_PATH.name} "
              f"[{slug}][{k}] @ {today.date()}")

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
        "engine": "rotation",
        "tranche_updated": k,
        "tranche_weights": new_w,
        "tranche_state_saved": executed_ok,
    }


# log writers

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


def _spy_adj_close_asof(date_iso: str) -> float | None:
    """SPY adj_close on the last available bar <= date_iso, or None."""
    p = ROOT / "data" / "clean" / "prices" / "SPY.parquet"
    if not p.exists():
        return None
    try:
        s = pd.read_parquet(p)["adj_close"].dropna().sort_index()
    except (KeyError, OSError, ValueError) as exc:
        log.warning("could not read SPY prices: %s", exc)
        return None
    s = s[s.index <= pd.Timestamp(date_iso)]
    if s.empty:
        return None
    return float(s.iloc[-1])


def compute_spy_return(date_iso: str) -> float | None:
    """SPY adj_close return from the previous monthly_comparison row to `date_iso`."""
    if not MONTHLY_CSV.exists():
        return None
    with open(MONTHLY_CSV, "r", newline="") as f:
        prior = [r["date"] for r in csv.DictReader(f)
                 if r.get("date") and r["date"] < date_iso]
    if not prior:
        return None
    p0 = _spy_adj_close_asof(max(prior))
    p1 = _spy_adj_close_asof(date_iso)
    if p0 is None or p1 is None or p0 <= 0:
        return None
    return p1 / p0 - 1.0


def write_monthly_comparison_row(date_iso: str, equities: dict, spy_return: float | None) -> None:
    MONTHLY_CSV.parent.mkdir(parents=True, exist_ok=True)
    headers = ["date"] + [f"s{i}_equity" for i in range(1, 10)] + ["spy_return", "spy_equity"]
    rows: list[dict] = []
    if MONTHLY_CSV.exists():
        with open(MONTHLY_CSV, "r", newline="") as f:
            rows = list(csv.DictReader(f))
        rows = [r for r in rows if r.get("date") != date_iso]
    new_row = {"date": date_iso, "spy_return": "" if spy_return is None else f"{spy_return:.6f}"}
    for i in range(1, 10):
        v = equities.get(i)
        new_row[f"s{i}_equity"] = "" if v is None else f"{v:.2f}"
    # spy_equity: 100000 compounded from the first row's date. Historic rows
    # are preserved as-is (backfill is handled by a separate script).
    first_date = min([r["date"] for r in rows] + [date_iso])
    if first_date == date_iso:
        spy_equity: float | None = 100000.0
    else:
        p0 = _spy_adj_close_asof(first_date)
        p1 = _spy_adj_close_asof(date_iso)
        spy_equity = 100000.0 * p1 / p0 if (p0 and p1 and p0 > 0) else None
    new_row["spy_equity"] = "" if spy_equity is None else f"{spy_equity:.2f}"
    rows.append(new_row)
    rows.sort(key=lambda r: r["date"])
    with open(MONTHLY_CSV, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=headers, restval="")
        w.writeheader()
        w.writerows(rows)


# report

TIER_TITLE = {
    "confident": "CONFIDENT TIER",
    "neutral":   "NEUTRAL TIER",
    "skeptical": "SKEPTICAL TIER",
    "candidate": "CANDIDATE TIER",
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
        title = TIER_TITLE.get(tier, f"{str(tier).upper()} TIER")
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


# subcommands

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
    # The emergency liquidation switch must NEVER be blocked by the instance
    # lock — a scheduled rebalance legitimately holds it for ~11h while
    # waiting for the open, which is exactly when an operator may need to
    # flatten everything. Warn about the in-flight run and proceed (the
    # interactive CONFIRM below is the safety); do not touch its lock file.
    if LOCK_PATH.exists():
        print("WARNING: logs/rebalance.lock exists — a rebalance run may be "
              "in flight; liquidation can race with its orders.")
        send_alert("kill_all invoked while rebalance lock is held", "WARNING")
    return _cmd_kill_all_locked()


def _cmd_kill_all_locked() -> int:
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
    if not acquire_lock():
        msg = "concurrent run blocked: logs/rebalance.lock is held by a live process"
        print(msg)
        send_alert(msg, "ALERT")
        return 3
    try:
        return _cmd_rebalance_locked(args)
    finally:
        release_lock()


def _cmd_rebalance_locked(args) -> int:
    accounts_cfg = load_accounts_cfg()
    initial = float(accounts_cfg.get("initial_capital", DEFAULT_INITIAL_CAPITAL))
    today = pd.Timestamp(args.date) if args.date else pd.Timestamp.utcnow().normalize().tz_localize(None)
    today = today.normalize()

    ltd = last_trading_day_of_month(today)
    today_is_ltd = today.normalize() == ltd.normalize()

    # Rotation-engine entries (accounts.yaml `engine: rotation`) rebalance on
    # month-end + tranche-offset days, not just month-end; the day determines
    # WHICH tranche updates. With no such entry wired (the default), this map
    # is empty and the flow below is identical to the classic 9-strategy path.
    rotation_active: dict[str, dict] = {}
    for slug, entry in accounts_cfg["strategies"].items():
        if entry.get("engine") != "rotation":
            continue
        try:
            scfg = _load_strategy_yaml(entry)
        except (OSError, yaml.YAMLError) as exc:
            print(f"!! rotation strategy '{slug}': cannot read {entry['config']}: {exc}")
            return 1
        offsets = _rotation_offsets(scfg)
        k = rotation_tranche_for_today(today, offsets, force=args.force)
        if k is not None:
            rotation_active[slug] = {"tranche_k": k, "offsets": offsets, "cfg": scfg}

    if not today_is_ltd and not rotation_active and not args.force:
        nxt = next_rebalance_date(today)
        print(f"Not a rebalance day ({today.date()}). Next: {nxt.date()}")
        return 0

    # Classic (StrategyRunner) strategies keep their month-end-only cadence;
    # on a pure tranche-offset day only the rotation entries trade.
    run_classic = today_is_ltd or args.force

    if args.execute:
        assert_paper_mode_or_exit()
        first_entry = next(iter(accounts_cfg["strategies"].values()))
        probe_client, _ = build_client_for(first_entry)
        if probe_client:
            clock = probe_client.get_clock()
            if not ("error" in clock) and not clock.get("is_open"):
                print(f"Note: market is closed. Executor will wait for open "
                      f"at {clock.get('next_open', '?')}")

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

    cfg_global = bundle = pred_reg = test_dates = None
    as_of = None
    if run_classic:
        print("Loading panel + classifier ...")
        cfg_global, bundle, pred_reg, test_dates = _load_shared_state()
        as_of = bundle.dates.max()

        if bundle.freshness:
            fr = bundle.freshness
            print(f"Panel as_of {as_of.date()} "
                  f"(raw panel ends {fr['panel_raw_max'].date()}, "
                  f"+{fr['extended_days']} live rows)")
            if fr.get("stale_core_features"):
                warnings.append(
                    f"{len(fr['stale_core_features'])} CORE features stale beyond "
                    f"ffill budget (e.g. {fr['stale_core_features'][:3]})"
                )

        # HARD FRESHNESS GATE — never trade a stale signal.
        if not signal_is_fresh(as_of, today, max_lag_td=MAX_SIGNAL_LAG_TD):
            msg = (f"STALE SIGNAL: panel as_of={as_of.date()} is more than "
                   f"{MAX_SIGNAL_LAG_TD} trading days behind {today.date()} — "
                   f"refusing to rebalance")
            print(f"!! {msg}")
            send_alert(msg, "ALERT")
            return 2

        # NaN GUARD — a NaN SMA-gate input must never silently mean risk-off.
        spy_dist_asof = float(bundle.spy_dist_sma200[-1])
        if np.isnan(spy_dist_asof):
            msg = (f"quality_dist_sma200__SPY is NaN at as_of={as_of.date()} — "
                   f"SMA gate input invalid, refusing to rebalance")
            print(f"!! {msg}")
            send_alert(msg, "ALERT")
            return 2

        # STALENESS GUARD on the same input — a forward-filled gate value passes
        # the NaN check while being weeks old; the RAW last-valid date must be
        # as fresh as the rest of the signal.
        spy_dist_lv = (bundle.freshness or {}).get("spy_dist_last_valid")
        if spy_dist_lv is not None and not signal_is_fresh(spy_dist_lv, today):
            msg = (f"quality_dist_sma200__SPY raw data ends {spy_dist_lv.date()} — "
                   f"SMA gate input stale beyond {MAX_SIGNAL_LAG_TD} trading days, "
                   f"refusing to rebalance")
            print(f"!! {msg}")
            send_alert(msg, "ALERT")
            return 2

    items = list(accounts_cfg["strategies"].items())
    if args.strategy is not None:
        items = [(slug, e) for slug, e in items if e["slot"] == args.strategy]
        if not items:
            print(f"No strategy with slot {args.strategy}")
            return 1
    selected_slugs = {slug for slug, _ in items}
    rotation_active = {s: c for s, c in rotation_active.items() if s in selected_slugs}

    # HARD FRESHNESS GATE for the rotation path — SAME rule as the panel gate,
    # applied to the price parquets the rotation signal is computed from: the
    # STALEST required ticker must lag today by at most MAX_SIGNAL_LAG_TD
    # trading days, else refuse to rebalance (exit 2).
    for slug, ctx in rotation_active.items():
        universe = list(ctx["cfg"].get("universe") or rotation.ROTATION_UNIVERSE)
        tickers = sorted(set(universe) | {rotation.GATE_TICKER})
        try:
            prices = load_price_frames(ROOT, tickers)
        except (FileNotFoundError, ValueError) as exc:
            msg = (f"rotation '{slug}': price parquets unavailable ({exc}) — "
                   f"refusing to rebalance")
            print(f"!! {msg}")
            send_alert(msg, "ALERT")
            return 2
        per_max = {t: prices[t]["adj_close"].dropna().index.max() for t in tickers}
        stalest = min(per_max, key=per_max.get)
        if not signal_is_fresh(per_max[stalest], today, max_lag_td=MAX_SIGNAL_LAG_TD):
            msg = (f"STALE PRICES for rotation '{slug}': {stalest} ends "
                   f"{per_max[stalest].date()}, more than {MAX_SIGNAL_LAG_TD} "
                   f"trading days behind {today.date()} — refusing to rebalance")
            print(f"!! {msg}")
            send_alert(msg, "ALERT")
            return 2
        ctx["prices"] = prices
        ctx["universe"] = universe
        # Decision date = freshest price row, clamped to `today` so a
        # backdated --date run never computes a signal on future rows
        # (live, prices never exceed the wall clock and the clamp is a no-op).
        ctx["as_of"] = min(max(per_max.values()), today)

    results: list[dict] = []
    log_strategies: dict[str, dict] = {}

    for slug, entry in items:
        if entry.get("engine") == "rotation":
            _run_rotation_entry(
                slug, entry, rotation_active, today, initial, args,
                results, log_strategies,
            )
            continue
        if not run_classic:
            print(f"\n>> S{entry['slot']} {entry['name']}: skipped "
                  f"(tranche-offset day — classic strategies rebalance at month-end)")
            continue
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
    # The monthly comparison CSV tracks the 9 classic slots at month-end only;
    # pure tranche-offset days must not append near-empty rows to it.
    if equities and run_classic:
        date_iso = today.date().isoformat()
        write_monthly_comparison_row(date_iso, equities,
                                     spy_return=compute_spy_return(date_iso))

    if not args.execute:
        print("\nDRY RUN — pass --execute to submit orders.")
        return 0

    # Executed run: any signal error or failed execution is a hard failure.
    failures: list[str] = []
    for r in results:
        if r.get("dry_run"):
            # only reachable under --execute via signal/credential errors
            if r.get("error"):
                failures.append(f"S{r['slot']}: {r['error']}")
            continue
        if not r.get("success", False):
            failures.append(f"S{r['slot']}: {r.get('error') or 'execution reported failure'}")
    if failures:
        msg = f"rebalance had {len(failures)} strategy failure(s): " + "; ".join(failures)
        print(f"\n!! {msg}")
        send_alert(msg, "ALERT")
        return 1
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
