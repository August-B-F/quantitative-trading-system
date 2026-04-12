"""Execute stress tests 1, 2, 3b, 4, 6, 7, 8, 9 against the cached baseline.

Saves intermediate JSON per test to results/stress/testN.json.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/model"))
from stress_harness import (  # noqa: E402
    load_cache, run_strategy_from_cache, stats, daily_stats,
    fomc_window_mask_from_idx, ETFS, LB_STABLE, LB_TRANS, M26_POST_DAYS,
    M26_WINDOW_POST, SMA_GATE, W_TOP1, W_TOPK, K,
)

OUT = ROOT / "results/stress"
OUT.mkdir(parents=True, exist_ok=True)


def _save(name, obj):
    p = OUT / f"{name}.json"
    p.write_text(json.dumps(obj, indent=2, default=str))
    print(f"  -> {p.name}")


def _fmt(st):
    return f"CAGR {st['cagr']*100:6.2f}%  Sharpe {st['sharpe']:.2f}  MaxDD {st['max_dd']*100:6.2f}%  n={st['n']}"


def main():
    print("Loading cache...")
    cache = load_cache()

    baseline = run_strategy_from_cache(cache, return_picks=True)
    b_st = baseline["stats"]
    print(f"Baseline : {_fmt(b_st)}")

    # ====================================================================
    # TEST 1 — Leave-one-year-out
    # ====================================================================
    print("\n=== TEST 1: Leave-one-year-out ===")
    t1 = {"baseline": b_st, "exclusions": {}}
    monthly = baseline["monthly"].copy()

    def excl(years):
        s = monthly[~monthly.index.year.isin(years)]
        return stats(s.values)

    targets = [[2018], [2020], [2021], [2022], [2024], [2025], [2020, 2021, 2022]]
    for yrs in targets:
        key = "-".join(str(y) for y in yrs)
        st = excl(yrs)
        flag = "FLAG" if (st["cagr"] < 0.18 or st["sharpe"] < 1.10) else "ok"
        t1["exclusions"][key] = {"stats": st, "flag": flag}
        print(f"  ex-{key:14s}: {_fmt(st)}  [{flag}]")
    _save("test1", t1)

    # ====================================================================
    # TEST 2 — Parameter sensitivity (no retrain; perturb per-param)
    # ====================================================================
    print("\n=== TEST 2: Parameter sensitivity ===")
    t2 = {"baseline": b_st, "perturbations": {}}

    def run_and_log(label, **kw):
        try:
            r = run_strategy_from_cache(cache, **kw)
            st = r["stats"]
            flag = "FLAG" if st["sharpe"] < 1.15 else "ok"
            t2["perturbations"][label] = {"stats": st, "params": kw, "flag": flag}
            print(f"  {label:28s}: {_fmt(st)}  [{flag}]")
        except Exception as e:
            t2["perturbations"][label] = {"error": str(e), "params": kw}
            print(f"  {label:28s}: ERROR {e}")

    # stable lookback — only 21/42/63/126 precomputed; use nearest available
    # (50 not available -> 42; 76 not available -> 126 or 63)
    run_and_log("lb_stable=42", lookback_stable=42)
    run_and_log("lb_stable=126", lookback_stable=126)
    # transition lookback — nearest to 17/25: 10 and 42
    run_and_log("lb_trans=42", lookback_trans=42)
    run_and_log("lb_trans=10", lookback_trans=10)
    # SMA gate
    run_and_log("sma_gate=-0.03", sma_gate=-0.03)
    run_and_log("sma_gate=-0.05", sma_gate=-0.05)
    # top1/top3 split
    run_and_log("split=40/60", weight_top1=0.4, weight_topk=0.6)
    run_and_log("split=60/40", weight_top1=0.6, weight_topk=0.4)
    # M26 defer days
    run_and_log("m26_defer=2", m26_post_days=2)
    run_and_log("m26_defer=5", m26_post_days=5)
    # M26 window
    run_and_log("m26_window=1", m26_window_post=1)
    run_and_log("m26_window=3", m26_window_post=3)
    # ATR window
    run_and_log("atr_window=14", atr_window=14)

    _save("test2", t2)

    # ====================================================================
    # TEST 3b — Classifier degradation (flip decisions)
    # ====================================================================
    print("\n=== TEST 3b: Classifier degradation (flip rebalance picks) ===")
    n_rebals = len(baseline["picks"])
    t3 = {"baseline_sharpe": b_st["sharpe"], "n_rebals": n_rebals, "rates": {}}
    rates = [0.10, 0.20, 0.30, 0.40, 0.50]
    n_iters = 200

    for rate in rates:
        sharpes = []
        cagrs = []
        maxdds = []
        for it in range(n_iters):
            rng = np.random.default_rng(int(rate * 1000) + it)
            mask = rng.random(n_rebals) < rate
            r = run_strategy_from_cache(cache, flip_mask=mask)
            st = r["stats"]
            sharpes.append(st["sharpe"])
            cagrs.append(st["cagr"])
            maxdds.append(st["max_dd"])
        sharpes = np.array(sharpes)
        cagrs = np.array(cagrs)
        maxdds = np.array(maxdds)
        t3["rates"][f"{int(rate*100)}%"] = {
            "sharpe_median": float(np.median(sharpes)),
            "sharpe_p05": float(np.percentile(sharpes, 5)),
            "sharpe_p95": float(np.percentile(sharpes, 95)),
            "cagr_median": float(np.median(cagrs)),
            "cagr_p05": float(np.percentile(cagrs, 5)),
            "maxdd_median": float(np.median(maxdds)),
        }
        print(f"  flip {int(rate*100):2d}%: sharpe med={np.median(sharpes):.2f}  "
              f"p05={np.percentile(sharpes, 5):.2f}  p95={np.percentile(sharpes, 95):.2f}  "
              f"cagr med={np.median(cagrs)*100:.2f}%")

    # Find break rate at median Sharpe<1.22
    break_rate = None
    for k_lbl, v in t3["rates"].items():
        if v["sharpe_median"] < 1.22 and break_rate is None:
            break_rate = k_lbl
    t3["break_rate_at_sharpe_1.22"] = break_rate
    # Also find p05 break
    p05_break = None
    for k_lbl, v in t3["rates"].items():
        if v["sharpe_p05"] < 1.22 and p05_break is None:
            p05_break = k_lbl
    t3["p05_break_at_sharpe_1.22"] = p05_break
    if break_rate is None:
        print(f"  Degradation budget: median Sharpe never drops below 1.22 up through 50% flip rate (robust)")
    else:
        print(f"  Degradation budget: median Sharpe<1.22 at flip rate >= {break_rate}")
    print(f"  p05 break (5%-ile Sharpe<1.22): {p05_break}")
    _save("test3b", t3)

    # ====================================================================
    # TEST 4 — Start dates
    # ====================================================================
    print("\n=== TEST 4: Start dates ===")
    t4 = {"starts": {}}
    starts = ["2008-01-01", "2010-01-01", "2012-01-01", "2014-01-01",
              "2016-01-01", "2018-01-01", "2020-01-01"]
    cagrs = []
    for s0 in starts:
        sub = monthly[monthly.index >= s0]
        st = stats(sub.values)
        cagrs.append(st["cagr"])
        t4["starts"][s0] = st
        print(f"  from {s0}: {_fmt(st)}")
    cagrs = [c for c in cagrs if not np.isnan(c)]
    cagr_range_pp = (max(cagrs) - min(cagrs)) * 100 if cagrs else 0.0
    t4["cagr_range_pp"] = cagr_range_pp
    t4["flag"] = cagr_range_pp > 8.0
    print(f"  CAGR range: {cagr_range_pp:.2f}pp  [{'FLAG' if t4['flag'] else 'ok'}]")
    _save("test4", t4)

    # ====================================================================
    # TEST 6 — Transaction costs
    # ====================================================================
    print("\n=== TEST 6: Transaction costs ===")
    t6 = {"levels": {}}
    # First compute turnover from baseline picks
    picks = baseline["picks"]
    W_ETFS = cache["ETFS"]
    n_r = len(picks)
    W = np.zeros((n_r, len(W_ETFS)))
    for i, row in picks.iterrows():
        top1_j = W_ETFS.index(row["top1"]) if not row["spy_gated"] else W_ETFS.index("SHY")
        W[i, top1_j] += W_TOP1
        for nm, wv in zip(row["topk"], row["topk_w"]):
            W[i, W_ETFS.index(nm)] += W_TOPK * (wv if not np.isnan(wv) else 1.0 / K)
    dW = np.abs(np.diff(W, axis=0, prepend=np.zeros((1, W.shape[1]))))
    turnover_per_rebal = dW.sum(axis=1)
    annual_turnover = float(turnover_per_rebal.mean() * 12)
    t6["annual_turnover"] = annual_turnover
    print(f"  annual turnover (sum |dW|): {annual_turnover:.2f}")

    # SPY benchmark over same window
    spy_monthly = pd.Series(cache["spy_ret_21d"],
                            index=cache["DATES"]).reindex(baseline["monthly"].index).dropna()
    # Use period-matched approximation: baseline already uses fwd21 -> monthly
    # Compute SPY CAGR over same monthly dates
    spy_at_month = pd.Series(cache["spy_ret_21d"], index=cache["DATES"])
    spy_month_vals = [float(spy_at_month.asof(d)) for d in baseline["monthly"].index]
    spy_sr = pd.Series(spy_month_vals, index=baseline["monthly"].index).dropna()
    spy_st = stats(spy_sr.values)
    t6["spy_stats"] = spy_st
    print(f"  SPY benchmark: {_fmt(spy_st)}")

    for bps in [0, 5, 10, 20, 30, 50]:
        r = run_strategy_from_cache(cache, cost_bps=bps)
        st = r["stats"]
        excess = st["cagr"] - spy_st["cagr"]
        t6["levels"][f"{bps}bps"] = {
            "stats": st,
            "excess_vs_spy_pp": excess * 100,
        }
        print(f"  {bps:3d}bps: {_fmt(st)}  excess vs SPY {excess*100:+.2f}pp")

    # Break-even bps where strategy CAGR == SPY CAGR (linear interp)
    levels = [(b, t6["levels"][f"{b}bps"]["stats"]["cagr"]) for b in [0, 5, 10, 20, 30, 50]]
    break_even = None
    for (b1, c1), (b2, c2) in zip(levels, levels[1:]):
        if (c1 - spy_st["cagr"]) * (c2 - spy_st["cagr"]) <= 0:
            # crossover in [b1, b2]
            if c1 != c2:
                break_even = b1 + (b2 - b1) * (c1 - spy_st["cagr"]) / (c1 - c2)
            else:
                break_even = b1
            break
    if break_even is None:
        # Extrapolate: slope between 20 and 50 bps
        b_a, c_a = levels[3]
        b_b, c_b = levels[5]
        if c_a != c_b:
            break_even = b_a + (b_b - b_a) * (c_a - spy_st["cagr"]) / (c_a - c_b)
    t6["break_even_bps"] = float(break_even) if break_even is not None else None
    t6["survives_20bps"] = t6["levels"]["20bps"]["stats"]["cagr"] > spy_st["cagr"]
    print(f"  break-even bps: {break_even}")
    print(f"  survives 20bps: {t6['survives_20bps']}")
    _save("test6", t6)

    # ====================================================================
    # TEST 7 — Drawdown deep dive (on monthly series; daily not reliably
    # available in cache — approximate with monthly cumulative)
    # ====================================================================
    print("\n=== TEST 7: Drawdowns ===")
    t7 = {}
    s = baseline["monthly"]
    eq = (1 + s).cumprod()
    peak = eq.cummax()
    dd = eq / peak - 1
    # Top-5 DDs
    episodes = []
    in_dd = False
    start = trough = None
    trough_val = 0
    for t, v in dd.items():
        if v < 0 and not in_dd:
            in_dd = True
            start = t; trough = t; trough_val = float(v)
        elif v < 0 and in_dd:
            if v < trough_val:
                trough = t; trough_val = float(v)
        elif v >= 0 and in_dd:
            episodes.append({"start": start, "trough": trough, "end": t, "dd": trough_val})
            in_dd = False
    if in_dd:
        episodes.append({"start": start, "trough": trough, "end": dd.index[-1], "dd": trough_val})
    episodes.sort(key=lambda e: e["dd"])
    top5 = episodes[:5]

    # Classify each
    picks_df = baseline["picks"].copy()
    picks_df["rebal_date"] = pd.to_datetime(picks_df["rebal_date"].astype(str))
    pred_reg = cache["pred_reg"]
    current_reg = cache["current_reg"]
    fomc_day_idx = cache["fomc_day_idx"]
    DATES = cache["DATES"]

    dd_rows = []
    for e in top5:
        s0 = pd.Timestamp(e["start"])
        s1 = pd.Timestamp(e["end"])
        in_picks = picks_df[(picks_df["rebal_date"] >= s0) & (picks_df["rebal_date"] <= s1)]
        sma_active = bool(in_picks["spy_gated"].any())
        m26_triggered = int(in_picks["deferred"].sum())
        # Transition regime active if any pred_reg != current_reg in window
        date_mask = (DATES >= s0) & (DATES <= s1)
        trans_days = int(((pred_reg[date_mask] != -1) & (pred_reg[date_mask] != current_reg[date_mask])).sum())
        total_days = int(date_mask.sum())
        # Top-1 picks held
        top1s = in_picks["top1"].value_counts().to_dict() if len(in_picks) else {}
        fomc_in_range = int(sum(1 for i in fomc_day_idx if s0 <= DATES[i] <= s1))
        dur_months = len(s[(s.index >= s0) & (s.index <= s1)])
        dd_rows.append({
            "start": str(s0.date()),
            "trough": str(pd.Timestamp(e["trough"]).date()),
            "end": str(s1.date()),
            "dd_pct": round(e["dd"] * 100, 2),
            "duration_months": dur_months,
            "sma_gate_active_in_window": sma_active,
            "m26_deferrals": m26_triggered,
            "transition_days_pct": round(100 * trans_days / max(total_days, 1), 1),
            "top1_picks": top1s,
            "fomc_meetings_in_range": fomc_in_range,
        })
        print(f"  DD {e['dd']*100:.2f}%  {s0.date()}->{s1.date()}  dur={dur_months}m  "
              f"SMA={sma_active}  M26def={m26_triggered}  trans%={round(100*trans_days/max(total_days,1),1)}")

    t7["top5_drawdowns"] = dd_rows

    # Longest 12m rolling excess<0 streak vs SPY
    excess_m = s - spy_sr.reindex(s.index)
    rolling_excess = excess_m.rolling(12).sum()
    underperf = rolling_excess < 0
    max_streak = 0
    cur = 0
    for b in underperf:
        if bool(b):
            cur += 1
            max_streak = max(max_streak, cur)
        else:
            cur = 0
    t7["longest_rolling_12m_underperf_spy_months"] = int(max_streak)
    print(f"  Longest 12m-rolling SPY-underperf streak: {max_streak} months")
    _save("test7", t7)

    # ====================================================================
    # TEST 8 — Monte Carlo bootstrap
    # ====================================================================
    print("\n=== TEST 8: Monte Carlo ===")
    t8 = {}
    r_arr = s.values
    n_obs = len(r_arr)
    n_runs = 10000
    n_months = 180  # 15y
    rng = np.random.default_rng(42)
    mc_cagrs = np.empty(n_runs)
    mc_sharpes = np.empty(n_runs)
    mc_maxdds = np.empty(n_runs)
    p_neg_3y = 0
    p_under_spy_5y = 0
    p_cagr_gt15_10y = 0
    spy_arr = spy_sr.reindex(s.index).values
    valid = ~np.isnan(spy_arr)
    spy_arr_v = spy_arr[valid]
    r_arr_v = r_arr[valid]
    for i in range(n_runs):
        idx = rng.integers(0, len(r_arr_v), size=n_months)
        sample = r_arr_v[idx].astype(float)
        # Drop any NaN in the bootstrapped sample
        sample = sample[~np.isnan(sample)]
        if len(sample) < 12:
            mc_cagrs[i] = np.nan
            mc_sharpes[i] = np.nan
            mc_maxdds[i] = np.nan
            continue
        eq = np.cumprod(1 + sample)
        yrs = len(sample) / 12
        final = eq[-1]
        mc_cagrs[i] = (final ** (1 / yrs) - 1) if final > 0 else -1.0
        sd = sample.std(ddof=1)
        mc_sharpes[i] = (sample.mean() / sd * np.sqrt(12)) if sd > 0 else 0
        peak = np.maximum.accumulate(eq)
        mc_maxdds[i] = float((eq / peak - 1).min())
        # 3y window
        w3 = sample[:36]
        if (np.prod(1 + w3) - 1) < 0:
            p_neg_3y += 1
        # 5y vs SPY — bootstrap matched
        spy_sample = spy_arr_v[idx]
        s5 = np.prod(1 + sample[:60]) - 1
        sp5 = np.prod(1 + spy_sample[:60]) - 1
        if s5 < sp5:
            p_under_spy_5y += 1
        # 10y CAGR > 15%
        s10 = sample[:120]
        c10 = np.prod(1 + s10) ** (12 / 120) - 1
        if c10 > 0.15:
            p_cagr_gt15_10y += 1

    mc_cagrs_v = mc_cagrs[~np.isnan(mc_cagrs)]
    mc_sharpes_v = mc_sharpes[~np.isnan(mc_sharpes)]
    mc_maxdds_v = mc_maxdds[~np.isnan(mc_maxdds)]
    t8 = {
        "runs": n_runs,
        "horizon_months": n_months,
        "n_valid": int(len(mc_cagrs_v)),
        "cagr_median": float(np.median(mc_cagrs_v)),
        "cagr_p05": float(np.percentile(mc_cagrs_v, 5)),
        "cagr_p95": float(np.percentile(mc_cagrs_v, 95)),
        "sharpe_median": float(np.median(mc_sharpes_v)),
        "sharpe_p05": float(np.percentile(mc_sharpes_v, 5)),
        "maxdd_p05": float(np.percentile(mc_maxdds_v, 5)),
        "maxdd_p95": float(np.percentile(mc_maxdds_v, 95)),
        "p_neg_3y": p_neg_3y / n_runs,
        "p_underperform_spy_5y": p_under_spy_5y / n_runs,
        "p_cagr_gt_15_10y": p_cagr_gt15_10y / n_runs,
    }
    for k_, v_ in t8.items():
        print(f"  {k_}: {v_}")
    _save("test8", t8)

    # ====================================================================
    # TEST 9 — Regime buckets
    # ====================================================================
    print("\n=== TEST 9: Regime buckets ===")
    t9 = {}
    DATES = cache["DATES"]
    vix = cache["vix"]
    spy_sma = pd.Series(cache["spy_dist"], index=DATES)  # this is dist from SMA200
    # trailing-12m SPY return (252 trading days)
    spy_series = pd.Series(cache["spy_ret_21d"], index=DATES).fillna(0)
    spy_price_proxy = (1 + spy_series.fillna(0) / 21).cumprod()  # crude
    # Better: use actual 252d trailing return via returns_126d*2 — but returns_252 not loaded.
    # Use rolling 12m of spy_sr (monthly already) since it's what we have aligned.
    spy_monthly = spy_sr.reindex(s.index)
    trailing_12m_spy = (1 + spy_monthly).rolling(12).apply(lambda x: x.prod() - 1)

    # VIX at month end
    vix_s = pd.Series(vix, index=DATES)
    vix_month = [float(vix_s.asof(d)) for d in s.index]
    vix_month = pd.Series(vix_month, index=s.index)

    def bucket_stats(mask, label):
        sub = s[mask]
        spy_sub = spy_monthly[mask]
        if len(sub) < 3:
            return None
        yrs = len(sub) / 12
        cagr = float((1 + sub).prod() ** (1 / yrs) - 1)
        spy_cagr = float((1 + spy_sub.dropna()).prod() ** (1 / max(len(spy_sub.dropna()) / 12, 1e-9)) - 1)
        return {"n": int(len(sub)), "strat_cagr": cagr, "spy_cagr": spy_cagr,
                "excess_pp": (cagr - spy_cagr) * 100}

    buckets_spy = {
        "spy12m_>15%": trailing_12m_spy > 0.15,
        "spy12m_0_15%": (trailing_12m_spy > 0) & (trailing_12m_spy <= 0.15),
        "spy12m_-15_0%": (trailing_12m_spy > -0.15) & (trailing_12m_spy <= 0),
        "spy12m_<-15%": trailing_12m_spy <= -0.15,
    }
    t9["spy_buckets"] = {}
    for lbl, mask in buckets_spy.items():
        r = bucket_stats(mask.fillna(False), lbl)
        t9["spy_buckets"][lbl] = r
        if r:
            print(f"  {lbl:15s}: n={r['n']:3d}  strat {r['strat_cagr']*100:+.2f}%  "
                  f"SPY {r['spy_cagr']*100:+.2f}%  excess {r['excess_pp']:+.2f}pp")

    buckets_vix = {
        "vix_<15": vix_month < 15,
        "vix_15_25": (vix_month >= 15) & (vix_month < 25),
        "vix_>25": vix_month >= 25,
    }
    t9["vix_buckets"] = {}
    for lbl, mask in buckets_vix.items():
        r = bucket_stats(mask.fillna(False), lbl)
        t9["vix_buckets"][lbl] = r
        if r:
            print(f"  {lbl:15s}: n={r['n']:3d}  strat {r['strat_cagr']*100:+.2f}%  "
                  f"SPY {r['spy_cagr']*100:+.2f}%  excess {r['excess_pp']:+.2f}pp")
    _save("test9", t9)

    print("\n=== ALL TESTS COMPLETE ===")


if __name__ == "__main__":
    main()
