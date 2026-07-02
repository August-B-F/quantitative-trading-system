"""Study 15 — CLS signal-flip study (see HYPOTHESIS.md, committed first).

Compares the frozen blend_126_252 selection computed at close[t] (true)
vs close[t-1] (stale) at every month-end 2005..2026, plus a full-window
ledger bracket (true vs stale schedules) at 10 and 20 bps/side.

Run from the repo root:  py -3 research/droplets/study15_cls_flip/run_study.py
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
from strategy.rotation import (  # noqa: E402
    GATE_TICKER,
    ROTATION_UNIVERSE,
    TOP_N,
    blend_rotation_weights,
    blend_scores,
    gate_risk_off,
    month_end_offset_dates,
)

OUT = Path(__file__).resolve().parent
START, END = "2005-01-01", "2026-06-30"
OFFSETS = (0, 5, 10, 15)          # 0 = primary bar; others = robustness
COSTS = (10.0, 20.0)


def top3_set(prices: dict, as_of: pd.Timestamp) -> frozenset:
    """Exactly the selection blend_rotation_weights makes (pre-gate)."""
    scores = blend_scores(prices, as_of).dropna()
    if scores.empty:
        return frozenset()
    return frozenset(scores.sort_values(ascending=False).head(TOP_N).index)


def fwd_return(adj: pd.DataFrame, w: dict, t0: pd.Timestamp, t1: pd.Timestamp) -> float:
    return float(sum(x * (adj.at[t1, tk] / adj.at[t0, tk] - 1.0) for tk, x in w.items()))


def main() -> None:
    tickers = sorted(set(ROTATION_UNIVERSE) | {GATE_TICKER, "SHV"})
    prices = load_prices(ROOT, tickers)

    # Joint trading calendar (universe + gate ticker), clipped to the window.
    cal = None
    for t in list(ROTATION_UNIVERSE) + [GATE_TICKER]:
        idx = prices[t]["adj_close"].dropna().index
        cal = idx if cal is None else cal.intersection(idx)
    cal = cal[(cal >= pd.Timestamp(START)) & (cal <= pd.Timestamp(END))]

    # Aligned adj_close frame for forward-return arithmetic.
    adj = pd.DataFrame(
        {t: prices[t]["adj_close"] for t in ROTATION_UNIVERSE}
    ).reindex(cal).ffill()

    per_offset: dict[int, dict] = {}
    rows: list[dict] = []
    for off in OFFSETS:
        dates = month_end_offset_dates(cal, off)
        n = n_top3_diff = n_gate_diff = n_comp = 0
        deltas: list[float] = []
        for d in dates:
            pos = cal.get_loc(d)
            if pos == 0:
                continue
            t_prev = cal[pos - 1]
            s_true, s_stale = top3_set(prices, d), top3_set(prices, t_prev)
            g_true, g_stale = gate_risk_off(prices, d), gate_risk_off(prices, t_prev)
            top3_diff = s_true != s_stale
            gate_diff = g_true != g_stale
            comp = gate_diff or ((not g_true) and (not g_stale) and top3_diff)
            n += 1
            n_top3_diff += top3_diff
            n_gate_diff += gate_diff
            n_comp += comp
            delta = np.nan
            if comp:
                nxt = dates[dates > d]
                if len(nxt):
                    w_true = blend_rotation_weights(prices, d)
                    w_stale = blend_rotation_weights(prices, t_prev)
                    delta = (fwd_return(adj, w_true, d, nxt[0])
                             - fwd_return(adj, w_stale, d, nxt[0]))
                    deltas.append(delta)
            if off == 0:
                rows.append({
                    "date": d.date(), "prev": t_prev.date(),
                    "top3_true": "|".join(sorted(s_true)),
                    "top3_stale": "|".join(sorted(s_stale)),
                    "gate_true": g_true, "gate_stale": g_stale,
                    "top3_differs": top3_diff, "gate_differs": gate_diff,
                    "composition_flip": comp, "fwd1m_true_minus_stale": delta,
                })
        arr = np.array(deltas, dtype=float)
        t_stat = (float(arr.mean() / arr.std(ddof=1) * np.sqrt(len(arr)))
                  if len(arr) > 1 and arr.std(ddof=1) > 0 else float("nan"))
        per_offset[off] = {
            "n_month_ends": n,
            "top3_set_identical_pct": round(100 * (1 - n_top3_diff / n), 2),
            "top3_set_differs_pct": round(100 * n_top3_diff / n, 2),
            "gate_flips_pct": round(100 * n_gate_diff / n, 2),
            "composition_flips_pct": round(100 * n_comp / n, 2),
            "n_flip_months_with_fwd": len(deltas),
            "flip_cost_fwd1m_mean_bps": round(1e4 * float(arr.mean()), 1) if len(arr) else None,
            "flip_cost_fwd1m_median_bps": round(1e4 * float(np.median(arr)), 1) if len(arr) else None,
            "flip_cost_t_stat": round(t_stat, 2) if np.isfinite(t_stat) else None,
            "annualized_stale_drag_bps": (
                round(1e4 * float(arr.mean()) * (n_comp / n) * 12, 1) if len(arr) else 0.0
            ),
        }

    pd.DataFrame(rows).to_csv(OUT / "per_monthend_flips_offset0.csv", index=False)

    # ---- ledger bracket: true vs one-day-stale signals, same decision dates
    me = month_end_offset_dates(cal, 0)
    sched_true, sched_stale = [], []
    for d in me:
        pos = cal.get_loc(d)
        if pos == 0:
            continue
        sched_true.append((d, blend_rotation_weights(prices, d)))
        sched_stale.append((d, blend_rotation_weights(prices, cal[pos - 1])))

    ledger = {}
    for cost in COSTS:
        for name, sched in (("true", sched_true), ("stale", sched_stale)):
            r = run_ledger_backtest(sched, prices, cost_bps=cost, cash_ticker="SHV",
                                    start=START, end=END, benchmarks=())
            ledger[f"{name}_{int(cost)}bps"] = {
                k: (round(v, 4) if isinstance(v, float) else str(v))
                for k, v in r.stats.items()
            }
    for cost in COSTS:
        tkey, skey = f"true_{int(cost)}bps", f"stale_{int(cost)}bps"
        ledger[f"delta_{int(cost)}bps"] = {
            "sharpe_true_minus_stale": round(
                ledger[tkey]["sharpe"] - ledger[skey]["sharpe"], 4),
            "cagr_true_minus_stale_bps_yr": round(
                1e4 * (ledger[tkey]["cagr"] - ledger[skey]["cagr"]), 1),
        }

    bar = per_offset[0]
    verdict = (bar["top3_set_identical_pct"] >= 90.0
               and bar["gate_flips_pct"] <= 2.0)
    results = {
        "study": "study15_cls_flip",
        "date": "2026-07-02",
        "window": f"{START}..{END}",
        "per_offset_flip_stats": per_offset,
        "ledger_bracket_full_window": ledger,
        "pre_registered_bar": ("top3 set identical >= 90% AND gate flips <= 2% "
                               "of month-ends (offset 0)"),
        "bar_passed": bool(verdict),
        "note": ("t-1-vs-t flips OVERSTATE the real 15:45-vs-close flip risk "
                 "(15 min of drift is a fraction of a full day's move); all "
                 "rates here are upper bounds."),
    }
    (OUT / "results.json").write_text(json.dumps(results, indent=2))
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
