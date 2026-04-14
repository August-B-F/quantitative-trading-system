"""QTS dashboard connectivity diagnostic — CLIENT SIDE (Italian laptop).

========================================================================
  INSTRUCTIONS FOR CLAUDE CODE RUNNING THIS SCRIPT
========================================================================

You have been handed this script to help the user debug why they cannot
reach the QTS dashboard on the Swedish host at:

    http://10.88.220.209:8765

The host-side is known-good. This script is READ-ONLY.

HARD RULES:
  1. Do NOT modify the user's ZeroTier, Tailscale, firewall, routing,
     browser, or any system setting without explicit consent from the user.
  2. Do NOT run `zerotier-cli join/leave`, `sudo` anything, edit files,
     or install packages. This script only *reads* and *probes*.
  3. If a check surfaces a problem that needs a change, print the
     suggested fix as text and STOP. Ask the user before acting.
  4. Sudo is only needed to read ZeroTier's auth token on Linux/macOS;
     if the user doesn't want to sudo, skip that section gracefully.
  5. Report back only what was observed. Don't embellish.

HOW TO RUN:
    python3 scripts/debug_zt_client.py

Optional environment variables:
    HOST_IP=10.88.220.209   # override target ZT IP
    HOST_PORT=8765          # override target port
    VERBOSE=1               # print full subprocess output

WHAT IT CHECKS (all read-only):
    - OS / platform / kernel
    - Whether ZeroTier is installed + service running
    - Which ZT networks are joined and their status + assigned IP
    - Whether the 10.88.220.0/24 route is installed in the OS routing table
    - ARP / neighbour table for the ZT subnet
    - ICMP ping to the host (10.88.220.209)
    - TCP connect to port 8765
    - HTTP GET of / and /backtest_presentation.json
    - Tailscale interference (is it up, does it hold 10/8 routes)
    - Environment proxy variables (HTTP_PROXY etc)

========================================================================
"""
from __future__ import annotations

import json
import os
import platform
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

HOST_IP = os.environ.get("HOST_IP", "10.88.220.209")
HOST_PORT = int(os.environ.get("HOST_PORT", "8765"))
NETWORK_ID = "b103a835d29357ad"
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
        warn("A proxy env var can reroute 10.88.220.209 through an upstream "
             "proxy that can't reach the ZT network.")
    return set_vars


def check_zerotier() -> dict:
    header("ZeroTier")
    out: dict = {"installed": False, "service": None, "networks": [],
                 "node_id": None, "online": None}

    exe = which("zerotier-cli")
    if not exe:
        # Windows default install path
        win_exe = r"C:\ProgramData\ZeroTier\One\zerotier-one_x64.exe"
        if os.path.exists(win_exe):
            exe = win_exe
            info(f"zerotier-cli not on PATH; found {win_exe}")
    if not exe:
        bad("ZeroTier not installed (no zerotier-cli on PATH and no Windows install)")
        info("FIX (ask user): install from https://www.zerotier.com/download/")
        return out
    out["installed"] = True
    ok(f"ZeroTier binary: {exe}")

    # info
    if exe.endswith(".exe"):
        rc, so, se = run([exe, "-q", "info"])
    else:
        rc, so, se = run([exe, "info"])
    if rc == 0 and so.strip():
        out["status_line"] = so.strip()
        info(f"info: {so.strip()}")
        parts = so.split()
        if len(parts) >= 4:
            out["node_id"] = parts[1] if parts[0] == "200" else parts[0]
            out["online"] = "ONLINE" in so.upper()
    else:
        # Non-Windows may need sudo to talk to the service
        if "root" in (se or "").lower() or "permission" in (se or "").lower():
            warn("zerotier-cli info requires root/admin on this platform")
            info("Try: sudo zerotier-cli info")
        else:
            bad(f"zerotier-cli info failed: {se.strip() or so.strip()}")
        return out

    # listnetworks
    if exe.endswith(".exe"):
        rc, so, se = run([exe, "-q", "listnetworks"])
    else:
        rc, so, se = run([exe, "listnetworks"])
    if rc != 0:
        warn(f"listnetworks failed: {se.strip() or so.strip()}")
        info("Try: sudo zerotier-cli listnetworks")
        return out

    # Parse: `200 listnetworks <nwid> <name> <mac> <status> <type> <dev> <ips>`
    for line in so.splitlines():
        line = line.strip()
        if not line or "listnetworks" not in line.split()[:2]:
            continue
        toks = line.split()
        # toks[0]=200 toks[1]=listnetworks toks[2]=nwid ...
        if len(toks) < 8:
            continue
        rec = {
            "nwid": toks[2],
            "name": toks[3],
            "mac": toks[4],
            "status": toks[5],
            "type": toks[6],
            "dev": toks[7],
            "ips": toks[8] if len(toks) > 8 else "-",
        }
        out["networks"].append(rec)
        line_ok = (rec["status"] == "OK")
        line_target = (rec["nwid"] == NETWORK_ID)
        fn = ok if (line_ok and line_target) else (warn if line_target else info)
        fn(f"{rec['nwid']}  name={rec['name']}  "
           f"status={rec['status']}  ips={rec['ips']}  dev={rec['dev']}")

    target = [n for n in out["networks"] if n["nwid"] == NETWORK_ID]
    if not target:
        bad(f"This device is NOT joined to network {NETWORK_ID}")
        info(f"FIX (ask user): `zerotier-cli join {NETWORK_ID}`, then "
             "authorize at https://my.zerotier.com")
    else:
        t = target[0]
        if t["status"] != "OK":
            bad(f"network {NETWORK_ID} status is {t['status']} (expected OK)")
            if t["status"] == "REQUESTING_CONFIGURATION":
                info("The controller has not authorized this member yet. "
                     "Fix at https://my.zerotier.com → Networks → "
                     f"{NETWORK_ID} → Members → tick Auth?")
            elif t["status"] == "ACCESS_DENIED":
                info("The member is explicitly denied by the controller.")
        elif t["ips"] in ("-", ""):
            bad("network OK but no managed IP assigned")
        else:
            ok(f"This device has ZT IP {t['ips']} on {NETWORK_ID}")
    return out


def check_route(target_cidr: str = "10.88.220.0/24") -> dict:
    header(f"Routing table for {target_cidr}")
    out: dict = {"found": False, "lines": []}
    if platform.system() == "Windows":
        rc, so, _ = run(["route", "print", "-4"])
        for line in so.splitlines():
            if "10.88.220" in line:
                out["lines"].append(line.strip())
    else:
        if which("ip"):
            rc, so, _ = run(["ip", "route"])
        else:
            rc, so, _ = run(["netstat", "-rn"])
        for line in so.splitlines():
            if "10.88.220" in line:
                out["lines"].append(line.strip())
    if out["lines"]:
        out["found"] = True
        for l in out["lines"]:
            ok(l)
    else:
        bad(f"No route for {target_cidr} in the OS routing table")
        info("This is the most common root cause on mobile: the ZT app is "
             "installed but the OS never installed the managed route. On "
             "iOS/Android, check 'Allow Managed' / 'Allow Default Route' "
             "for this network in the ZeroTier app.")
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
        info("If the routing-table check above also failed, the ZT route is "
             "missing → fix in the ZeroTier app, not here.")
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


def check_tailscale() -> dict:
    header("Tailscale (interference check)")
    out: dict = {"installed": False, "backend": None, "up": False,
                 "grabs_private": None}
    exe = which("tailscale")
    if not exe:
        info("tailscale not installed — cannot interfere")
        return out
    out["installed"] = True
    rc, so, se = run([exe, "status", "--json"])
    if rc != 0:
        warn(f"tailscale status failed: {se.strip() or so.strip()}")
        return out
    try:
        st = json.loads(so)
    except json.JSONDecodeError:
        warn("could not parse tailscale status")
        return out
    backend = st.get("BackendState")
    out["backend"] = backend
    out["up"] = backend == "Running"
    if backend == "Running":
        warn(f"Tailscale backend is Running (self={st.get('Self',{}).get('TailscaleIPs')})")
        # Check if any peer advertises 10.88.220.0/24 or 10.0.0.0/8
        covers = []
        for peer in (st.get("Peer") or {}).values():
            for r in (peer.get("PrimaryRoutes") or []):
                if r.startswith("10.") or r == "0.0.0.0/0":
                    covers.append((peer.get("HostName"), r))
        if covers:
            warn(f"Tailscale peers advertise private routes: {covers}")
        else:
            ok("No Tailscale peer advertises 10.x — Tailscale should not "
               "intercept 10.88.220.209")
        # ExitNodeID
        if st.get("ExitNodeStatus") and st["ExitNodeStatus"].get("ID"):
            warn(f"Tailscale exit node is set: {st['ExitNodeStatus']}")
    else:
        info(f"Tailscale backend: {backend}")
    return out


def check_ips_on_host() -> dict:
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
             if "zerotier" in l.lower() or "10.88.220" in l
             or "tailscale" in l.lower() or "utun" in l.lower()]
    for l in lines:
        info(l.strip())
    out["matches"] = lines
    return out


# --------------------------------------------------------------------- main

def main() -> int:
    print(f"{BOLD}QTS dashboard — client-side connectivity diagnostic{RESET}")
    print(f"{DIM}target: http://{HOST_IP}:{HOST_PORT}/   "
          f"network: {NETWORK_ID}{RESET}")

    report: dict = {}
    report["platform"] = check_platform()
    report["proxy_env"] = check_env_proxies()
    report["zerotier"] = check_zerotier()
    report["local_if"] = check_ips_on_host()
    report["route"] = check_route()
    report["ping"] = check_ping()
    report["tcp"] = check_tcp()
    report["http"] = check_http()
    report["tailscale"] = check_tailscale()

    # Summary
    header("Summary")
    problems: list[str] = []
    zt = report["zerotier"]
    if not zt.get("installed"):
        problems.append("ZeroTier is not installed on this device.")
    elif not zt.get("networks"):
        problems.append("No ZeroTier networks joined (or cli needs sudo).")
    else:
        target = [n for n in zt["networks"] if n["nwid"] == NETWORK_ID]
        if not target:
            problems.append(
                f"Not joined to target network {NETWORK_ID}."
            )
        else:
            t = target[0]
            if t["status"] != "OK":
                problems.append(
                    f"Network {NETWORK_ID} status={t['status']} — "
                    "authorize at https://my.zerotier.com."
                )
            elif t["ips"] in ("-", ""):
                problems.append(f"Network {NETWORK_ID} joined but no IP assigned.")
    if not report["route"]["found"]:
        problems.append(
            f"No OS route for 10.88.220.0/24 — the ZT app is not installing "
            "the managed route. Check 'Allow Managed' / 'Allow Default Route' "
            "in the ZT app for this network."
        )
    if not report["ping"]["alive"]:
        problems.append(f"ICMP ping to {HOST_IP} fails.")
    if not report["tcp"].get("ok"):
        problems.append(f"TCP connect to {HOST_IP}:{HOST_PORT} fails.")
    if report["proxy_env"]:
        problems.append("Proxy environment variables are set; unset them "
                        "or add 10.88.220.0/24 to NO_PROXY.")
    if report["tailscale"].get("up"):
        problems.append(
            "Tailscale is running. Confirm it is NOT your source of "
            "interference by disabling it and re-running this script."
        )

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
