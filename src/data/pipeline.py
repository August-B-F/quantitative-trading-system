"""Data pipeline: load master panel + pre-computed returns for the production run.

Two responsibilities:
1. Backtest path (`load_panel`): thin wrapper over /data/features/ artifacts,
   matching the canonical research load path in scripts/model/run_m26_deep.py.
2. Live refresh path (`refresh_all_data`): pull fresh prices + macro into
   /data/clean/ and report a per-source health dict for the rebalance script.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

log = logging.getLogger(__name__)

# Forward-fill limits in trading days (§4.1.2). Macro frequencies map to
# the limit applied when realigning each series onto the trading-day calendar.
FFILL_LIMITS = {"daily": 2, "weekly": 5, "monthly": 45, "quarterly": 66}

# Stale thresholds (calendar days) per frequency for the refresh status report.
STALE_DAYS = {"daily": 7, "weekly": 14, "monthly": 75, "quarterly": 200}


@dataclass
class PanelBundle:
    """Loaded panel + price-derived arrays for the backtest engine."""
    df: pd.DataFrame                      # master panel (DatetimeIndex x features)
    dates: pd.DatetimeIndex
    returns: dict[int, pd.DataFrame]      # {lookback_days: returns df}
    atr21: pd.DataFrame                   # ATR21 per-ticker (vol proxy for inv-vol)
    fwd21: dict[str, np.ndarray]          # ticker -> forward-21d returns
    spy_dist_sma200: np.ndarray           # (NDAYS,)
    is_fomc_day: np.ndarray               # (NDAYS,) bool


def load_config(root: Path) -> dict:
    """Load strategy.yaml."""
    with open(root / "configs/strategy.yaml", "r") as f:
        return yaml.safe_load(f)


def load_panel(root: Path, cfg: dict) -> PanelBundle:
    """Load master panel, returns, atr, and derived arrays needed by the engine."""
    root = Path(root)
    panel_path = root / cfg["paths"]["master_panel"]
    rdir = root / cfg["paths"]["returns_dir"]
    log.info("loading master panel: %s", panel_path)
    df = pd.read_parquet(panel_path)
    dates = df.index

    # Universe + any extras the feature frames cover
    universe = list(cfg["universe"])
    extras = list(cfg.get("feature_extras", []))
    all_tickers = sorted(set(universe) | set(extras) | {cfg["reference_index"]})

    # Pre-computed N-day total return tables (used for momentum + fwd21)
    returns = {}
    for n in (10, 21, 42, 63, 126):
        p = rdir / f"returns_{n}d.parquet"
        if p.exists():
            returns[n] = pd.read_parquet(p).reindex(dates)

    atr21 = pd.read_parquet(rdir / "atr_21d.parquet").reindex(dates)

    # forward 21d return per ticker — prefer TARGET_FWD21_<t> columns if present,
    # else shift the returns_21d frame (matches run_m26_deep.py:60-65)
    fwd21 = {}
    for t in all_tickers:
        col = f"TARGET_FWD21_{t}"
        if col in df.columns:
            fwd21[t] = df[col].values
        elif 21 in returns and t in returns[21].columns:
            fwd21[t] = returns[21][t].shift(-21).reindex(dates).values
        else:
            fwd21[t] = np.full(len(dates), np.nan)

    # SPY distance from SMA200 lives in the panel (quality_dist_sma200__SPY)
    sma_col = f"quality_dist_sma200__{cfg['sma_gate_index']}"
    if sma_col not in df.columns:
        raise KeyError(f"missing {sma_col} in master panel")
    spy_dist = df[sma_col].values

    # FOMC day flag from the timing features block
    fomc_col = "timing__is_fomc_day"
    if fomc_col in df.columns:
        is_fomc_day = (df[fomc_col].values > 0)
    else:
        log.warning("no %s in panel; FOMC deferral will never fire", fomc_col)
        is_fomc_day = np.zeros(len(dates), dtype=bool)

    return PanelBundle(
        df=df,
        dates=dates,
        returns=returns,
        atr21=atr21,
        fwd21=fwd21,
        spy_dist_sma200=spy_dist,
        is_fomc_day=is_fomc_day,
    )


# ======================================================================
# Live refresh path — used by the rebalance script on rebalance day.
# ======================================================================

def _trading_calendar(start: str, end: pd.Timestamp) -> pd.DatetimeIndex:
    try:
        import pandas_market_calendars as mcal
        cal = mcal.get_calendar("NYSE")
        sched = cal.schedule(start_date=start, end_date=end)
        return pd.DatetimeIndex(sched.index).tz_localize(None)
    except Exception:
        return pd.bdate_range(start=start, end=end)


def _append_clean_parquet(path: Path, new_df: pd.DataFrame) -> pd.DataFrame:
    """Merge `new_df` into the existing parquet at `path`, dedupe, return final frame."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        old = pd.read_parquet(path)
        merged = pd.concat([old, new_df]).sort_index()
        merged = merged[~merged.index.duplicated(keep="last")]
    else:
        merged = new_df.sort_index()
    merged.to_parquet(path)
    return merged


def _refresh_prices(root: Path, cfg: dict) -> dict:
    """Fetch latest OHLCV for universe + reference + extras + VIX, append to /data/clean/prices/."""
    from src.data.fetchers.yahoo_prices import fetch_ohlcv

    tickers = list(dict.fromkeys(
        list(cfg["universe"]) + [cfg["reference_index"]]
        + list(cfg.get("feature_extras", [])) + ["^VIX"]
    ))
    out_dir = root / cfg["paths"]["prices_clean"]
    out_dir.mkdir(parents=True, exist_ok=True)

    # 6 months of history overlap is plenty to backfill any gap and recompute
    # rolling stats; canonical history was built once in phase1_download.
    start = (pd.Timestamp.utcnow().normalize().tz_localize(None) - pd.Timedelta(days=180)).date().isoformat()
    panels = fetch_ohlcv(tickers, start=start)
    if panels is None:
        return {"status": "error", "latest_date": None, "gaps": [], "error": "yahoo_unavailable"}

    latest_dates = []
    gaps = []
    for t, df in panels.items():
        df = df.dropna(subset=["adj_close"])
        if df.empty:
            gaps.append(t)
            continue
        fname = "_VIX.parquet" if t == "^VIX" else f"{t}.parquet"
        merged = _append_clean_parquet(out_dir / fname, df)
        latest_dates.append(merged.index.max())

    if not latest_dates:
        return {"status": "error", "latest_date": None, "gaps": gaps, "error": "all_tickers_empty"}

    latest = max(latest_dates).date().isoformat()
    return {
        "status": "ok" if not gaps else "degraded",
        "latest_date": latest,
        "gaps": gaps,
        "tickers": len(panels),
    }


# Map config-yaml key -> (descriptive_filename, freq) for /data/clean/macro/.
_MACRO_FILE_FREQ = {
    "cpi_yoy":              ("cpi_all_urban",       "monthly"),
    "cpi_mom":              ("cpi_all_urban",       "monthly"),
    "breakeven_5y":         ("breakeven_5y",        "daily"),
    "breakeven_10y":        ("breakeven_10y",       "daily"),
    "ism_pmi_proxy_indpro": ("industrial_production","monthly"),
    "ism_pmi_proxy_tcu":    ("capacity_utilization", "monthly"),
    "capacity_utilization": ("capacity_utilization", "monthly"),
    "initial_claims":       ("initial_claims",      "weekly"),
    "oecd_cli":             ("oecd_cli_us",         "monthly"),
    "rail_traffic":         ("rail_traffic",        "monthly"),
    "consumer_credit":      ("consumer_credit_total","monthly"),
    "margin_debt":          ("margin_debt_fred",    "quarterly"),
    "wti_crude":            ("wti_crude",           "daily"),
}


def _refresh_macro(root: Path, cfg: dict) -> dict:
    """Fetch every FRED series in data_sources.yaml, append to /data/clean/macro/."""
    from src.data.fetchers.fred_macro import fetch_fred_series

    macro_dir = root / cfg["paths"]["macro_clean"]
    macro_dir.mkdir(parents=True, exist_ok=True)

    fred_cfg = cfg.get("fred_series_map") or {}  # not used; we read data_sources
    with open(root / "configs/data_sources.yaml") as f:
        ds = yaml.safe_load(f)

    today = pd.Timestamp.utcnow().normalize().tz_localize(None)
    cal = _trading_calendar("2003-01-01", today)

    fetched, stale, errors = [], [], []
    for key, sid in ds["fred"].items():
        fname, freq = _MACRO_FILE_FREQ.get(key, (key, "monthly"))
        df = fetch_fred_series(sid, cache_dir=macro_dir)
        if df.empty:
            errors.append(f"{key}({sid})")
            continue
        df.columns = [fname]

        # forward-fill onto the trading calendar within the freq budget
        ffill_limit = FFILL_LIMITS.get(freq, 5)
        union = cal.union(df.index)
        aligned = df.reindex(union).ffill(limit=ffill_limit).reindex(cal)
        aligned = aligned.dropna(how="all")

        merged = _append_clean_parquet(macro_dir / f"{fname}.parquet", aligned)

        latest = merged.dropna().index.max()
        days_stale = (today - latest).days
        if days_stale > STALE_DAYS.get(freq, 30):
            stale.append(key)
        fetched.append(key)

    status = "ok" if not errors else ("degraded" if fetched else "error")
    return {
        "status": status,
        "series_count": len(fetched),
        "stale": stale,
        "errors": errors,
    }


def _refresh_fomc(root: Path, cfg: dict) -> dict:
    """Load the FOMC calendar (manual annual update, no live fetch)."""
    p = root / cfg["paths"]["fomc_calendar"]
    if not p.exists():
        return {"status": "error", "next_meeting": None, "error": f"missing {p}"}
    df = pd.read_parquet(p)
    if "is_fomc_day" not in df.columns:
        return {"status": "error", "next_meeting": None, "error": "no is_fomc_day column"}
    today = pd.Timestamp.utcnow().normalize().tz_localize(None)
    upcoming = df.index[(df.index >= today) & (df["is_fomc_day"] > 0)]
    nxt = upcoming.min().date().isoformat() if len(upcoming) else None
    last_calendar_date = df.index.max().date().isoformat()
    return {
        "status": "ok",
        "next_meeting": nxt,
        "calendar_through": last_calendar_date,
    }


def rebuild_features(root: Path | None = None) -> dict:
    """Recompute the per-feature parquets the live signal path reads from.

    Targeted at the CORE feature set: re-runs `engineer` price builders
    over the freshly refreshed `data/clean/prices/` and `macro_features`
    over `data/clean/macro/`. We invoke the canonical builders rather than
    re-implementing slices, so the output is byte-identical to the panel
    construction path. Returns a small status dict for the caller log.
    """
    root = Path(root) if root else Path(__file__).resolve().parents[2]
    import contextlib, io as _io, sys as _sys
    if str(root) not in _sys.path:
        _sys.path.insert(0, str(root))
    if str(root / "src") not in _sys.path:
        _sys.path.insert(0, str(root / "src"))

    from src.features import engineer as eng  # noqa: WPS433
    from src.features import macro_features as macf  # noqa: WPS433

    out = {"price_features": "ok", "macro_features": "ok", "errors": []}

    try:
        prices = eng.load_prices(eng.ALL_TICKERS)
        close = eng._stack("adj_close", prices)
        high = eng._stack("high", prices)
        low = eng._stack("low", prices)
        # silence the catalog-print noise from the builders
        with contextlib.redirect_stdout(_io.StringIO()):
            eng.step2_returns(close)
            eng.step3_volatility(close, high, low)
            eng.step4_quality(close, high, low)
            eng.step5_cross_sectional(close)
            eng.step6_volume(prices)
            eng.step7_relative_strength(close)
    except Exception as e:
        log.exception("price feature rebuild failed")
        out["price_features"] = "error"
        out["errors"].append(f"price: {e}")

    try:
        with contextlib.redirect_stdout(_io.StringIO()):
            macf.build()
    except Exception as e:
        log.exception("macro feature rebuild failed")
        out["macro_features"] = "error"
        out["errors"].append(f"macro: {e}")

    return out


def refresh_and_rebuild(root: Path | None = None) -> dict:
    """Live refresh + targeted feature rebuild for the rebalance script."""
    status = refresh_all_data(root)
    if status.get("prices", {}).get("status") in ("ok", "degraded"):
        status["rebuild"] = rebuild_features(root)
    else:
        status["rebuild"] = {"status": "skipped", "reason": "prices_unavailable"}
    return status


def refresh_all_data(root: Path | None = None) -> dict:
    """Refresh prices, macro, and FOMC for live rebalance day. Returns status dict."""
    root = Path(root) if root else Path(__file__).resolve().parents[2]
    cfg = load_config(root)

    status: dict = {"prices": {}, "macro": {}, "fomc": {}, "errors": []}
    try:
        status["prices"] = _refresh_prices(root, cfg)
    except Exception as e:
        log.exception("price refresh failed")
        status["prices"] = {"status": "error", "error": str(e)}
        status["errors"].append(f"prices: {e}")

    try:
        status["macro"] = _refresh_macro(root, cfg)
    except Exception as e:
        log.exception("macro refresh failed")
        status["macro"] = {"status": "error", "error": str(e)}
        status["errors"].append(f"macro: {e}")

    try:
        status["fomc"] = _refresh_fomc(root, cfg)
    except Exception as e:
        log.exception("fomc refresh failed")
        status["fomc"] = {"status": "error", "error": str(e)}
        status["errors"].append(f"fomc: {e}")

    return status
