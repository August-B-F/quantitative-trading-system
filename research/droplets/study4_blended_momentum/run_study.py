"""Study 4 — Blended Momentum Ensemble. Runs the pre-registered configs of
HYPOTHESIS.md through the daily-ledger engine.

Stages (run separately so the validation look is a deliberate act):
  py -3 run_study.py dev
  py -3 run_study.py cliff <winner_id>
  py -3 run_study.py validation <adopted_id>

All outputs land in this droplet folder. Never touches production files.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

DROPLET = Path(__file__).resolve().parent
ROOT = DROPLET.parents[2]          # repo root
sys.path.insert(0, str(ROOT / "src"))

from backtest.ledger import run_ledger_backtest, load_prices  # noqa: E402
from strategy.sleeves import build_schedule                   # noqa: E402

UNIVERSE = ["SOXX", "QQQ", "XLK", "VGT", "IGV", "XLE", "GLD", "SHY"]
GATE_TICKER = "SPY"
CASH = "SHV"
MIN_BARS = 274            # 252 + 21 + 1 — common start across all configs
SMA_N = 200
VOL_SIZE_N = 63           # inverse-vol sizing lookback (fixed chassis)
ANN = np.sqrt(252.0)

DEV_END = "2017-12-31"
VAL_START = "2018-01-01"

# ---- frozen config table (HYPOTHESIS.md) ------------------------------------
# legs: (L, skip, voladj)
CONFIGS: dict[str, list[tuple[int, int, bool]]] = {
    "a_pin_63":                  [(63, 0, False)],
    "b_pin_252_21":              [(252, 21, False)],
    "c_blend_63_126_252":        [(63, 0, False), (126, 0, False), (252, 0, False)],
    "d_blend_21_63_126_252":     [(21, 0, False), (63, 0, False), (126, 0, False), (252, 0, False)],
    "e_voladj_63":               [(63, 0, True)],
    "f_voladj_blend_63_126_252": [(63, 0, True), (126, 0, True), (252, 0, True)],
    "g_blend_skip252":           [(63, 0, False), (126, 0, False), (252, 21, False)],
    "h_voladj_blend_skip252":    [(63, 0, True), (126, 0, True), (252, 21, True)],
    "i_blend_126_252":           [(126, 0, False), (252, 0, False)],
}

# cliff perturbations: one leg at a time, +/-20%, rounded to int
def perturb(L: int, pct: float) -> int:
    return int(round(L * (1.0 + pct)))


def leg_score(s: pd.Series, L: int, skip: int, voladj: bool) -> float | None:
    """Score for one leg on adj_close series s (data <= as_of already)."""
    if len(s) < L + 1:
        return None
    r = float(s.iloc[-1 - skip] / s.iloc[-1 - L] - 1.0)
    if voladj:
        window = s.iloc[-(L + 1):]              # L+1 prices -> L daily returns
        rets = window.pct_change().dropna()
        if skip > 0:
            rets = rets.iloc[: len(rets) - skip]
        vol = float(rets.std(ddof=1) * ANN)
        if not np.isfinite(vol) or vol <= 0.0:
            return None
        r = r / vol
    return r


def make_weight_fn(legs: list[tuple[int, int, bool]]):
    def fn(prices: dict, as_of: pd.Timestamp):
        # common start gate: every universe ticker + SPY has >= MIN_BARS bars
        series: dict[str, pd.Series] = {}
        for t in UNIVERSE + [GATE_TICKER]:
            s = prices[t]["adj_close"].loc[:as_of].dropna()
            if len(s) < MIN_BARS:
                return None
            series[t] = s
        # SMA200 gate on SPY
        spy = series[GATE_TICKER]
        if float(spy.iloc[-1]) <= float(spy.iloc[-SMA_N:].mean()):
            return {"SHY": 1.0}
        # blended rank score
        leg_rows = []
        for (L, skip, va) in legs:
            scores = {}
            for t in UNIVERSE:
                sc = leg_score(series[t], L, skip, va)
                if sc is not None:
                    scores[t] = sc
            leg_rows.append(pd.Series(scores).rank(ascending=True, method="average"))
        blended = pd.DataFrame(leg_rows).mean(axis=0).dropna()
        top3 = blended.nlargest(3).index.tolist()
        # inverse 63d vol weights
        inv = {}
        for t in top3:
            rets = series[t].iloc[-(VOL_SIZE_N + 1):].pct_change().dropna()
            vol = float(rets.std(ddof=1) * ANN)
            if np.isfinite(vol) and vol > 0.0:
                inv[t] = 1.0 / vol
        if not inv:
            return {"SHY": 1.0}
        tot = sum(inv.values())
        return {t: v / tot for t, v in inv.items()}
    return fn


def yearly_returns(nav: pd.Series) -> pd.Series:
    """Calendar-year total returns from the NAV path."""
    yr = nav.groupby(nav.index.year).last()
    prev = yr.shift(1)
    prev.iloc[0] = nav.iloc[0]
    return yr / prev - 1.0


def sharpe_excl_year(nav: pd.Series, year: int) -> float:
    d = (nav / nav.shift(1) - 1.0).dropna()
    d = d[d.index.year != year]
    sd = d.std(ddof=1)
    return float(d.mean() / sd * ANN) if sd > 0 else float("nan")


def run_config(name, legs, prices, sched_prices, cost_bps, start, end):
    sched = build_schedule(sched_prices, "2005-01-01", None, make_weight_fn(legs))
    res = run_ledger_backtest(sched, prices, cost_bps=cost_bps, cash_ticker=CASH,
                              start=start, end=end, benchmarks=())
    return res


def main():
    stage = sys.argv[1] if len(sys.argv) > 1 else "dev"
    prices = load_prices(ROOT, UNIVERSE + [GATE_TICKER, CASH])
    sched_prices = {t: prices[t] for t in UNIVERSE + [GATE_TICKER]}  # SHV excluded from calendar (lists 2007)

    trials_path = DROPLET / "trials.csv"
    if not trials_path.exists():
        trials_path.write_text("trial_id,date,name,engine,window,sharpe,cagr,max_dd,n_trials_represented,source,notes\n")

    def log_trial(tid, name, window, stats, source, notes):
        with open(trials_path, "a") as f:
            f.write(f"{tid},2026-07-02,{name},daily_ledger_v1,{window},"
                    f"{stats['sharpe']:.3f},{stats['cagr']*100:.2f},{stats['max_dd']*100:.2f},"
                    f"1,{source},{notes}\n")

    if stage == "dev":
        rows, navs10 = [], {}
        n = 0
        for name, legs in CONFIGS.items():
            for cost in (10.0, 20.0):
                n += 1
                res = run_config(name, legs, prices, sched_prices, cost, None, DEV_END)
                s = res.stats
                rows.append({"config": name, "cost_bps": cost, "sharpe": s["sharpe"],
                             "cagr": s["cagr"], "vol": s["vol"], "max_dd": s["max_dd"],
                             "ann_turnover": s["ann_turnover"],
                             "start": s["start"].date(), "end": s["end"].date()})
                log_trial(f"S4BM_{n:03d}", name, "2006-2017_dev", s, "dev", f"cost={int(cost)}bps")
                if cost == 10.0:
                    navs10[name] = res.nav
        df = pd.DataFrame(rows)
        df.to_csv(DROPLET / "dev_results.csv", index=False)
        print(df.pivot(index="config", columns="cost_bps",
                       values=["sharpe", "cagr", "max_dd", "ann_turnover"]).round(3).to_string())

        # year-by-year (10 bps) + LOYO Sharpe table
        yr = pd.DataFrame({k: yearly_returns(v) for k, v in navs10.items()})
        yr.to_csv(DROPLET / "dev_yearly_returns_10bps.csv")
        print("\nYearly returns (10 bps):\n", (yr * 100).round(1).to_string())
        years = sorted({y for y in navs10["a_pin_63"].index.year.unique()})
        loyo = pd.DataFrame({k: {y: sharpe_excl_year(v, y) for y in years}
                             for k, v in navs10.items()})
        loyo.to_csv(DROPLET / "dev_loyo_sharpe_10bps.csv")
        print("\nLeave-one-year-out Sharpe (10 bps):\n", loyo.round(3).to_string())

    elif stage == "cliff":
        winner = sys.argv[2]
        legs = CONFIGS[winner]
        runs = [("base", legs)]
        for li, (L, skip, va) in enumerate(legs):
            for pct in (-0.2, +0.2):
                newlegs = list(legs)
                newlegs[li] = (perturb(L, pct), skip, va)
                runs.append((f"leg{li}_{L}to{perturb(L, pct)}", newlegs))
        # incumbent contrast
        if winner != "a_pin_63":
            runs.append(("incumbent_base", CONFIGS["a_pin_63"]))
            for pct in (-0.2, +0.2):
                runs.append((f"incumbent_63to{perturb(63, pct)}", [(perturb(63, pct), 0, False)]))
        rows = []
        for i, (tag, lg) in enumerate(runs):
            res = run_config(tag, lg, prices, sched_prices, 10.0, None, DEV_END)
            s = res.stats
            rows.append({"run": tag, "legs": str(lg), "sharpe": s["sharpe"],
                         "cagr": s["cagr"], "max_dd": s["max_dd"]})
            log_trial(f"S4BM_C{i:02d}", f"{winner}__{tag}", "2006-2017_dev", s,
                      "cliff_test", "cost=10bps;robustness-not-candidate")
        df = pd.DataFrame(rows)
        df.to_csv(DROPLET / "cliff_results.csv", index=False)
        print(df.round(3).to_string())

    elif stage == "validation":
        adopted = sys.argv[2]
        legs = CONFIGS[adopted]
        for i, cost in enumerate((10.0, 20.0)):
            res = run_config(adopted, legs, prices, sched_prices, cost, VAL_START, None)
            s = res.stats
            log_trial(f"S4BM_V{i:02d}", adopted, "2018-latest_validation", s,
                      "validation", f"cost={int(cost)}bps;THE-one-look")
            print(f"VALIDATION {adopted} @ {int(cost)}bps: {s['start'].date()}..{s['end'].date()} "
                  f"Sharpe={s['sharpe']:.3f} CAGR={s['cagr']*100:.2f}% MaxDD={s['max_dd']*100:.2f}% "
                  f"vol={s['vol']*100:.2f}% turnover={s['ann_turnover']:.2f}x/yr")
            if cost == 10.0:
                yr = yearly_returns(res.nav)
                print("validation yearly returns (10bps):")
                print((yr * 100).round(1).to_string())
    else:
        raise SystemExit(f"unknown stage {stage}")


if __name__ == "__main__":
    main()
