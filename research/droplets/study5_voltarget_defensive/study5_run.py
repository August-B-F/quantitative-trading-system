"""STUDY 5 runner — vol targeting + defensive menu overlays on the untuned
63d top-3 inverse-vol rotation with SPY SMA200 gate.

Stages (run separately, per the pre-registered plan in HYPOTHESIS.md):
  --stage dev_ab                       base + A1..A3 + B1..B3 on DEV, 10 & 20 bps
  --stage dev_c  --target T --def D    C1 (combined) on DEV
  --stage validation --target T --def D   ONE look: final pick + base, 2018+
All signals use adj_close data strictly <= decision date. Fills/costs via
src/backtest/ledger.py (daily_ledger_v1).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(r"c:/Users/august/Documents/GitHub/quantitative-trading-system")
sys.path.insert(0, str(REPO / "src"))

from backtest.ledger import run_ledger_backtest, load_prices  # noqa: E402
from strategy.sleeves import _vol_target_scale  # noqa: E402

DROPLET = REPO / "research" / "droplets" / "study5_voltarget_defensive"

RISK = ["SOXX", "QQQ", "XLK", "VGT", "IGV", "XLE", "GLD"]
PARK_BASE = "SHY"
DEFENSIVE_MENU = ["SHY", "IEF", "GLD"]
ALL_TICKERS = sorted(set(RISK) | {"SHY", "IEF", "SHV", "SPY", "AGG"})

DEV_END = pd.Timestamp("2017-12-31")
VAL_START = pd.Timestamp("2018-01-01")
TDY = 252


def _upto(prices: dict, t: str, as_of: pd.Timestamp) -> pd.Series:
    return prices[t]["adj_close"].loc[:as_of].dropna()


def _ret(s: pd.Series, lookback: int) -> float:
    return float(s.iloc[-1] / s.iloc[-1 - lookback] - 1.0)


def weights_for(
    prices: dict,
    as_of: pd.Timestamp,
    vol_target: float | None = None,
    defensive: str = "SHY",
) -> dict[str, float] | None:
    """Base rule + optional overlays. None while history is insufficient."""
    as_of = pd.Timestamp(as_of)
    # shared history gate so every config trades the same decision calendar
    for t in set(RISK) | set(DEFENSIVE_MENU):
        if len(_upto(prices, t, as_of)) < 127:
            return None
    spy = _upto(prices, "SPY", as_of)
    if len(spy) < 200:
        return None

    risk_on = float(spy.iloc[-1]) > float(spy.iloc[-200:].mean())
    if risk_on:
        scores = {t: _ret(_upto(prices, t, as_of), 63) for t in RISK}
        top3 = sorted(scores, key=scores.get, reverse=True)[:3]
        inv = {}
        for t in top3:
            s = _upto(prices, t, as_of)
            daily = s.iloc[-64:].pct_change().dropna()
            v = float(daily.std(ddof=1) * np.sqrt(TDY))
            inv[t] = 1.0 / v if np.isfinite(v) and v > 0 else 0.0
        tot = sum(inv.values())
        w = {t: x / tot for t, x in inv.items()} if tot > 0 else {t: 1 / 3 for t in top3}
    else:
        if defensive == "SHY":
            w = {"SHY": 1.0}
        elif defensive == "TREND":
            tr = {t: _ret(_upto(prices, t, as_of), 126) for t in DEFENSIVE_MENU}
            w = {max(tr, key=tr.get): 1.0}
        elif defensive == "5050":
            w = {"IEF": 0.5, "GLD": 0.5}
        elif defensive == "SHV":
            w = {"SHV": 1.0}
        else:
            raise ValueError(defensive)

    if vol_target is not None:
        s = _vol_target_scale(prices, as_of, w, vol_target, 63)
        w = {t: x * s for t, x in w.items()}
    return w


def build_schedule(prices, end, vol_target=None, defensive="SHY"):
    cal = prices["SPY"].index
    cal = cal[(cal >= pd.Timestamp("2005-01-01")) & (cal <= end)]
    month_ends = cal.to_series().groupby(cal.to_period("M")).last()
    sched, diag = [], []
    for d in month_ends:
        d = pd.Timestamp(d)
        w = weights_for(prices, d, vol_target=vol_target, defensive=defensive)
        if w is None:
            continue
        sched.append((d, w))
        diag.append({"date": d, "gross": sum(w.values()), "names": ",".join(sorted(w))})
    return sched, pd.DataFrame(diag)


def yearly_returns(nav: pd.Series) -> pd.Series:
    y = nav.groupby(nav.index.year).last()
    first = nav.iloc[0]
    prev = y.shift(1)
    prev.iloc[0] = first
    return (y / prev - 1.0).round(4)


def run_config(prices, name, vol_target, defensive, start, end):
    sched, diag = build_schedule(prices, end if end is not None else prices["SPY"].index.max(),
                                 vol_target=vol_target, defensive=defensive)
    rows = {}
    nav10 = None
    for bps in (10.0, 20.0):
        res = run_ledger_backtest(sched, prices, cost_bps=bps, cash_ticker="SHV",
                                  start=start, end=end, benchmarks=())
        st = res.stats
        rows[bps] = {
            "name": name, "cost_bps": bps,
            "sharpe": round(st["sharpe"], 4), "cagr": round(st["cagr"], 4),
            "vol": round(st["vol"], 4), "max_dd": round(st["max_dd"], 4),
            "ann_turnover": round(st["ann_turnover"], 2),
            "ann_cost_drag_bps": round(st["ann_cost_drag"] * 1e4, 1),
            "n_rebalances": st["n_rebalances"],
            "start": str(st["start"].date()), "end": str(st["end"].date()),
        }
        if bps == 10.0:
            nav10 = res.nav
    avg_gross = float(diag["gross"].mean())
    # risk-on always holds exactly 3 names; risk-off holds 1 (or 2 for 50/50)
    frac_riskoff = float((diag["names"].str.count(",") < 2).mean())
    return rows, nav10, {"avg_gross": avg_gross, "frac_riskoff_decisions": frac_riskoff}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", required=True, choices=["dev_ab", "dev_c", "validation"])
    ap.add_argument("--target", type=float, default=None, help="vol target, e.g. 0.12")
    ap.add_argument("--defensive", default="SHY", choices=["SHY", "TREND", "5050", "SHV"])
    args = ap.parse_args()

    prices = load_prices(REPO, ALL_TICKERS)

    if args.stage == "dev_ab":
        configs = [
            ("base", None, "SHY"),
            ("A1_vt10", 0.10, "SHY"),
            ("A2_vt12", 0.12, "SHY"),
            ("A3_vt15", 0.15, "SHY"),
            ("B1_trend_menu", None, "TREND"),
            ("B2_ief_gld_5050", None, "5050"),
            ("B3_shv", None, "SHV"),
        ]
        start, end, tag = None, DEV_END, "dev"
    elif args.stage == "dev_c":
        configs = [(f"C1_vt{int(args.target*100)}_{args.defensive}", args.target, args.defensive)]
        start, end, tag = None, DEV_END, "dev"
    else:
        configs = [
            (f"FINAL_vt{int(args.target*100) if args.target else 'none'}_{args.defensive}",
             args.target, args.defensive),
            ("base", None, "SHY"),
        ]
        start, end, tag = VAL_START, None, "validation"

    all_rows, extras, yearly = [], {}, {}
    for name, vt, dfn in configs:
        rows, nav10, ex = run_config(prices, name, vt, dfn, start, end)
        all_rows += [rows[10.0], rows[20.0]]
        extras[name] = ex
        yearly[name] = yearly_returns(nav10).to_dict()
        print(f"\n== {name} ({tag}) ==")
        for bps in (10.0, 20.0):
            r = rows[bps]
            print(f"  {int(bps)}bps: Sharpe={r['sharpe']:.3f} CAGR={r['cagr']*100:6.2f}% "
                  f"vol={r['vol']*100:5.2f}% MaxDD={r['max_dd']*100:6.2f}% "
                  f"TO={r['ann_turnover']:.1f}x drag={r['ann_cost_drag_bps']:.0f}bps "
                  f"[{r['start']}..{r['end']}]")
        print(f"  avg_gross_exposure={ex['avg_gross']:.3f} "
              f"frac_riskoff_decisions={ex['frac_riskoff_decisions']:.3f}")

    out = DROPLET / f"results_{args.stage}.json"
    with open(out, "w") as f:
        json.dump({"rows": all_rows, "extras": extras, "yearly": yearly}, f, indent=2, default=str)
    pd.DataFrame(all_rows).to_csv(DROPLET / f"results_{args.stage}.csv", index=False)
    print(f"\nsaved -> {out}")


if __name__ == "__main__":
    main()
