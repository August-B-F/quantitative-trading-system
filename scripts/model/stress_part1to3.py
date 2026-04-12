"""Stress continuation — Part 1 (blended lookback), Part 2 (dispersion-conditional),
Part 3 (rebalance timing, best-effort within cached-fwd21 constraint).

Run: py scripts/model/stress_part1to3.py
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
    load_cache,
    run_strategy_from_cache,
    stats,
    ETFS,
    K,
    W_TOP1,
    W_TOPK,
    SMA_GATE,
    M26_POST_DAYS,
    M26_WINDOW_POST,
    fomc_window_mask_from_idx,
)

OUT = ROOT / "results/stress"
OUT.mkdir(exist_ok=True, parents=True)


# ---------- helpers ----------------------------------------------------------

def load_price_panel(dates: pd.DatetimeIndex) -> np.ndarray:
    """Load adjusted close for each ETF into (NDAYS, n_etfs)."""
    arr = np.full((len(dates), len(ETFS)), np.nan)
    for j, t in enumerate(ETFS):
        fp = ROOT / f"data/clean/prices/{t}.parquet"
        df = pd.read_parquet(fp)
        if not isinstance(df.index, pd.DatetimeIndex):
            # try common date columns
            for c in ("date", "Date", "timestamp"):
                if c in df.columns:
                    df = df.set_index(c)
                    break
        df.index = pd.to_datetime(df.index)
        col = None
        for c in ("adj_close", "Adj Close", "close", "Close"):
            if c in df.columns:
                col = c
                break
        if col is None:
            raise RuntimeError(f"No close col in {fp}, cols={df.columns.tolist()}")
        s = df[col].reindex(dates).ffill()
        arr[:, j] = s.values
    return arr


def returns_lb(prices: np.ndarray, lb: int) -> np.ndarray:
    """N-day simple return P[t]/P[t-lb] - 1, vectorized."""
    out = np.full_like(prices, np.nan)
    out[lb:] = prices[lb:] / prices[:-lb] - 1.0
    return out


def run_blended(cache, mom_stable: np.ndarray, mom_trans: np.ndarray | None = None,
                **kwargs):
    """Run strategy_from_cache with injected stable/trans momentum arrays.

    We monkey-patch by temporarily assigning to the cache dict (same refs used inside).
    """
    # Save
    saved_s = cache["M_STABLE"]
    saved_t = cache["M_TRANS"]
    try:
        cache["M_STABLE"] = mom_stable
        if mom_trans is not None:
            cache["M_TRANS"] = mom_trans
        res = run_strategy_from_cache(cache, **kwargs)
    finally:
        cache["M_STABLE"] = saved_s
        cache["M_TRANS"] = saved_t
    return res


def fmt(st):
    return f"CAGR {st['cagr']*100:.2f}%  Sharpe {st['sharpe']:.2f}  MaxDD {st['max_dd']*100:.2f}%"


# ---------- PART 1 -----------------------------------------------------------

def part1(cache):
    print("\n=== PART 1 — Blended lookback ===")
    DATES = cache["DATES"]
    NDAYS = cache["NDAYS"]

    # Load prices to compute arbitrary lookbacks for Variant B
    print("[part1] loading price panel for 58d/68d compute...")
    prices = load_price_panel(DATES)

    # Precomputed momentum arrays for 42, 63, 126 via parquet (use harness lookback plumbing via cache swap)
    def mom_from_parquet(lb):
        rdf = pd.read_parquet(ROOT / f"data/features/price/returns_{lb}d.parquet").reindex(DATES)
        a = np.full((NDAYS, len(ETFS)), np.nan)
        for j, t in enumerate(ETFS):
            a[:, j] = rdf[t].values
        return a

    M63 = mom_from_parquet(63)
    M126 = mom_from_parquet(126)
    M42 = mom_from_parquet(42)
    M58 = returns_lb(prices, 58)
    M68 = returns_lb(prices, 68)

    results = {}

    # C: baseline
    r_c = run_strategy_from_cache(cache)
    results["C_ctrl_63"] = {"desc": "stable=63d (control)", "stats": r_c["stats"]}
    print(f"  C (63 ctrl)       : {fmt(r_c['stats'])}")

    # A: avg(63, 126) stable
    A_stable = np.nanmean(np.stack([M63, M126], 0), axis=0)
    r_a = run_blended(cache, A_stable)
    results["A_avg_63_126"] = {"desc": "stable=avg(63,126)", "stats": r_a["stats"]}
    print(f"  A (avg 63,126)    : {fmt(r_a['stats'])}")

    # B: avg(58, 68) stable
    B_stable = np.nanmean(np.stack([M58, M68], 0), axis=0)
    r_b = run_blended(cache, B_stable)
    results["B_avg_58_68"] = {"desc": "stable=avg(58,68) [on-the-fly]", "stats": r_b["stats"]}
    print(f"  B (avg 58,68)     : {fmt(r_b['stats'])}")

    # Cliff test: A with 63 replaced by 42 -> avg(42,126)
    cliff_stable = np.nanmean(np.stack([M42, M126], 0), axis=0)
    r_cliff = run_blended(cache, cliff_stable)
    results["A_cliff_42_126"] = {"desc": "stable=avg(42,126) cliff test", "stats": r_cliff["stats"]}
    print(f"  Cliff (42,126)    : {fmt(r_cliff['stats'])}")

    # For completeness: lb_stable=42 alone (already known 1.13 but verify)
    r_42 = run_strategy_from_cache(cache, lookback_stable=42)
    results["lb42_alone"] = {"desc": "stable=42 alone (known cliff)", "stats": r_42["stats"]}
    print(f"  lb42 alone        : {fmt(r_42['stats'])}")

    (OUT / "test_part1_blended.json").write_text(json.dumps(results, indent=2, default=str))
    print(f"[part1] wrote {OUT / 'test_part1_blended.json'}")
    return results


# ---------- PART 2 -----------------------------------------------------------

def part2(cache):
    print("\n=== PART 2 — Dispersion-conditional expectations ===")
    DATES = cache["DATES"]
    # Use cached M_STABLE (63d returns) for dispersion
    M63 = cache["M_STABLE"]
    disp_daily = np.nanstd(M63, axis=1)  # per-day cross-sectional stdev

    # Run baseline
    r = run_strategy_from_cache(cache)
    monthly = r["monthly"]  # pd.Series indexed by month-end date

    # For each strategy month, grab dispersion at the rebalance day (orig_i from picks)
    picks = run_strategy_from_cache(cache, return_picks=True)["picks"]
    disp_per_month = []
    for _, row in picks.iterrows():
        i = int(row["orig_i"])
        disp_per_month.append(disp_daily[i])
    disp_per_month = np.array(disp_per_month)

    # Align strategy & spy returns
    strat_ret = np.array([monthly.values[i] for i in range(len(monthly))])

    # SPY monthly return proxy: use 21d forward from same position
    spy_fwd = []
    FWD = cache["FWD_ARR"]
    # SPY isn't in our 8-ETF panel — use spy_ret_21d from cache? That's trailing.
    # Use QQQ as a weak proxy? No — use precomputed SPY fwd from returns parquet.
    try:
        r21 = pd.read_parquet(ROOT / "data/features/price/returns_21d.parquet").reindex(DATES)
        spy_trailing = r21["SPY"].values
        # forward return = trailing shifted -21
        spy_fwd_arr = np.full_like(spy_trailing, np.nan)
        spy_fwd_arr[:-21] = spy_trailing[21:]
    except Exception:
        spy_fwd_arr = np.full(len(DATES), np.nan)

    for _, row in picks.iterrows():
        i = int(row["used_i"])
        spy_fwd.append(spy_fwd_arr[i])
    spy_fwd = np.array(spy_fwd)

    # Terciles
    valid = ~np.isnan(disp_per_month)
    d = disp_per_month[valid]
    q33, q67 = np.quantile(d, [1/3, 2/3])
    print(f"  dispersion terciles: q33={q33:.4f}  q67={q67:.4f}")

    def tercile_label(x):
        if x <= q33: return "low"
        if x <= q67: return "med"
        return "high"

    labels = np.array([tercile_label(x) if not np.isnan(x) else "na" for x in disp_per_month])

    results = {"terciles": {"q33": float(q33), "q67": float(q67)}, "buckets": {}}
    for lbl in ["low", "med", "high"]:
        mask = labels == lbl
        sr = strat_ret[mask]
        sp = spy_fwd[mask]
        sp = sp[~np.isnan(sp)]
        sr_stats = stats(sr)
        sp_stats = stats(sp)
        excess_cagr = sr_stats["cagr"] - sp_stats["cagr"]
        results["buckets"][lbl] = {
            "months": int(mask.sum()),
            "strat_cagr": sr_stats["cagr"],
            "strat_sharpe": sr_stats["sharpe"],
            "spy_cagr": sp_stats["cagr"],
            "excess_cagr": excess_cagr,
        }
        print(f"  {lbl:4s}: n={mask.sum():3d}  strat CAGR {sr_stats['cagr']*100:6.2f}% Sh {sr_stats['sharpe']:.2f}  SPY CAGR {sp_stats['cagr']*100:6.2f}%  excess {excess_cagr*100:+.2f}pp")

    (OUT / "test_dispersion.json").write_text(json.dumps(results, indent=2, default=str))
    print(f"[part2] wrote {OUT / 'test_dispersion.json'}")
    return results


# ---------- PART 3 -----------------------------------------------------------

def run_strategy_custom_timing(cache, dom_mode: str = "end", seed: int | None = None):
    """Rerun strategy but with rebalance day shifted inside each month.

    Uses the same cached predictions / momentum / FWD_ARR; only the test-date
    index per month changes. Note: FWD returns remain 21d forward regardless.
    """
    DATES = cache["DATES"]
    NDAYS = cache["NDAYS"]
    FWD_ARR = cache["FWD_ARR"]
    shy_ret = cache["shy_ret"]
    spy_dist = cache["spy_dist"]
    test_dates = cache["test_dates"]
    te_pos = cache["te_pos"]
    pred_reg = cache["pred_reg"]
    current_reg = cache["current_reg"]
    M_STABLE = cache["M_STABLE"]
    M_TRANS = cache["M_TRANS"]
    ATR = cache["ATR"]
    fomc_day_idx = cache["fomc_day_idx"]

    use_trans = (pred_reg != -1) & (pred_reg != current_reg)
    MOM = np.where(use_trans[:, None], M_TRANS, M_STABLE)
    SF = np.where(np.isnan(MOM), -np.inf, MOM)

    s_idx = pd.Series(te_pos, index=test_dates)
    groups = s_idx.groupby(test_dates.to_period("M"))

    rng = np.random.default_rng(seed) if seed is not None else None

    if dom_mode == "end":
        picks = groups.tail(1)
    elif dom_mode == "start":
        picks = groups.head(1)
    elif dom_mode == "mid":
        # pick median-index row per group
        rows = []
        for _, g in groups:
            g = g.sort_index()
            rows.append(g.iloc[len(g) // 2])
        picks = pd.Series([r for r in rows], index=[r.name if hasattr(r, "name") else None for r in rows])
        # simpler: rebuild Series
        picks = []
        idx = []
        for p, g in groups:
            g = g.sort_index()
            mi = len(g) // 2
            picks.append(int(g.iloc[mi]))
            idx.append(g.index[mi])
        picks = pd.Series(picks, index=pd.DatetimeIndex(idx))
    elif dom_mode == "random":
        picks = []
        idx = []
        for p, g in groups:
            g = g.sort_index()
            mi = int(rng.integers(0, len(g)))
            picks.append(int(g.iloc[mi]))
            idx.append(g.index[mi])
        picks = pd.Series(picks, index=pd.DatetimeIndex(idx))
    else:
        raise ValueError(dom_mode)

    fomc_post = fomc_window_mask_from_idx(fomc_day_idx, NDAYS, pre_days=0, post_days=M26_WINDOW_POST)

    out = {}
    for d, i in picks.items():
        i = int(i)
        if M26_POST_DAYS > 0 and fomc_post[i]:
            i_use = min(i + M26_POST_DAYS, NDAYS - 1)
        else:
            i_use = i
        sf_i = SF[i_use]
        if not np.isfinite(sf_i).any():
            continue
        top1 = int(np.argmax(sf_i))
        tk = np.argsort(-sf_i)[:K]
        r1_raw = FWD_ARR[i_use, top1]
        if spy_dist[i_use] > SMA_GATE:
            r1 = r1_raw
        else:
            r1 = shy_ret[i_use]
        sel_atr = ATR[i_use, tk]
        inv = 1.0 / np.where(sel_atr > 0, sel_atr, np.nan)
        if np.isnan(inv).all():
            rk = np.nanmean(FWD_ARR[i_use, tk])
        else:
            w = inv / np.nansum(inv)
            rk = np.nansum(FWD_ARR[i_use, tk] * w)
        ret = W_TOP1 * r1 + W_TOPK * rk
        out[d] = ret
    s = pd.Series(out).sort_index()
    return stats(s.values)


def part3(cache):
    print("\n=== PART 3 — Rebalance timing ===")
    results = {}
    for mode in ["end", "mid", "start"]:
        st = run_strategy_custom_timing(cache, dom_mode=mode)
        results[mode] = st
        print(f"  {mode:5s}: {fmt(st)}")

    # Random 200 runs
    rand_cagrs, rand_sh, rand_dd = [], [], []
    for seed in range(200):
        st = run_strategy_custom_timing(cache, dom_mode="random", seed=seed)
        rand_cagrs.append(st["cagr"])
        rand_sh.append(st["sharpe"])
        rand_dd.append(st["max_dd"])
    rand_cagrs = np.array(rand_cagrs)
    rand_sh = np.array(rand_sh)
    rand_dd = np.array(rand_dd)
    results["random"] = {
        "n": 200,
        "cagr_median": float(np.median(rand_cagrs)),
        "cagr_p05": float(np.quantile(rand_cagrs, 0.05)),
        "cagr_p95": float(np.quantile(rand_cagrs, 0.95)),
        "sharpe_median": float(np.median(rand_sh)),
        "sharpe_p05": float(np.quantile(rand_sh, 0.05)),
        "sharpe_p95": float(np.quantile(rand_sh, 0.95)),
        "maxdd_median": float(np.median(rand_dd)),
        "maxdd_p05": float(np.quantile(rand_dd, 0.05)),
        "maxdd_p95": float(np.quantile(rand_dd, 0.95)),
    }
    print(f"  random: CAGR median {results['random']['cagr_median']*100:.2f}% "
          f"[p05 {results['random']['cagr_p05']*100:.2f}% / p95 {results['random']['cagr_p95']*100:.2f}%]  "
          f"Sharpe median {results['random']['sharpe_median']:.2f}")
    (OUT / "test5.json").write_text(json.dumps(results, indent=2, default=str))
    print(f"[part3] wrote {OUT / 'test5.json'}")
    return results


# ---------- main -------------------------------------------------------------

def main():
    cache = load_cache()
    p1 = part1(cache)
    p2 = part2(cache)
    p3 = part3(cache)
    summary = {"part1": p1, "part2": p2, "part3": p3}
    (OUT / "part1to3_summary.json").write_text(json.dumps(summary, indent=2, default=str))
    print("\nDONE")


if __name__ == "__main__":
    main()
