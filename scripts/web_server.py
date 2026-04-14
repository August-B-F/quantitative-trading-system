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

from scripts import web_data as wd

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

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


_pm = ProcessManager()


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
    metrics = wd.get_metrics()
    eq      = wd.get_equity_series(benchmark=False)
    return {
        "metrics":    metrics,
        "equity":     eq["values"][-60:],
        "regime":     wd.get_current_regime(),
        "model":      wd.load_model_info(),
        "gpu":        wd.get_gpu_info(),
        "process":    _pm.status(),
        "holdings":   wd.load_holdings(),
        "updated_at": datetime.now().isoformat(),
    }


@app.get("/api/equity")
async def equity():
    """Monthly equity curve + SPY benchmark (canonical ETF Momentum Rotation)."""
    return wd.get_equity_series(benchmark=True)


@app.get("/api/trades")
async def trades():
    """Rotation trade log — each entry is a monthly rebalance, not a flat buy/sell."""
    log = wd.get_trade_log(limit=200)
    rows = []
    for t in log:
        to_map = t.get("to", {}) or {}
        rows.append({
            "date":      t.get("date", ""),
            "regime":    t.get("regime", ""),
            "lookback":  t.get("lookback"),
            "deferred":  bool(t.get("deferred")),
            "ret":       t.get("ret"),
            "holdings":  to_map,
            "top":       ", ".join(f"{k} {v:.0%}" for k, v in to_map.items()),
        })
    return {"trades": rows}


@app.get("/api/performance")
async def performance():
    pres    = wd.load_presentation()
    metrics = wd.get_metrics()
    eq      = wd.get_equity_series(benchmark=False)
    dates   = eq["dates"]
    vals    = eq["values"]
    pnl_vals: list[float] = []
    for i, v in enumerate(vals):
        pnl_vals.append(0.0 if i == 0 else (v - vals[i - 1]))
    return {
        "metrics":        metrics,
        "pnl_dates":      dates[-60:],
        "pnl_values":     pnl_vals[-60:],
        "rolling_sharpe": wd.get_rolling_sharpe(),
        "drawdowns":      wd.get_drawdowns(),
        "annual_returns": wd.get_annual_returns(),
        "regime_breakdown": wd.get_regime_breakdown(),
    }


@app.get("/api/positions")
async def positions():
    """Placeholder until paper trading is wired. Returns target weights from holdings.json."""
    holdings = wd.load_holdings()
    return {
        "positions": [],
        "account":   None,
        "target_weights": holdings,
        "broker_connected": False,
        "note": "Paper trading not yet wired. Showing target weights from configs/holdings.json.",
    }


@app.get("/api/signals")
async def signals():
    """Phase A stub. The old 5-class classifier signals are dead.
    Phase B will rebuild this as ETF rotation rankings.
    """
    holdings = wd.load_holdings()
    strat    = wd.load_strategy_config()
    universe = strat.get("universe") or []
    regime   = wd.get_current_regime()
    return {
        "signals":  [],
        "summary":  {"universe_size": len(universe), "regime": regime},
        "universe": universe,
        "holdings": holdings,
        "date":     None,
    }


@app.get("/api/status")
async def status():
    return _pm.status()


# ═══════════════════════════════════════════════════════════════════════════
# Data endpoints
# ═══════════════════════════════════════════════════════════════════════════

@app.get("/api/data/summary")
async def data_summary():
    return wd.scan_data_summary()


@app.get("/api/data/symbols")
async def data_symbols():
    results = wd.scan_symbols()
    return {"symbols": results, "count": len(results)}


@app.get("/api/model")
async def model_info_route():
    return wd.load_model_info()


@app.get("/api/model/checkpoints")
async def model_checkpoints():
    return {"checkpoints": wd.load_model_checkpoints()}


@app.get("/api/gpu")
async def gpu():
    return wd.get_gpu_info()


@app.get("/api/strategy")
async def strategy_cfg():
    return {
        "config":   wd.load_strategy_config(),
        "holdings": wd.load_holdings(),
    }


# ═══════════════════════════════════════════════════════════════════════════
# System health & logs
# ═══════════════════════════════════════════════════════════════════════════

@app.get("/api/system/health")
async def system_health():
    health: dict = {}

    if HAS_PSUTIL:
        health["cpu_pct"]   = psutil.cpu_percent(interval=0.2)
        vm = psutil.virtual_memory()
        health["mem_pct"]   = vm.percent
        health["mem_used"]  = wd.fmt_bytes(vm.used)
        health["mem_total"] = wd.fmt_bytes(vm.total)
        du = psutil.disk_usage(str(_ROOT))
        health["disk_pct"]   = du.percent
        health["disk_used"]  = wd.fmt_bytes(du.used)
        health["disk_total"] = wd.fmt_bytes(du.total)
    else:
        disk = wd.get_disk_usage()
        if disk:
            health["disk_pct"]   = disk["pct"]
            health["disk_used"]  = disk["used_fmt"]
            health["disk_total"] = disk["total_fmt"]

    gpu_info = wd.get_gpu_info()
    if gpu_info:
        health["gpu_pct"]   = round(gpu_info.get("pct", 0) * 100, 1)
        health["gpu_used"]  = f"{gpu_info.get('used_gb', 0):.1f} GB"
        health["gpu_total"] = f"{gpu_info.get('total_gb', 0):.0f} GB"
        health["gpu_name"]  = gpu_info.get("name", "")

    pres_path = _ROOT / "results" / "backtest_presentation.json"
    if pres_path.exists():
        health["presentation_size"] = wd.fmt_bytes(pres_path.stat().st_size)

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
async def run_download(): return _run("Data Download", "phase1_download.py")

@app.post("/api/run/download/fred")
async def run_download_fred(): return _run("FRED Download", "phase1_fred.py")

@app.post("/api/run/download/alt")
async def run_download_alt(): return _run("Alt Data", "phase2_alternative.py")

@app.post("/api/run/health")
async def run_health(): return _run("Data Health Check", "phase3_integrate_and_health.py")

@app.post("/api/run/train")
async def run_train(): return _run("Training (retrain)", "run_retrain.py")

@app.post("/api/run/backtest")
async def run_backtest(): return _run("Backtest", "run_backtest.py")

@app.post("/api/run/rebalance")
async def run_rebalance(): return _run("Rebalance (dry)", "run_rebalance.py")

@app.post("/api/run/signal_test")
async def run_signal_test(): return _run("Signal Test", "run_signal_test.py")

@app.post("/api/run/bot")
async def run_bot():
    raise HTTPException(
        501,
        "Live/paper trading is not wired yet. Use /api/run/rebalance for a dry-run rebalance.",
    )

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

def _zerotier_ip() -> str:
    """Bind to the ZeroTier interface so only VPN peers can reach us.

    Tries ipconfig (Windows) first since the CLI needs admin for the authtoken,
    then falls back to `zerotier-cli listnetworks`, then socket interface scan.
    """
    import subprocess, re

    # 1. Windows ipconfig — parse the "ZeroTier" adapter's IPv4 line.
    try:
        r = subprocess.run(["ipconfig"], capture_output=True, text=True, timeout=3)
        if r.returncode == 0:
            blocks = re.split(r"\r?\n\r?\n", r.stdout)
            for blk in blocks:
                if "ZeroTier" in blk:
                    m = re.search(r"IPv4 Address[^\n:]*:\s*([0-9.]+)", blk)
                    if m:
                        return m.group(1)
    except Exception:
        pass

    # 2. zerotier-cli (needs admin on Windows, works on Linux/Mac as user).
    for exe in ("zerotier-cli",
                r"C:\Program Files (x86)\ZeroTier\One\zerotier-cli.bat"):
        try:
            r = subprocess.run([exe, "-j", "listnetworks"],
                               capture_output=True, text=True, timeout=3)
            if r.returncode == 0 and r.stdout.strip():
                import json as _json
                data = _json.loads(r.stdout)
                for net in data:
                    for ip in net.get("assignedAddresses", []) or []:
                        ip = ip.split("/")[0]
                        if ":" not in ip:
                            return ip
        except Exception:
            continue

    # 3. Socket fallback — first non-loopback, non-private-LAN-looking IP.
    try:
        import socket
        for ip in socket.gethostbyname_ex(socket.gethostname())[2]:
            if ip.startswith(("127.", "169.254.")):
                continue
            return ip
    except Exception:
        pass

    print("  WARNING: ZeroTier IP not found — binding to 127.0.0.1 (local only)")
    return "127.0.0.1"


def serve(host: str = None, port: int = 8000, open_browser: bool = False):
    if host is None:
        host = _zerotier_ip()
    if open_browser:
        import threading, webbrowser
        threading.Timer(1.2, lambda: webbrowser.open(f"http://{host}:{port}")).start()
    print(f"\n  iStock  ·  http://{host}:{port}  (ZeroTier only)\n")
    uvicorn.run(app, host=host, port=port, log_level="warning")


if __name__ == "__main__":
    serve(open_browser=True)
