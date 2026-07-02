"""Study 1 — execution timing & microstructure. Engineering measurements.

Run from repo root:  py -3 research/droplets/exec_timing_micro/analysis.py
Writes results JSON + trials.csv rows into the droplet folder.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from backtest.ledger import run_ledger_backtest, load_prices  # noqa: E402
from strategy.sleeves import gem_weights, build_schedule       # noqa: E402

OUT = Path(__file__).resolve().parent
U8 = ["SOXX", "QQQ", "XLK", "VGT", "IGV", "XLE", "GLD", "SHY"]
CASH = "SHV"
FULL_START, FULL_END = "2005-01-01", "2026-06-30"
DEV_START, DEV_END = "2005-01-01", "2017-12-31"
YEARS_FULL = None  # computed from nav index


def mom_weights_factory(universe, top_n, lookback=63):
    def fn(prices, as_of):
        rets = {}
        for t in universe:
            s = prices[t]["adj_close"].loc[:as_of].dropna()
            if len(s) < lookback + 1:
                return None
            rets[t] = float(s.iloc[-1] / s.iloc[-1 - lookback] - 1.0)
        top = sorted(rets, key=rets.get, reverse=True)[:top_n]
        return {t: 1.0 / top_n for t in top}
    return fn


def frames_for(prices, tickers):
    """adj_close, adj_open aligned frames."""
    ac = {}
    ao = {}
    for t in tickers:
        df = prices[t]
        a = df["adj_close"].astype(float)
        o = df["open"].astype(float) * a / df["close"].astype(float)
        ac[t] = a
        ao[t] = o
    AC = pd.DataFrame(ac).sort_index().ffill()
    AO = pd.DataFrame(ao).reindex(AC.index)
    AO = AO.fillna(AC.shift(1))
    return AC, AO


def leg_stats(res, prices, name):
    """Overnight-gap stats on buy/sell legs + exact open-vs-close-fill delta."""
    trades = res.trades
    tickers = sorted(set(trades["ticker"]))
    AC, AO = frames_for(prices, tickers)
    prev_AC = AC.shift(1)
    gap = AO / prev_AC - 1.0          # overnight: prev close -> today's open
    intra = AC / AO - 1.0             # intraday: today's open -> close

    rows = []
    for date, grp in trades.groupby("date"):
        g_buy = g_sell = 0.0
        nf_buy = nf_sell = 0.0
        oc_delta = 0.0                # (open-fill minus close-fill) NAV growth
        for _, r in grp.iterrows():
            t, nf = r["ticker"], float(r["notional_frac"])
            gp = float(gap.at[date, t])
            it = float(intra.at[date, t])
            sign = 1.0 if r["side"] == "buy" else -1.0
            oc_delta += sign * nf * it
            if sign > 0:
                g_buy += nf * gp
                nf_buy += nf
            else:
                g_sell += nf * gp
                nf_sell += nf
        rows.append({
            "date": date, "nf_buy": nf_buy, "nf_sell": nf_sell,
            "wgap_buy": g_buy, "wgap_sell": g_sell,
            "open_drift_cost": g_buy - g_sell,   # vs untradeable decision close
            "open_minus_close_fill": oc_delta,   # >0 => open fill better
        })
    df = pd.DataFrame(rows).set_index("date")
    nav = res.nav
    years = (nav.index[-1] - nav.index[0]).days / 365.25
    out = {
        "name": name,
        "n_rebalances": len(df),
        "years": round(years, 2),
        "ann_turnover_x": round(res.stats["ann_turnover"], 2),
        "mean_gap_buy_bps_per_unit": round(1e4 * (df["wgap_buy"].sum() / df["nf_buy"].sum()), 2),
        "mean_gap_sell_bps_per_unit": round(1e4 * (df["wgap_sell"].sum() / df["nf_sell"].sum()), 2),
        "open_drift_cost_bps_yr": round(1e4 * df["open_drift_cost"].sum() / years, 2),
        "open_minus_close_fill_bps_yr": round(1e4 * df["open_minus_close_fill"].sum() / years, 2),
        "oc_delta_tstat": round(
            float(df["open_minus_close_fill"].mean()
                  / (df["open_minus_close_fill"].std(ddof=1) / np.sqrt(len(df)))), 2)
        if len(df) > 2 else None,
    }
    return out, df


def shift_schedule(schedule, calendar):
    """Move each decision date to the next trading day (fill one day later)."""
    cal = pd.DatetimeIndex(calendar)
    out = []
    for d, w in schedule:
        pos = int(cal.searchsorted(pd.Timestamp(d), side="right"))
        if pos >= len(cal):
            continue
        out.append((cal[pos], w))
    return out


def stat_row(name, res):
    s = res.stats
    return {
        "name": name, "sharpe": round(s["sharpe"], 3), "cagr": round(s["cagr"], 4),
        "max_dd": round(s["max_dd"], 4), "ann_turnover": round(s["ann_turnover"], 2),
        "ann_cost_drag_bps": round(s["ann_cost_drag"] * 1e4, 1),
        "start": str(s["start"].date()), "end": str(s["end"].date()),
    }


def main():
    results = {}
    all_tickers = sorted(set(U8 + ["SMH", "SPY", "EFA", "AGG", CASH]))
    prices = load_prices(ROOT, all_tickers)

    # ---------------- Q1: open vs close fills ----------------
    u8_prices = {t: prices[t] for t in U8 + [CASH]}
    gem_prices = {t: prices[t] for t in ["SPY", "EFA", "AGG", CASH]}

    sched_r2 = build_schedule(u8_prices, FULL_START, FULL_END, mom_weights_factory(U8, 3))
    sched_r3 = build_schedule(u8_prices, FULL_START, FULL_END, mom_weights_factory(U8, 1))
    sched_r1 = build_schedule(gem_prices, FULL_START, FULL_END,
                              lambda p, d: gem_weights(p, d))

    q1 = {}
    per_reb = {}
    for name, sched, pr in [("R1_gem", sched_r1, gem_prices),
                            ("R2_ewtop3_63d", sched_r2, u8_prices),
                            ("R3_top1_63d", sched_r3, u8_prices)]:
        res = run_ledger_backtest(sched, pr, cost_bps=0.0, cash_ticker=CASH,
                                  start=FULL_START, end=FULL_END, benchmarks=())
        st, df = leg_stats(res, pr, name)
        st.update({"ledger_" + k: v for k, v in stat_row(name, res).items()
                   if k in ("sharpe", "cagr")})
        q1[name] = st
        per_reb[name] = df

        # 1-day-delay bracket (0 bps)
        cal = res.nav.index
        res_d = run_ledger_backtest(shift_schedule(sched, cal), pr, cost_bps=0.0,
                                    cash_ticker=CASH, start=FULL_START,
                                    end=FULL_END, benchmarks=())
        years = (res.nav.index[-1] - res.nav.index[0]).days / 365.25
        delay_bps_yr = 1e4 * ((res_d.nav.iloc[-1] / res.nav.iloc[-1]) ** (1 / years) - 1)
        q1[name]["one_day_delay_cagr_delta_bps_yr"] = round(float(delay_bps_yr), 1)
        q1[name]["delay_sharpe"] = round(res_d.stats["sharpe"], 3)
    results["q1_open_vs_close"] = q1

    # ---------------- Q2: twin substitution ----------------
    pairs = [("SOXX", "SMH"), ("XLK", "VGT"), ("QQQ", "XLK"), ("QQQ", "VGT")]
    twin_tbl = []
    liq_win = ("2023-07-01", "2026-06-30")
    for a, b in pairs:
        ra = prices[a]["adj_close"].pct_change()
        rb = prices[b]["adj_close"].pct_change()
        both = pd.concat([ra, rb], axis=1, keys=[a, b]).dropna()
        corr = float(both[a].corr(both[b]))
        te = float((both[a] - both[b]).std(ddof=1) * np.sqrt(252))
        liq = {}
        for t in (a, b):
            df = prices[t].loc[liq_win[0]:liq_win[1]]
            liq[t] = float((df["volume"] * df["close"]).median())
        twin_tbl.append({
            "pair": f"{a}/{b}", "corr": round(corr, 4), "te_ann_pct": round(te * 100, 2),
            f"med_dollar_vol_{a}_$M": round(liq[a] / 1e6, 1),
            f"med_dollar_vol_{b}_$M": round(liq[b] / 1e6, 1),
        })
    results["q2_twin_table"] = twin_tbl

    universes = {
        "U0_base": U8,
        "U1_smh_for_soxx": ["SMH" if t == "SOXX" else t for t in U8],
        "U2_xlk_for_vgt": [t for t in U8 if t != "VGT"],
        "U3_both": [("SMH" if t == "SOXX" else t) for t in U8 if t != "VGT"],
    }
    q2_runs = {}
    trials = []
    tid = 1
    for uname, uni in universes.items():
        pr = {t: prices[t] for t in uni + [CASH]}
        sched = build_schedule(pr, DEV_START, DEV_END, mom_weights_factory(uni, 3))
        row = {}
        for cb in (10.0, 20.0):
            res = run_ledger_backtest(sched, pr, cost_bps=cb, cash_ticker=CASH,
                                      start=DEV_START, end=DEV_END, benchmarks=())
            row[f"{int(cb)}bps"] = stat_row(f"{uname}@{int(cb)}", res)
            trials.append({
                "trial_id": f"ETM{tid:02d}", "date": "2026-07-02",
                "name": f"ewtop3_63d_{uname}_{int(cb)}bps",
                "engine": "daily_ledger_v1", "window": f"{DEV_START}..{DEV_END}",
                "sharpe": round(res.stats["sharpe"], 3),
                "cagr": round(res.stats["cagr"], 4),
                "max_dd": round(res.stats["max_dd"], 4),
                "n_trials_represented": 1, "source": "exec_timing_micro",
                "notes": f"twin substitution check, cost={int(cb)}bps/side",
            })
            tid += 1
            if uname == "U0_base" and cb == 10.0:
                # per-ticker traded-notional shares for spread-saving estimate
                tr = res.trades
                years = (res.nav.index[-1] - res.nav.index[0]).days / 365.25
                share = tr.groupby("ticker")["notional_frac"].sum() / years
                results["q2_u0_ann_traded_by_ticker_x"] = {
                    k: round(float(v), 3) for k, v in share.items()}
        q2_runs[uname] = row
    results["q2_ledger_dev"] = q2_runs

    # measurement trials (Q1, engineering, full window, 0 bps)
    for nm in ("R1_gem", "R2_ewtop3_63d", "R3_top1_63d"):
        trials.append({
            "trial_id": f"ETM{tid:02d}", "date": "2026-07-02",
            "name": f"{nm}_fullwin_0bps_measurement",
            "engine": "daily_ledger_v1", "window": f"{FULL_START}..{FULL_END}",
            "sharpe": q1[nm]["ledger_sharpe"], "cagr": q1[nm]["ledger_cagr"],
            "max_dd": "", "n_trials_represented": 1,
            "source": "exec_timing_micro",
            "notes": "engineering measurement (fill-convention study), gross",
        })
        tid += 1
    pd.DataFrame(trials).to_csv(OUT / "trials.csv", index=False)

    # ---------------- Q3: order type ----------------
    # gap-miss frequencies for close-pegged marketable limit +/- 20 bps
    q3 = {}
    gaps = {}
    for t in U8:
        df = prices[t]
        a = df["adj_close"].astype(float)
        o = df["open"].astype(float) * a / df["close"].astype(float)
        g = (o / a.shift(1) - 1.0).dropna()
        gaps[t] = g
        miss_buy = g > 0.0020    # buy limit at close+20bp misses
        q3[t] = {
            "pct_days_abs_gap_gt_20bp": round(100 * float((g.abs() > 0.0020).mean()), 1),
            "pct_days_buy_miss": round(100 * float(miss_buy.mean()), 1),
            "mean_overshoot_when_missed_bps": round(
                1e4 * float((g[miss_buy] - 0.0020).mean()), 1),
        }
    results["q3_gap_miss_table"] = q3

    # live slippage records
    try:
        with open(ROOT / "logs" / "rebalance_log.json") as f:
            log_j = json.load(f)
        slps = []
        def walk(o):
            if isinstance(o, dict):
                for k, v in o.items():
                    if k == "slippage_bps" and isinstance(v, (int, float)):
                        slps.append(float(v))
                    else:
                        walk(v)
            elif isinstance(o, list):
                for x in o:
                    walk(x)
        walk(log_j)
        if slps:
            s = pd.Series(slps)
            results["q3_live_slippage_bps"] = {
                "n": int(len(s)), "mean": round(float(s.mean()), 2),
                "median": round(float(s.median()), 2), "std": round(float(s.std()), 2),
                "min": round(float(s.min()), 2), "max": round(float(s.max()), 2),
            }
    except Exception as e:  # noqa: BLE001
        results["q3_live_slippage_bps"] = {"error": str(e)}

    with open(OUT / "results.json", "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(json.dumps(results, indent=2, default=str))


if __name__ == "__main__":
    main()
