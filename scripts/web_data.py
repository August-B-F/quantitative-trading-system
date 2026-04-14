"""Data loaders for the iStock web UI.

Single source of truth for everything the FastAPI server serves. Reads the
canonical ETF Momentum Rotation backtest from results/backtest_presentation.json,
plus configs/, data/models/, data/raw/.

Kept separate from web_server.py so loaders can be unit-tested and swapped
without touching HTTP plumbing.
"""
from __future__ import annotations

import json
import math
import os
import shutil
import time
from datetime import datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
_PRES_PATH     = _ROOT / "results" / "backtest_presentation.json"
_HOLDINGS_PATH = _ROOT / "configs" / "holdings.json"
_STRATEGY_YAML = _ROOT / "configs" / "strategy.yaml"
_MODELS_DIR    = _ROOT / "data" / "models"
_RAW_DIR       = _ROOT / "data" / "raw"
_LOGS_DIR      = _ROOT / "logs"


# ══════════════════════════════════════════════════════════════════════════
# Formatting helpers
# ══════════════════════════════════════════════════════════════════════════

def fmt_bytes(n: int | float) -> str:
    n = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.1f} {unit}" if unit != "B" else f"{int(n)} {unit}"
        n /= 1024
    return f"{n:.1f} PB"


def _safe_mtime(p: Path) -> float:
    try:
        return p.stat().st_mtime
    except OSError:
        return 0.0


def _sanitize(obj: Any) -> Any:
    """Replace NaN/inf with None recursively so JSON serialization is strict-compliant."""
    if isinstance(obj, float):
        return obj if math.isfinite(obj) else None
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize(v) for v in obj]
    return obj


# ══════════════════════════════════════════════════════════════════════════
# Canonical backtest (presentation JSON)
# ══════════════════════════════════════════════════════════════════════════

_pres_cache: tuple[float, dict] | None = None


def load_presentation() -> dict:
    """Return the full canonical backtest presentation (ETF Momentum Rotation).

    Cached by mtime so we don't re-parse the JSON on every request.
    """
    global _pres_cache
    if not _PRES_PATH.exists():
        return {}
    mt = _safe_mtime(_PRES_PATH)
    if _pres_cache and _pres_cache[0] == mt:
        return _pres_cache[1]
    try:
        with open(_PRES_PATH, encoding="utf-8") as f:
            data = json.load(f)
        data = _sanitize(data)
    except Exception:
        return {}
    _pres_cache = (mt, data)
    return data


def _canonical_metrics(pres: dict) -> dict:
    """Flatten headline + key_stats.strategy into the shape the old UI expects."""
    ks = pres.get("key_stats", {}).get("strategy", {}) or {}
    hd = pres.get("headline", {}) or {}
    eq_series = pres.get("equity", {}).get("strategy", []) or []
    final_equity = eq_series[-1]["value"] if eq_series else None
    return {
        "total_return":  (final_equity / eq_series[0]["value"] - 1) if eq_series else None,
        "cagr":          ks.get("cagr"),
        "sharpe":        ks.get("sharpe"),
        "sortino":       ks.get("sortino"),
        "calmar":        ks.get("calmar"),
        "max_drawdown":  ks.get("max_dd"),
        "win_rate":      ks.get("win_rate"),
        "best_month":    ks.get("best_month"),
        "worst_month":   ks.get("worst_month"),
        "best_year":     ks.get("best_year"),
        "worst_year":    ks.get("worst_year"),
        "n_trades":      hd.get("n_trades"),
        "n_months":      ks.get("n_months"),
        "upside_capture":   ks.get("upside_capture"),
        "downside_capture": ks.get("downside_capture"),
        "monthly_turnover": hd.get("monthly_turnover"),
        "annual_turnover":  hd.get("annual_turnover"),
        "final_equity":  final_equity,
        "strategy_name": hd.get("name"),
        "period":        hd.get("subtitle"),
    }


def get_metrics() -> dict:
    return _canonical_metrics(load_presentation())


def get_equity_series(benchmark: bool = True) -> dict:
    """Return {dates, values, spy?} from the monthly equity curve."""
    pres = load_presentation()
    eq = pres.get("equity", {}) or {}
    strat = eq.get("strategy", []) or []
    dates = [row["date"] for row in strat]
    vals  = [row["value"] for row in strat]
    out: dict[str, Any] = {"dates": dates, "values": vals}
    if benchmark:
        spy = eq.get("spy", []) or []
        out["spy"] = [row.get("value") for row in spy]
    return out


def get_rolling_sharpe() -> list[dict]:
    return load_presentation().get("rolling_sharpe", []) or []


def get_drawdowns() -> dict:
    return load_presentation().get("drawdowns", {}) or {}


def get_annual_returns() -> list[dict]:
    return load_presentation().get("annual_returns", []) or []


def get_monthly_heatmap() -> list[dict]:
    return load_presentation().get("monthly_heatmap", []) or []


def get_regime_breakdown() -> dict:
    return load_presentation().get("regime_breakdown", {}) or {}


def get_current_regime() -> str:
    """Latest regime label from the most recent rebalance."""
    log = load_presentation().get("trade_log", []) or []
    if log:
        return log[-1].get("regime") or "unknown"
    return "unknown"


def get_trade_log(limit: int = 200) -> list[dict]:
    """Rotation trade log. Each entry: {date, from, to, regime, lookback, deferred, ret}."""
    log = load_presentation().get("trade_log", []) or []
    return log[-limit:]


def get_attribution() -> dict:
    return load_presentation().get("attribution", {}) or {}


def get_validation() -> dict:
    return load_presentation().get("validation", {}) or {}


# ══════════════════════════════════════════════════════════════════════════
# Config files
# ══════════════════════════════════════════════════════════════════════════

def load_holdings() -> dict:
    if not _HOLDINGS_PATH.exists():
        return {}
    try:
        with open(_HOLDINGS_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def load_strategy_config() -> dict:
    if not _STRATEGY_YAML.exists():
        return {}
    try:
        import yaml
        with open(_STRATEGY_YAML, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}


# ══════════════════════════════════════════════════════════════════════════
# Model checkpoints
# ══════════════════════════════════════════════════════════════════════════

def load_model_info() -> dict:
    """Summarise the latest best_model.pt (or newest *.pt) checkpoint."""
    if not _MODELS_DIR.exists():
        return {}
    best = _MODELS_DIR / "best_model.pt"
    cand = best if best.exists() else None
    if cand is None:
        pts = sorted(_MODELS_DIR.glob("*.pt"), key=_safe_mtime, reverse=True)
        cand = pts[0] if pts else None
    if cand is None:
        return {}
    st = cand.stat()
    age_s = time.time() - st.st_mtime
    return {
        "name":     cand.name,
        "path":     str(cand.relative_to(_ROOT)),
        "size":     st.st_size,
        "size_fmt": fmt_bytes(st.st_size),
        "mtime":    st.st_mtime,
        "age_str":  _fmt_age(age_s),
        "updated":  datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M"),
    }


def load_model_checkpoints() -> list[dict]:
    """All .pt files in data/models/ with metadata."""
    if not _MODELS_DIR.exists():
        return []
    out = []
    for p in sorted(_MODELS_DIR.glob("*.pt"), key=_safe_mtime, reverse=True):
        st = p.stat()
        out.append({
            "name":     p.name,
            "size":     st.st_size,
            "size_fmt": fmt_bytes(st.st_size),
            "updated":  datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M"),
            "mtime":    st.st_mtime,
        })
    return out


def _fmt_age(secs: float) -> str:
    if secs < 60:  return f"{int(secs)}s ago"
    if secs < 3600: return f"{int(secs/60)}m ago"
    if secs < 86400: return f"{int(secs/3600)}h ago"
    return f"{int(secs/86400)}d ago"


# ══════════════════════════════════════════════════════════════════════════
# Raw data scan
# ══════════════════════════════════════════════════════════════════════════

_DATA_SOURCES = ("bars", "fred", "news", "yahoo")


def scan_data_files() -> list[dict]:
    """Flat list of all files under data/raw/{source}/ with metadata."""
    if not _RAW_DIR.exists():
        return []
    out = []
    for src in _DATA_SOURCES:
        sub = _RAW_DIR / src
        if not sub.exists():
            continue
        for p in sub.rglob("*"):
            if not p.is_file():
                continue
            st = p.stat()
            out.append({
                "source": src,
                "file":   p.name,
                "path":   str(p.relative_to(_ROOT)),
                "size":   st.st_size,
                "rows":   "?",
                "mtime":  st.st_mtime,
            })
    return out


def scan_data_summary() -> dict:
    files = scan_data_files()
    total_size = sum(f["size"] for f in files)
    latest_mt  = max((f["mtime"] for f in files), default=0.0)
    by_source: dict[str, dict] = {}
    for f in files:
        b = by_source.setdefault(f["source"], {"count": 0, "size": 0})
        b["count"] += 1
        b["size"]  += f["size"]
    for src, b in by_source.items():
        b["size_fmt"] = fmt_bytes(b["size"])
    for f in files:
        f["size_fmt"] = fmt_bytes(f["size"])
        f["updated"]  = datetime.fromtimestamp(f["mtime"]).strftime("%Y-%m-%d %H:%M")
    return {
        "files":        files,
        "total_files":  len(files),
        "total_size":   fmt_bytes(total_size),
        "by_source":    by_source,
        "last_updated": datetime.fromtimestamp(latest_mt).strftime("%Y-%m-%d %H:%M") if latest_mt else "—",
    }


def scan_symbols() -> list[dict]:
    """Per-symbol coverage from data/raw/bars/. Reads parquet/csv lazily."""
    bars = _RAW_DIR / "bars"
    if not bars.exists():
        return []
    out = []
    for fp in sorted(list(bars.glob("*.parquet")) + list(bars.glob("*.csv"))):
        st = fp.stat()
        row: dict[str, Any] = {
            "symbol":    fp.stem.upper(),
            "file":      fp.name,
            "size":      fmt_bytes(st.st_size),
            "updated":   datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M"),
            "rows":      "?",
            "date_from": "?",
            "date_to":   "?",
            "days":      "?",
        }
        try:
            import pandas as pd
            df = pd.read_parquet(fp) if fp.suffix == ".parquet" else pd.read_csv(fp)
            row["rows"] = len(df)
            dcol = next((c for c in ("date", "Date", "datetime", "timestamp") if c in df.columns), None)
            if dcol:
                dts = pd.to_datetime(df[dcol], errors="coerce").dropna()
                if not dts.empty:
                    row["date_from"] = dts.min().strftime("%Y-%m-%d")
                    row["date_to"]   = dts.max().strftime("%Y-%m-%d")
                    row["days"]      = (dts.max() - dts.min()).days
        except Exception:
            pass
        out.append(row)
    return out


# ══════════════════════════════════════════════════════════════════════════
# GPU / system
# ══════════════════════════════════════════════════════════════════════════

def get_gpu_info() -> dict:
    """Lightweight GPU probe. Tries torch first, then nvidia-smi."""
    try:
        import torch  # type: ignore
        if torch.cuda.is_available():
            idx = 0
            props = torch.cuda.get_device_properties(idx)
            free, total = torch.cuda.mem_get_info(idx)
            used = total - free
            return {
                "name":     props.name,
                "used_gb":  used  / 1e9,
                "total_gb": total / 1e9,
                "pct":      used / total if total else 0.0,
            }
    except Exception:
        pass
    try:
        import subprocess
        r = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.used,memory.total",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=2,
        )
        if r.returncode == 0 and r.stdout.strip():
            name, used_mb, total_mb = [x.strip() for x in r.stdout.strip().split("\n")[0].split(",")]
            used, total = float(used_mb) * 1e6, float(total_mb) * 1e6
            return {
                "name":     name,
                "used_gb":  used  / 1e9,
                "total_gb": total / 1e9,
                "pct":      used / total if total else 0.0,
            }
    except Exception:
        pass
    return {}


def get_disk_usage() -> dict:
    try:
        total, used, free = shutil.disk_usage(str(_ROOT))
        return {
            "total": total, "used": used, "free": free,
            "pct":   round(used / total * 100, 1),
            "total_fmt": fmt_bytes(total),
            "used_fmt":  fmt_bytes(used),
        }
    except Exception:
        return {}
