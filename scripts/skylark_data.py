"""Skylark — data layer for the 9-strategy horse race UI.

Single source of truth for the Skylark web server. Reads:
  - configs/accounts.yaml           → 9 strategies, 3 tiers, env-var mapping
  - configs/strategies/*.yaml       → per-strategy specs
  - results/multi_strategy_backtest.json → historical metrics + monthly returns
  - logs/rebalance_log.json         → live trade log
  - logs/monthly_comparison.csv     → forward-test monthly returns
  - Alpaca (paper or live)          → account equity, positions, orders

Live-ready: set ``ALPACA_LIVE=1`` in the environment to flip every account
from https://paper-api.alpaca.markets to https://api.alpaca.markets without
touching any other code.
"""
from __future__ import annotations

import csv
import json
import math
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any

import yaml

from src.execution.alpaca_client import AlpacaPaperClient, LIVE_BASE, PAPER_BASE

_ROOT          = Path(__file__).resolve().parent.parent
_ACCOUNTS_YAML = _ROOT / "configs" / "accounts.yaml"
_STRATEGIES    = _ROOT / "configs" / "strategies"
_BACKTEST_JSON = _ROOT / "results" / "multi_strategy_backtest.json"
_SELECTION_MD  = _ROOT / "results" / "STRATEGY_SELECTION.md"
_REBAL_LOG     = _ROOT / "logs" / "rebalance_log.json"
_MONTHLY_CSV   = _ROOT / "logs" / "monthly_comparison.csv"

TIER_ORDER = ("confident", "neutral", "skeptical")

_YAHOO_DIR = _ROOT / "data" / "raw" / "yahoo"
_PRESENTATION = _ROOT / "results" / "backtest_presentation.json"


# ═══════════════════════════════════════════════════════════════════════════
# Small utilities
# ═══════════════════════════════════════════════════════════════════════════

def _sanitize(obj: Any) -> Any:
    if isinstance(obj, float):
        return obj if math.isfinite(obj) else None
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize(v) for v in obj]
    return obj


def _safe_mtime(p: Path) -> float:
    try:
        return p.stat().st_mtime
    except OSError:
        return 0.0


def _fmt_age(secs: float) -> str:
    if secs < 60:    return f"{int(secs)}s"
    if secs < 3600:  return f"{int(secs/60)}m"
    if secs < 86400: return f"{int(secs/3600)}h"
    return f"{int(secs/86400)}d"


def is_live() -> bool:
    return os.environ.get("ALPACA_LIVE", "0") == "1"


# ═══════════════════════════════════════════════════════════════════════════
# Config loading (cached by mtime)
# ═══════════════════════════════════════════════════════════════════════════

_cache: dict[str, tuple[float, Any]] = {}
_cache_lock = Lock()


def _load_yaml(path: Path) -> dict:
    with _cache_lock:
        key = str(path)
        mt = _safe_mtime(path)
        hit = _cache.get(key)
        if hit and hit[0] == mt:
            return hit[1]
        if not path.exists():
            _cache[key] = (0.0, {})
            return {}
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        _cache[key] = (mt, data)
        return data


def _load_json(path: Path) -> Any:
    with _cache_lock:
        key = str(path)
        mt = _safe_mtime(path)
        hit = _cache.get(key)
        if hit and hit[0] == mt:
            return hit[1]
        if not path.exists():
            _cache[key] = (0.0, None)
            return None
        with open(path, encoding="utf-8") as f:
            data = _sanitize(json.load(f))
        _cache[key] = (mt, data)
        return data


def load_accounts_cfg() -> dict:
    return _load_yaml(_ACCOUNTS_YAML)


def load_strategy_spec(slot_id: str) -> dict:
    """slot_id like 'strategy_1_optimized'."""
    return _load_yaml(_STRATEGIES / f"{slot_id}.yaml")


def load_backtest() -> dict:
    """Return {'strategies': {NAME: {slot, metrics, annual_returns, monthly_returns}}}."""
    return _load_json(_BACKTEST_JSON) or {}


def load_rebalance_log() -> list[dict]:
    data = _load_json(_REBAL_LOG)
    return data if isinstance(data, list) else []


def load_monthly_comparison() -> list[dict]:
    if not _MONTHLY_CSV.exists():
        return []
    rows: list[dict] = []
    with open(_MONTHLY_CSV, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            out: dict[str, Any] = {"date": row.get("date", "")}
            for k, v in row.items():
                if k == "date":
                    continue
                try:
                    out[k] = float(v) if v not in (None, "") else None
                except ValueError:
                    out[k] = None
            rows.append(out)
    return rows


# ═══════════════════════════════════════════════════════════════════════════
# Strategy registry — canonical slot list
# ═══════════════════════════════════════════════════════════════════════════

def strategy_registry() -> list[dict]:
    """Return the 9 slots in slot order, each merged with its yaml spec + backtest metrics.

    Shape per entry:
      {slot, slot_id, name, tier, login, alpaca_key_env, alpaca_secret_env,
       config_path, spec: {...yaml...}, backtest: {cagr, sharpe, max_dd, ...}}
    """
    cfg = load_accounts_cfg()
    strategies_map = cfg.get("strategies", {}) or {}
    bt = load_backtest().get("strategies", {}) or {}
    out: list[dict] = []
    for slot_id, entry in strategies_map.items():
        name = entry.get("name", slot_id)
        spec = load_strategy_spec(slot_id)
        out.append({
            "slot":              entry.get("slot"),
            "slot_id":           slot_id,
            "name":              name,
            "tier":              entry.get("tier"),
            "login":             entry.get("login"),
            "alpaca_key_env":    entry.get("alpaca_key_env"),
            "alpaca_secret_env": entry.get("alpaca_secret_env"),
            "config_path":       entry.get("config"),
            "spec":              spec,
            "backtest":          (bt.get(name) or {}).get("metrics", {}),
            "annual_returns":    (bt.get(name) or {}).get("annual_returns", {}),
            "monthly_returns":   (bt.get(name) or {}).get("monthly_returns", {}),
            "n_months":          (bt.get(name) or {}).get("n"),
            "description":       (spec.get("description") or "").strip(),
            "universe":          spec.get("universe") or [],
        })
    out.sort(key=lambda s: s["slot"] or 99)
    return out


def strategy_by_slot(slot: int) -> dict | None:
    for s in strategy_registry():
        if s["slot"] == slot:
            return s
    return None


def tier_groups() -> dict[str, list[dict]]:
    groups: dict[str, list[dict]] = {t: [] for t in TIER_ORDER}
    for s in strategy_registry():
        if s["tier"] in groups:
            groups[s["tier"]].append(s)
    return groups


# ═══════════════════════════════════════════════════════════════════════════
# Alpaca client pool (one per strategy, cached)
# ═══════════════════════════════════════════════════════════════════════════

_client_pool: dict[str, AlpacaPaperClient] = {}
_pool_lock = Lock()


def _alpaca_client_for(strategy: dict) -> AlpacaPaperClient | None:
    slot_id = strategy["slot_id"]
    with _pool_lock:
        if slot_id in _client_pool:
            return _client_pool[slot_id]
        key_env    = strategy.get("alpaca_key_env")
        secret_env = strategy.get("alpaca_secret_env")
        if not key_env or not secret_env:
            return None
        api_key = os.environ.get(key_env, "")
        secret  = os.environ.get(secret_env, "")
        if not api_key or not secret:
            return None
        base = LIVE_BASE if is_live() else PAPER_BASE
        client = AlpacaPaperClient(api_key, secret, base_url=base)
        _client_pool[slot_id] = client
        return client


# Alpaca response cache — don't hammer the API on every page refresh.
_alpaca_cache: dict[str, tuple[float, Any]] = {}
_alpaca_ttl = 30.0  # seconds
_alpaca_lock = Lock()


def _cached_call(key: str, fn) -> Any:
    now = time.time()
    with _alpaca_lock:
        hit = _alpaca_cache.get(key)
        if hit and (now - hit[0]) < _alpaca_ttl:
            return hit[1]
    try:
        val = fn()
    except Exception as exc:
        val = {"error": f"exception: {exc}"}
    with _alpaca_lock:
        _alpaca_cache[key] = (now, val)
    return val


def alpaca_account(strategy: dict) -> dict:
    client = _alpaca_client_for(strategy)
    if client is None:
        return {"connected": False, "reason": "no credentials"}
    res = _cached_call(f"acct:{strategy['slot_id']}", client.get_account)
    if isinstance(res, dict) and "error" in res:
        return {"connected": False, "reason": res["error"]}
    res["connected"] = True
    res["live"] = is_live()
    return res


def alpaca_positions(strategy: dict) -> dict:
    client = _alpaca_client_for(strategy)
    if client is None:
        return {}
    res = _cached_call(f"pos:{strategy['slot_id']}", client.get_positions)
    if isinstance(res, dict) and "error" in res:
        return {}
    return res or {}


def alpaca_portfolio_history(strategy: dict, period: str = "6M") -> dict:
    client = _alpaca_client_for(strategy)
    if client is None:
        return {"points": []}
    key = f"hist:{strategy['slot_id']}:{period}"
    res = _cached_call(key, lambda: client.get_portfolio_history(period=period, timeframe="1D"))
    if isinstance(res, dict) and "error" in res:
        return {"points": [], "error": res["error"]}
    return res


def alpaca_orders(strategy: dict, limit: int = 50) -> list:
    client = _alpaca_client_for(strategy)
    if client is None:
        return []
    res = _cached_call(f"ord:{strategy['slot_id']}:{limit}",
                       lambda: client.list_orders(status="all", limit=limit))
    return res if isinstance(res, list) else []


def alpaca_clock() -> dict:
    """One clock call is enough for all accounts (same market)."""
    for s in strategy_registry():
        client = _alpaca_client_for(s)
        if client is None:
            continue
        res = _cached_call("clock", client.get_clock)
        if isinstance(res, dict) and "error" not in res:
            return {
                "is_open":       bool(res.get("is_open")),
                "next_open":     res.get("next_open"),
                "next_close":    res.get("next_close"),
                "timestamp":     res.get("timestamp"),
                "source":        "alpaca",
            }
    return {"is_open": None, "source": "offline"}


# ═══════════════════════════════════════════════════════════════════════════
# Live equity assembly
# ═══════════════════════════════════════════════════════════════════════════

def live_strategy_equity(strategy: dict) -> dict:
    """Return the strategy's current equity state — Alpaca first, fallback to initial capital."""
    cfg  = load_accounts_cfg()
    init = float(cfg.get("initial_capital", 100_000.0))
    acct = alpaca_account(strategy)
    if acct.get("connected"):
        eq  = acct["equity"]
        ret = (eq / init) - 1.0 if init else 0.0
        return {
            "equity":       eq,
            "cash":         acct.get("cash"),
            "buying_power": acct.get("buying_power"),
            "return_pct":   ret,
            "connected":    True,
            "live":         acct.get("live", False),
        }
    return {
        "equity":       init,
        "cash":         init,
        "buying_power": init,
        "return_pct":   0.0,
        "connected":    False,
        "live":         False,
        "reason":       acct.get("reason"),
    }


def live_equity_curves(period: str = "1M") -> dict:
    """Pull Alpaca portfolio history for each strategy and build a SPY
    benchmark in dollars starting from the same initial capital.

    Returns {labels: [...dates], strategies: {name: [equity_usd]}, spy: [usd]}
    with all series aligned to the union of sample dates.
    """
    cfg = load_accounts_cfg()
    initial = float(cfg.get("initial_capital", 100_000.0))

    from datetime import datetime as _dt
    today_iso = _dt.now().strftime("%Y-%m-%d")

    histories: dict[str, list[dict]] = {}
    current_eq: dict[str, float] = {}
    all_dates: set[str] = set()
    for s in strategy_registry():
        hist = alpaca_portfolio_history(s, period=period)
        pts = hist.get("points") or []
        if pts:
            histories[s["name"]] = pts
            for p in pts:
                all_dates.add(p["date"])
        # Real-time equity (portfolio_history lags until EOD settlement, so
        # intraday "what have I made today" comes from /v2/account directly)
        acct = alpaca_account(s)
        if acct.get("connected"):
            current_eq[s["name"]] = float(acct.get("equity") or initial)
            all_dates.add(today_iso)

    dates = sorted(all_dates)
    if not dates:
        return {"labels": [], "strategies": {}, "spy": []}

    # Align each strategy's series to the full date index. Alpaca returns 0
    # for days before the account had any activity — replace those with the
    # initial capital so the chart shows a clean "flat $100k baseline → real
    # returns after first rebalance" picture instead of a zero floor.
    # Today's point is overwritten with the live /v2/account equity because
    # portfolio_history lags EOD.
    out_strats: dict[str, list[float | None]] = {}
    for name, pts in histories.items():
        by_date = {p["date"]: float(p["equity"]) for p in pts}
        # Override today's datapoint with real-time equity
        if name in current_eq:
            by_date[today_iso] = current_eq[name]
        last = initial
        col: list[float | None] = []
        for d in dates:
            v = by_date.get(d)
            if v is None or v <= 0:
                v = last
            col.append(v)
            last = v
        out_strats[name] = col
    # Any strategy we got /v2/account equity for but no portfolio history at all
    for name, eq in current_eq.items():
        if name not in out_strats:
            out_strats[name] = [initial if d != today_iso else eq for d in dates]

    # SPY benchmark in dollars — start at `initial`, scale by cumulative SPY return
    spy = _load_adj_close("SPY")
    spy_col: list[float | None] = []
    if spy is not None:
        spy_px = _resample_series_to_dates(spy, dates)
        base = next((p for p in spy_px if p), None)
        if base:
            for p in spy_px:
                spy_col.append(initial * (p / base) if p else None)
        else:
            spy_col = [None] * len(dates)
    else:
        spy_col = [None] * len(dates)

    return {
        "labels":     dates,
        "strategies": out_strats,
        "spy":        spy_col,
        "initial":    initial,
    }


def dashboard_summary() -> dict:
    regs  = strategy_registry()
    rows: list[dict] = []
    total_aum = 0.0
    for s in regs:
        eq  = live_strategy_equity(s)
        bt  = s["backtest"] or {}
        total_aum += eq["equity"] or 0.0
        rows.append({
            "slot":        s["slot"],
            "slot_id":     s["slot_id"],
            "name":        s["name"],
            "tier":        s["tier"],
            "equity":      eq["equity"],
            "return_pct":  eq["return_pct"],
            "connected":   eq["connected"],
            "bt_cagr":     bt.get("cagr"),
            "bt_sharpe":   bt.get("sharpe"),
            "bt_max_dd":   bt.get("max_dd"),
            "bt_sortino":  bt.get("sortino"),
            "bt_win_pct":  bt.get("win_pct"),
            "bt_worst_yr": bt.get("worst_year"),
        })
    ranked = sorted(rows, key=lambda r: (r["return_pct"] if r["return_pct"] is not None else -9), reverse=True)
    best  = ranked[0] if ranked else None
    worst = ranked[-1] if ranked else None
    clock = alpaca_clock()
    # Count strategies currently in profit
    n_profit  = sum(1 for r in rows if (r["return_pct"] or 0) > 0)
    n_loss    = sum(1 for r in rows if (r["return_pct"] or 0) < 0)
    # Average backtest Sharpe across the field (weighted equally)
    sharpes = [r["bt_sharpe"] for r in rows if r["bt_sharpe"] is not None]
    avg_sharpe = sum(sharpes) / len(sharpes) if sharpes else None
    regime = current_regime()
    return {
        "total_aum":       total_aum,
        "n_strategies":    len(rows),
        "n_profit":        n_profit,
        "n_loss":          n_loss,
        "avg_sharpe":      avg_sharpe,
        "live_mode":       is_live(),
        "best":            best,
        "worst":           worst,
        "market_open":     clock.get("is_open"),
        "market_source":   clock.get("source"),
        "next_open":       clock.get("next_open"),
        "next_close":      clock.get("next_close"),
        "rows":            ranked,
        "regime":          regime,
        "updated_at":      datetime.now().isoformat(timespec="seconds"),
        "data_health":     data_health_summary(),
        "days_to_rebalance": days_to_month_end(),
        "live_curves":     live_equity_curves(period="1M"),
    }


def days_to_month_end() -> int | None:
    import calendar
    today = datetime.now()
    last_day = calendar.monthrange(today.year, today.month)[1]
    return max(0, last_day - today.day)


# ═══════════════════════════════════════════════════════════════════════════
# Horse race comparison
# ═══════════════════════════════════════════════════════════════════════════

def _load_adj_close(symbol: str):
    """Load adjusted close series for a symbol from data/raw/yahoo/{symbol}.parquet.

    Returns a pandas Series indexed by pandas Timestamp, or None if missing.
    Cached in the module _cache dict alongside yaml/json files.
    """
    path = _YAHOO_DIR / f"{symbol}.parquet"
    if not path.exists():
        return None
    with _cache_lock:
        key = f"parquet::{symbol}"
        mt = _safe_mtime(path)
        hit = _cache.get(key)
        if hit and hit[0] == mt:
            return hit[1]
        try:
            import pandas as pd
            df = pd.read_parquet(path)
        except Exception:
            _cache[key] = (mt, None)
            return None
        col = "adj_close" if "adj_close" in df.columns else "close" if "close" in df.columns else None
        if col is None:
            _cache[key] = (mt, None)
            return None
        s = df[col].dropna()
        _cache[key] = (mt, s)
        return s


def _resample_series_to_dates(series, target_dates: list[str]):
    """Given a daily price Series and a list of ISO-date strings, return the
    price on-or-before each target date. Used to align SPY/AGG closes to
    strategy rebalance dates.
    """
    if series is None or not target_dates:
        return []
    import pandas as pd
    out = []
    idx = series.index
    for d in target_dates:
        ts = pd.Timestamp(d)
        # position of the last index entry <= ts
        pos = idx.searchsorted(ts, side="right") - 1
        if pos < 0:
            out.append(None)
        else:
            try:
                v = float(series.iloc[pos])
                out.append(v if math.isfinite(v) else None)
            except Exception:
                out.append(None)
    return out


def benchmark_curves(dates: list[str]) -> dict:
    """Build benchmark equity curves aligned to the supplied date index.

    Returns {label: [{date, value}]} with value starting at 1.0. Computes:
      - SPY:     buy-and-hold SPY (adj close)
      - 60/40:   60% SPY + 40% AGG, rebalanced monthly
      - EqualWt: average of all 9 strategy monthly returns (proxy for picking all)
    """
    out: dict[str, list[dict]] = {}
    if not dates:
        return out

    spy = _load_adj_close("SPY")
    agg = _load_adj_close("AGG")

    # SPY buy-and-hold
    spy_px = _resample_series_to_dates(spy, dates)
    if spy_px and spy_px[0]:
        base = spy_px[0]
        out["SPY"] = [{"date": d, "value": (p / base) if p else None} for d, p in zip(dates, spy_px)]

    # 60/40 monthly-rebalanced
    if spy_px and agg is not None:
        agg_px = _resample_series_to_dates(agg, dates)
        if agg_px and any(a is not None for a in agg_px) and any(s is not None for s in spy_px):
            # Find first date where BOTH series have a price (AGG inception post-SPY).
            start = None
            for i, (s, a) in enumerate(zip(spy_px, agg_px)):
                if s and a:
                    start = i
                    break
            if start is not None:
                val = 1.0
                curve: list[dict] = []
                # Pad the pre-start part with None so the series aligns to full dates index
                for i in range(start):
                    curve.append({"date": dates[i], "value": None})
                curve.append({"date": dates[start], "value": 1.0})
                for i in range(start + 1, len(dates)):
                    s0, s1 = spy_px[i - 1], spy_px[i]
                    a0, a1 = agg_px[i - 1], agg_px[i]
                    if s0 and s1 and a0 and a1:
                        monthly = 0.6 * (s1 / s0 - 1.0) + 0.4 * (a1 / a0 - 1.0)
                        val *= (1.0 + monthly)
                        curve.append({"date": dates[i], "value": val})
                    else:
                        curve.append({"date": dates[i], "value": val})
                out["60/40"] = curve

    return out


def spy_monthly_returns(target_dates: list[str]) -> dict[str, float]:
    """Return a {date: spy_monthly_return} aligned to strategy rebalance dates,
    computed from the raw SPY adj-close series. First date is 0.0 (inception)."""
    spy = _load_adj_close("SPY")
    if spy is None or not target_dates:
        return {}
    prices = _resample_series_to_dates(spy, target_dates)
    out: dict[str, float] = {}
    prev = None
    for d, p in zip(target_dates, prices):
        if p is None:
            continue
        if prev is not None and prev > 0:
            out[d] = (p / prev) - 1.0
        prev = p
    return out


def vs_spy_stats(slot: int) -> dict:
    """Compute strategy vs SPY comparison metrics: SPY key stats + beta, alpha,
    correlation, info ratio, upside/downside capture, CAGR/return differentials.
    """
    s = strategy_by_slot(slot)
    if s is None:
        return {}
    monthly_strat = s["monthly_returns"] or {}
    if not monthly_strat:
        return {}
    dates = sorted(monthly_strat.keys())
    monthly_spy = spy_monthly_returns(dates)
    # Align on the intersection
    pairs = [(monthly_strat[d], monthly_spy[d]) for d in dates
             if monthly_strat.get(d) is not None and monthly_spy.get(d) is not None]
    if len(pairs) < 6:
        return {"spy_key_stats": {}, "vs_spy": {}}

    strat_rets = [p[0] for p in pairs]
    spy_rets   = [p[1] for p in pairs]
    n = len(pairs)

    # SPY standalone stats from the aligned window
    spy_ks = _compute_key_stats({f"d{i}": r for i, r in enumerate(spy_rets)})

    # Correlation
    ms = sum(strat_rets) / n
    mp = sum(spy_rets)   / n
    cov   = sum((a - ms) * (b - mp) for a, b in pairs) / max(n - 1, 1)
    var_s = sum((a - ms) ** 2 for a in strat_rets) / max(n - 1, 1)
    var_p = sum((b - mp) ** 2 for b in spy_rets)   / max(n - 1, 1)
    sd_s  = math.sqrt(var_s)
    sd_p  = math.sqrt(var_p)
    corr  = (cov / (sd_s * sd_p)) if (sd_s > 0 and sd_p > 0) else None
    beta  = (cov / var_p) if var_p > 0 else None
    # Monthly alpha → annualized
    alpha_m = ms - (beta or 0) * mp if beta is not None else None
    alpha_a = alpha_m * 12 if alpha_m is not None else None

    # Active returns, information ratio
    active = [a - b for a, b in pairs]
    ma = sum(active) / n
    va = sum((x - ma) ** 2 for x in active) / max(n - 1, 1)
    sda = math.sqrt(va)
    info_ratio = (ma * 12) / (sda * math.sqrt(12)) if sda > 0 else None

    # Upside / downside capture
    up_s = [a for a, b in pairs if b > 0]
    up_p = [b for a, b in pairs if b > 0]
    dn_s = [a for a, b in pairs if b < 0]
    dn_p = [b for a, b in pairs if b < 0]
    up_capture = (sum(up_s) / sum(up_p)) if up_p and sum(up_p) != 0 else None
    dn_capture = (sum(dn_s) / sum(dn_p)) if dn_p and sum(dn_p) != 0 else None

    # Cumulative excess return over the aligned window
    cum_strat = 1.0; cum_spy = 1.0
    for a, b in pairs:
        cum_strat *= (1 + a); cum_spy *= (1 + b)
    excess_total = (cum_strat - 1) - (cum_spy - 1)
    # Annualized CAGR diff
    years = n / 12
    cagr_strat = cum_strat ** (1 / years) - 1 if years > 0 else None
    cagr_spy   = cum_spy   ** (1 / years) - 1 if years > 0 else None
    cagr_diff  = (cagr_strat - cagr_spy) if (cagr_strat is not None and cagr_spy is not None) else None

    return {
        "spy_key_stats": spy_ks,
        "vs_spy": {
            "correlation":    corr,
            "beta":           beta,
            "alpha_annual":   alpha_a,
            "info_ratio":     info_ratio,
            "up_capture":     up_capture,
            "down_capture":   dn_capture,
            "excess_total":   excess_total,
            "cagr_diff":      cagr_diff,
            "n_months":       n,
        },
    }


def comparison_matrix() -> dict:
    """Full comparison: metrics table + monthly returns series aligned across strategies."""
    regs = strategy_registry()
    strategies: list[dict] = []
    for s in regs:
        bt = s["backtest"] or {}
        strategies.append({
            "slot":    s["slot"],
            "slot_id": s["slot_id"],
            "name":    s["name"],
            "tier":    s["tier"],
            "cagr":    bt.get("cagr"),
            "sharpe":  bt.get("sharpe"),
            "max_dd":  bt.get("max_dd"),
            "sortino": bt.get("sortino"),
            "win_pct": bt.get("win_pct"),
            "worst_year": bt.get("worst_year"),
            "n_months": s["n_months"],
        })

    # Backtest monthly returns per strategy → aligned date index
    series: dict[str, dict[str, float]] = {}
    all_dates: set[str] = set()
    for s in regs:
        mr = s["monthly_returns"] or {}
        series[s["name"]] = mr
        all_dates.update(mr.keys())
    dates = sorted(all_dates)

    # Build equity curves from monthly returns, base=1.0
    equity_curves: dict[str, list[dict]] = {}
    for s in regs:
        mr = series[s["name"]]
        val = 1.0
        curve = []
        for d in dates:
            r = mr.get(d)
            if r is not None:
                val *= (1.0 + float(r))
            curve.append({"date": d, "value": val})
        equity_curves[s["name"]] = curve

    # Correlation matrix on monthly returns
    corr = _corr_matrix({s["name"]: series[s["name"]] for s in regs}, dates)

    # Best/worst highlight per column
    highlights = _highlight_best_worst(strategies,
                                       higher_is_better=("cagr", "sharpe", "sortino", "win_pct"),
                                       lower_is_better=("max_dd", "worst_year"))
    return {
        "strategies":    strategies,
        "dates":         dates,
        "equity_curves": equity_curves,
        "benchmarks":    benchmark_curves(dates),
        "correlation":   corr,
        "highlights":    highlights,
    }


def _highlight_best_worst(rows: list[dict], higher_is_better: tuple, lower_is_better: tuple) -> dict:
    out: dict[str, dict[str, str]] = {}
    for col in higher_is_better + lower_is_better:
        vals = [(r["name"], r.get(col)) for r in rows if r.get(col) is not None]
        if not vals:
            continue
        reverse = col in higher_is_better
        vals.sort(key=lambda x: x[1], reverse=reverse)
        if vals:
            out.setdefault(vals[0][0], {})[col] = "best"
            out.setdefault(vals[-1][0], {})[col] = "worst"
    return out


def _corr_matrix(series: dict[str, dict[str, float]], dates: list[str]) -> dict:
    names = list(series.keys())
    # Build aligned vectors
    vectors: dict[str, list[float]] = {}
    for name, mr in series.items():
        vectors[name] = [float(mr.get(d)) if mr.get(d) is not None else float("nan") for d in dates]

    def pearson(a: list[float], b: list[float]) -> float | None:
        pairs = [(x, y) for x, y in zip(a, b) if not (math.isnan(x) or math.isnan(y))]
        if len(pairs) < 6:
            return None
        ax = [p[0] for p in pairs]; bx = [p[1] for p in pairs]
        ma = sum(ax) / len(ax); mb = sum(bx) / len(bx)
        num = sum((x - ma) * (y - mb) for x, y in pairs)
        da  = math.sqrt(sum((x - ma) ** 2 for x in ax))
        db  = math.sqrt(sum((y - mb) ** 2 for y in bx))
        if da == 0 or db == 0:
            return None
        return num / (da * db)

    matrix: list[list[float | None]] = []
    for a in names:
        row = []
        for b in names:
            row.append(1.0 if a == b else pearson(vectors[a], vectors[b]))
        matrix.append(row)
    return {"labels": names, "matrix": matrix}


# ═══════════════════════════════════════════════════════════════════════════
# Data health / regime / rebalance log
# ═══════════════════════════════════════════════════════════════════════════

_DATA_SOURCES = [
    ("Yahoo ETFs",    "prices",   _ROOT / "data" / "raw" / "yahoo"),
    ("Stock bars",    "prices",   _ROOT / "data" / "raw" / "bars"),
    ("FRED macro",    "macro",    _ROOT / "data" / "raw" / "fred"),
    ("News",          "alt",      _ROOT / "data" / "raw" / "news"),
    ("Features",      "features", _ROOT / "data" / "features"),
    ("Models",        "models",   _ROOT / "data" / "models"),
    ("Rebalance log", "logs",     _REBAL_LOG),
    ("Backtest data", "backtest", _BACKTEST_JSON),
]

# FRED series worth flagging individually (used by classifier / regime model).
# If the file's there, report it; otherwise silently skip.
_FRED_KEY_SERIES = [
    ("DFF",      "Fed funds rate"),
    ("DGS10",    "10y Treasury"),
    ("DGS2",     "2y Treasury"),
    ("T10Y2Y",   "10y-2y spread"),
    ("CPIAUCSL", "CPI headline"),
    ("CPILFESL", "CPI core"),
    ("UNRATE",   "Unemployment"),
    ("VIXCLS",   "VIX close"),
    ("BAMLH0A0HYM2", "HY OAS"),
    ("BAMLC0A4CBBB", "BBB OAS"),
    ("USEPUINDXD",   "Econ policy uncertainty"),
    ("DCOILBRENTEU", "Brent crude"),
]


def _required_universe() -> set[str]:
    """Union of every ETF mentioned in any strategy YAML universe/cash_proxy."""
    out: set[str] = set()
    for s in strategy_registry():
        spec = s.get("spec") or {}
        for sym in spec.get("universe") or []:
            if isinstance(sym, str):
                out.add(sym.upper())
        cash = spec.get("cash_proxy")
        if isinstance(cash, str):
            out.add(cash.upper())
        bench = spec.get("reference_index")
        if isinstance(bench, str):
            out.add(bench.upper())
    return out


def _scan_dir(path: Path) -> tuple[int, int, float]:
    """Recursively scan a directory — return (n_files, total_bytes, newest_mtime)."""
    if not path.exists():
        return (0, 0, 0.0)
    if path.is_file():
        st = path.stat()
        return (1, st.st_size, st.st_mtime)
    n = 0; total = 0; newest = 0.0
    for p in path.rglob("*"):
        if p.is_file():
            st = p.stat()
            n += 1
            total += st.st_size
            if st.st_mtime > newest:
                newest = st.st_mtime
    return (n, total, newest)


def _parquet_last_date(path: Path) -> str | None:
    """Read a parquet's index (Date) and return the last entry as 'YYYY-MM-DD'.

    Uses the cached series loader where possible, otherwise reads the file.
    """
    try:
        import pandas as pd
        df = pd.read_parquet(path)
        idx = df.index
        if len(idx) == 0:
            return None
        last = idx[-1]
        if hasattr(last, "strftime"):
            return last.strftime("%Y-%m-%d")
        return str(last)[:10]
    except Exception:
        return None


_dh_cache: tuple[float, dict] | None = None
_dh_lock = Lock()
_DH_TTL = 60.0


def data_health_summary() -> dict:
    """Rich data health report: per-source rollups, required ETF freshness,
    FRED key series, and overall status. Cached for 60 s.
    """
    global _dh_cache
    now = time.time()
    with _dh_lock:
        if _dh_cache and (now - _dh_cache[0]) < _DH_TTL:
            return _dh_cache[1]

    worst = "ok"
    sources: list[dict] = []
    total_files = 0
    total_bytes = 0

    for label, kind, path in _DATA_SOURCES:
        if not path.exists():
            sources.append({
                "name": label, "kind": kind, "status": "missing",
                "age": "—", "age_s": None,
                "n_files": 0, "size_fmt": "—",
                "path": str(path.relative_to(_ROOT)) if str(path).startswith(str(_ROOT)) else str(path),
            })
            worst = "alert"
            continue

        n, size, newest = _scan_dir(path)
        total_files += n
        total_bytes += size
        age = now - newest if newest else None

        if age is None:
            status = "missing"; worst = "alert"
        elif age > 14 * 86400:
            status = "alert"; worst = "alert"
        elif age > 7 * 86400:
            status = "stale"
            if worst == "ok": worst = "warning"
        else:
            status = "ok"

        sources.append({
            "name":     label,
            "kind":     kind,
            "status":   status,
            "age_s":    age,
            "age":      _fmt_age(age) if age is not None else "—",
            "n_files":  n,
            "size_fmt": _fmt_bytes(size),
            "path":     str(path.relative_to(_ROOT)),
        })

    # Required ETF freshness — union of all strategy universes
    required = sorted(_required_universe())
    etf_rows: list[dict] = []
    stale_etfs = 0
    missing_etfs = 0
    for sym in required:
        p = _YAHOO_DIR / f"{sym}.parquet"
        if not p.exists():
            etf_rows.append({"symbol": sym, "status": "missing", "latest": None, "age": "—"})
            missing_etfs += 1
            continue
        last = _parquet_last_date(p)
        st_age = None
        sym_status = "ok"
        if last:
            try:
                import datetime as dt
                last_ts = dt.datetime.strptime(last, "%Y-%m-%d")
                st_age = (dt.datetime.now() - last_ts).total_seconds()
                if st_age > 14 * 86400:
                    sym_status = "alert"; stale_etfs += 1
                elif st_age > 7 * 86400:
                    sym_status = "stale"; stale_etfs += 1
            except Exception:
                pass
        etf_rows.append({
            "symbol": sym,
            "status": sym_status,
            "latest": last,
            "age":    _fmt_age(st_age) if st_age is not None else "—",
        })
    if missing_etfs > 0:
        worst = "alert"
    elif stale_etfs > 0 and worst == "ok":
        worst = "warning"

    # FRED key series snapshot
    fred_rows: list[dict] = []
    fred_dir = _ROOT / "data" / "raw" / "fred"
    if fred_dir.exists():
        for code, label in _FRED_KEY_SERIES:
            p = fred_dir / f"{code}.parquet"
            if not p.exists():
                continue
            last = _parquet_last_date(p)
            age_s = None
            if last:
                try:
                    import datetime as dt
                    age_s = (dt.datetime.now() - dt.datetime.strptime(last, "%Y-%m-%d")).total_seconds()
                except Exception:
                    pass
            fred_rows.append({
                "code":    code,
                "label":   label,
                "latest":  last,
                "age":     _fmt_age(age_s) if age_s is not None else "—",
            })

    result = {
        "status":   worst,
        "sources":  sources,
        "summary": {
            "total_files":   total_files,
            "total_size_fmt": _fmt_bytes(total_bytes),
            "n_sources":     sum(1 for s in sources if s["status"] != "missing"),
            "n_required_etfs": len(required),
            "n_stale_etfs":    stale_etfs,
            "n_missing_etfs":  missing_etfs,
        },
        "required_etfs": etf_rows,
        "fred_series":   fred_rows,
    }
    with _dh_lock:
        _dh_cache = (now, result)
    return result


def _fmt_bytes(n: float) -> str:
    n = float(n)
    for u in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.0f} {u}" if u == "B" else f"{n:.1f} {u}"
        n /= 1024
    return f"{n:.1f} PB"


def rebalance_log(limit: int = 100) -> list[dict]:
    log = load_rebalance_log()
    return log[-limit:][::-1]


_rationale_cache: tuple[float, dict[int, str]] | None = None


def strategy_rationale() -> dict[int, str]:
    """Parse STRATEGY_SELECTION.md into {slot: markdown_block}.

    Each slot section is a ``### Slot N — NAME`` header followed by paragraphs
    until the next ``###`` or ``---``.
    """
    global _rationale_cache
    if not _SELECTION_MD.exists():
        return {}
    mt = _safe_mtime(_SELECTION_MD)
    if _rationale_cache and _rationale_cache[0] == mt:
        return _rationale_cache[1]

    import re
    text = _SELECTION_MD.read_text(encoding="utf-8")
    pattern = re.compile(r"### Slot (\d+)[^\n]*\n(.*?)(?=\n### |\n---\n|\Z)", re.S)
    out: dict[int, str] = {}
    for m in pattern.finditer(text):
        slot = int(m.group(1))
        body = m.group(2).strip()
        out[slot] = body
    _rationale_cache = (mt, out)
    return out


def load_presentation() -> dict:
    """Cached load of the OPTIMIZED presentation artifact (slot 1).

    Contains precomputed key_stats / rolling_sharpe / drawdowns / monthly_heatmap
    / attribution.per_year. Returned as-is; caller picks the pieces it needs.
    """
    return _load_json(_PRESENTATION) or {}


def _compute_key_stats(monthly: dict[str, float]) -> dict:
    """Compute Sharpe / Sortino / MaxDD / Calmar / win-rate / etc from a
    monthly-returns dict. Used for slots 2-9 which lack a presentation artifact.
    """
    if not monthly:
        return {}
    dates = sorted(monthly.keys())
    rets  = [float(monthly[d]) for d in dates if monthly[d] is not None]
    if not rets:
        return {}
    n = len(rets)
    mean = sum(rets) / n
    var  = sum((r - mean) ** 2 for r in rets) / max(n - 1, 1)
    std  = math.sqrt(var)
    neg  = [r for r in rets if r < 0]
    down_var = sum(r * r for r in neg) / max(n - 1, 1)
    down_std = math.sqrt(down_var)
    sharpe  = (mean * 12) / (std * math.sqrt(12)) if std > 0 else None
    sortino = (mean * 12) / (down_std * math.sqrt(12)) if down_std > 0 else None
    # Equity curve + max drawdown
    val = 1.0; peak = 1.0; max_dd = 0.0
    for r in rets:
        val *= (1.0 + r)
        peak = max(peak, val)
        dd = val / peak - 1.0
        if dd < max_dd:
            max_dd = dd
    n_years = n / 12
    cagr = (val ** (1 / n_years) - 1) if n_years > 0 else None
    calmar = (cagr / abs(max_dd)) if (cagr is not None and max_dd < 0) else None
    return {
        "cagr":        cagr,
        "sharpe":      sharpe,
        "sortino":     sortino,
        "max_dd":      max_dd,
        "calmar":      calmar,
        "best_month":  max(rets),
        "worst_month": min(rets),
        "win_rate":    sum(1 for r in rets if r > 0) / n,
        "avg_month":   mean,
        "vol_annual":  std * math.sqrt(12),
        "n_months":    n,
    }


def _compute_rolling_sharpe(monthly: dict[str, float], window: int = 12) -> list[dict]:
    if not monthly:
        return []
    dates = sorted(monthly.keys())
    rets  = [float(monthly[d]) if monthly[d] is not None else None for d in dates]
    out: list[dict] = []
    for i in range(len(rets)):
        if i < window - 1:
            out.append({"date": dates[i], "value": None})
            continue
        win = [r for r in rets[i - window + 1:i + 1] if r is not None]
        if len(win) < window:
            out.append({"date": dates[i], "value": None})
            continue
        m = sum(win) / len(win)
        v = sum((r - m) ** 2 for r in win) / (len(win) - 1) if len(win) > 1 else 0.0
        s = math.sqrt(v)
        val = (m * 12) / (s * math.sqrt(12)) if s > 0 else None
        out.append({"date": dates[i], "value": val})
    return out


def _compute_drawdowns(monthly: dict[str, float]) -> list[dict]:
    if not monthly:
        return []
    dates = sorted(monthly.keys())
    val = 1.0; peak = 1.0
    out: list[dict] = []
    for d in dates:
        r = monthly[d]
        if r is None:
            out.append({"date": d, "dd": 0.0})
            continue
        val *= (1.0 + float(r))
        peak = max(peak, val)
        out.append({"date": d, "dd": val / peak - 1.0})
    return out


def _compute_heatmap(monthly: dict[str, float]) -> list[dict]:
    if not monthly:
        return []
    out = []
    for d in sorted(monthly.keys()):
        # date strings are "YYYY-MM-DD"
        try:
            y = int(d[:4]); m = int(d[5:7])
        except Exception:
            continue
        r = monthly[d]
        out.append({"year": y, "month": m, "ret": float(r) if r is not None else None})
    return out


def strategy_stats(slot: int) -> dict:
    """Return extended per-slot stats: key_stats, rolling_sharpe, drawdowns,
    monthly_heatmap, attribution. Slot 1 pulls from the presentation artifact
    where available; other slots compute on the fly.
    """
    s = strategy_by_slot(slot)
    if s is None:
        return {}
    monthly = s["monthly_returns"] or {}
    pres = load_presentation() if slot == 1 else {}

    if pres:
        ks  = (pres.get("key_stats") or {}).get("strategy") or {}
        rs  = pres.get("rolling_sharpe") or []
        dd  = (pres.get("drawdowns") or {}).get("strategy") or []
        hm  = pres.get("monthly_heatmap") or []
        att = (pres.get("attribution") or {}).get("per_year") or []
        spy_dd = (pres.get("drawdowns") or {}).get("spy") or []
    else:
        ks  = _compute_key_stats(monthly)
        rs_raw = _compute_rolling_sharpe(monthly)
        rs  = [{"date": r["date"], "strategy": r["value"], "spy": None} for r in rs_raw]
        dd  = _compute_drawdowns(monthly)
        hm  = _compute_heatmap(monthly)
        att = []  # component attribution only available for OPTIMIZED
        # Compute SPY drawdowns aligned to this strategy's monthly dates
        spy_rets = spy_monthly_returns(sorted(monthly.keys()))
        spy_dd = _compute_drawdowns(spy_rets) if spy_rets else []

    # Merge metric fields from the multi-strategy backtest JSON so we always
    # have sharpe/cagr/max_dd even if presentation is empty.
    bt_metrics = s["backtest"] or {}
    merged: dict[str, object] = dict(ks)
    for k, v in bt_metrics.items():
        merged.setdefault(k, v)
    # Volatility if not present but we can compute it
    if "vol_annual" not in merged and monthly:
        merged["vol_annual"] = _compute_key_stats(monthly).get("vol_annual")

    return {
        "key_stats":      merged,
        "rolling_sharpe": rs,
        "drawdowns":      dd,
        "spy_drawdowns":  spy_dd,
        "monthly_heatmap": hm,
        "attribution":    att,
        "has_attribution": bool(att),
    }


def current_regime() -> dict:
    log = load_rebalance_log()
    if not log:
        return {"regime": None, "predicted": None, "source": "none"}
    last = log[-1]
    info = last.get("regime_info") or {}
    return {
        "regime":    info.get("current"),
        "predicted": info.get("predicted"),
        "lookback":  last.get("lookback"),
        "sma_dist":  last.get("sma_distance"),
        "fomc_def":  last.get("fomc_deferred"),
        "top1":      last.get("top1"),
        "topk":      last.get("topk"),
        "date":      last.get("date"),
        "source":    "rebalance_log",
    }
