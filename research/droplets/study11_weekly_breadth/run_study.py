"""Study 11 — weekly cross-sectional breadth spec. Runner.

Implements HYPOTHESIS.md verbatim (frozen before this file was written).
Phases:
  --phase dev    : 10 configs x {10,20} bps on the dev window -> dev_results.csv + trials.csv
  --phase final  : applies the frozen decision rule to dev_results.csv;
                   if KILLED  -> one 0-bps diagnostic run of W on dev
                   if ADOPTED -> one validation look 2018+ on W at 10 and 20 bps
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "src"))

from backtest.ledger import load_prices, run_ledger_backtest  # noqa: E402

UNIVERSE = sorted(
    "AGG DBA DBC EEM EFA EWG EWJ EWZ FXE FXI FXY GDX GLD HYG IBB IEF IEI IWM IYR "
    "LQD QQQ SHY SLV SMH SPY TIP TLT UNG USO UUP XBI XLB XLE XLF XLI XLP XLU XLV XLK".split()
)
HURDLE = "SHV"
LEGS = {"b63_126": (63, 126), "b126_252": (126, 252)}
DEV_END = pd.Timestamp("2017-12-31")
VAL_START = pd.Timestamp("2018-01-01")

CONFIGS = [
    # id, signal, topN, cadence, abs_filter
    ("A", "b126_252", 8, "weekly", True),
    ("B", "b63_126", 8, "weekly", True),
    ("C", "b126_252", 5, "weekly", True),
    ("D", "b126_252", 12, "weekly", True),
    ("E", "b126_252", 8, "biweekly", True),
    ("F", "b126_252", 8, "weekly", False),
    ("G", "b63_126", 5, "weekly", True),
    ("H", "b63_126", 8, "biweekly", True),
    ("I", "b126_252", 12, "biweekly", True),
    ("J", "b63_126", 12, "weekly", True),
]

TRIALS = HERE / "trials.csv"
DEVCSV = HERE / "dev_results.csv"
NOTE = "owner-authorized-budget-expansion"


def cfg_name(cid: str) -> str:
    _, sig, n, cad, f = next(c for c in CONFIGS if c[0] == cid)
    return f"{cid}_{sig}_n{n}_{'wk' if cad == 'weekly' else 'bw'}_f{'ON' if f else 'OFF'}"


def build_panel():
    prices = load_prices(ROOT, UNIVERSE + [HURDLE])
    adj = pd.DataFrame({t: prices[t]["adj_close"].astype(float) for t in UNIVERSE + [HURDLE]})
    adj = adj.sort_index().ffill()
    rets = adj.pct_change()
    r = {L: adj / adj.shift(L) - 1.0 for L in (63, 126, 252)}
    vol63 = rets.rolling(63).std(ddof=1)
    cal = adj.index
    weekly = list(cal.to_series().groupby(cal.to_period("W")).last())
    # common start: first weekly date where every universe ticker + SHV has
    # finite legs (63/126/252) and every universe ticker finite/positive vol63
    need_r = UNIVERSE + [HURDLE]
    first = None
    for d in weekly:
        ok = all(np.isfinite(r[L].loc[d, need_r]).all() for L in (63, 126, 252))
        v = vol63.loc[d, UNIVERSE]
        if ok and np.isfinite(v).all() and (v > 0).all():
            first = d
            break
    decisions = [d for d in weekly if d >= first]
    return prices, r, vol63, decisions, first


def build_schedule(r, vol63, decisions, signal, top_n, cadence, abs_filter):
    legs = LEGS[signal]
    dates = decisions if cadence == "weekly" else decisions[::2]
    schedule = []
    for d in dates:
        ranks = [r[L].loc[d, UNIVERSE].rank(ascending=True, method="average") for L in legs]
        score = sum(ranks) / len(ranks)
        sel = sorted(UNIVERSE, key=lambda t: (-score[t], t))[:top_n]
        iv = 1.0 / vol63.loc[d, sel]
        w = iv / iv.sum()
        if abs_filter:
            keep = [t for t in sel
                    if np.mean([r[L].loc[d, t] - r[L].loc[d, HURDLE] for L in legs]) > 0]
        else:
            keep = sel
        schedule.append((d, {t: float(w[t]) for t in keep}))
    return schedule


def append_trials(rows):
    hdr = not TRIALS.exists()
    pd.DataFrame(rows).to_csv(TRIALS, mode="a", header=hdr, index=False)


def next_trial_id():
    if not TRIALS.exists():
        return 1
    return len(pd.read_csv(TRIALS)) + 1


def run_one(schedule, prices, cost_bps, start, end):
    res = run_ledger_backtest(schedule, prices, cost_bps=cost_bps, cash_ticker=HURDLE,
                              start=start, end=end, benchmarks=())
    return res.stats


def phase_dev():
    prices, r, vol63, decisions, first = build_panel()
    dev_dec = [d for d in decisions if d <= DEV_END]
    print(f"common start (first decision): {first.date()}  |  weekly dev decisions: {len(dev_dec)}")
    window = f"{first.year}-2017_dev"
    tid = next_trial_id()
    out, trows = [], []
    for cid, sig, n, cad, f in CONFIGS:
        sched = build_schedule(r, vol63, decisions, sig, n, cad, f)
        for bps in (10.0, 20.0):
            s = run_one(sched, prices, bps, first, DEV_END)
            out.append({
                "config": cfg_name(cid), "cost_bps": bps,
                "sharpe": round(s["sharpe"], 3), "cagr_pct": round(s["cagr"] * 100, 2),
                "vol_pct": round(s["vol"] * 100, 2), "max_dd_pct": round(s["max_dd"] * 100, 2),
                "ann_turnover_x": round(s["ann_turnover"], 2),
                "ann_cost_drag_bps": round(s["ann_cost_drag"] * 1e4, 1),
                "n_rebalances": s["n_rebalances"],
            })
            trows.append({
                "trial_id": f"S11WB_{tid:03d}", "date": "2026-07-02", "name": cfg_name(cid),
                "engine": "daily_ledger_v1", "window": window,
                "sharpe": round(s["sharpe"], 3), "cagr": round(s["cagr"] * 100, 2),
                "max_dd": round(s["max_dd"] * 100, 2), "n_trials_represented": 1,
                "source": "dev", "notes": f"cost={int(bps)}bps;{NOTE}",
            })
            tid += 1
            print(f"{cfg_name(cid):26s} @{int(bps):2d}bps  Sharpe={s['sharpe']:6.3f}  "
                  f"CAGR={s['cagr'] * 100:6.2f}%  MaxDD={s['max_dd'] * 100:7.2f}%  "
                  f"TO={s['ann_turnover']:5.2f}x/yr  cost={s['ann_cost_drag'] * 1e4:6.1f}bps/yr")
    pd.DataFrame(out).to_csv(DEVCSV, index=False)
    append_trials(trows)
    print(f"\nwrote {DEVCSV} and {TRIALS}")


def phase_final():
    dev = pd.read_csv(DEVCSV)
    at10 = dev[dev["cost_bps"] == 10.0].set_index("config")
    at20 = dev[dev["cost_bps"] == 20.0].set_index("config")
    wname = at10["sharpe"].idxmax()
    s10, s20 = float(at10.loc[wname, "sharpe"]), float(at20.loc[wname, "sharpe"])
    adopted = (s10 >= 0.90) and (s20 >= 0.75)
    print(f"Winner W = {wname}: dev Sharpe {s10:.3f} @10bps, {s20:.3f} @20bps "
          f"-> {'ADOPTED' if adopted else 'KILLED (bar: >=0.90 @10 AND >=0.75 @20)'}")

    cid = wname.split("_")[0]
    _, sig, n, cad, f = next(c for c in CONFIGS if c[0] == cid)
    prices, r, vol63, decisions, first = build_panel()
    sched = build_schedule(r, vol63, decisions, sig, n, cad, f)
    tid = next_trial_id()
    trows = []
    if adopted:
        for bps in (10.0, 20.0):
            s = run_one(sched, prices, bps, VAL_START, None)
            trows.append({
                "trial_id": f"S11WB_{tid:03d}", "date": "2026-07-02", "name": wname,
                "engine": "daily_ledger_v1", "window": "2018-latest_validation",
                "sharpe": round(s["sharpe"], 3), "cagr": round(s["cagr"] * 100, 2),
                "max_dd": round(s["max_dd"] * 100, 2), "n_trials_represented": 1,
                "source": "validation", "notes": f"cost={int(bps)}bps;THE-one-look;{NOTE}",
            })
            tid += 1
            print(f"VALIDATION {wname} @{int(bps)}bps: Sharpe={s['sharpe']:.3f} "
                  f"CAGR={s['cagr'] * 100:.2f}% MaxDD={s['max_dd'] * 100:.2f}% "
                  f"TO={s['ann_turnover']:.2f}x cost={s['ann_cost_drag'] * 1e4:.1f}bps/yr")
    else:
        s = run_one(sched, prices, 0.0, first, DEV_END)
        trows.append({
            "trial_id": f"S11WB_{tid:03d}", "date": "2026-07-02", "name": wname,
            "engine": "daily_ledger_v1", "window": f"{first.year}-2017_dev",
            "sharpe": round(s["sharpe"], 3), "cagr": round(s["cagr"] * 100, 2),
            "max_dd": round(s["max_dd"] * 100, 2), "n_trials_represented": 1,
            "source": "diagnostic", "notes": f"cost=0bps;signal-vs-cost-attribution;{NOTE}",
        })
        print(f"DIAGNOSTIC {wname} @0bps (dev): Sharpe={s['sharpe']:.3f} "
              f"CAGR={s['cagr'] * 100:.2f}% MaxDD={s['max_dd'] * 100:.2f}% "
              f"TO={s['ann_turnover']:.2f}x")
        print("attribution: signal died" if s["sharpe"] < 0.90 else "attribution: costs killed it")
    append_trials(trows)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", choices=["dev", "final"], required=True)
    args = ap.parse_args()
    (phase_dev if args.phase == "dev" else phase_final)()
