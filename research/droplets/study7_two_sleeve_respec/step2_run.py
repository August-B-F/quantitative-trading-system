"""Run pre-registered configs on the dev window at 10/20 bps.

Usage: py -3 step2_run.py C1 C2 C3 C4
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib_study7 import CONFIGS, DEV_END, DEV_START, fmt, get_prices, run_config  # noqa: E402

ids = sys.argv[1:]
prices = get_prices()
for cid in ids:
    params = CONFIGS[cid]
    out = run_config(prices, params, DEV_START, DEV_END)
    tag = "/".join(str(v) for v in params.values())
    for bps, s in out.items():
        print(f"{cid} [{tag}]  {bps:4.0f}bps  {s['start'].date()}..{s['end'].date()}  {fmt(s)}")
