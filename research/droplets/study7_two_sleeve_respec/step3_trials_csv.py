"""Regenerate all study-7 runs at full precision and write trials.csv."""
from __future__ import annotations

import csv
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from lib_study7 import (  # noqa: E402
    CAL_TICKERS, CASH, CONFIGS, DEV_END, DEV_START, build_schedule,
    get_prices, run_config, run_ledger_backtest,
)
from strategy.sleeves import tsmom_weights, gem_weights  # noqa: E402

prices = get_prices()
cal_prices = {t: prices[t] for t in CAL_TICKERS}
rows = []


def add(trial_id, name, stats10, stats20, source, notes):
    win = f"{stats10['start'].date()}..{stats10['end'].date()}"
    n20 = (f"20bps: sharpe={stats20['sharpe']:.3f} cagr={stats20['cagr']:.4f} "
           f"dd={stats20['max_dd']:.4f}; " if stats20 else "")
    rows.append(dict(
        trial_id=trial_id, date="2026-07-02", name=name,
        engine="daily_ledger_v1", window=win,
        sharpe=f"{stats10['sharpe']:.4f}", cagr=f"{stats10['cagr']:.4f}",
        max_dd=f"{stats10['max_dd']:.4f}", n_trials_represented=1,
        source=source, notes=(n20 + notes).strip(),
    ))


# diagnostics: existing baselines re-windowed to dev (exempt from budget)
for nm, fn in [("study7_dev_tsmom", lambda p, d: tsmom_weights(p, d)),
               ("study7_dev_gem", lambda p, d: gem_weights(p, d))]:
    sched = build_schedule(cal_prices, DEV_START, DEV_END, fn)
    s = run_ledger_backtest(sched, prices, cost_bps=10.0, cash_ticker=CASH,
                            start=sched[0][0], end=DEV_END, benchmarks=()).stats
    add(nm, nm, s, None, "study7_diagnostic",
        "existing baseline sleeve re-windowed to dev; 10bps only")


def _sma_trend(p, as_of):
    s = p["SPY"]["close"].loc[:as_of].dropna()
    if len(s) < 200:
        return None
    return {"SPY": 1.0} if float(s.iloc[-1]) > float(s.iloc[-200:].mean()) else {"SHY": 1.0}


sched = build_schedule({t: prices[t] for t in ["SPY", "SHY"]}, DEV_START, DEV_END, _sma_trend)
s = run_ledger_backtest(sched, prices, cost_bps=10.0, cash_ticker=CASH,
                        start=sched[0][0], end=DEV_END, benchmarks=()).stats
add("study7_dev_spy_sma200", "study7_dev_spy_sma200", s, None, "study7_diagnostic",
    "S_bar reference for decision rule; 10bps only")

# R0 + the 10 pre-registered configs
all_cfgs = dict(CONFIGS)
all_cfgs["C10"] = dict(rule="T12", weighting="IV", vt=0.12, frac=0.7, gemfb="AGG")
descr = {
    "R0": "reference: current two_sleeve (not in budget)",
    "C10": "adaptive assembly slot per pre-registered rule",
}
for cid, params in all_cfgs.items():
    out = run_config(prices, params, DEV_START, DEV_END)
    tag = "{rule}/{weighting}/vt={vt}/frac={frac}/gemfb={gemfb}".format(**params)
    src = "study7_diagnostic" if cid == "R0" else "study7_prereg"
    add(f"study7_{cid}", f"study7_two_sleeve_{cid}", out[10.0], out[20.0], src,
        f"{tag}; {descr.get(cid, 'pre-registered config')}")

cols = ["trial_id", "date", "name", "engine", "window", "sharpe", "cagr",
        "max_dd", "n_trials_represented", "source", "notes"]
with open(HERE / "trials.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=cols)
    w.writeheader()
    w.writerows(rows)
print(f"wrote {len(rows)} rows to {HERE / 'trials.csv'}")
for r in rows:
    print(f"{r['trial_id']:26s} {r['window']}  sharpe={r['sharpe']}  cagr={r['cagr']}  dd={r['max_dd']}")
