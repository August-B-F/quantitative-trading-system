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

# Live-extension forward-fill budget in trading-day rows (~45 calendar days).
# Applied to NON-TARGET_ feature columns only when `load_panel(live_extend=True)`
# stretches the stale master-panel index onto the fresh price-feature calendar.
LIVE_FFILL_LIMIT = 31


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
    freshness: dict | None = None         # live_extend metadata (see load_panel)


def load_config(root: Path) -> dict:
    with open(root / "configs/strategy.yaml", "r") as f:
        return yaml.safe_load(f)


def load_panel(root: Path, cfg: dict, live_extend: bool = False) -> PanelBundle:
    """Load master panel, returns, atr, and derived arrays needed by the engine.

    With ``live_extend=False`` (research/backtest path) the output is
    byte-identical to the historical behavior: everything is reindexed onto
    the master panel's own DatetimeIndex.

    With ``live_extend=True`` (live signal path) the panel index is extended
    to the union with the fresh per-feature price parquets (which are rebuilt
    nightly and may run months past a stale master panel):

    - ``quality_dist_sma200__<ticker>`` columns are overwritten from the fresh
      ``quality_dist_sma200.parquet`` so the SMA gate input is never stale/NaN
      at the tail while the parquet has data.
    - All NON-``TARGET_`` feature columns are forward-filled with a budget of
      ``LIVE_FFILL_LIMIT`` trading days. ``TARGET_`` columns are NEVER filled.
    - ``fwd21`` prefers the panel's ``TARGET_FWD21_<t>`` values but backfills
      post-panel dates from the fresh ``returns_21d`` table (honest NaN tail).
    - ``bundle.freshness`` records ``panel_raw_max`` (pre-extension max),
      ``as_of`` (post-extension max), ``extended_days`` (rows added), and
      ``stale_core_features`` (CORE columns whose raw data ends more than
      ``LIVE_FFILL_LIMIT`` trading days before ``as_of``).
    """
    root = Path(root)
    panel_path = root / cfg["paths"]["master_panel"]
    rdir = root / cfg["paths"]["returns_dir"]
    log.info("loading master panel: %s", panel_path)
    df = pd.read_parquet(panel_path)
    dates = df.index
    freshness: dict | None = None

    if live_extend:
        panel_raw_max = dates.max()
        n_raw = len(dates)
        r63_idx = pd.read_parquet(rdir / "returns_63d.parquet").index
        q_fresh = pd.read_parquet(rdir / "quality_dist_sma200.parquet")
        new_dates = dates.union(r63_idx).union(q_fresh.index)
        if len(new_dates) > n_raw:
            log.info("live_extend: panel index %s -> %s (+%d rows)",
                     panel_raw_max.date(), new_dates.max().date(),
                     len(new_dates) - n_raw)
        df = df.reindex(new_dates)
        dates = df.index

    # Universe + any extras the feature frames cover
    universe = list(cfg["universe"])
    extras = list(cfg.get("feature_extras", []))
    all_tickers = sorted(set(universe) | set(extras) | {cfg["reference_index"]})

    # Pre-computed N-day total return tables (used for momentum + fwd21).
    # In live_extend mode `dates` is already the extended index, so the fresh
    # tail of these tables survives the reindex instead of being truncated.
    returns = {}
    for n in (10, 21, 42, 63, 126):
        p = rdir / f"returns_{n}d.parquet"
        if p.exists():
            returns[n] = pd.read_parquet(p).reindex(dates)

    atr21 = pd.read_parquet(rdir / "atr_21d.parquet").reindex(dates)

    if live_extend:
        # Overwrite quality_dist_sma200__<t> from the fresh parquet wherever
        # it has data (the panel copy is stale at — or missing from — the tail).
        q_aligned = q_fresh.reindex(dates)
        for col in df.columns:
            if not col.startswith("quality_dist_sma200__"):
                continue
            t = col.split("__", 1)[1]
            if t in q_aligned.columns:
                df[col] = q_aligned[t].combine_first(df[col])

        # Staleness audit BEFORE forward-fill so the ffill cannot mask it.
        with open(root / "configs/feature_sets.yaml", "r") as f:
            core_cols = list(yaml.safe_load(f).get("core", []))
        n_days = len(dates)
        stale_core: list[str] = []
        for c in core_cols:
            if c not in df.columns:
                continue
            lv = df[c].last_valid_index()
            if lv is None or (n_days - 1 - dates.get_loc(lv)) > LIVE_FFILL_LIMIT:
                stale_core.append(c)
        if stale_core:
            log.warning("live_extend: %d CORE features end > %d trading days "
                        "before as_of (first few: %s)",
                        len(stale_core), LIVE_FFILL_LIMIT, stale_core[:5])

        # Forward-fill features into the EXTENSION ROWS ONLY — never TARGET_
        # columns, and never historical rows: the panel build deliberately
        # left historical NaN gaps (per-frequency FFILL_LIMITS), and filling
        # them here would train the live classifier on inputs the research
        # path never saw.
        non_target = [c for c in df.columns if not c.startswith("TARGET_")]
        ext_mask = dates > panel_raw_max
        if ext_mask.any():
            filled = df[non_target].ffill(limit=LIVE_FFILL_LIMIT)
            df.loc[ext_mask, non_target] = filled.loc[ext_mask, non_target]

        # The FOMC flag is a binary EVENT, not a level — forward-filling it
        # would smear (or hide) meetings across the live tail. Fill extension
        # rows from the actual FOMC calendar instead.
        fomc_col = "timing__is_fomc_day"
        if fomc_col in df.columns and ext_mask.any():
            df.loc[ext_mask, fomc_col] = 0.0
            fomc_path = root / cfg["paths"].get("fomc_calendar", "")
            if fomc_path.is_file():
                cal = pd.read_parquet(fomc_path)
                if "is_fomc_day" in cal.columns:
                    flag = cal["is_fomc_day"].reindex(dates).fillna(0.0)
                    df.loc[ext_mask, fomc_col] = flag[ext_mask].values
            else:
                log.warning("live_extend: FOMC calendar missing — extension "
                            "rows assume no FOMC days")

        # Raw (pre-ffill) recency of the SMA-gate input — the rebalance gate
        # refuses to trade when this lags, because a forward-filled gate value
        # passes a NaN check while being weeks old.
        gate_ticker = cfg.get("sma_gate_index", "SPY")
        spy_dist_last_valid = (
            q_fresh[gate_ticker].last_valid_index()
            if gate_ticker in q_fresh.columns else None
        )

        freshness = {
            "panel_raw_max": panel_raw_max,
            "as_of": dates.max(),
            "extended_days": int(len(dates) - n_raw),
            "stale_core_features": stale_core,
            "spy_dist_last_valid": spy_dist_last_valid,
        }

    # forward 21d return per ticker — prefer TARGET_FWD21_<t> columns if present,
    # else shift the returns_21d frame (matches run_m26_deep.py:60-65)
    fwd21 = {}
    for t in all_tickers:
        col = f"TARGET_FWD21_{t}"
        if col in df.columns:
            s = df[col]
            if live_extend and 21 in returns and t in returns[21].columns:
                # Post-panel dates get real forward returns where computable;
                # the last 21 rows stay NaN (honest tail).
                s = s.combine_first(returns[21][t].shift(-21))
            fwd21[t] = s.values
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
        freshness=freshness,
    )


# Live refresh path — used by the rebalance script on rebalance day.

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


def _panels_are_fresh(panels: dict[str, pd.DataFrame], max_staleness_days: int = 5) -> bool:
    """True if the newest bar across all returned tickers is within `max_staleness_days`
    calendar days of today. Used to decide whether a primary source is healthy enough
    to skip the backup."""
    if not panels:
        return False
    today = pd.Timestamp.utcnow().normalize().tz_localize(None)
    latest_per_ticker = []
    for _, df in panels.items():
        d = df.dropna(subset=["adj_close"]) if "adj_close" in df.columns else df.dropna(how="all")
        if d.empty:
            continue
        latest_per_ticker.append(d.index.max())
    if not latest_per_ticker:
        return False
    newest = max(latest_per_ticker)
    return (today - newest).days <= max_staleness_days


def _write_panels(out_dir: Path, panels: dict[str, pd.DataFrame]) -> tuple[list, list]:
    """Dedupe + write each ticker's DataFrame to the clean prices dir."""
    latest_dates: list = []
    gaps: list = []
    for t, df in panels.items():
        df = df.dropna(subset=["adj_close"]) if "adj_close" in df.columns else df.dropna(how="all")
        if df.empty:
            gaps.append(t)
            continue
        fname = "_VIX.parquet" if t == "^VIX" else f"{t}.parquet"
        merged = _append_clean_parquet(out_dir / fname, df)
        latest_dates.append(merged.index.max())
    return latest_dates, gaps


def _cache_staleness_days(out_dir: Path, tickers: list[str]) -> int | None:
    """Newest date across the cached parquets, expressed in calendar days from today.
    Returns None if no cached ticker exists."""
    today = pd.Timestamp.utcnow().normalize().tz_localize(None)
    newest: pd.Timestamp | None = None
    for t in tickers:
        fname = "_VIX.parquet" if t == "^VIX" else f"{t}.parquet"
        p = out_dir / fname
        if not p.exists():
            continue
        try:
            df = pd.read_parquet(p)
        except Exception:
            continue
        if df.empty:
            continue
        d = df.dropna(how="all").index.max()
        if newest is None or d > newest:
            newest = d
    if newest is None:
        return None
    return int((today - newest).days)


def _refresh_prices(root: Path, cfg: dict) -> dict:
    """Fetch latest OHLCV with auto-failover: Yahoo → Twelve Data → cached parquets.

    Returns a status dict. `source` is one of {"yahoo", "twelve_data", "cache", "none"}.
    A degraded status with `source=cache` is still usable for a monthly strategy as
    long as `staleness_days <= 2` (one missed trading day), per §6.4.
    """
    from src.data.fetchers.yahoo_prices import fetch_ohlcv as yahoo_fetch

    tickers = list(dict.fromkeys(
        list(cfg["universe"]) + [cfg["reference_index"]]
        + list(cfg.get("feature_extras", [])) + ["^VIX"]
    ))
    out_dir = root / cfg["paths"]["prices_clean"]
    out_dir.mkdir(parents=True, exist_ok=True)

    start = (pd.Timestamp.utcnow().normalize().tz_localize(None) - pd.Timedelta(days=180)).date().isoformat()

    # --- tier 1: Yahoo -------------------------------------------------
    panels = None
    try:
        panels = yahoo_fetch(tickers, start=start)
    except Exception as e:
        log.warning("yahoo fetch raised: %s", e)
        panels = None

    if panels is not None and _panels_are_fresh(panels):
        latest_dates, gaps = _write_panels(out_dir, panels)
        if latest_dates:
            return {
                "status": "ok" if not gaps else "degraded",
                "source": "yahoo",
                "latest_date": max(latest_dates).date().isoformat(),
                "gaps": gaps,
                "tickers": len(panels),
            }

    # --- tier 2: Twelve Data ------------------------------------------
    log.warning("yahoo price fetch failed or stale; trying twelve_data backup")
    try:
        from src.data.fetchers.twelve_data import fetch_ohlcv as td_fetch
        backup_panels = td_fetch(tickers, start=start)
    except Exception as e:
        log.warning("twelve_data fetch raised: %s", e)
        backup_panels = None

    if backup_panels is not None and _panels_are_fresh(backup_panels):
        latest_dates, gaps = _write_panels(out_dir, backup_panels)
        if latest_dates:
            return {
                "status": "degraded",
                "source": "twelve_data",
                "latest_date": max(latest_dates).date().isoformat(),
                "gaps": gaps,
                "tickers": len(backup_panels),
                "warning": "using backup price source (twelve_data)",
            }

    # --- tier 3: cached parquets --------------------------------------
    log.error("both price sources unavailable; falling back to cache")
    staleness = _cache_staleness_days(out_dir, tickers)
    if staleness is not None and staleness <= 2:
        return {
            "status": "degraded",
            "source": "cache",
            "latest_date": None,
            "staleness_days": staleness,
            "warning": f"serving prices from cache, {staleness}d stale",
        }

    return {
        "status": "error",
        "source": "none",
        "latest_date": None,
        "staleness_days": staleness,
        "error": "all price sources unavailable",
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
    backup_used: list[str] = []
    for key, sid in ds["fred"].items():
        fname, freq = _MACRO_FILE_FREQ.get(key, (key, "monthly"))
        df = fetch_fred_series(sid, cache_dir=macro_dir)
        if df.empty and sid == "CPIAUCSL":
            # Tier-3 fallback for the most critical macro series: BLS direct.
            try:
                from src.data.fetchers.bls import fetch_cpi, CPI_SA
                bls_df = fetch_cpi(CPI_SA)
            except Exception as e:
                log.warning("bls CPI fallback raised: %s", e)
                bls_df = None
            if bls_df is not None and not bls_df.empty:
                df = bls_df.rename(columns={CPI_SA: sid})
                backup_used.append(f"{key}=bls")
                log.warning("CPI served from BLS fallback")
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
    if backup_used and status == "ok":
        status = "degraded"
    return {
        "status": status,
        "series_count": len(fetched),
        "stale": stale,
        "errors": errors,
        "backup_used": backup_used,
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

    out = {"price_features": "ok", "macro_features": "ok",
           "interaction_features": "ok", "errors": []}

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

    # Interaction + target features consume the price/macro parquets built
    # above; without this step the CORE interaction features (mom63_when_*,
    # cross_asset_*) freeze at their last manual build and the classifier's
    # live tail degrades to ffill/NaN.
    try:
        from src.features import interactions_targets as itf  # noqa: WPS433
        with contextlib.redirect_stdout(_io.StringIO()):
            int_prices = itf.load_prices(eng.ALL_TICKERS)
            int_close = itf._stack("adj_close", int_prices)
            itf.build_interactions(int_close)
            itf.build_targets(int_close)
    except Exception as e:
        log.exception("interaction/target feature rebuild failed")
        out["interaction_features"] = "error"
        out["errors"].append(f"interaction: {e}")

    return out


def refresh_and_rebuild(root: Path | None = None) -> dict:
    """Live refresh + targeted feature rebuild for the rebalance script."""
    status = refresh_all_data(root)
    if status.get("prices", {}).get("status") in ("ok", "degraded"):
        status["rebuild"] = rebuild_features(root)
    else:
        status["rebuild"] = {"status": "skipped", "reason": "prices_unavailable"}
    return status


def source_health_report(timeout: float = 10.0) -> dict:
    """Probe every upstream data source and return a status dict per source.

    Each entry has `status` in {"ok", "down", "skipped"}, plus `latency_ms`
    and a short `detail` string when useful. Cheap probes only — a single
    ticker / series per source. Intended for the daily health check.
    """
    import time as _time
    report: dict[str, dict] = {}

    # --- yahoo -----------------------------------------------------------
    t0 = _time.monotonic()
    try:
        from src.data.fetchers.yahoo_prices import fetch_adj_close
        df = fetch_adj_close(["SPY"], start=(pd.Timestamp.utcnow() - pd.Timedelta(days=10)).date().isoformat())
        ok = df is not None and not df.empty
        report["yahoo"] = {
            "status": "ok" if ok else "down",
            "latency_ms": int((_time.monotonic() - t0) * 1000),
            "detail": f"rows={len(df)}" if ok else "empty/None",
        }
    except Exception as e:
        report["yahoo"] = {"status": "down", "latency_ms": int((_time.monotonic() - t0) * 1000), "detail": str(e)[:80]}

    # --- twelve_data -----------------------------------------------------
    import os as _os
    if not _os.environ.get("TWELVE_DATA_KEY"):
        report["twelve_data"] = {"status": "skipped", "detail": "TWELVE_DATA_KEY not set"}
    else:
        t0 = _time.monotonic()
        try:
            from src.data.fetchers.twelve_data import fetch_daily
            df = fetch_daily("SPY", start=(pd.Timestamp.utcnow() - pd.Timedelta(days=10)).date().isoformat())
            ok = df is not None and not df.empty
            report["twelve_data"] = {
                "status": "ok" if ok else "down",
                "latency_ms": int((_time.monotonic() - t0) * 1000),
                "detail": f"rows={len(df)}" if ok else "empty/None",
            }
        except Exception as e:
            report["twelve_data"] = {"status": "down", "latency_ms": int((_time.monotonic() - t0) * 1000), "detail": str(e)[:80]}

    # --- fred (api + csv) -----------------------------------------------
    import requests as _rq
    for name, url in (
        ("fred_api", "https://api.stlouisfed.org/fred/series/observations?series_id=CPIAUCSL&file_type=json&limit=1"
                     + (f"&api_key={_os.environ['FRED_API_KEY']}" if _os.environ.get("FRED_API_KEY") else "")),
        ("fred_csv", "https://fred.stlouisfed.org/graph/fredgraph.csv?id=CPIAUCSL"),
    ):
        if name == "fred_api" and not _os.environ.get("FRED_API_KEY"):
            report[name] = {"status": "skipped", "detail": "FRED_API_KEY not set"}
            continue
        t0 = _time.monotonic()
        try:
            r = _rq.get(url, timeout=timeout, headers={"User-Agent": "Mozilla/5.0"})
            report[name] = {
                "status": "ok" if r.status_code == 200 else "down",
                "latency_ms": int((_time.monotonic() - t0) * 1000),
                "detail": f"HTTP {r.status_code}",
            }
        except Exception as e:
            report[name] = {"status": "down", "latency_ms": int((_time.monotonic() - t0) * 1000), "detail": str(e)[:80]}

    # --- bls -------------------------------------------------------------
    t0 = _time.monotonic()
    try:
        from src.data.fetchers.bls import fetch_cpi
        current_year = pd.Timestamp.utcnow().year
        df = fetch_cpi(start_year=current_year - 1, end_year=current_year)
        ok = df is not None and not df.empty
        report["bls"] = {
            "status": "ok" if ok else "down",
            "latency_ms": int((_time.monotonic() - t0) * 1000),
            "detail": f"rows={len(df)}" if ok else "empty/None",
        }
    except Exception as e:
        report["bls"] = {"status": "down", "latency_ms": int((_time.monotonic() - t0) * 1000), "detail": str(e)[:80]}

    return report


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
