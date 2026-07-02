"""Study 8 — Universe legitimacy of blend_126_252 (frozen-rule evaluation).

Applies the adopted blend chassis VERBATIM (production module
src/strategy/rotation.py, zero parameter changes) to four pre-declared
universes and each universe's own SPY/SMA200->SHY gate baseline, per
HYPOTHESIS.md in this folder. Outputs land only in this droplet folder.

  py -3 run_study.py
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
from strategy.rotation import blend_rotation_weights           # noqa: E402

GATE_TICKER = "SPY"
CASH = "SHV"
RISK_OFF = "SHY"
MIN_BARS = 274            # study4 common-start convention (252+21+1)
SMA_N = 200
DEV_END = "2017-12-31"
COSTS = (10.0, 20.0)

UNIVERSES: dict[str, list[str]] = {
    "U1_incumbent":   ["SOXX", "QQQ", "XLK", "VGT", "IGV", "XLE", "GLD", "SHY"],
    "U2_sectors":     ["XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "GLD", "SHY"],
    "U3_cross_asset": ["SPY", "QQQ", "IWM", "EFA", "EEM", "VNQ", "GLD", "DBC", "TLT", "SHY"],
    "U4_no_semis":    ["QQQ", "XLK", "VGT", "IGV", "XLE", "GLD", "SHY"],
}

U1_BUCKETS = {
    "SOXX": "semis", "QQQ": "other_tech", "XLK": "other_tech",
    "VGT": "other_tech", "IGV": "other_tech", "XLE": "energy",
    "GLD": "gold", "SHY": "defensive",
}
U2_BUCKETS = {
    "XLK": "tech", "XLB": "cyclical", "XLE": "cyclical", "XLF": "cyclical",
    "XLI": "cyclical", "XLP": "defensive_sector", "XLU": "defensive_sector",
    "XLV": "defensive_sector", "GLD": "gold", "SHY": "defensive",
}


def common_start_ok(prices: dict, universe: list[str], as_of: pd.Timestamp) -> bool:
    for t in universe + [GATE_TICKER]:
        if len(prices[t]["adj_close"].loc[:as_of].dropna()) < MIN_BARS:
            return False
    return True


def make_blend_fn(universe: list[str]):
    def fn(prices: dict, as_of: pd.Timestamp):
        if not common_start_ok(prices, universe, as_of):
            return None
        return blend_rotation_weights(prices, as_of, universe=universe)
    return fn


def make_gate_fn(universe: list[str]):
    """Gate-only baseline: SPY when adj_close > SMA200 else SHY; same start."""
    def fn(prices: dict, as_of: pd.Timestamp):
        if not common_start_ok(prices, universe, as_of):
            return None
        spy = prices[GATE_TICKER]["adj_close"].loc[:as_of].dropna()
        risk_off = float(spy.iloc[-1]) <= float(spy.iloc[-SMA_N:].mean())
        return {RISK_OFF: 1.0} if risk_off else {GATE_TICKER: 1.0}
    return fn


def main() -> None:
    all_tickers = sorted({t for u in UNIVERSES.values() for t in u}
                         | {GATE_TICKER, CASH, RISK_OFF})
    prices = load_prices(ROOT, all_tickers)

    trials_path = DROPLET / "trials.csv"
    if not trials_path.exists():
        trials_path.write_text(
            "trial_id,date,name,engine,window,sharpe,cagr,max_dd,"
            "n_trials_represented,source,notes\n")

    def log_trial(tid, name, window, s, source, cost):
        with open(trials_path, "a") as f:
            f.write(
                f"{tid},2026-07-02,{name},daily_ledger_v1,{window},"
                f"{s['sharpe']:.3f},{s['cagr']*100:.2f},{s['max_dd']*100:.2f},"
                f"1,{source},cost={int(cost)}bps;frozen-rule-eval;"
                f"owner-authorized-budget-expansion\n")

    rows = []
    schedules_full: dict[str, list] = {}
    weights_full_10: dict[str, pd.DataFrame] = {}
    n = 0
    for uname, univ in UNIVERSES.items():
        sched_prices = {t: prices[t] for t in dict.fromkeys(univ + [GATE_TICKER])}
        for kind, fn in (("blend", make_blend_fn(univ)), ("gate_baseline", make_gate_fn(univ))):
            sched = build_schedule(sched_prices, "2005-01-01", None, fn)
            if kind == "blend":
                schedules_full[uname] = sched
            for window, end in (("dev_to_2017-12-31", DEV_END), ("full_2005_latest", None)):
                for cost in COSTS:
                    n += 1
                    res = run_ledger_backtest(
                        sched, prices, cost_bps=cost, cash_ticker=CASH,
                        start=None, end=end, benchmarks=())
                    s = res.stats
                    rows.append({
                        "universe": uname, "kind": kind, "window": window,
                        "cost_bps": cost, "start": s["start"].date(),
                        "end": s["end"].date(), "sharpe": s["sharpe"],
                        "cagr": s["cagr"], "vol": s["vol"], "max_dd": s["max_dd"],
                        "ann_turnover": s["ann_turnover"],
                        "ann_cost_drag_bps": s["ann_cost_drag"] * 1e4,
                        "n_rebalances": s["n_rebalances"],
                    })
                    log_trial(f"S8UN_{n:03d}", f"{uname}__{kind}", window, s,
                              "frozen_eval", cost)
                    if kind == "blend" and window == "full_2005_latest" and cost == 10.0:
                        weights_full_10[uname] = res.weights
                    print(f"{uname:15s} {kind:14s} {window:18s} {int(cost):2d}bps  "
                          f"{s['start'].date()}..{s['end'].date()}  "
                          f"Sharpe={s['sharpe']:.3f} CAGR={s['cagr']*100:6.2f}% "
                          f"MaxDD={s['max_dd']*100:6.2f}% vol={s['vol']*100:5.2f}% "
                          f"to={s['ann_turnover']:.2f}x", flush=True)

    df = pd.DataFrame(rows)
    df.to_csv(DROPLET / "results.csv", index=False)

    # ---- decomposition (pre-declared diagnostics) ---------------------------
    for uname, buckets in (("U1_incumbent", U1_BUCKETS), ("U2_sectors", U2_BUCKETS)):
        sched = schedules_full[uname]
        risk_off = [w for _, w in sched if w == {RISK_OFF: 1.0}]
        risk_on = [w for _, w in sched if w != {RISK_OFF: 1.0}]
        univ = UNIVERSES[uname]
        sel = {t: np.mean([t in w for w in risk_on]) for t in univ}
        avgw = {t: np.mean([w.get(t, 0.0) for w in risk_on]) for t in univ}
        daily = weights_full_10[uname].mean()
        dec = pd.DataFrame({"sel_freq_risk_on": sel, "avg_target_w_risk_on": avgw})
        dec["avg_daily_ledger_w"] = daily.reindex(dec.index).fillna(0.0)
        dec["bucket"] = pd.Series(buckets)
        dec.loc["__risk_off_months__", "sel_freq_risk_on"] = (
            len(risk_off) / max(len(sched), 1))
        dec.to_csv(DROPLET / f"decomposition_{uname}.csv")
        print(f"\n{uname} decomposition (full-window schedule, 10bps ledger):")
        print(dec.round(4).to_string())
        bt = dec.dropna(subset=["bucket"]).groupby("bucket")[
            ["avg_target_w_risk_on", "avg_daily_ledger_w"]].sum()
        print("by bucket:\n", bt.round(4).to_string())

    print(f"\nwrote {trials_path} ({n} strategy/baseline runs)")


if __name__ == "__main__":
    main()
