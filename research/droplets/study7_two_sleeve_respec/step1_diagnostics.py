"""Step 1 — exempt engineering diagnostics on the dev window.

D0: dev re-window of existing baselines (two_sleeve=R0, tsmom, gem,
    spy_sma200) -> reference Sharpes S_ts, S_bar for the decision rule.
Dw: TSMOM sleeve duration share (IEF+TLT+LQD) at dev month-ends.
Dv: vol-target scale distribution at dev month-ends.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib_study7 import (  # noqa: E402
    CAL_TICKERS, CASH, DEV_END, DEV_START, ROOT, fmt, get_prices,
    run_config, run_ledger_backtest, build_schedule,
)
from strategy.sleeves import tsmom_weights, gem_weights, _vol_target_scale  # noqa: E402

prices = get_prices()
cal_prices = {t: prices[t] for t in CAL_TICKERS}

# ---- D0: reference strategies on dev ----------------------------------------
print("== D0: dev-window references (2005-01-01..2017-12-31 build, 10/20 bps) ==")

# R0 current two_sleeve
r0 = run_config(prices, dict(rule="T12", weighting="IV", vt=0.10, frac=0.6,
                             gemfb="AGG"), DEV_START, DEV_END)
for bps, s in r0.items():
    print(f"R0 two_sleeve  {bps:4.0f}bps  {s['start'].date()}..{s['end'].date()}  {fmt(s)}")

# tsmom alone / gem alone (existing sleeves, re-windowed)
for name, fn in [("tsmom", lambda p, d: tsmom_weights(p, d)),
                 ("gem", lambda p, d: gem_weights(p, d))]:
    sched = build_schedule(cal_prices, DEV_START, DEV_END, fn)
    res = run_ledger_backtest(sched, prices, cost_bps=10.0, cash_ticker=CASH,
                              start=sched[0][0], end=DEV_END, benchmarks=())
    s = res.stats
    print(f"{name:13s}   10bps  {s['start'].date()}..{s['end'].date()}  {fmt(s)}")

# spy_sma200 (exact rules of scripts/run_baselines.py)
def _sma_trend(p, as_of):
    s = p["SPY"]["close"].loc[:as_of].dropna()
    if len(s) < 200:
        return None
    return {"SPY": 1.0} if float(s.iloc[-1]) > float(s.iloc[-200:].mean()) else {"SHY": 1.0}

sma_prices = {t: prices[t] for t in ["SPY", "SHY"]}
sched = build_schedule(sma_prices, DEV_START, DEV_END, _sma_trend)
res = run_ledger_backtest(sched, prices, cost_bps=10.0, cash_ticker=CASH,
                          start=sched[0][0], end=DEV_END, benchmarks=())
s = res.stats
print(f"spy_sma200      10bps  {s['start'].date()}..{s['end'].date()}  {fmt(s)}")

# ---- Dw / Dv: sleeve composition and vol-target scale ------------------------
print("\n== Dw/Dv: TSMOM sleeve composition & vol-target scale at dev month-ends ==")
cal = None
for df in cal_prices.values():
    cal = df.index if cal is None else cal.intersection(df.index)
cal = cal[(cal >= pd.Timestamp(DEV_START)) & (cal <= pd.Timestamp(DEV_END))]
month_ends = cal.to_series().groupby(cal.to_period("M")).last()

rows = []
for d in month_ends:
    d = pd.Timestamp(d)
    ts = tsmom_weights(prices, d)
    gem = gem_weights(prices, d)
    if gem is None:
        continue
    dur = sum(ts.get(t, 0.0) for t in ("IEF", "TLT", "LQD"))
    cashw = ts.get(CASH, 0.0)
    combined = {}
    for t, w in ts.items():
        combined[t] = combined.get(t, 0.0) + 0.6 * w
    for t, w in gem.items():
        combined[t] = combined.get(t, 0.0) + 0.4 * w
    scale = _vol_target_scale(prices, d, combined, 0.10, 63)
    rows.append((d, dur, cashw, scale))

df = pd.DataFrame(rows, columns=["date", "dur_share", "cash_share", "vt_scale"]).set_index("date")
inv = df[df.cash_share < 1.0]
print(f"month-ends: {len(df)}; sleeve fully in SHV: {(df.cash_share >= 1.0).sum()}")
print(f"duration share of TSMOM sleeve (when invested): mean {inv.dur_share.mean():.2%}, "
      f"median {inv.dur_share.median():.2%}, p90 {inv.dur_share.quantile(0.9):.2%}")
print(f"vol-target scale: mean {df.vt_scale.mean():.3f}, median {df.vt_scale.median():.3f}, "
      f"share of months binding (<1): {(df.vt_scale < 0.999).mean():.1%}, "
      f"p10 {df.vt_scale.quantile(0.10):.3f}")
by_year = df.groupby(df.index.year).agg(dur=("dur_share", "mean"), scale=("vt_scale", "mean"))
print("\nper-year means:")
print(by_year.to_string(float_format=lambda x: f"{x:.2f}"))
