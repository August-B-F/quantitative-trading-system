"""Daily health check — MASTER_ARCHITECTURE §6.1 / §6.4.

Scheduled for 17:00 ET on trading days (see configs/SCHEDULE.md). Writes
a status report to stdout and appends it to logs/health_check.log.

Exit code:
    0  — OK / WARNING-only (includes architecturally-accepted oecd_cli)
    1  — any ALERT-level finding

Checks:
    1. price freshness     (universe + SPY + VIX + feature_extras)
    2. macro freshness     (key FRED series, per-frequency thresholds)
    3. holdings staleness  (days since last rebalance)
    4. performance         (return vs SPY since last rebalance, drawdown)
    5. classifier age      (warn at 120d, alert at 365d)
    6. SMA200 proximity    (info when SPY within -2% to -6% of SMA200)
    7. rebalance countdown + FOMC conflict
    8. signal freshness    (parquets the live signal path actually consumes)
    9. core staleness      (per-feature last-valid dates for the CORE set)
   10. last rebalance      (success flags in logs/rebalance_log.json)
   11. broker drift        (Alpaca positions vs logged targets; network-optional)
"""
from __future__ import annotations

import json
import pickle
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

PRICES_DIR = ROOT / "data/clean/prices"
MACRO_DIR = ROOT / "data/clean/macro"
FEATURES_PRICE_DIR = ROOT / "data/features/price"
MASTER_PANEL_PATH = ROOT / "data/features/master_panel.parquet"
RETURNS_63D_PATH = FEATURES_PRICE_DIR / "returns_63d.parquet"
QUALITY_SMA200_PATH = FEATURES_PRICE_DIR / "quality_dist_sma200.parquet"
ACCOUNTS_PATH = ROOT / "configs/accounts.yaml"
MODELS_DIR = ROOT / "data/models"
CALENDAR_PATH = ROOT / "data/clean/calendar/events.parquet"
HOLDINGS_PATH = ROOT / "configs/holdings.json"
REBAL_LOG_PATH = ROOT / "logs/rebalance_log.json"
HEALTH_LOG_PATH = ROOT / "logs/health_check.log"
STRATEGY_PATH = ROOT / "configs/strategy.yaml"
DATA_SOURCES_PATH = ROOT / "configs/data_sources.yaml"
ALERTS_PATH = ROOT / "configs/alerts.yaml"

BAR = "=" * 60

# (display_name, parquet filename, frequency)
MACRO_SERIES: list[tuple[str, str, str]] = [
    ("cpi_yoy", "cpi_yoy.parquet", "monthly"),
    ("cpi_mom", "cpi_mom.parquet", "monthly"),
    ("breakeven_5y", "breakeven_5y.parquet", "daily"),
    ("breakeven_10y", "breakeven_10y.parquet", "daily"),
    ("industrial_production", "industrial_production.parquet", "monthly"),
    ("capacity_utilization", "capacity_utilization.parquet", "monthly"),
    ("initial_claims", "initial_claims.parquet", "weekly"),
    ("rail_traffic", "rail_traffic.parquet", "weekly"),
    ("consumer_credit", "consumer_credit_total.parquet", "monthly"),
    ("margin_debt", "margin_debt_fred.parquet", "quarterly"),
    ("wti_crude", "wti_crude.parquet", "daily"),
]
OECD_SERIES = ("oecd_cli", "oecd_cli_us.parquet")

FREQ_MAX_TDAYS = {
    "daily": 3,
    "weekly": 8,
    "monthly": 45,
    "quarterly": 75,
}


# utilities


@dataclass
class Section:
    name: str
    status: str              # "OK" | "WARNING" | "ALERT" | "INFO" | "n/a"
    detail: str
    accepted: bool = False   # architecturally-accepted warnings don't page
    extra: list[str] = field(default_factory=list)


def _nyse():
    import pandas_market_calendars as mcal
    return mcal.get_calendar("NYSE")


def trading_days(start: pd.Timestamp, end: pd.Timestamp) -> pd.DatetimeIndex:
    sched = _nyse().schedule(start_date=start, end_date=end)
    return pd.DatetimeIndex(sched.index).tz_localize(None).normalize()


def trading_days_between(a: pd.Timestamp, b: pd.Timestamp) -> int:
    """Count trading days strictly between a and b (exclusive of a, inclusive of b)."""
    if a >= b:
        return 0
    td = trading_days(a, b)
    return int((td > a).sum())


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


def is_trading_day(today: pd.Timestamp) -> bool:
    return today.normalize() in set(trading_days(today - pd.Timedelta(days=7), today))


def load_yaml(path: Path) -> dict:
    with open(path, "r") as f:
        return yaml.safe_load(f)


def _read_parquet_last_date(path: Path) -> pd.Timestamp | None:
    if not path.exists():
        return None
    df = pd.read_parquet(path)
    if df.empty:
        return None
    # Drop fully-NaN trailing rows (forward-fill artifacts on some macro series
    # hold the real last observation even if rows exist beyond it).
    if df.shape[1] == 1:
        ser = df.iloc[:, 0].dropna()
        if ser.empty:
            return None
        return pd.Timestamp(ser.index.max()).normalize()
    return pd.Timestamp(df.index.max()).normalize()


# checks


def check_prices(today: pd.Timestamp, cfg: dict, alerts_cfg: dict) -> Section:
    """Yahoo price freshness for universe + SPY + VIX + feature_extras."""
    tickers: list[str] = []
    tickers.extend(cfg.get("universe", []))
    tickers.extend(cfg.get("feature_extras", []))
    tickers.append(cfg.get("reference_index", "SPY"))
    tickers.append("_VIX")  # Yahoo ^VIX stored as _VIX.parquet
    tickers = sorted(set(tickers))

    staleness = alerts_cfg.get("staleness", {})
    max_days = int(staleness.get("daily_price_max_days", 2))

    latest_seen: pd.Timestamp | None = None
    alert_tickers: list[str] = []
    missing: list[str] = []
    ok_count = 0

    for t in tickers:
        path = PRICES_DIR / f"{t}.parquet"
        if not path.exists():
            missing.append(t)
            continue
        last = _read_parquet_last_date(path)
        if last is None:
            missing.append(t)
            continue
        if latest_seen is None or last > latest_seen:
            latest_seen = last
        gap = trading_days_between(last, today)
        if gap > max_days:
            alert_tickers.append(f"{t}({gap}td)")
        else:
            ok_count += 1

    total = len(tickers)
    latest_str = latest_seen.date().isoformat() if latest_seen else "?"
    if missing or alert_tickers:
        det_bits: list[str] = []
        if missing:
            det_bits.append(f"missing {len(missing)}: {','.join(missing[:4])}")
        if alert_tickers:
            det_bits.append(f"{len(alert_tickers)} >{max_days}td stale: {','.join(alert_tickers[:4])}")
        return Section("PRICES", "ALERT", "; ".join(det_bits))
    return Section("PRICES", "OK", f"{ok_count}/{total} tickers current, latest {latest_str}")


def check_macro(today: pd.Timestamp, alerts_cfg: dict) -> Section:
    """FRED series freshness per frequency bucket; oecd_cli handled specially.

    Macro staleness is a WARNING, not an ALERT — per §6.4, only price
    feeds trigger IMMEDIATE escalation.
    """
    stale: list[str] = []
    missing: list[str] = []
    checked = 0

    for name, fname, freq in MACRO_SERIES:
        path = MACRO_DIR / fname
        last = _read_parquet_last_date(path)
        if last is None:
            missing.append(name)
            continue
        checked += 1
        max_t = FREQ_MAX_TDAYS.get(freq, 45)
        gap = trading_days_between(last, today)
        if gap > max_t:
            stale.append(f"{name} {gap}td>{max_t}td")

    # oecd_cli — architecturally stale, always a WARNING
    oecd_name, oecd_file = OECD_SERIES
    oecd_last = _read_parquet_last_date(MACRO_DIR / oecd_file)
    oecd_accepted = False
    oecd_line: str | None = None
    if oecd_last is not None:
        age_days = (today.normalize() - oecd_last.normalize()).days
        warn_days = int(alerts_cfg.get("warning", {}).get("oecd_cli_age_days", 90))
        if age_days > warn_days:
            oecd_line = f"{oecd_name} stale {age_days}d [accepted]"
            oecd_accepted = True

    bits: list[str] = []
    if oecd_line:
        bits.append(oecd_line)
    if stale:
        bits.append(f"{len(stale)} stale: " + ", ".join(stale[:2]) + ("..." if len(stale) > 2 else ""))
    if missing:
        bits.append(f"{len(missing)} missing")

    if not bits:
        return Section("MACRO", "OK", f"{checked}/{len(MACRO_SERIES)} FRED series current")
    accepted = oecd_accepted and not stale and not missing
    return Section("MACRO", "WARNING", "; ".join(bits), accepted=accepted)


def _last_rebalance_entry(records: list[dict]) -> dict | None:
    """Walk the log backwards to find the last executed rebalance.

    Supports both legacy single-strategy format (top-level target_weights)
    and the 9-strategy format (weights nested under strategies.{name}).
    For the multi-strategy format, returns a synthetic entry with the
    equal-weighted average of all strategies' target_weights.
    """
    for r in reversed(records):
        if "target_weights" in r:
            return r
        if r.get("executed") and "strategies" in r:
            merged: dict[str, float] = {}
            count = 0
            for _sname, sdata in r["strategies"].items():
                tw = sdata.get("target_weights") or sdata.get("post_rebalance_weights") or {}
                if tw:
                    count += 1
                    for ticker, w in tw.items():
                        merged[ticker] = merged.get(ticker, 0.0) + float(w)
            if count > 0:
                merged = {k: v / count for k, v in merged.items()}
                return {"date": r["date"], "target_weights": merged}
    return None


def check_holdings(today: pd.Timestamp, alerts_cfg: dict) -> tuple[Section, dict | None]:
    if not REBAL_LOG_PATH.exists():
        return Section("HOLDINGS", "WARNING", "no rebalance log found"), None
    try:
        with open(REBAL_LOG_PATH, "r") as f:
            records = json.load(f)
    except Exception as exc:
        return Section("HOLDINGS", "ALERT", f"rebalance log unreadable: {exc}"), None

    last = _last_rebalance_entry(records or [])
    if last is None:
        return Section("HOLDINGS", "WARNING", "no executed rebalance on record"), None

    last_date = pd.Timestamp(last["date"]).normalize()
    cal_days = (today.normalize() - last_date).days
    t_days = trading_days_between(last_date, today)

    if t_days > 50:
        status = "ALERT"
    elif t_days > 35:
        status = "WARNING"
    else:
        status = "OK"
    detail = f"last rebalance {last_date.date()}, {cal_days} days ago ({t_days} trading)"
    return Section("HOLDINGS", status, detail), last


def check_performance(
    today: pd.Timestamp,
    last_rebal: dict | None,
    alerts_cfg: dict,
) -> Section:
    if last_rebal is None:
        return Section("PERFORMANCE", "n/a", "no rebalance history")

    last_date = pd.Timestamp(last_rebal["date"]).normalize()
    # Use executed/current weights if present, else target
    weights = (
        last_rebal.get("current_weights")
        or last_rebal.get("target_weights")
        or {}
    )
    weights = {k: float(v) for k, v in weights.items() if v > 1e-6}
    if not weights:
        return Section("PERFORMANCE", "n/a", "no weights in last rebalance")

    strat_ret = 0.0
    spy_ret = 0.0
    n_present = 0

    def _ret(ticker: str) -> float | None:
        path = PRICES_DIR / f"{ticker}.parquet"
        if not path.exists():
            return None
        df = pd.read_parquet(path)
        col = "adj_close" if "adj_close" in df.columns else df.columns[0]
        ser = df[col].dropna()
        if ser.empty:
            return None
        idx = pd.DatetimeIndex(ser.index).normalize()
        ser = ser.copy()
        ser.index = idx
        prior = ser.loc[ser.index <= last_date]
        post = ser.loc[ser.index <= today]
        if prior.empty or post.empty:
            return None
        return float(post.iloc[-1] / prior.iloc[-1] - 1.0)

    for t, w in weights.items():
        r = _ret(t)
        if r is None:
            continue
        strat_ret += w * r
        n_present += 1

    if n_present == 0 or (today.normalize() - last_date).days < 1:
        return Section("PERFORMANCE", "n/a", "no history yet")

    spy_r = _ret("SPY")
    spy_txt = f"SPY {spy_r*100:+.2f}%" if spy_r is not None else "SPY n/a"
    detail = f"strategy {strat_ret*100:+.2f}% vs {spy_txt} since {last_date.date()}"

    dd_investigate = float(alerts_cfg.get("immediate", {}).get("drawdown_investigate_pct", -15.0)) / 100
    if strat_ret <= dd_investigate:
        return Section("PERFORMANCE", "ALERT", f"{detail} (drawdown {strat_ret*100:.2f}%)")
    return Section("PERFORMANCE", "OK", detail)


def check_classifier(today: pd.Timestamp) -> Section:
    """Age of the production classifier file."""
    candidates = [
        MODELS_DIR / "regime_detector.pkl",
        MODELS_DIR / "best_model.pt",
    ]
    chosen: Path | None = next((p for p in candidates if p.exists()), None)
    if chosen is None:
        any_models = list(MODELS_DIR.glob("*.pkl")) + list(MODELS_DIR.glob("*.pt"))
        if not any_models:
            return Section("CLASSIFIER", "ALERT", "no model file found")
        chosen = max(any_models, key=lambda p: p.stat().st_mtime)

    mtime = datetime.fromtimestamp(chosen.stat().st_mtime)
    age_days = (today.to_pydatetime() - mtime).days

    if age_days > 365:
        status = "ALERT"
    elif age_days > 120:
        status = "WARNING"
    else:
        status = "OK"
    detail = f"model age: {age_days} days ({chosen.name})"
    return Section("CLASSIFIER", status, detail)


def check_sma200(today: pd.Timestamp, cfg: dict) -> Section:
    """SPY proximity to its 200-day SMA."""
    path = PRICES_DIR / "SPY.parquet"
    if not path.exists():
        return Section("SMA200", "ALERT", "SPY parquet missing")
    df = pd.read_parquet(path)
    col = "adj_close" if "adj_close" in df.columns else "close"
    ser = df[col].dropna()
    if len(ser) < 200:
        return Section("SMA200", "WARNING", f"only {len(ser)} SPY rows (<200)")
    sma = ser.rolling(200).mean()
    last_px = float(ser.iloc[-1])
    last_sma = float(sma.iloc[-1])
    dist = last_px / last_sma - 1.0
    buffer = float(cfg.get("sma_gate_buffer", -0.04))  # -0.04 → fire at <-4%

    pct = dist * 100
    sign = "+" if dist >= 0 else ""
    detail = f"SPY {sign}{pct:.2f}% {'above' if dist >= 0 else 'below'} SMA200"

    # INFO window: -2% to -6% (spanning the gate threshold)
    if -0.06 <= dist <= -0.02:
        return Section("SMA200", "INFO", detail + " (near gate)")
    if dist < buffer:
        return Section("SMA200", "ALERT", detail + " (gate fired)")
    return Section("SMA200", "OK", detail)


def _raw_index_max(path: Path) -> pd.Timestamp | None:
    """Raw index max of a parquet, regardless of trailing-NaN rows."""
    if not path.exists():
        return None
    df = pd.read_parquet(path)
    if df.empty:
        return None
    return pd.Timestamp(df.index.max()).normalize()


def _column_last_valid(path: Path, column: str) -> tuple[pd.Timestamp | None, float | None]:
    """(last date with a non-NaN value in `column`, value at the file's raw max index).

    The second element is None when the column is NaN at the file's last
    row — exactly the state where gate_fired(NaN) silently forces risk-off.
    """
    if not path.exists():
        return None, None
    df = pd.read_parquet(path)
    if df.empty or column not in df.columns:
        return None, None
    ser = pd.to_numeric(df[column], errors="coerce").sort_index()
    valid = ser.dropna()
    last_valid = pd.Timestamp(valid.index.max()).normalize() if not valid.empty else None
    value_at_max = float(ser.iloc[-1]) if pd.notna(ser.iloc[-1]) else None
    return last_valid, value_at_max


def check_signal_freshness(
    today: pd.Timestamp,
    panel_path: Path = MASTER_PANEL_PATH,
    returns_path: Path = RETURNS_63D_PATH,
    quality_path: Path = QUALITY_SMA200_PATH,
    max_tdays: int = 3,
) -> Section:
    """Freshness of the parquets that live signals actually consume.

    This is the section that would have caught the 2026 Q2 freeze:
    master_panel.parquet stalled at 2026-04-10 while the per-feature
    parquets stayed current, and load_panel reindexed fresh features back
    onto the stale panel index — so every rebalance re-traded April
    signals with zero warnings. We therefore ALERT on the per-feature
    parquets and only WARN on the raw panel age (the live_extend path
    covers a stale panel).
    """
    alerts: list[str] = []
    warns: list[str] = []
    info: list[str] = []

    ret_max = _raw_index_max(returns_path)
    if ret_max is None:
        alerts.append("returns_63d missing/empty")
    else:
        gap = trading_days_between(ret_max, today)
        if gap > max_tdays:
            alerts.append(f"returns_63d stale {gap}td (last {ret_max.date()})")
        else:
            info.append(f"returns_63d {ret_max.date()} ({gap}td)")

    q_last_valid, q_value_at_max = _column_last_valid(quality_path, "SPY")
    if q_last_valid is None:
        alerts.append("quality_dist_sma200 SPY missing/empty")
    else:
        gap = trading_days_between(q_last_valid, today)
        if gap > max_tdays:
            alerts.append(
                f"quality_dist_sma200 SPY stale {gap}td (last valid {q_last_valid.date()})"
            )
        else:
            info.append(f"quality SPY {q_last_valid.date()} ({gap}td)")
        if q_value_at_max is None:
            alerts.append(
                "quality_dist_sma200 SPY is NaN at max date"
                " (gate_fired(NaN)=True -> silent risk-off)"
            )

    panel_max = _raw_index_max(panel_path)
    if panel_max is None:
        warns.append("master_panel missing")
    else:
        gap = trading_days_between(panel_max, today)
        if gap > max_tdays:
            warns.append(
                f"master_panel raw index ends {panel_max.date()}"
                f" ({gap}td behind; live_extend covers it)"
            )
        else:
            info.append(f"master_panel {panel_max.date()}")

    if alerts:
        return Section("SIGNALS", "ALERT", "; ".join(alerts), extra=warns + info)
    if warns:
        return Section("SIGNALS", "WARNING", "; ".join(warns), extra=info)
    return Section("SIGNALS", "OK", "; ".join(info))


def core_feature_staleness(
    root: Path,
    today: pd.Timestamp,
) -> list[tuple[str, pd.Timestamp | None, int | None]]:
    """(feature, last-valid date, calendar age in days) per CORE feature.

    Resolves each name in configs/feature_sets.yaml 'core' through the
    same per-feature parquet lookup the live classifier path uses
    (features.live_features._resolve_feature). Sorted stalest first;
    unresolved features sort as stalest with (None, None).
    """
    from features.live_features import _resolve_feature, load_core_set

    root = Path(root)
    rows: list[tuple[str, pd.Timestamp | None, int | None]] = []
    for name in load_core_set(root):
        ser = _resolve_feature(name, root)
        if ser is None or ser.dropna().empty:
            rows.append((name, None, None))
            continue
        last = pd.Timestamp(ser.dropna().index.max()).normalize()
        rows.append((name, last, int((today.normalize() - last).days)))
    rows.sort(key=lambda r: r[2] if r[2] is not None else 10**9, reverse=True)
    return rows


def check_core_staleness(
    today: pd.Timestamp,
    root: Path = ROOT,
    max_age_days: int = 45,
) -> Section:
    """CORE feature staleness — per-feature last-valid dates.

    ALERTs on any CORE feature staler than `max_age_days` calendar days
    (or unresolvable). Interaction/cross-asset features are NOT rebuilt
    by the nightly price-feature refresh, so they can silently freeze
    while returns_* stay current.
    """
    try:
        rows = core_feature_staleness(root, today)
    except Exception as exc:
        return Section("CORE_FEATS", "ALERT", f"core staleness check failed: {exc}")

    stale = [r for r in rows if r[2] is None or r[2] > max_age_days]
    extra = [
        f"{name}: " + ("unresolved" if last is None else f"{last.date()} ({age}d)")
        for name, last, age in rows[:10]
    ]
    if stale:
        return Section(
            "CORE_FEATS",
            "ALERT",
            f"{len(stale)}/{len(rows)} CORE features staler than {max_age_days}d",
            extra=extra,
        )
    return Section(
        "CORE_FEATS", "OK",
        f"all {len(rows)} CORE features within {max_age_days}d",
        extra=extra,
    )


def check_last_rebalance(
    today: pd.Timestamp,
    log_path: Path = REBAL_LOG_PATH,
    max_age_days: int = 7,
) -> Section:
    """Success flags of the most recent executed rebalance."""
    if not log_path.exists():
        return Section("REBALANCE", "WARNING", "no rebalance log found")
    try:
        records = json.loads(log_path.read_text())
    except Exception as exc:
        return Section("REBALANCE", "ALERT", f"rebalance log unreadable: {exc}")

    entry = next((r for r in reversed(records or []) if r.get("executed")), None)
    if entry is None:
        return Section("REBALANCE", "WARNING", "no executed rebalance on record")

    entry_date = pd.Timestamp(entry["date"]).normalize()
    age = (today.normalize() - entry_date).days
    strategies = entry.get("strategies") or {}
    # Healthy only when success is EXPLICITLY true — credential failures are
    # logged WITHOUT a 'success' key, so `is False` alone reported a dead
    # slot as "all strategies succeeded".
    failed = sorted(
        name for name, sdata in strategies.items()
        if sdata.get("success") is not True
    )
    # Strategies that raised before logging are absent from the entry
    # entirely — compare against the configured lineup.
    try:
        expected = set((load_yaml(ACCOUNTS_PATH).get("strategies") or {}).keys())
    except Exception:
        expected = set()
    # Skip the missing-strategy check for deliberate single-slot runs
    # (run_rebalance --strategy N) — those legitimately log one entry.
    if expected and len(strategies) > 1:
        failed = sorted(
            set(failed) | {f"{m} (no log entry)" for m in expected - set(strategies)}
        )
    if failed and age < max_age_days:
        return Section(
            "REBALANCE", "ALERT",
            f"{entry_date.date()} ({age}d ago): success=false for {', '.join(failed)}",
        )
    if failed:
        return Section(
            "REBALANCE", "WARNING",
            f"{entry_date.date()} ({age}d ago, >{max_age_days}d): "
            f"success=false for {', '.join(failed)}",
        )
    return Section(
        "REBALANCE", "OK",
        f"{entry_date.date()} ({age}d ago): all strategies succeeded",
    )


def _latest_target_weights(records: list[dict], strategy: str) -> dict[str, float] | None:
    """Most recent target_weights logged for `strategy`, newest first."""
    for r in reversed(records):
        sdata = (r.get("strategies") or {}).get(strategy)
        if sdata and sdata.get("target_weights"):
            return {k: float(v) for k, v in sdata["target_weights"].items()}
    return None


def check_broker_drift(
    today: pd.Timestamp,
    accounts_path: Path = ACCOUNTS_PATH,
    log_path: Path = REBAL_LOG_PATH,
    threshold: float = 0.02,
) -> Section:
    """Alpaca positions vs the last logged target weights (network-optional).

    Any failure — missing credentials, offline broker, unreadable log —
    degrades to a skipped/n-a section rather than crashing the check.
    """
    import os

    try:
        accounts = load_yaml(accounts_path)
        records = json.loads(log_path.read_text()) if log_path.exists() else []
    except Exception as exc:
        return Section("BROKER", "n/a", f"skipped ({exc})")

    checked = 0
    skipped = 0
    drifts: list[str] = []
    try:
        from execution.alpaca_client import AlpacaPaperClient

        for sname, entry in (accounts.get("strategies") or {}).items():
            key = os.environ.get(entry.get("alpaca_key_env", ""), "").strip()
            sec = os.environ.get(entry.get("alpaca_secret_env", ""), "").strip()
            if not key or not sec:
                skipped += 1
                continue
            targets = _latest_target_weights(records if isinstance(records, list) else [], sname)
            if targets is None:
                skipped += 1
                continue
            client = AlpacaPaperClient(key, sec)
            account = client.get_account()
            positions = client.get_positions()
            if "error" in account:
                return Section("BROKER", "n/a", f"skipped (offline: {account['error']})")
            if "error" in positions:
                return Section("BROKER", "n/a", f"skipped (offline: {positions['error']})")
            equity = float(account["equity"])
            if equity <= 0:
                skipped += 1
                continue
            actual = {t: p["market_value"] / equity for t, p in positions.items()}
            for ticker in sorted(set(targets) | set(actual)):
                dev = abs(actual.get(ticker, 0.0) - targets.get(ticker, 0.0))
                if dev > threshold:
                    drifts.append(f"{sname}:{ticker} {dev * 100:.1f}%")
            checked += 1
    except Exception as exc:
        return Section("BROKER", "n/a", f"skipped (offline: {exc})")

    if checked == 0:
        return Section("BROKER", "n/a", f"skipped (no credentials/targets, {skipped} strategies)")
    if drifts:
        return Section(
            "BROKER", "WARNING",
            f"drift >{threshold * 100:.0f}% on {len(drifts)} position(s): "
            + ", ".join(drifts[:6]) + ("..." if len(drifts) > 6 else ""),
        )
    return Section(
        "BROKER", "OK",
        f"{checked} account(s) within {threshold * 100:.0f}% of targets"
        + (f" ({skipped} skipped)" if skipped else ""),
    )


def next_fomc_after(today: pd.Timestamp) -> pd.Timestamp | None:
    if not CALENDAR_PATH.exists():
        return None
    df = pd.read_parquet(CALENDAR_PATH)
    if "is_fomc_day" not in df.columns:
        return None
    fomc = pd.DatetimeIndex(df.index[df["is_fomc_day"] > 0]).normalize()
    future = fomc[fomc >= today.normalize()]
    return future[0] if len(future) else None


def rebalance_countdown(today: pd.Timestamp) -> tuple[pd.Timestamp, int, pd.Timestamp | None, Section | None]:
    nxt = next_rebalance_date(today)
    cal_days = (nxt.normalize() - today.normalize()).days
    fomc = next_fomc_after(today)

    info_section: Section | None = None
    if fomc is not None and (nxt - pd.Timedelta(days=2)) <= fomc <= nxt:
        info_section = Section(
            "FOMC",
            "INFO",
            f"Next rebalance may be deferred due to FOMC on {fomc.date()}",
        )
    return nxt, cal_days, fomc, info_section


# report


def _format_report(
    today: pd.Timestamp,
    sections: list[Section],
    rebal_info: tuple[pd.Timestamp, int, pd.Timestamp | None, Section | None],
    now_stamp: str,
) -> str:
    nxt, cal_days, fomc, info_section = rebal_info
    lines: list[str] = []
    lines.append(BAR)
    lines.append(f"DAILY HEALTH CHECK — {now_stamp}")
    lines.append(BAR)

    labels = {
        "PRICES":      "PRICES:     ",
        "MACRO":       "MACRO:      ",
        "HOLDINGS":    "HOLDINGS:   ",
        "PERFORMANCE": "PERFORMANCE:",
        "CLASSIFIER":  "CLASSIFIER: ",
        "SMA200":      "SMA200:     ",
        "SIGNALS":     "SIGNALS:    ",
        "CORE_FEATS":  "CORE_FEATS: ",
        "REBALANCE":   "REBALANCE:  ",
        "BROKER":      "BROKER:     ",
    }
    for s in sections:
        prefix = labels.get(s.name, f"{s.name}: ")
        lines.append(f"{prefix} {s.status} ({s.detail})")
        for x in s.extra:
            lines.append(f"    - {x}")

    lines.append("")
    fomc_str = fomc.date().isoformat() if fomc is not None else "none scheduled"
    conflict = ""
    if fomc is not None:
        if (nxt - pd.Timedelta(days=2)) <= fomc <= nxt:
            conflict = f" (CONFLICT with {nxt.date()})"
        else:
            conflict = f" (no conflict with {nxt.date()})"
    lines.append(f"NEXT REBALANCE: {nxt.date()} ({cal_days} days)")
    lines.append(f"FOMC CHECK:     {fomc_str}{conflict}")
    if info_section is not None:
        lines.append(f"  INFO: {info_section.detail}")

    alerts = [s for s in sections if s.status == "ALERT"]
    warnings = [s for s in sections if s.status == "WARNING"]
    lines.append("")
    lines.append(f"ALERTS: {len(alerts)}" + (
        " (" + "; ".join(f"{s.name}: {s.detail}" for s in alerts) + ")" if alerts else ""
    ))
    warn_txt = f"WARNINGS: {len(warnings)}"
    if warnings:
        bits = []
        for s in warnings:
            tag = " — architecturally accepted" if s.accepted else ""
            bits.append(f"{s.name.lower()}{tag}")
        warn_txt += " (" + "; ".join(bits) + ")"
    lines.append(warn_txt)
    lines.append(BAR)
    return "\n".join(lines)


def _append_log(report: str) -> None:
    HEALTH_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(HEALTH_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(f"\n[{stamp}]\n{report}\n")


# main


def main(argv: list[str] | None = None) -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Daily health check (§6.1)")
    parser.add_argument("--date", default=None, help="override today's date (YYYY-MM-DD)")
    parser.add_argument("--no-log", action="store_true", help="do not append to logs/health_check.log")
    parser.add_argument("--probe-sources", action="store_true",
                        help="probe live data sources (yahoo/twelve_data/fred/bls) and print their status")
    args = parser.parse_args(argv)

    today = (
        pd.Timestamp(args.date).normalize()
        if args.date
        else pd.Timestamp(datetime.now().date())
    )

    cfg = load_yaml(STRATEGY_PATH)
    alerts_cfg = load_yaml(ALERTS_PATH)

    sections: list[Section] = []
    sections.append(check_prices(today, cfg, alerts_cfg))
    sections.append(check_macro(today, alerts_cfg))
    holdings_section, last_rebal = check_holdings(today, alerts_cfg)
    sections.append(holdings_section)
    sections.append(check_performance(today, last_rebal, alerts_cfg))
    sections.append(check_classifier(today))
    sections.append(check_sma200(today, cfg))
    sections.append(check_signal_freshness(today))
    sections.append(check_core_staleness(today))
    sections.append(check_last_rebalance(today))
    sections.append(check_broker_drift(today))

    rebal_info = rebalance_countdown(today)

    now_stamp = datetime.now().strftime("%Y-%m-%d %H:%M ET")
    report = _format_report(today, sections, rebal_info, now_stamp)
    print(report)

    if args.probe_sources:
        try:
            from data.pipeline import source_health_report
            health = source_health_report()
        except Exception as exc:
            print(f"SOURCES: probe failed — {exc}")
        else:
            print("SOURCES:")
            for name, info in health.items():
                lat = f"{info.get('latency_ms','?')}ms" if info.get("status") != "skipped" else "-"
                print(f"  {name:12s} {info.get('status','?'):8s} {lat:>8s}  {info.get('detail','')}")

    if not args.no_log:
        _append_log(report)

    # Exit 1 if any ALERT-level finding; page a human first.
    alerts = [s for s in sections if s.status == "ALERT"]
    if alerts:
        try:
            from risk.notify import send_alert
            send_alert(
                f"Health check: {len(alerts)} alert(s) — "
                + "; ".join(s.name for s in alerts),
                "ALERT",
            )
        except Exception as exc:
            print(f"[notify] send_alert failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
