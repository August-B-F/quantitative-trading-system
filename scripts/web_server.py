"""iStock Web Server — FastAPI backend."""
from __future__ import annotations

import asyncio
import collections
import glob
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import AsyncIterator, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

try:
    from ultimate_trader.utils.config_loader import load_config
    from ultimate_trader.utils.logging import PerformanceDB
    _CONFIG_AVAILABLE = True
except ImportError:
    _CONFIG_AVAILABLE = False

from scripts.tui import (
    load_backtest_results, load_predictions, load_model_info,
    get_gpu_info, scan_data_files, load_alpaca_positions,
    load_equity_series, fmt_bytes,
)

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

import pandas as pd

_SCRIPTS = Path(__file__).parent
_ROOT    = _SCRIPTS.parent

# ═══════════════════════════════════════════════════════════════════════════
# State
# ═══════════════════════════════════════════════════════════════════════════

_ACCESS_LOG: collections.deque = collections.deque(maxlen=1000)


class ProcessManager:
    def __init__(self, maxlines: int = 500):
        self.proc:       Optional[subprocess.Popen] = None
        self.name:       str   = ""
        self.started_at: Optional[float] = None
        self.buf:        collections.deque = collections.deque(maxlen=maxlines)
        self._new_line   = asyncio.Event()

    @property
    def running(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def start(self, name: str, cmd: list[str]) -> None:
        self.buf.clear()
        self.name = name
        self.started_at = time.time()
        self.proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1, cwd=str(_ROOT),
        )
        import threading
        threading.Thread(target=self._reader, daemon=True).start()

    def _reader(self) -> None:
        for line in iter(self.proc.stdout.readline, ""):
            line = line.rstrip()
            if line:
                self.buf.append({"t": datetime.now().strftime("%H:%M:%S"), "msg": line})
                self._new_line.set()
        self.proc.wait()
        rc = self.proc.returncode
        msg = "✓ Finished (exit 0)" if rc == 0 else f"✗ Exited with code {rc}"
        self.buf.append({"t": datetime.now().strftime("%H:%M:%S"), "msg": msg, "rc": rc})
        self._new_line.set()

    def stop(self) -> None:
        if self.running:
            self.proc.terminate()

    def status(self) -> dict:
        up = int(time.time() - self.started_at) if self.started_at else 0
        return {
            "running": self.running, "name": self.name,
            "pid": self.proc.pid if self.proc else None,
            "uptime": up,
            "rc": self.proc.returncode if self.proc and not self.running else None,
        }


_pm  = ProcessManager()
_cfg = None
_db  = None


def _get_cfg():
    global _cfg
    if _cfg is None and _CONFIG_AVAILABLE:
        try:
            _cfg = load_config(str(_ROOT / "config"))
        except Exception:
            pass
    return _cfg


def _get_db():
    global _db
    if _db is None:
        cfg = _get_cfg()
        if cfg:
            try:
                _db = PerformanceDB(cfg.paths.db_path)
            except Exception:
                pass
    return _db


# ═══════════════════════════════════════════════════════════════════════════
# FastAPI + middleware
# ═══════════════════════════════════════════════════════════════════════════

app = FastAPI(title="iStock", docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=str(_SCRIPTS / "static")), name="static")


@app.middleware("http")
async def _access_log(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    dur = round((time.time() - start) * 1000)
    if not request.url.path.startswith("/static"):
        _ACCESS_LOG.append({
            "t":      datetime.now().strftime("%H:%M:%S"),
            "method": request.method,
            "path":   request.url.path,
            "status": response.status_code,
            "ms":     dur,
            "ip":     request.client.host if request.client else "—",
        })
    return response


@app.get("/", response_class=HTMLResponse)
async def root():
    return FileResponse(str(_SCRIPTS / "static" / "index.html"))


# ═══════════════════════════════════════════════════════════════════════════
# Trading data endpoints
# ═══════════════════════════════════════════════════════════════════════════

@app.get("/api/overview")
async def overview():
    bt      = load_backtest_results()
    metrics = bt.get("metrics", {})
    eq_vals: list = []
    if "equity_curve" in bt:
        eq_vals = bt["equity_curve"]["equity"].tolist()
    elif (db := _get_db()):
        eq_vals = load_equity_series(db)
    regime = "unknown"
    if (db := _get_db()):
        try:
            df = db.get_daily_pnl()
            if not df.empty:
                regime = df.iloc[-1].get("regime", "unknown")
        except Exception:
            pass
    models_dir = str(_ROOT / "data" / "models")
    cfg = _get_cfg()
    if cfg:
        models_dir = getattr(getattr(cfg, "paths", None), "models_dir", models_dir)
    return {
        "metrics": metrics, "equity": eq_vals[-60:] if eq_vals else [],
        "regime": regime, "model": load_model_info(models_dir),
        "gpu": get_gpu_info(), "process": _pm.status(),
        "updated_at": datetime.now().isoformat(),
    }


@app.get("/api/equity")
async def equity():
    bt = load_backtest_results()
    if "equity_curve" in bt:
        ec    = bt["equity_curve"]
        dates = list(ec.index.astype(str))
        vals  = ec["equity"].tolist()
    elif (db := _get_db()):
        try:
            df    = db.get_daily_pnl()
            dates = df["date"].astype(str).tolist() if not df.empty else []
            vals  = df["equity"].tolist() if not df.empty else []
        except Exception:
            dates, vals = [], []
    else:
        dates, vals = [], []
    return {"dates": dates, "values": vals}


@app.get("/api/trades")
async def trades():
    bt  = load_backtest_results()
    df  = bt.get("trades", None)
    if df is None or (isinstance(df, pd.DataFrame) and df.empty):
        if (db := _get_db()):
            try:
                df = db.get_all_trades()
            except Exception:
                df = pd.DataFrame()
    if df is None or (isinstance(df, pd.DataFrame) and df.empty):
        return {"trades": []}
    rows = []
    for _, r in df.tail(200).iterrows():
        rows.append({
            "symbol": str(r.get("symbol", "")),
            "entry_date": str(r.get("entry_date", ""))[:10],
            "exit_date":  str(r.get("exit_date",  ""))[:10],
            "pnl_pct":    float(r.get("pnl_pct",    0)),
            "pnl_dollar": float(r.get("pnl_dollar",  0)),
            "exit_reason": str(r.get("exit_reason", "")),
            "regime": str(r.get("regime", "")),
        })
    return {"trades": rows}


@app.get("/api/performance")
async def performance():
    bt      = load_backtest_results()
    metrics = bt.get("metrics", {})
    pnl_dates: list = []
    pnl_vals:  list = []
    if (db := _get_db()):
        try:
            df = db.get_daily_pnl()
            if not df.empty:
                pnl_dates = df["date"].astype(str).tolist()
                pnl_vals  = df["pnl"].tolist()
        except Exception:
            pass
    elif "equity_curve" in bt:
        ec        = bt["equity_curve"]["equity"]
        pnl_vals  = ec.diff().fillna(0).tolist()
        pnl_dates = list(bt["equity_curve"].index.astype(str))
    return {"metrics": metrics, "pnl_dates": pnl_dates[-60:], "pnl_values": pnl_vals[-60:]}


@app.get("/api/positions")
async def positions():
    cfg = _get_cfg()
    if not cfg:
        return {"positions": [], "account": None, "error": "Config not loaded"}
    pos_list, account = load_alpaca_positions(cfg)
    account_data = None
    if account:
        account_data = {
            "equity":          float(account.equity),
            "cash":            float(account.cash),
            "buying_power":    float(account.buying_power),
            "portfolio_value": float(account.portfolio_value),
        }
    positions_data = []
    for p in pos_list:
        avg = float(p.avg_entry_price)
        cur = float(p.current_price)
        positions_data.append({
            "symbol": p.symbol, "qty": float(p.qty),
            "avg_entry": avg, "current": cur,
            "market_value": float(p.market_value),
            "unrealized_pl": float(p.unrealized_pl),
            "pnl_pct": (cur - avg) / avg if avg else 0,
        })
    return {"positions": positions_data, "account": account_data}


@app.get("/api/signals")
async def signals():
    df = load_predictions()
    if df.empty:
        return {"signals": [], "summary": {}, "date": None}
    latest    = df["date"].max()
    latest_df = df[df["date"] == latest]
    rows = []
    for _, r in latest_df.sort_values("confidence", ascending=False).iterrows():
        pc        = int(r["pred_class"])
        prob_cols = [f"prob_{i}" for i in range(5)]
        probs     = [float(r[c]) for c in prob_cols if c in r]
        rows.append({
            "symbol":      str(r["symbol"]),
            "pred_class":  pc,
            "confidence":  float(r["confidence"]),
            "uncertainty": float(r.get("uncertainty", 0)),
            "probs":       probs,
        })
    summary = {
        "buys":     int(latest_df["pred_class"].isin([3, 4]).sum()),
        "sells":    int(latest_df["pred_class"].isin([0, 1]).sum()),
        "holds":    int((latest_df["pred_class"] == 2).sum()),
        "avg_conf": float(latest_df["confidence"].mean()) if not latest_df.empty else 0,
    }
    return {"signals": rows, "summary": summary, "date": str(latest)}


@app.get("/api/status")
async def status():
    return _pm.status()


# ═══════════════════════════════════════════════════════════════════════════
# Data endpoints
# ═══════════════════════════════════════════════════════════════════════════

@app.get("/api/data/summary")
async def data_summary():
    files = scan_data_files()
    total_size = sum(f["size"] for f in files)
    total_rows = sum(f["rows"] for f in files if isinstance(f["rows"], int))
    latest_mt  = max((f["mtime"] for f in files), default=0)
    for f in files:
        f["size_fmt"] = fmt_bytes(f["size"])
        f["updated"]  = datetime.fromtimestamp(f["mtime"]).strftime("%Y-%m-%d %H:%M")
    return {
        "files":        files,
        "total_files":  len(files),
        "total_rows":   total_rows,
        "total_size":   fmt_bytes(total_size),
        "last_updated": datetime.fromtimestamp(latest_mt).strftime("%Y-%m-%d %H:%M") if latest_mt else "—",
    }


@app.get("/api/data/symbols")
async def data_symbols():
    """Per-symbol coverage from bars directory."""
    bars_dir = _ROOT / "data" / "raw" / "bars"
    results  = []
    if not bars_dir.exists():
        # fallback: scan generic raw dir
        bars_dir = _ROOT / "data" / "raw"
    if bars_dir.exists():
        for fp in sorted(bars_dir.glob("*.parquet")) + sorted(bars_dir.glob("*.csv")):
            symbol = fp.stem.upper()
            stat   = fp.stat()
            row = {
                "symbol":    symbol,
                "file":      fp.name,
                "size":      fmt_bytes(stat.st_size),
                "updated":   datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
                "rows":      "?",
                "date_from": "?",
                "date_to":   "?",
                "days":      "?",
            }
            try:
                df = pd.read_parquet(fp) if fp.suffix == ".parquet" else pd.read_csv(fp)
                row["rows"] = len(df)
                dcol = next((c for c in ("date","Date","datetime","timestamp") if c in df.columns), None)
                if dcol:
                    dates = pd.to_datetime(df[dcol], errors="coerce").dropna()
                    if not dates.empty:
                        row["date_from"] = dates.min().strftime("%Y-%m-%d")
                        row["date_to"]   = dates.max().strftime("%Y-%m-%d")
                        row["days"]      = (dates.max() - dates.min()).days
            except Exception:
                pass
            results.append(row)
    return {"symbols": results, "count": len(results)}


@app.get("/api/model")
async def model_info_route():
    cfg        = _get_cfg()
    models_dir = str(_ROOT / "data" / "models")
    if cfg:
        models_dir = getattr(getattr(cfg, "paths", None), "models_dir", models_dir)
    info = load_model_info(models_dir)
    if info.get("mtime"):
        age_s       = time.time() - info["mtime"]
        info["age_str"] = f"{int(age_s / 3600)}h ago"
    return info


@app.get("/api/gpu")
async def gpu():
    return get_gpu_info()


# ═══════════════════════════════════════════════════════════════════════════
# System health & logs
# ═══════════════════════════════════════════════════════════════════════════

@app.get("/api/system/health")
async def system_health():
    health: dict = {}

    if HAS_PSUTIL:
        health["cpu_pct"]  = psutil.cpu_percent(interval=0.2)
        vm = psutil.virtual_memory()
        health["mem_pct"]  = vm.percent
        health["mem_used"] = fmt_bytes(vm.used)
        health["mem_total"]= fmt_bytes(vm.total)
        du = psutil.disk_usage(str(_ROOT))
        health["disk_pct"] = du.percent
        health["disk_used"]= fmt_bytes(du.used)
        health["disk_total"]= fmt_bytes(du.total)
    else:
        # basic fallback via /proc on Linux
        try:
            import shutil
            total, used, free = shutil.disk_usage(str(_ROOT))
            health["disk_pct"]  = round(used / total * 100, 1)
            health["disk_used"] = fmt_bytes(used)
            health["disk_total"]= fmt_bytes(total)
        except Exception:
            pass

    # GPU
    gpu_info = get_gpu_info()
    if gpu_info:
        health["gpu_pct"]  = round(gpu_info.get("pct", 0) * 100, 1)
        health["gpu_used"] = f"{gpu_info.get('used_gb', 0):.1f} GB"
        health["gpu_total"]= f"{gpu_info.get('total_gb', 0):.0f} GB"
        health["gpu_name"] = gpu_info.get("name", "")

    # DB size
    db_path = _ROOT / "data" / "performance.db"
    if db_path.exists():
        health["db_size"] = fmt_bytes(db_path.stat().st_size)

    health["uptime_str"] = _get_uptime()
    return health


def _get_uptime() -> str:
    if HAS_PSUTIL:
        boot = psutil.boot_time()
        secs = int(time.time() - boot)
    else:
        try:
            with open("/proc/uptime") as f:
                secs = int(float(f.read().split()[0]))
        except Exception:
            return "—"
    h, rem = divmod(secs, 3600)
    m = rem // 60
    return f"{h}h {m}m"


@app.get("/api/system/logs")
async def system_logs(days: int = 7, limit: int = 500):
    """Read app logs from logs/{date}.log files for the past N days."""
    logs_dir = _ROOT / "logs"
    entries  = []
    now      = datetime.now()
    for i in range(days):
        date     = (now - timedelta(days=i)).strftime("%Y-%m-%d")
        log_file = logs_dir / f"{date}.log"
        if not log_file.exists():
            continue
        try:
            with open(log_file, errors="replace") as f:
                for line in f:
                    line = line.rstrip()
                    if not line:
                        continue
                    ll   = line.lower()
                    level = "error" if "error" in ll or "traceback" in ll \
                        else "warning" if "warning" in ll or "warn" in ll \
                        else "info"
                    entries.append({"date": date, "msg": line, "level": level})
        except Exception:
            pass
    entries.reverse()          # newest first
    return {"entries": entries[:limit], "total": len(entries)}


@app.get("/api/system/access-logs")
async def access_logs():
    return {"entries": list(reversed(list(_ACCESS_LOG)))}


# ═══════════════════════════════════════════════════════════════════════════
# Process control
# ═══════════════════════════════════════════════════════════════════════════

def _run(name: str, script: str, extra: list[str] = None):
    if _pm.running:
        raise HTTPException(409, f"Process '{_pm.name}' already running")
    cmd = [sys.executable, str(_SCRIPTS / script)] + (extra or [])
    _pm.start(name, cmd)
    return {"started": True, "name": name, "pid": _pm.proc.pid}


@app.post("/api/run/download")
async def run_download(): return _run("Data Download", "download_data.py")

@app.post("/api/run/train")
async def run_train(): return _run("Training", "train.py")

@app.post("/api/run/backtest")
async def run_backtest(): return _run("Backtest", "backtest.py")

@app.post("/api/run/bot")
async def run_bot(): return _run("Live Bot", "run_live_bot.py", ["--now"])

@app.post("/api/stop")
async def stop_process():
    _pm.stop()
    return {"stopped": True}


# ═══════════════════════════════════════════════════════════════════════════
# SSE log stream
# ═══════════════════════════════════════════════════════════════════════════

@app.get("/api/logs/stream")
async def logs_stream():
    async def generator() -> AsyncIterator[str]:
        sent = 0
        history = list(_pm.buf)
        for entry in history:
            yield f"data: {json.dumps(entry)}\n\n"
            sent += 1
        while True:
            _pm._new_line.clear()
            cur = list(_pm.buf)
            while sent < len(cur):
                yield f"data: {json.dumps(cur[sent])}\n\n"
                sent += 1
            if not _pm.running and sent >= len(list(_pm.buf)):
                break
            try:
                await asyncio.wait_for(_pm._new_line.wait(), timeout=1.0)
            except asyncio.TimeoutError:
                yield ": keep-alive\n\n"
    return StreamingResponse(generator(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache",
                                      "X-Accel-Buffering": "no"})


@app.get("/api/logs/history")
async def logs_history():
    return {"lines": list(_pm.buf)}


# ═══════════════════════════════════════════════════════════════════════════
# Entry
# ═══════════════════════════════════════════════════════════════════════════

def _tailscale_ip() -> str:
    """Bind to the Tailscale interface (100.x.x.x) so only VPN peers can reach us."""
    import subprocess
    try:
        r = subprocess.run(["tailscale", "ip", "-4"], capture_output=True, text=True, timeout=3)
        ip = r.stdout.strip()
        if ip.startswith("100."):
            return ip
    except Exception:
        pass
    # Fallback: scan local interfaces for a 100.x address
    try:
        import socket
        for ip in socket.gethostbyname_ex(socket.gethostname())[2]:
            if ip.startswith("100."):
                return ip
    except Exception:
        pass
    print("  WARNING: Tailscale IP not found — binding to 127.0.0.1 (local only)")
    return "127.0.0.1"


def serve(host: str = None, port: int = 8000, open_browser: bool = False):
    if host is None:
        host = _tailscale_ip()
    if open_browser:
        import threading, webbrowser
        threading.Timer(1.2, lambda: webbrowser.open(f"http://{host}:{port}")).start()
    print(f"\n  iStock  ·  http://{host}:{port}  (Tailscale only)\n")
    uvicorn.run(app, host=host, port=port, log_level="warning")


if __name__ == "__main__":
    serve(open_browser=True)
