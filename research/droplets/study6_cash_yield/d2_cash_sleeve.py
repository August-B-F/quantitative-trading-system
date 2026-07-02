"""Droplet 2: cash-sleeve yield — SHY vs SHV vs pure cash (BIL unavailable).

Engineering measurement, full window allowed. 5 schedule configs x 2 cost
levels, all through run_ledger_backtest. Logs rows for trials.csv.
"""
import sys
sys.path.insert(0, "src")

import numpy as np
import pandas as pd

from backtest.ledger import run_ledger_backtest, load_prices
from strategy.sleeves import tsmom_weights, build_schedule

ROOT = "."
CAL_YEARS = 365.25

tickers = ["SPY", "SHY", "SHV", "EFA", "EEM", "IEF", "TLT", "LQD", "GLD", "DBC", "VNQ", "AGG"]
prices = load_prices(ROOT, tickers)

# ---------- per-ETF stats ----------
def etf_stats(t, start=None):
    s = prices[t]["adj_close"].dropna()
    if start:
        s = s.loc[start:]
    yrs = (s.index[-1] - s.index[0]).days / CAL_YEARS
    ann = (s.iloc[-1] / s.iloc[0]) ** (1 / yrs) - 1
    daily = s.pct_change().dropna()
    vol = daily.std(ddof=1) * np.sqrt(252)
    dd = (s / s.cummax() - 1).min()
    return s.index[0].date(), s.index[-1].date(), ann, vol, dd

print("--- per-ETF annualized total return / vol / maxDD (adj_close) ---")
for t in ("SHV", "SHY"):
    print(f"{t} full : start={etf_stats(t)[0]} end={etf_stats(t)[1]} "
          f"ann={etf_stats(t)[2]*100:.3f}%  vol={etf_stats(t)[3]*100:.3f}%  maxDD={etf_stats(t)[4]*100:.3f}%")
    st = etf_stats(t, "2023-07-01")
    print(f"{t} 3y   : ann={st[2]*100:.3f}%  vol={st[3]*100:.3f}%  maxDD={st[4]*100:.3f}%")
    s = prices[t]["adj_close"].dropna()
    y2022 = s.loc["2021-12-25":"2022-12-31"]
    print(f"{t} 2022 : calendar return={(y2022.iloc[-1]/y2022.iloc[0]-1)*100:.3f}%  "
          f"2022 maxDD={(y2022/y2022.cummax()-1).min()*100:.3f}%")

# ---------- spy_sma200 with different parking assets ----------
def sma_gate(park):
    def fn(pr, as_of):
        s = pr["SPY"]["close"].loc[:as_of].dropna()
        if len(s) < 200:
            return None
        sma = float(s.iloc[-200:].mean())
        if float(s.iloc[-1]) > sma:
            return {"SPY": 1.0}
        return {park: 1.0} if park else {}   # {} -> all cash_ticker (pure cash)
    return fn

runs = []
for park, cash_t, label in (("SHY", "SHV", "sma200_park_SHY"),
                            ("SHV", "SHV", "sma200_park_SHV"),
                            (None, "CASH0", "sma200_park_pure_cash")):
    sched = build_schedule(prices, "2005-01-01", None, sma_gate(park))
    for cost in (10.0, 20.0):
        r = run_ledger_backtest(sched, prices, cost_bps=cost, cash_ticker=cash_t,
                                benchmarks=())
        runs.append((label, cost, r))

# fraction of days parked (weights in the parking asset / cash)
r0 = runs[0][2]
spy_w = r0.weights["SPY"]
parked_frac = float((spy_w < 0.5).mean())
print(f"\nSMA gate: parked (not in SPY) {parked_frac*100:.1f}% of days, "
      f"window {r0.stats['start'].date()}..{r0.stats['end'].date()}")

# ---------- tsmom OFF sleeve: SHV (spec) vs SHY ----------
def tsmom_park(park):
    def fn(pr, as_of):
        w = tsmom_weights(pr, as_of)
        if park != "SHV" and "SHV" in w:
            w = {**{k: v for k, v in w.items() if k != "SHV"}, park: w["SHV"]}
        return w
    return fn

for park, label in (("SHV", "tsmom_off_SHV"), ("SHY", "tsmom_off_SHY")):
    sched = build_schedule(prices, "2007-01-01", None, tsmom_park(park))
    for cost in (10.0, 20.0):
        r = run_ledger_backtest(sched, prices, cost_bps=cost, cash_ticker=park,
                                benchmarks=())
        runs.append((label, cost, r))

print("\n--- ledger results ---")
print(f"{'config':26s} {'cost':>4s} {'CAGR':>7s} {'vol':>6s} {'Sharpe':>6s} {'MaxDD':>8s} {'TO/yr':>6s}")
for label, cost, r in runs:
    s = r.stats
    print(f"{label:26s} {cost:4.0f} {s['cagr']*100:7.3f} {s['vol']*100:6.2f} "
          f"{s['sharpe']:6.3f} {s['max_dd']*100:8.2f} {s['ann_turnover']:6.2f}")

# 2022 calendar-year NAV return for the sma variants at 10bps
print("\n--- 2022 calendar-year NAV return (10 bps runs) ---")
for label, cost, r in runs:
    if cost != 10.0:
        continue
    nav = r.nav.loc["2021-12-25":"2022-12-31"]
    if len(nav) > 1:
        print(f"{label:26s} 2022: {(nav.iloc[-1]/nav.iloc[0]-1)*100:7.3f}%")

# trials.csv rows
print("\n--- trials rows ---")
for i, (label, cost, r) in enumerate(runs, 1):
    s = r.stats
    print(f"{label}_{int(cost)}bps,{s['sharpe']:.4f},{s['cagr']:.6f},{s['max_dd']:.4f},"
          f"{s['start'].date()},{s['end'].date()}")
