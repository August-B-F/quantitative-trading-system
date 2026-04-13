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


# ---------- utilities ------------------------------------------------------


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


# ---------- checks ---------------------------------------------------------


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
    """Walk the log backwards to find the last entry with target_weights
    (skips fomc_defer event markers)."""
    for r in reversed(records):
        if "target_weights" in r:
            return r
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


# ---------- report ---------------------------------------------------------


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
    }
    for s in sections:
        prefix = labels.get(s.name, f"{s.name}: ")
        lines.append(f"{prefix} {s.status} ({s.detail})")

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


# ---------- main -----------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Daily health check (§6.1)")
    parser.add_argument("--date", default=None, help="override today's date (YYYY-MM-DD)")
    parser.add_argument("--no-log", action="store_true", help="do not append to logs/health_check.log")
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

    rebal_info = rebalance_countdown(today)

    now_stamp = datetime.now().strftime("%Y-%m-%d %H:%M ET")
    report = _format_report(today, sections, rebal_info, now_stamp)
    print(report)

    if not args.no_log:
        _append_log(report)

    # Exit 1 if any ALERT-level finding
    if any(s.status == "ALERT" for s in sections):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
