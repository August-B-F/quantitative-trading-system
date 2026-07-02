"""Study 10 — structural-flow calendar specs. See HYPOTHESIS.md (pre-registered).

Run from repo root: py -3 research/droplets/study10_calendar/run_study10.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from backtest.ledger import (  # noqa: E402
    TRADING_DAYS_PER_YEAR,
    _build_return_frames,
    load_prices,
    run_ledger_backtest,
)

OUT = ROOT / "research" / "droplets" / "study10_calendar"

FULL = ("2005-01-01", "2026-06-30")
HALF1 = ("2005-01-01", "2015-12-31")
HALF2 = ("2016-01-01", "2026-06-30")
WINDOWS = {"full": FULL, "half1_2005_2015": HALF1, "half2_2016_2026": HALF2}

UNSCHEDULED_FOMC = {pd.Timestamp(d) for d in
                    ("2008-01-22", "2008-10-08", "2020-03-03", "2020-03-16")}


def nav_stats(nav: pd.Series) -> dict:
    daily = (nav / nav.shift(1) - 1.0).dropna()
    years = max((nav.index[-1] - nav.index[0]).days / 365.25, 1e-9)
    sd = float(daily.std(ddof=1))
    return {
        "cagr": float((nav.iloc[-1] / nav.iloc[0]) ** (1 / years) - 1),
        "vol": float(sd * np.sqrt(TRADING_DAYS_PER_YEAR)),
        "sharpe": float(daily.mean() / sd * np.sqrt(TRADING_DAYS_PER_YEAR)) if sd > 0 else float("nan"),
        "max_dd": float((nav / nav.cummax() - 1.0).min()),
    }


def per_trade_edge(prices: dict, ticker: str, episodes: list[tuple]) -> dict:
    """Gross fill-to-fill (adj open -> adj open) per-episode returns, bps + t."""
    df = prices[ticker]
    adj_open = (df["open"] * df["adj_close"] / df["close"]).astype(float)
    cal = df.index
    rets = []
    for dec_in, dec_out in episodes:
        i = cal.searchsorted(pd.Timestamp(dec_in), side="right")
        j = cal.searchsorted(pd.Timestamp(dec_out), side="right")
        if j >= len(cal) or i >= len(cal) or j <= i:
            continue
        rets.append(float(adj_open.iloc[j] / adj_open.iloc[i] - 1.0))
    r = np.array(rets)
    return {
        "n": len(r),
        "mean_bps": float(r.mean() * 1e4),
        "t": float(r.mean() / r.std(ddof=1) * np.sqrt(len(r))),
        "hit": float((r > 0).mean()),
    }


def run_schedule_spec(name, schedule, prices, cost_bps, episodes):
    print(f"\n=== {name} @ {cost_bps} bps/side ===")
    rows = []
    for wname, (s, e) in WINDOWS.items():
        res = run_ledger_backtest(schedule, prices, cost_bps=cost_bps,
                                  cash_ticker="SHV", start=s, end=e, benchmarks=())
        gross = run_ledger_backtest(schedule, prices, cost_bps=0.0,
                                    cash_ticker="SHV", start=s, end=e, benchmarks=())
        st, gt = res.stats, gross.stats
        exposure = float((res.weights.drop(columns=["SHV"], errors="ignore").sum(axis=1) > 0.5).mean())
        rows.append({
            "window": wname, "cost_bps": cost_bps,
            "gross_cagr": gt["cagr"], "net_cagr": st["cagr"],
            "gross_sharpe": gt["sharpe"], "net_sharpe": st["sharpe"],
            "net_max_dd": st["max_dd"], "net_vol": st["vol"],
            "exposure": exposure, "cost_drag_bps_yr": st["ann_cost_drag"] * 1e4,
            "n_rebalances": st["n_rebalances"],
        })
        print(f"{wname:18s} grossCAGR={gt['cagr']*100:6.2f}%  netCAGR={st['cagr']*100:6.2f}%  "
              f"grossSh={gt['sharpe']:.3f}  netSh={st['sharpe']:.3f}  MaxDD={st['max_dd']*100:6.2f}%  "
              f"expo={exposure*100:5.1f}%  drag={st['ann_cost_drag']*1e4:5.1f}bps/yr  reb={st['n_rebalances']}")
    edge = per_trade_edge(prices, "SPY", episodes)
    print(f"per-episode gross edge: n={edge['n']}  mean={edge['mean_bps']:.1f} bps  "
          f"t={edge['t']:.2f}  hit={edge['hit']*100:.1f}%")
    return rows, edge


def month_groups(cal: pd.DatetimeIndex):
    s = pd.Series(cal, index=cal)
    return {p: idx.index for p, idx in s.groupby(cal.to_period("M"))}


def tom_schedule_and_episodes(cal: pd.DatetimeIndex):
    groups = month_groups(cal)
    periods = sorted(groups)
    schedule, episodes = [], []
    for k, p in enumerate(periods[:-1]):
        days, nxt = groups[p], groups[periods[k + 1]]
        if len(days) < 4 or len(nxt) < 3:
            continue
        dec_in, dec_out = days[-4], nxt[2]
        schedule += [(dec_in, {"SPY": 1.0}), (dec_out, {})]
        episodes.append((dec_in, dec_out))
    return schedule, episodes


def fomc_schedule_and_episodes(cal: pd.DatetimeIndex, events_path):
    ev = pd.read_parquet(events_path)
    fomc = [d for d in ev[ev["is_fomc_day"] > 0].index
            if d not in UNSCHEDULED_FOMC and d in cal]
    schedule, episodes = [], []
    for d in fomc:
        pos = cal.get_loc(d)
        if pos < 2:
            continue
        dec_in, dec_out = cal[pos - 2], d
        schedule += [(dec_in, {"SPY": 1.0}), (dec_out, {})]
        episodes.append((dec_in, dec_out))
    return schedule, episodes


def overnight_spec(prices):
    _, _, overnight, _ = _build_return_frames(["QQQ"], prices, cash_ticker="QQQ")
    on = overnight["QQQ"].iloc[1:]  # drop the global first row (fillna(0) artifact)
    print("\n=== overnight_qqq ===")
    rows = []
    for cost in (0.0, 1.0, 2.0, 10.0, 20.0):
        per_day = (1.0 - cost / 1e4) ** 2  # buy at close + sell at open, per night
        for wname, (s, e) in WINDOWS.items():
            r = on.loc[s:e]
            nav = (1.0 + r).mul(per_day).cumprod()
            nav = pd.concat([pd.Series([1.0], index=[r.index[0] - pd.Timedelta(days=1)]), nav])
            st = nav_stats(nav)
            rows.append({"window": wname, "cost_bps": cost, "net_cagr": st["cagr"],
                         "net_sharpe": st["sharpe"], "net_max_dd": st["max_dd"],
                         "net_vol": st["vol"], "exposure": 1.0,
                         "n_nights": int(len(r))})
            print(f"cost={cost:4.1f}  {wname:18s} CAGR={st['cagr']*100:6.2f}%  "
                  f"Sh={st['sharpe']:.3f}  MaxDD={st['max_dd']*100:6.2f}%  vol={st['vol']*100:5.2f}%")
    r_full = on.loc[FULL[0]:FULL[1]].iloc[1:]
    edge = {"n": int(len(r_full)), "mean_bps": float(r_full.mean() * 1e4),
            "t": float(r_full.mean() / r_full.std(ddof=1) * np.sqrt(len(r_full))),
            "hit": float((r_full > 0).mean())}
    print(f"per-night gross edge: n={edge['n']}  mean={edge['mean_bps']:.2f} bps  "
          f"t={edge['t']:.2f}  hit={edge['hit']*100:.1f}%")
    return rows, edge


def main():
    prices = load_prices(ROOT, ["SPY", "SHV", "QQQ"])
    spy_cal = prices["SPY"].index

    all_rows = []

    tom_sched, tom_eps = tom_schedule_and_episodes(spy_cal)
    for cost in (2.0, 10.0, 20.0):
        rows, edge = run_schedule_spec("turn_of_month_spy", tom_sched, prices, cost, tom_eps)
        for r in rows:
            r.update({"spec": "turn_of_month_spy"})
        all_rows += rows
    tom_edge = edge  # edge is cost-independent (gross)

    on_rows, on_edge = overnight_spec(prices)
    for r in on_rows:
        r.update({"spec": "overnight_qqq"})
    all_rows += on_rows

    fomc_sched, fomc_eps = fomc_schedule_and_episodes(
        spy_cal, ROOT / "data" / "clean" / "calendar" / "events.parquet")
    for cost in (2.0, 10.0, 20.0):
        rows, edge = run_schedule_spec("pre_fomc_spy", fomc_sched, prices, cost, fomc_eps)
        for r in rows:
            r.update({"spec": "pre_fomc_spy"})
        all_rows += rows
    fomc_edge = edge

    df = pd.DataFrame(all_rows)
    df.to_csv(OUT / "results_raw.csv", index=False)
    print("\nedges:", {"tom": tom_edge, "overnight": on_edge, "fomc": fomc_edge})
    print(f"\nwrote {OUT / 'results_raw.csv'}")


if __name__ == "__main__":
    main()
