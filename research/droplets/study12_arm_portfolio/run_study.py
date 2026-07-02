"""STUDY 12 — Portfolio of arms. Runs exactly what HYPOTHESIS.md pre-declares.

Arms: BLEND (blend_126_252, single-tranche month-end), GEM, SMA (SPY/SMA200).
Books: EW (1/3 each), IVOL (inverse dev-window NAV vol), CONV (50/25/25).
Engine: src/backtest/ledger.py at 10 and 20 bps/side, cash SHV.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from backtest.ledger import load_prices, run_ledger_backtest  # noqa: E402
from strategy.rotation import blend_rotation_weights  # noqa: E402
from strategy.sleeves import gem_weights  # noqa: E402

OUT = Path(__file__).resolve().parent
TICKERS = ["SOXX", "QQQ", "XLK", "VGT", "IGV", "XLE", "GLD", "SHY",
           "SPY", "EFA", "AGG", "SHV"]
CASH = "SHV"
DEV_END = pd.Timestamp("2017-12-31")
VAL_START = pd.Timestamp("2018-01-01")
COSTS = (10.0, 20.0)


def sma_weights(prices: dict, as_of: pd.Timestamp):
    """Verbatim scripts/run_baselines.py::_sma_trend_weights."""
    s = prices["SPY"]["close"].loc[:as_of].dropna()
    if len(s) < 200:
        return None
    sma = float(s.iloc[-200:].mean())
    return {"SPY": 1.0} if float(s.iloc[-1]) > sma else {"SHY": 1.0}


def gem_arm(prices: dict, as_of: pd.Timestamp):
    return gem_weights(prices, as_of)


def blend_arm(prices: dict, as_of: pd.Timestamp):
    return blend_rotation_weights(prices, as_of)


ARMS = {"BLEND": blend_arm, "GEM": gem_arm, "SMA": sma_weights}


def month_ends(cal: pd.DatetimeIndex) -> list[pd.Timestamp]:
    return [pd.Timestamp(d) for d in cal.to_series().groupby(cal.to_period("M")).last()]


def main() -> int:
    prices = load_prices(ROOT, TICKERS)
    cal = None
    for t in TICKERS:
        idx = prices[t]["adj_close"].dropna().index
        cal = idx if cal is None else cal.intersection(idx)
    mes = month_ends(cal)

    # first month-end where ALL arms return valid weights (HYPOTHESIS: expected 2007-01-31)
    start_me = None
    for d in mes:
        if all(fn(prices, d) is not None for fn in ARMS.values()):
            start_me = d
            break
    decisions = [d for d in mes if d >= start_me]
    print(f"common calendar {cal[0].date()}..{cal[-1].date()}; "
          f"first valid decision {start_me.date()}; {len(decisions)} decisions")

    # arm ticker-weight panels (one signal computation per arm per decision)
    arm_w: dict[str, dict[pd.Timestamp, dict]] = {
        a: {d: fn(prices, d) for d in decisions} for a, fn in ARMS.items()
    }
    arm_sched = {a: [(d, w) for d, w in arm_w[a].items()] for a in ARMS}

    results: dict = {"windows": {}}
    navs: dict[tuple, pd.Series] = {}          # (name, cost, window) -> nav
    stats: dict[tuple, dict] = {}

    def run(name, sched, cost, wstart, wend, wlabel):
        res = run_ledger_backtest(sched, prices, cost_bps=cost, cash_ticker=CASH,
                                  start=wstart, end=wend, benchmarks=())
        navs[(name, cost, wlabel)] = res.nav
        s = dict(res.stats)
        s["start"], s["end"] = str(s["start"].date()), str(s["end"].date())
        stats[(name, cost, wlabel)] = s
        print(f"{wlabel:5s} {name:6s} @{cost:.0f}bps  Sharpe={s['sharpe']:.3f} "
              f"CAGR={s['cagr']*100:.2f}% MaxDD={s['max_dd']*100:.2f}% "
              f"turn={s['ann_turnover']:.2f}x cost={s['ann_cost_drag']*1e4:.1f}bps/yr")
        return s

    # ---- arms: dev and full window (arms are published references — exempt) ----
    for a in ARMS:
        for c in COSTS:
            run(a, arm_sched[a], c, start_me, DEV_END, "dev")
            run(a, arm_sched[a], c, start_me, None, "full")

    # ---- IVOL weights from dev arm NAV vols at 10 bps (frozen ex-ante rule) ----
    dev_vol = {a: stats[(a, 10.0, "dev")]["vol"] for a in ARMS}
    inv = {a: 1.0 / v for a, v in dev_vol.items()}
    tot = sum(inv.values())
    ivol_frac = {a: iv / tot for a, iv in inv.items()}
    print("IVOL fractions:", {a: round(f, 4) for a, f in ivol_frac.items()})

    BOOKS = {
        "EW": {a: 1.0 / 3.0 for a in ARMS},
        "IVOL": ivol_frac,
        "CONV": {"BLEND": 0.50, "GEM": 0.25, "SMA": 0.25},
    }

    def book_schedule(fracs):
        sched = []
        for d in decisions:
            w: dict[str, float] = {}
            for a, f in fracs.items():
                for t, x in arm_w[a][d].items():
                    w[t] = w.get(t, 0.0) + f * x
            sched.append((d, w))
        return sched

    # ---- books: DEV ONLY (validation is one look on FINAL if PASS) ----
    for b, fr in BOOKS.items():
        sched = book_schedule(fr)
        for c in COSTS:
            s = run(b, sched, c, start_me, DEV_END, "dev")
            s["unnetted_cost_drag"] = float(
                sum(fr[a] * stats[(a, c, "dev")]["ann_cost_drag"] for a in ARMS))
            s["arm_fractions"] = {a: round(fr[a], 4) for a in ARMS}

    # ---- correlations (daily and monthly), dev and full, at 10 bps ----
    def corr_block(wlabel):
        rets = pd.DataFrame({a: navs[(a, 10.0, wlabel)].pct_change() for a in ARMS}).dropna()
        mnav = pd.DataFrame({a: navs[(a, 10.0, wlabel)] for a in ARMS})
        mret = mnav.groupby(mnav.index.to_period("M")).last().pct_change().dropna()
        return {"daily": rets.corr().round(3).to_dict(),
                "monthly": mret.corr().round(3).to_dict()}

    results["correlations"] = {w: corr_block(w) for w in ("dev", "full")}
    for w in ("dev", "full"):
        print(f"--- {w} daily corr ---")
        print(pd.DataFrame(results["correlations"][w]["daily"]))
        print(f"--- {w} monthly corr ---")
        print(pd.DataFrame(results["correlations"][w]["monthly"]))

    # ---- decision rule (binding, 10 bps dev; must also hold at 20) ----
    best_arm = max(ARMS, key=lambda a: stats[(a, 10.0, "dev")]["sharpe"])
    final = max(BOOKS, key=lambda b: (stats[(b, 10.0, "dev")]["sharpe"],
                                      stats[(b, 10.0, "dev")]["max_dd"]))
    def cond(c):
        return (stats[(final, c, "dev")]["sharpe"] >= stats[(best_arm, c, "dev")]["sharpe"]
                and stats[(final, c, "dev")]["max_dd"] >= stats[(best_arm, c, "dev")]["max_dd"])
    passed = cond(10.0) and cond(20.0)
    print(f"best_arm={best_arm}  FINAL={final}  PASS={passed}")

    if passed:
        sched = book_schedule(BOOKS[final])
        for c in COSTS:
            run(final, sched, c, VAL_START, None, "val")

    results["ivol_fractions"] = {a: round(f, 4) for a, f in ivol_frac.items()}
    results["best_arm"], results["final"], results["pass"] = best_arm, final, passed
    results["stats"] = {f"{n}|{int(c)}bps|{w}": s for (n, c, w), s in stats.items()}
    (OUT / "results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")

    # NAV export for any downstream checks
    nav_df = pd.DataFrame({f"{n}_{int(c)}_{w}": s for (n, c, w), s in navs.items()})
    nav_df.to_csv(OUT / "navs.csv")
    print("wrote results.json, navs.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
