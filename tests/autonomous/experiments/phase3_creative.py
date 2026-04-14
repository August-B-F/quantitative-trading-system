"""Phase 3: creative momentum signals, using custom_engine + raw prices.

- Lookback blends: avg(63,84), avg(63,105), avg(63,126)
- Multi-timeframe: 21d * weight + 63d * weight
- Momentum of momentum (acceleration): 21d - 63d
- Risk-adjusted momentum: 63d / 63d_vol
- 12-1 momentum: 12m excluding most recent month

All evaluated on the current champion config (dropoverlap + 60/40).
"""
from __future__ import annotations
import sys, datetime as dt
from pathlib import Path
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from utils.base_test import _load, _STATE, fmt, haircut_verdict  # noqa: E402
from utils.custom_engine import run_custom  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
CHAMP = {"universe": ["SOXX","QQQ","IGV","XLE","GLD","SHY"], "top1_weight":0.60, "top3_weight":0.40}

_load()
bundle = _STATE["bundle"]
dates = bundle.dates

# Load prices for all relevant tickers
TICKERS = sorted(set(CHAMP["universe"]) | set(_STATE["cfg"].get("feature_extras", [])) | {"SPY"})
def load_close(tk):
    p = ROOT / f"data/clean/prices/{tk}.parquet"
    if not p.exists(): return None
    df = pd.read_parquet(p)
    return df["adj_close"]

prices = {}
for t in TICKERS:
    c = load_close(t)
    if c is not None:
        prices[t] = c
# Align to bundle.dates
px = pd.DataFrame({k: v for k, v in prices.items()}).reindex(dates).ffill()


def nd_return(N):
    return px / px.shift(N) - 1.0

def blended(*windows_and_weights):
    """Equal or weighted blend of N-day returns. Pass (N, w) pairs."""
    parts = []
    for N, w in windows_and_weights:
        parts.append(nd_return(N) * w)
    return sum(parts)

def accel_21_63():
    return nd_return(21) - nd_return(63)

def volaadj_63():
    r = px.pct_change()
    sigma = r.rolling(63).std()
    return (nd_return(63) / (sigma + 1e-9))

def mom_12_1():
    # 252d return of (t-21) / 252d shifted by 21 == price(t-21) / price(t-21-252)
    return (px.shift(21) / px.shift(21 + 252)) - 1.0


EXPERIMENTS = []
# Baseline champion sanity with custom engine (should match)
EXPERIMENTS.append(("P3.00_sanity_63", nd_return(63), None))
EXPERIMENTS.append(("P3.01_blend63_84", blended((63,0.5),(84,0.5)), None))
EXPERIMENTS.append(("P3.02_blend63_105", blended((63,0.5),(105,0.5)), None))
EXPERIMENTS.append(("P3.03_blend63_126", blended((63,0.5),(126,0.5)), None))
EXPERIMENTS.append(("P3.04_blend42_63_126", blended((42,1/3),(63,1/3),(126,1/3)), None))
EXPERIMENTS.append(("P3.05_blend63_252", blended((63,0.5),(252,0.5)), None))
EXPERIMENTS.append(("P3.06_blend_21_63", blended((21,0.5),(63,0.5)), None))
EXPERIMENTS.append(("P3.07_blend_w63w126_weighted", blended((63,0.7),(126,0.3)), None))
EXPERIMENTS.append(("P3.08_volaadj_63", volaadj_63(), None))
EXPERIMENTS.append(("P3.09_mom_12_1", mom_12_1(), None))
EXPERIMENTS.append(("P3.10_accel_21_63", accel_21_63(), None))

# Asymmetric: stable=blend, transition remains 21d default
# Transition signal experiments: use 10d returns for trans
EXPERIMENTS.append(("P3.11_trans_10d", None, nd_return(10)))
EXPERIMENTS.append(("P3.12_trans_5d", None, nd_return(5)))
EXPERIMENTS.append(("P3.13_trans_42d_on_stable_blend", blended((63,0.5),(126,0.5)), nd_return(42)))


def main():
    log_path = HERE.parent / "LOG.md"
    ts = dt.datetime.now().isoformat(timespec="seconds")
    lines = [f"\n### phase3_creative  {ts}\n",
             "| name | CAGR | Sharpe | MaxDD | verdict |",
             "|---|---|---|---|---|"]
    for name, stable_sig, trans_sig in EXPERIMENTS:
        try:
            s = run_custom(stable_sig, trans_sig, overrides=CHAMP)
        except Exception as e:
            s = {"error": str(e)}
        if "error" in s:
            print(name, "ERROR", s["error"])
            lines.append(f"| {name} | | | | ERR {s['error'][:40]} |")
            continue
        passes, _ = haircut_verdict(s)
        v = "PASS" if passes else "fail"
        print(name, fmt(s), v)
        lines.append(f"| {name} | {s['cagr']*100:.2f}% | {s['sharpe']:.2f} | {s['max_dd']*100:.2f}% | {v} |")
    with open(log_path, "a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

if __name__ == "__main__":
    main()
