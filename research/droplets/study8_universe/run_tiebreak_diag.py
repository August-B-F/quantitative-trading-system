"""Study 8 post-hoc DIAGNOSTIC (not pre-registered, no selection rides on it).

While tying U1 out to study4's stored dev result, a fidelity gap surfaced:
study4's harness (pd.Series.nlargest -> keeps first-in-universe-order among
tied blended ranks) and the production module rotation.py
(sort_values(ascending=False).head(3) -> unstable quicksort order among
ties) are two faithful implementations of the same frozen spec text, and
21/143 U1 dev decisions differ — every one an exact tie at the 3rd slot
(blended ranks of 2 legs over 8-10 names are multiples of 0.5; ties are
frequent). U1 dev Sharpe @10bps: 1.005 (study4 order) vs 0.920 (production).

This diagnostic re-runs the SAME frozen chassis on all four universes with
the study4 tie-break, 10 bps, both windows, to check whether the
universe-robustness verdict depends on tie-break order. Logged to
trials.csv as source=tiebreak_diag. Zero parameters change.

  py -3 run_tiebreak_diag.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

DROPLET = Path(__file__).resolve().parent
ROOT = DROPLET.parents[2]
sys.path.insert(0, str(ROOT / "src"))

from backtest.ledger import run_ledger_backtest, load_prices   # noqa: E402
from strategy.sleeves import build_schedule                    # noqa: E402
from strategy.rotation import blend_scores                     # noqa: E402
from run_study import (UNIVERSES, GATE_TICKER, CASH, RISK_OFF, MIN_BARS,     # noqa: E402
                       SMA_N, DEV_END, common_start_ok)

ANN = np.sqrt(252.0)


def make_s4_order_fn(universe: list[str]):
    """Frozen chassis with study4's deterministic tie-break (nlargest,
    first-in-universe-order among ties)."""
    def fn(prices: dict, as_of: pd.Timestamp):
        if not common_start_ok(prices, universe, as_of):
            return None
        spy = prices[GATE_TICKER]["adj_close"].loc[:as_of].dropna()
        if float(spy.iloc[-1]) <= float(spy.iloc[-SMA_N:].mean()):
            return {RISK_OFF: 1.0}
        scores = blend_scores(prices, as_of, universe=universe).dropna()
        if scores.empty:
            return {RISK_OFF: 1.0}
        top = scores.nlargest(3).index.tolist()
        inv = {}
        for t in top:
            s = prices[t]["adj_close"].loc[:as_of].dropna()
            rets = s.iloc[-64:].pct_change().dropna()
            vol = float(rets.std(ddof=1) * ANN)
            if np.isfinite(vol) and vol > 0.0:
                inv[t] = 1.0 / vol
        if not inv:
            return {RISK_OFF: 1.0}
        tot = sum(inv.values())
        return {t: v / tot for t, v in inv.items()}
    return fn


def main() -> None:
    all_tickers = sorted({t for u in UNIVERSES.values() for t in u}
                         | {GATE_TICKER, CASH, RISK_OFF})
    prices = load_prices(ROOT, all_tickers)
    trials_path = DROPLET / "trials.csv"

    rows = []
    n = 0
    for uname, univ in UNIVERSES.items():
        sched_prices = {t: prices[t] for t in dict.fromkeys(univ + [GATE_TICKER])}
        sched = build_schedule(sched_prices, "2005-01-01", None,
                               make_s4_order_fn(univ))
        for window, end in (("dev_to_2017-12-31", DEV_END),
                            ("full_2005_latest", None)):
            n += 1
            res = run_ledger_backtest(sched, prices, cost_bps=10.0,
                                      cash_ticker=CASH, start=None, end=end,
                                      benchmarks=())
            s = res.stats
            rows.append({"universe": uname, "tiebreak": "s4_order",
                         "window": window, "sharpe": s["sharpe"],
                         "cagr": s["cagr"], "max_dd": s["max_dd"],
                         "ann_turnover": s["ann_turnover"]})
            with open(trials_path, "a") as f:
                f.write(f"S8UN_T{n:02d},2026-07-02,{uname}__blend_s4tiebreak,"
                        f"daily_ledger_v1,{window},{s['sharpe']:.3f},"
                        f"{s['cagr']*100:.2f},{s['max_dd']*100:.2f},1,"
                        f"tiebreak_diag,cost=10bps;posthoc-diagnostic;"
                        f"owner-authorized-budget-expansion\n")
            print(f"{uname:15s} s4_order {window:18s} 10bps  "
                  f"Sharpe={s['sharpe']:.3f} CAGR={s['cagr']*100:6.2f}% "
                  f"MaxDD={s['max_dd']*100:6.2f}% to={s['ann_turnover']:.2f}x",
                  flush=True)
    pd.DataFrame(rows).to_csv(DROPLET / "tiebreak_diag.csv", index=False)


if __name__ == "__main__":
    main()
