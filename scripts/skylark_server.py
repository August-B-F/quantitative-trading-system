"""Skylark — FastAPI backend for the 9-strategy horse race UI.

Replaces the old scripts/web_server.py. Serves scripts/static/ (the Skylark
single-page app) and exposes JSON endpoints backed by scripts/skylark_data.py.

Paper vs live is a single env var: ``ALPACA_LIVE=1`` flips every account to
the live base URL. All other code paths are identical — the UI is ready for
real money as soon as the flag is thrown.
"""
from __future__ import annotations

import asyncio
import collections
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _load_dotenv() -> None:
    """Minimal .env loader so Alpaca credentials reach this process.

    Matches the loader used by scripts/run_rebalance.py — no third-party
    dependency, only sets keys that aren't already in os.environ.
    """
    import os as _os
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        _os.environ.setdefault(k.strip(), v.strip())


_load_dotenv()

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

from scripts import skylark_data as sd

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

_SCRIPTS = Path(__file__).resolve().parent
_ROOT    = _SCRIPTS.parent

app = FastAPI(title="Skylark", docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=str(_SCRIPTS / "static")), name="static")


# ───────────────────────────────────────────────────────────────────────────
# Process manager (for /api/rebalance/run)
# ───────────────────────────────────────────────────────────────────────────

class ProcessManager:
    def __init__(self, maxlines: int = 500):
        self.proc: Optional[subprocess.Popen] = None
        self.name: str = ""
        self.started_at: Optional[float] = None
        self.buf: collections.deque = collections.deque(maxlen=maxlines)

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
        threading.Thread(target=self._reader, daemon=True).start()

    def _reader(self) -> None:
        for line in iter(self.proc.stdout.readline, ""):
            line = line.rstrip()
            if line:
                self.buf.append({"t": datetime.now().strftime("%H:%M:%S"), "msg": line})
        self.proc.wait()
        rc = self.proc.returncode
        msg = "✓ Finished (exit 0)" if rc == 0 else f"✗ Exited with code {rc}"
        self.buf.append({"t": datetime.now().strftime("%H:%M:%S"), "msg": msg, "rc": rc})

    def stop(self) -> None:
        if self.running:
            self.proc.terminate()

    def status(self) -> dict:
        up = int(time.time() - self.started_at) if self.started_at else 0
        return {
            "running": self.running,
            "name":    self.name,
            "pid":     self.proc.pid if self.proc else None,
            "uptime":  up,
            "rc":      self.proc.returncode if self.proc and not self.running else None,
        }


_pm = ProcessManager()
_ACCESS_LOG: collections.deque = collections.deque(maxlen=500)
_SERVER_START_TS: float = time.time()


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
        })
    return response


@app.get("/", response_class=HTMLResponse)
async def root():
    return FileResponse(str(_SCRIPTS / "static" / "index.html"))


# ───────────────────────────────────────────────────────────────────────────
# Dashboard + strategies
# ───────────────────────────────────────────────────────────────────────────

@app.get("/api/dashboard")
async def dashboard():
    return sd.dashboard_summary()


@app.get("/api/strategies")
async def strategies():
    regs = sd.strategy_registry()
    out = []
    for s in regs:
        eq = sd.live_strategy_equity(s)
        bt = s["backtest"] or {}
        out.append({
            "slot":        s["slot"],
            "slot_id":     s["slot_id"],
            "name":        s["name"],
            "tier":        s["tier"],
            "login":       s["login"],
            "description": s["description"],
            "universe":    s["universe"],
            "equity":      eq["equity"],
            "return_pct":  eq["return_pct"],
            "connected":   eq["connected"],
            "backtest":    bt,
            "tracking":    sd.expectations_quick(s["slot"]),
        })
    return {"strategies": out, "live_mode": sd.is_live()}


@app.get("/api/strategy/{slot}")
async def strategy_detail(slot: int):
    s = sd.strategy_by_slot(slot)
    if s is None:
        raise HTTPException(404, f"slot {slot} not found")
    eq   = sd.live_strategy_equity(s)
    pos  = sd.alpaca_positions(s)
    hist = sd.alpaca_portfolio_history(s, period="6M")
    orders = sd.alpaca_orders(s, limit=50)
    reb_log = [r for r in sd.load_rebalance_log() if r.get("slot") in (slot, None)][-50:][::-1]
    rationale = sd.strategy_rationale().get(slot, "")
    stats    = sd.strategy_stats(slot)
    vs_spy   = sd.vs_spy_stats(slot)
    expect   = sd.expectations_check(slot)
    # Build a comparable backtest equity curve (base=1.0) from monthly returns
    monthly = s["monthly_returns"] or {}
    bt_curve = []
    val = 1.0
    for d in sorted(monthly.keys()):
        val *= (1.0 + float(monthly[d] or 0.0))
        bt_curve.append({"date": d, "value": val})
    return {
        "slot":        s["slot"],
        "slot_id":     s["slot_id"],
        "name":        s["name"],
        "tier":        s["tier"],
        "login":       s["login"],
        "description": s["description"],
        "rationale":   rationale,
        "spec":        s["spec"],
        "universe":    s["universe"],
        "backtest":    s["backtest"],
        "annual_returns":  s["annual_returns"],
        "backtest_curve":  bt_curve,
        "key_stats":       stats.get("key_stats", {}),
        "rolling_sharpe":  stats.get("rolling_sharpe", []),
        "drawdowns":       stats.get("drawdowns", []),
        "spy_drawdowns":   stats.get("spy_drawdowns", []),
        "monthly_heatmap": stats.get("monthly_heatmap", []),
        "attribution":     stats.get("attribution", []),
        "has_attribution": stats.get("has_attribution", False),
        "spy_key_stats":   vs_spy.get("spy_key_stats", {}),
        "vs_spy":          vs_spy.get("vs_spy", {}),
        "live":        eq,
        "positions":   pos,
        "portfolio_history": hist,
        "orders":      orders,
        "rebalance_log": reb_log,
        "expectations":  expect,
    }


@app.get("/api/comparison")
async def comparison():
    return sd.comparison_matrix()


# ───────────────────────────────────────────────────────────────────────────
# Accounts (tier-level rollups — Phase B will expand)
# ───────────────────────────────────────────────────────────────────────────

@app.get("/api/accounts")
async def accounts():
    groups = sd.tier_groups()
    out = []
    for tier, lst in groups.items():
        tier_equity = 0.0
        rows = []
        for s in lst:
            eq = sd.live_strategy_equity(s)
            tier_equity += eq["equity"] or 0.0
            rows.append({
                "slot": s["slot"], "name": s["name"],
                "equity": eq["equity"], "return_pct": eq["return_pct"],
                "connected": eq["connected"],
            })
        out.append({"tier": tier, "equity": tier_equity, "strategies": rows})
    return {"tiers": out, "live_mode": sd.is_live()}


@app.get("/api/account/{tier}")
async def account_tier(tier: str):
    groups = sd.tier_groups()
    if tier not in groups:
        raise HTTPException(404, f"unknown tier {tier}")
    rows = []
    for s in groups[tier]:
        rows.append({
            "slot":      s["slot"],
            "name":      s["name"],
            "live":      sd.live_strategy_equity(s),
            "positions": sd.alpaca_positions(s),
            "orders":    sd.alpaca_orders(s, limit=25),
            "history":   sd.alpaca_portfolio_history(s, period="3M"),
        })
    return {"tier": tier, "strategies": rows}


# ───────────────────────────────────────────────────────────────────────────
# Data health / regime
# ───────────────────────────────────────────────────────────────────────────

@app.get("/api/data/health")
async def data_health():
    return sd.data_health_summary()


@app.get("/api/data/regime")
async def data_regime():
    return sd.current_regime()


# ───────────────────────────────────────────────────────────────────────────
# Rebalance
# ───────────────────────────────────────────────────────────────────────────

@app.get("/api/rebalance/log")
async def rebalance_log(limit: int = 100):
    return {"entries": sd.rebalance_log(limit=limit)}


@app.post("/api/rebalance/run")
async def rebalance_run(dry_run: bool = True):
    if _pm.running:
        raise HTTPException(409, f"Process '{_pm.name}' already running")
    script = _SCRIPTS / "run_rebalance.py"
    cmd = [sys.executable, str(script)]
    if dry_run:
        cmd.append("--dry-run")
    _pm.start("Rebalance" + (" (dry)" if dry_run else ""), cmd)
    return {"started": True, "pid": _pm.proc.pid, "dry_run": dry_run}


@app.post("/api/process/stop")
async def process_stop():
    _pm.stop()
    return {"stopped": True}


@app.get("/api/process/status")
async def process_status():
    return _pm.status()


@app.get("/api/process/log")
async def process_log():
    return {"lines": list(_pm.buf)}


# ───────────────────────────────────────────────────────────────────────────
# System health
# ───────────────────────────────────────────────────────────────────────────

@app.get("/api/system/health")
async def system_health():
    h: dict = {"live_mode": sd.is_live()}
    if HAS_PSUTIL:
        import platform
        h["hostname"] = platform.node()
        h["os"]       = f"{platform.system()} {platform.release()}"
        h["python"]   = platform.python_version()

        h["cpu_pct"]      = psutil.cpu_percent(interval=0.2)
        h["cpu_per_core"] = psutil.cpu_percent(interval=None, percpu=True)
        h["cpu_count"]    = psutil.cpu_count(logical=True)
        h["cpu_physical"] = psutil.cpu_count(logical=False)
        try:
            freq = psutil.cpu_freq()
            h["cpu_ghz"] = round(freq.current / 1000, 2) if freq else None
        except Exception:
            h["cpu_ghz"] = None

        vm = psutil.virtual_memory()
        h["mem_pct"]      = vm.percent
        h["mem_used_gb"]  = round(vm.used  / 1e9, 1)
        h["mem_total_gb"] = round(vm.total / 1e9, 1)
        h["mem_free_gb"]  = round(vm.available / 1e9, 1)
        sw = psutil.swap_memory()
        h["swap_pct"]     = sw.percent
        h["swap_used_gb"] = round(sw.used / 1e9, 1)

        du = psutil.disk_usage(str(_ROOT))
        h["disk_pct"]     = du.percent
        h["disk_used_gb"] = round(du.used / 1e9, 1)
        h["disk_free_gb"] = round(du.free / 1e9, 1)
        h["disk_total_gb"] = round(du.total / 1e9, 1)

        try:
            net = psutil.net_io_counters()
            h["net_sent_gb"] = round(net.bytes_sent / 1e9, 2)
            h["net_recv_gb"] = round(net.bytes_recv / 1e9, 2)
        except Exception:
            pass

        try:
            h["n_processes"] = len(psutil.pids())
            h["n_threads"]   = sum(p.num_threads() for p in psutil.process_iter(["num_threads"]) if p.info.get("num_threads"))
        except Exception:
            pass

        # CPU/GPU temperature (best-effort — not all platforms/CPUs expose this)
        try:
            temps = psutil.sensors_temperatures() if hasattr(psutil, "sensors_temperatures") else {}
            hot = []
            for _name, entries in (temps or {}).items():
                for e in entries:
                    if e.current:
                        hot.append(float(e.current))
            h["temp_c"] = round(max(hot), 1) if hot else None
        except Exception:
            h["temp_c"] = None

        # Boot time
        boot = psutil.boot_time()
        secs = int(time.time() - boot)
        d, rem = divmod(secs, 86400)
        hh, rem = divmod(rem, 3600)
        mm = rem // 60
        h["uptime"] = (f"{d}d " if d else "") + f"{hh}h {mm}m"
        h["boot_ts"] = boot

    # GPU (NVIDIA via pynvml, best-effort)
    try:
        import pynvml
        pynvml.nvmlInit()
        cnt = pynvml.nvmlDeviceGetCount()
        gpus = []
        for i in range(cnt):
            hd = pynvml.nvmlDeviceGetHandleByIndex(i)
            mem = pynvml.nvmlDeviceGetMemoryInfo(hd)
            util = pynvml.nvmlDeviceGetUtilizationRates(hd)
            try:
                t = pynvml.nvmlDeviceGetTemperature(hd, pynvml.NVML_TEMPERATURE_GPU)
            except Exception:
                t = None
            gpus.append({
                "name":     pynvml.nvmlDeviceGetName(hd),
                "mem_used_gb":  round(mem.used / 1e9, 1),
                "mem_total_gb": round(mem.total / 1e9, 1),
                "mem_pct":  round(100 * mem.used / mem.total, 1),
                "util_pct": util.gpu,
                "temp_c":   t,
            })
        h["gpus"] = gpus
        pynvml.nvmlShutdown()
    except Exception:
        h["gpus"] = []

    h["process"]    = _pm.status()
    h["access_log"] = list(reversed(list(_ACCESS_LOG)))[:50]
    h["server_start_ts"] = _SERVER_START_TS
    h["server_uptime_s"] = int(time.time() - _SERVER_START_TS)
    return h


# ───────────────────────────────────────────────────────────────────────────
# Entry
# ───────────────────────────────────────────────────────────────────────────

def _wireguard_ip() -> str:
    """Bind to the VPN tunnel interface so only VPN peers can reach the UI."""
    import re, subprocess, socket

    try:
        r = subprocess.run(["ipconfig"], capture_output=True, text=True, timeout=3)
        if r.returncode == 0:
            for blk in re.split(r"\r?\n\r?\n", r.stdout):
                # WireGuard (10.200.200.x) or ZeroTier (named adapter)
                m = re.search(r"IPv4 Address[^\n:]*:\s*(10\.200\.200\.\d+)", blk)
                if m:
                    return m.group(1)
                if re.search(r"ZeroTier", blk, re.IGNORECASE):
                    m = re.search(r"IPv4 Address[^\n:]*:\s*(\d+\.\d+\.\d+\.\d+)", blk)
                    if m:
                        return m.group(1)
    except Exception:
        pass

    try:
        for ip in socket.gethostbyname_ex(socket.gethostname())[2]:
            if ip.startswith("10.200.200."):
                return ip
    except Exception:
        pass

    # Fallback — exclude loopback, link-local, and Hyper-V virtual switches.
    try:
        for ip in socket.gethostbyname_ex(socket.gethostname())[2]:
            if not ip.startswith(("127.", "169.254.", "172.")):
                return ip
    except Exception:
        pass

    print("  WARNING: VPN IP not found — binding to 127.0.0.1 (local only)")
    return "127.0.0.1"


def serve(host: str | None = None, port: int = 8765, open_browser: bool = False):
    if host is None:
        host = _wireguard_ip()
    if open_browser:
        threading.Timer(1.2, lambda: __import__("webbrowser").open(f"http://{host}:{port}")).start()
    mode = "LIVE" if sd.is_live() else "paper"
    print(f"\n  Skylark · http://{host}:{port} · {mode} · WireGuard only\n")
    uvicorn.run(app, host=host, port=port, log_level="warning")


if __name__ == "__main__":
    serve(open_browser=True)
