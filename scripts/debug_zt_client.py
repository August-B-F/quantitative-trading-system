"""QTS dashboard connectivity diagnostic — CLIENT SIDE.

========================================================================
  INSTRUCTIONS FOR CLAUDE CODE RUNNING THIS SCRIPT
========================================================================

You have been handed this script to help the user debug why they cannot
reach the QTS dashboard on the Swedish host via WireGuard at:

    http://10.200.200.2:8765

The host-side is known-good. This script is READ-ONLY.

HARD RULES:
  1. Do NOT modify the user's WireGuard, firewall, routing, browser, or
     any system setting without explicit consent from the user.
  2. Do NOT edit files, or install packages. This script only *reads*
     and *probes*.
  3. If a check surfaces a problem that needs a change, print the
     suggested fix as text and STOP. Ask the user before acting.
  4. Report back only what was observed. Don't embellish.

HOW TO RUN:
    python3 scripts/debug_zt_client.py

Optional environment variables:
    HOST_IP=10.200.200.2    # override target WireGuard IP
    HOST_PORT=8765          # override target port
    VERBOSE=1               # print full subprocess output

WHAT IT CHECKS (all read-only):
    - OS / platform / kernel
    - Whether the WireGuard tunnel interface is up (ipconfig / ip addr)
    - Whether the 10.200.200.0/24 route is installed in the OS routing table
    - ICMP ping to the host (10.200.200.2)
    - TCP connect to port 8765
    - HTTP GET of / and /backtest_presentation.json
    - Environment proxy variables (HTTP_PROXY etc)

========================================================================
"""
from __future__ import annotations

import json
import os
import platform
import re
import shutil
import socket
import subprocess
import sys
import urllib.request
from typing import Optional

# Force UTF-8 stdout so unicode chars render on Windows consoles (cp1252).
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HOST_IP = os.environ.get("HOST_IP", "10.200.200.2")
HOST_PORT = int(os.environ.get("HOST_PORT", "8765"))
WG_SUBNET = "10.200.200."
VERBOSE = bool(os.environ.get("VERBOSE"))


# --------------------------------------------------------------------- UI
BOLD = "\033[1m"
DIM = "\033[2m"
GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
RESET = "\033[0m"
if not sys.stdout.isatty() or os.name == "nt":
    BOLD = DIM = GREEN = RED = YELLOW = CYAN = RESET = ""


def header(title: str) -> None:
    print(f"\n{BOLD}{CYAN}── {title} ──{RESET}")


def ok(msg: str) -> None:
    print(f"  {GREEN}✓{RESET} {msg}")


def bad(msg: str) -> None:
    print(f"  {RED}✗{RESET} {msg}")


def warn(msg: str) -> None:
    print(f"  {YELLOW}!{RESET} {msg}")


def info(msg: str) -> None:
    print(f"  {DIM}·{RESET} {msg}")


def run(cmd: list[str], timeout: int = 8) -> tuple[int, str, str]:
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return p.returncode, p.stdout or "", p.stderr or ""
    except FileNotFoundError:
        return 127, "", "not-found"
    except subprocess.TimeoutExpired:
        return 124, "", "timeout"
    except Exception as e:  # noqa: BLE001
        return 1, "", str(e)


def which(bin_name: str) -> Optional[str]:
    return shutil.which(bin_name)


# --------------------------------------------------------------------- checks

def check_platform() -> dict:
    header("Platform")
    d = {
        "system": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
        "python": sys.version.split()[0],
    }
    info(f"OS: {d['system']} {d['release']} ({d['machine']})")
    info(f"Python: {d['python']}")
    return d


def check_env_proxies() -> dict:
    header("HTTP proxy environment")
    keys = [
        "HTTP_PROXY", "http_proxy", "HTTPS_PROXY", "https_proxy",
        "ALL_PROXY", "all_proxy", "NO_PROXY", "no_proxy",
    ]
    set_vars = {k: os.environ.get(k) for k in keys if os.environ.get(k)}
    if not set_vars:
        ok("no proxy env vars set")
    else:
        for k, v in set_vars.items():
            warn(f"{k}={v}")
        warn("A proxy env var can reroute traffic through an upstream "
             "proxy that can't reach the WireGuard network.")
    return set_vars


def check_wireguard() -> dict:
    header("WireGuard tunnel interface")
    out: dict = {"found": False, "ip": None}

    if platform.system() == "Windows":
        rc, so, _ = run(["ipconfig"])
        if rc == 0:
            for blk in re.split(r"\r?\n\r?\n", so):
                m = re.search(r"IPv4 Address[^\n:]*:\s*(10\.200\.200\.\d+)", blk)
                if m:
                    out["found"] = True
                    out["ip"] = m.group(1)
                    adapter = ""
                    am = re.search(r"adapter\s+(.+?):", blk)
                    if am:
                        adapter = am.group(1)
                    ok(f"WireGuard adapter '{adapter}' has IP {out['ip']}")
                    break
    else:
        if which("ip"):
            rc, so, _ = run(["ip", "-4", "addr"])
        else:
            rc, so, _ = run(["ifconfig"])
        for line in so.splitlines():
            m = re.search(r"(10\.200\.200\.\d+)", line)
            if m:
                out["found"] = True
                out["ip"] = m.group(1)
                ok(f"WireGuard interface has IP {out['ip']}")
                break

    if not out["found"]:
        bad("No interface with a 10.200.200.x address found")
        info("FIX: ensure the WireGuard tunnel is active.")
        if platform.system() == "Windows":
            info("Open WireGuard app → activate the 'tower' tunnel")
        else:
            info("Try: sudo wg-quick up tower")
    return out


def check_route() -> dict:
    header(f"Routing table for {WG_SUBNET}0/24")
    out: dict = {"found": False, "lines": []}
    if platform.system() == "Windows":
        rc, so, _ = run(["route", "print", "-4"])
        for line in so.splitlines():
            if WG_SUBNET.rstrip(".") in line:
                out["lines"].append(line.strip())
    else:
        if which("ip"):
            rc, so, _ = run(["ip", "route"])
        else:
            rc, so, _ = run(["netstat", "-rn"])
        for line in so.splitlines():
            if WG_SUBNET.rstrip(".") in line:
                out["lines"].append(line.strip())
    if out["lines"]:
        out["found"] = True
        for l in out["lines"]:
            ok(l)
    else:
        bad(f"No route for {WG_SUBNET}0/24 in the OS routing table")
        info("The WireGuard tunnel may not be active, or AllowedIPs "
             "does not include this subnet.")
    return out


def check_ping() -> dict:
    header(f"ICMP ping to {HOST_IP}")
    if platform.system() == "Windows":
        cmd = ["ping", "-n", "3", "-w", "1500", HOST_IP]
    else:
        cmd = ["ping", "-c", "3", "-W", "2", HOST_IP]
    rc, so, se = run(cmd, timeout=10)
    if VERBOSE:
        print(so)
    alive = rc == 0 and ("ttl=" in so.lower() or "TTL=" in so)
    if alive:
        for line in so.splitlines():
            if any(k in line.lower() for k in ("avg", "min/avg", "average")):
                info(line.strip())
        ok(f"host {HOST_IP} reachable via ICMP")
    else:
        bad(f"host {HOST_IP} NOT reachable via ICMP")
        info("If the routing-table check above also failed, the WireGuard "
             "tunnel is likely not active.")
    return {"alive": alive, "output": so}


def check_tcp() -> dict:
    header(f"TCP connect {HOST_IP}:{HOST_PORT}")
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(5)
    try:
        s.connect((HOST_IP, HOST_PORT))
        ok(f"TCP handshake OK  (local {s.getsockname()})")
        s.close()
        return {"ok": True}
    except Exception as e:
        bad(f"TCP connect failed: {e}")
        return {"ok": False, "error": str(e)}
    finally:
        try:
            s.close()
        except Exception:
            pass


def check_http() -> dict:
    header(f"HTTP GET http://{HOST_IP}:{HOST_PORT}/")
    out: dict = {}
    urls = [
        f"http://{HOST_IP}:{HOST_PORT}/",
        f"http://{HOST_IP}:{HOST_PORT}/backtest_presentation.json",
    ]
    for url in urls:
        try:
            r = urllib.request.urlopen(url, timeout=6)
            body = r.read()
            ok(f"{url}  →  HTTP {r.status}  {len(body)} bytes  "
               f"({r.headers.get('content-type','?')})")
            out[url] = {"status": r.status, "len": len(body)}
        except Exception as e:
            bad(f"{url}  →  {type(e).__name__}: {e}")
            out[url] = {"error": str(e)}
    return out


def check_local_interfaces() -> dict:
    header("Local interfaces")
    out: dict = {"interfaces": []}
    if platform.system() == "Windows":
        rc, so, _ = run(["ipconfig"])
    else:
        if which("ip"):
            rc, so, _ = run(["ip", "-4", "addr"])
        else:
            rc, so, _ = run(["ifconfig"])
    lines = [l for l in so.splitlines()
             if "wireguard" in l.lower() or "tower" in l.lower()
             or "10.200.200" in l or "wg" in l.lower()]
    for l in lines:
        info(l.strip())
    out["matches"] = lines
    return out


# --------------------------------------------------------------------- main

def main() -> int:
    print(f"{BOLD}QTS dashboard — client-side connectivity diagnostic{RESET}")
    print(f"{DIM}target: http://{HOST_IP}:{HOST_PORT}/   "
          f"subnet: {WG_SUBNET}0/24{RESET}")

    report: dict = {}
    report["platform"] = check_platform()
    report["proxy_env"] = check_env_proxies()
    report["wireguard"] = check_wireguard()
    report["local_if"] = check_local_interfaces()
    report["route"] = check_route()
    report["ping"] = check_ping()
    report["tcp"] = check_tcp()
    report["http"] = check_http()

    # Summary
    header("Summary")
    problems: list[str] = []
    wg = report["wireguard"]
    if not wg.get("found"):
        problems.append("No WireGuard tunnel interface found (no 10.200.200.x IP). "
                        "Activate the tunnel first.")
    if not report["route"]["found"]:
        problems.append(
            f"No OS route for {WG_SUBNET}0/24 — the WireGuard tunnel "
            "may not be active or AllowedIPs is misconfigured."
        )
    if not report["ping"]["alive"]:
        problems.append(f"ICMP ping to {HOST_IP} fails.")
    if not report["tcp"].get("ok"):
        problems.append(f"TCP connect to {HOST_IP}:{HOST_PORT} fails.")
    if report["proxy_env"]:
        problems.append("Proxy environment variables are set; unset them "
                        f"or add {WG_SUBNET}0/24 to NO_PROXY.")

    if not problems:
        ok("All checks passed — the client can reach the dashboard. "
           "If the browser still fails, it's browser-local (proxy, DNS, "
           "cached splash). Try a private window or curl.")
        return 0

    print()
    for i, p in enumerate(problems, 1):
        bad(f"{i}. {p}")
    print()
    print(f"{BOLD}Do NOT change anything without the user's consent.{RESET}")
    print(f"{DIM}Report the findings above and let them decide.{RESET}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
