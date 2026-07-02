"""Study 13 — race decisiveness: bootstrap power of the promotion rule + SPA.

Pre-registered in HYPOTHESIS.md (same folder, written first). Runs the three
frozen race arms through the daily-ledger engine, then:

Part 1 (power): circular block bootstrap (block=21td, joint across arms) of the
2018+ daily returns to estimate (a) the sampling std of 12-month Sharpes and
edges, (b) FPR/FNR of the literal ">= 0.20 Sharpe edge after 12 months"
promotion rule via mean-shift calibration, (c) the minimum window at which a
true 0.20 edge is detected with 80% power under three decision statistics
(literal rule, one-sided 5% Sharpe-difference test, one-sided 5% PAIRED
daily-difference Sharpe test).

Part 2 (SPA): Hansen's SPA (arch.bootstrap.SPA), losses = -daily returns,
benchmark = each control, model = blend, full common window.

Outputs (this folder): power_results.csv, spa_results.csv, trials.csv,
arm_returns_<window>_<cost>bps.parquet.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from backtest.ledger import load_prices, run_ledger_backtest          # noqa: E402
from strategy.rotation import (                                        # noqa: E402
    ROTATION_UNIVERSE, GATE_TICKER, blend_rotation_weights,
    month_end_offset_dates,
)
from strategy.sleeves import (                                         # noqa: E402
    CASH, GEM_FALLBACK, GEM_RISK_ASSETS, build_schedule, gem_weights,
)

SEED = 13
BLOCK = 21
B_12M = 5000
B_GRID = 2000
DAYS_PER_MONTH = 21
TDPY = 252
EDGE_BAR = 0.20
WINDOW_GRID_MONTHS = [12, 24, 36, 60, 96, 120, 180, 240]
COSTS = [10.0, 20.0]
DATE = "2026-07-02"
BUDGET_NOTE = "owner-authorized-budget-expansion"

ALL_TICKERS = sorted(
    set(ROTATION_UNIVERSE) | set(GEM_RISK_ASSETS)
    | {GATE_TICKER, CASH, GEM_FALLBACK, "SHY"}
)


def ann_sharpe(x: np.ndarray, axis=None) -> np.ndarray:
    m = x.mean(axis=axis)
    s = x.std(axis=axis, ddof=1)
    return m / s * np.sqrt(TDPY)


# ---------- arm schedules (frozen specs) --------------------------------------

def blend_schedule(prices, start, end):
    tickers = set(ROTATION_UNIVERSE) | {GATE_TICKER}
    cal = None
    for t in tickers:
        idx = prices[t]["adj_close"].dropna().index
        cal = idx if cal is None else cal.intersection(idx)
    end_ts = pd.Timestamp(end) if end is not None else cal.max()
    cal = cal[(cal >= pd.Timestamp(start)) & (cal <= end_ts)]
    dates = month_end_offset_dates(cal, 0)
    return [(d, blend_rotation_weights(prices, d)) for d in dates]


def sma_trend_weights(prices, as_of):
    s = prices["SPY"]["close"].loc[:as_of].dropna()
    if len(s) < 200:
        return None
    sma = float(s.iloc[-200:].mean())
    return {"SPY": 1.0} if float(s.iloc[-1]) > sma else {"SHY": 1.0}


def build_arm_returns(prices, cost_bps, start, end):
    """Daily NAV returns for the 3 arms, inner-joined. Returns (df, stats)."""
    full_start, full_end = "2005-01-01", end
    scheds = {
        "blend": blend_schedule(prices, full_start, full_end),
        "gem": build_schedule(
            {t: prices[t] for t in sorted(set(GEM_RISK_ASSETS) | {GEM_FALLBACK, CASH})},
            full_start, full_end, gem_weights),
        "spy_sma200": build_schedule(
            {t: prices[t] for t in ["SPY", "SHY"]},
            full_start, full_end, sma_trend_weights),
    }
    rets, stats = {}, {}
    for name, sched in scheds.items():
        run_start = pd.Timestamp(start) if start is not None else sched[0][0]
        res = run_ledger_backtest(
            sched, prices, cost_bps=cost_bps, cash_ticker=CASH,
            start=run_start, end=end, benchmarks=(),
        )
        rets[name] = res.nav.pct_change().dropna()
        stats[name] = res.stats
    df = pd.DataFrame(rets).dropna()
    return df, stats


# ---------- bootstrap machinery -----------------------------------------------

def block_index(rng, n_obs, path_len, B):
    n_blocks = int(np.ceil(path_len / BLOCK))
    starts = rng.integers(0, n_obs, size=(B, n_blocks), dtype=np.int64)
    offs = np.arange(BLOCK, dtype=np.int64)
    idx = (starts[:, :, None] + offs[None, None, :]) % n_obs
    return idx.reshape(B, -1)[:, :path_len].astype(np.int32)


def boot_stats(R, idx, chunk=250):
    """Per-rep annualized Sharpe of each column and of col0-minus-others diffs.

    R: (n_obs, k) float array, col 0 = blend. Returns dict with
    'sharpe' (B, k) and 'pair_sharpe' (B, k-1) for d = R[:,0]-R[:,j].
    """
    B = idx.shape[0]
    k = R.shape[1]
    sh = np.empty((B, k))
    ps = np.empty((B, k - 1))
    for lo in range(0, B, chunk):
        hi = min(lo + chunk, B)
        X = R[idx[lo:hi]]                       # (b, L, k)
        sh[lo:hi] = ann_sharpe(X, axis=1)
        D = X[:, :, :1] - X[:, :, 1:]           # (b, L, k-1)
        ps[lo:hi] = ann_sharpe(D, axis=1)
    return {"sharpe": sh, "pair_sharpe": ps}


def calibrate_shift(blend: np.ndarray, target_ann_sharpe: float) -> float:
    """Constant daily shift so the blend column's full-sample ann. Sharpe hits target."""
    m, s = blend.mean(), blend.std(ddof=1)
    return s * target_ann_sharpe / np.sqrt(TDPY) - m


# ---------- main --------------------------------------------------------------

def main():
    prices = load_prices(ROOT, ALL_TICKERS)
    rng = np.random.default_rng(SEED)
    power_rows, spa_rows, trial_rows = [], [], []
    tno = 0

    def log_trial(name, window, sharpe, cagr, max_dd, source, notes):
        nonlocal tno
        tno += 1
        trial_rows.append({
            "trial_id": f"S13RP_{tno:03d}", "date": DATE, "name": name,
            "engine": "daily_ledger_v1", "window": window,
            "sharpe": round(float(sharpe), 3) if np.isfinite(sharpe) else "",
            "cagr": round(float(cagr) * 100, 2) if np.isfinite(cagr) else "",
            "max_dd": round(float(max_dd) * 100, 2) if np.isfinite(max_dd) else "",
            "n_trials_represented": 1, "source": source,
            "notes": f"{notes};{BUDGET_NOTE}",
        })

    for cost in COSTS:
        # ---- ledger runs: 2018+ power window and full common window ----------
        R18_df, st18 = build_arm_returns(prices, cost, "2018-01-01", None)
        Rfull_df, stfull = build_arm_returns(prices, cost, None, None)
        R18_df.to_parquet(HERE / f"arm_returns_2018plus_{int(cost)}bps.parquet")
        Rfull_df.to_parquet(HERE / f"arm_returns_full_{int(cost)}bps.parquet")
        for wlabel, stats in (("2018-latest", st18), ("full-common", stfull)):
            for arm, s in stats.items():
                log_trial(arm, wlabel, s["sharpe"], s["cagr"], s["max_dd"],
                          "power_input" if wlabel == "2018-latest" else "spa_input",
                          f"cost={int(cost)}bps;arm-rerun-not-new-config")

        R = R18_df.to_numpy()
        arms = list(R18_df.columns)               # ['blend','gem','spy_sma200']
        n_obs = R.shape[0]
        obs_sharpe = {a: ann_sharpe(R18_df[a].to_numpy()) for a in arms}

        # ---- (a) 12-month sampling std, uncalibrated --------------------------
        idx12 = block_index(rng, n_obs, 12 * DAYS_PER_MONTH, B_12M)
        bs = boot_stats(R, idx12)
        for j, a in enumerate(arms):
            power_rows.append({
                "cost_bps": cost, "control": "", "metric": "sharpe_sd_12m",
                "arm": a, "window_months": 12,
                "value": bs["sharpe"][:, j].std(ddof=1),
                "extra": f"obs_sharpe_2018plus={obs_sharpe[a]:.3f}",
            })
        for j, c in enumerate(arms[1:]):
            edge = bs["sharpe"][:, 0] - bs["sharpe"][:, 1 + j]
            corr = float(np.corrcoef(R[:, 0], R[:, 1 + j])[0, 1])
            power_rows.append({
                "cost_bps": cost, "control": c, "metric": "edge_sd_12m",
                "arm": "blend", "window_months": 12,
                "value": edge.std(ddof=1),
                "extra": (f"obs_edge={obs_sharpe['blend'] - obs_sharpe[c]:.3f};"
                          f"daily_corr={corr:.3f}"),
            })

        # ---- (b) + (c): calibrated FPR/FNR and power curves --------------------
        for j, c in enumerate(arms[1:], start=1):
            s_c = float(obs_sharpe[c])
            d0 = calibrate_shift(R[:, 0], s_c)            # true edge = 0
            d1 = calibrate_shift(R[:, 0], s_c + EDGE_BAR)  # true edge = +0.20
            for months in WINDOW_GRID_MONTHS:
                L = months * DAYS_PER_MONTH
                B = B_12M if months == 12 else B_GRID
                idx = idx12 if months == 12 else block_index(rng, n_obs, L, B)
                cols = [0, j]
                Rsub = R[:, cols]
                R0 = Rsub.copy(); R0[:, 0] += d0
                R1 = Rsub.copy(); R1[:, 0] += d1
                b0 = boot_stats(R0, idx)
                b1 = boot_stats(R1, idx)
                edge0 = b0["sharpe"][:, 0] - b0["sharpe"][:, 1]
                edge1 = b1["sharpe"][:, 0] - b1["sharpe"][:, 1]
                pair0 = b0["pair_sharpe"][:, 0]
                pair1 = b1["pair_sharpe"][:, 0]
                crit_edge = np.quantile(edge0, 0.95)
                crit_pair = np.quantile(pair0, 0.95)
                rows = [
                    ("fpr_literal_rule", (edge0 >= EDGE_BAR).mean(),
                     f"P(edge_hat>={EDGE_BAR}|true=0);B={B}"),
                    ("fnr_literal_rule", (edge1 < EDGE_BAR).mean(),
                     f"P(edge_hat<{EDGE_BAR}|true={EDGE_BAR});B={B}"),
                    ("power_literal_rule", (edge1 >= EDGE_BAR).mean(),
                     f"1-FNR;B={B}"),
                    ("power_sharpe_diff_test5pct", (edge1 > crit_edge).mean(),
                     f"crit={crit_edge:.3f};B={B}"),
                    ("power_paired_test5pct", (pair1 > crit_pair).mean(),
                     f"crit={crit_pair:.3f};true_pair_sharpe={ann_sharpe(R1[:, 0] - R1[:, 1]):.3f};B={B}"),
                ]
                for metric, val, extra in rows:
                    power_rows.append({
                        "cost_bps": cost, "control": c, "metric": metric,
                        "arm": "blend", "window_months": months,
                        "value": float(val), "extra": extra,
                    })
                if months == 12:
                    log_trial(f"promotion_rule_vs_{c}", "12m-bootstrap",
                              float(obs_sharpe["blend"] - s_c), np.nan, np.nan,
                              "power_analysis",
                              f"cost={int(cost)}bps;FPR={(edge0 >= EDGE_BAR).mean():.3f};"
                              f"FNR={(edge1 < EDGE_BAR).mean():.3f};block=21;B={B}")

        # ---- worst-case JOINT rule FPR (blend true Sharpe = better control) ----
        s_best = max(float(obs_sharpe[a]) for a in arms[1:])
        dj = calibrate_shift(R[:, 0], s_best)
        Rj = R.copy(); Rj[:, 0] += dj
        bj = boot_stats(Rj, idx12)
        both = ((bj["sharpe"][:, 0] - bj["sharpe"][:, 1] >= EDGE_BAR)
                & (bj["sharpe"][:, 0] - bj["sharpe"][:, 2] >= EDGE_BAR)).mean()
        power_rows.append({
            "cost_bps": cost, "control": "both", "metric": "fpr_joint_rule_12m",
            "arm": "blend", "window_months": 12, "value": float(both),
            "extra": f"blend_true_sharpe_set_to_better_control={s_best:.3f};B={B_12M}",
        })

        # ---- Part 2: SPA on the full common window ----------------------------
        from arch.bootstrap import SPA
        Rf = Rfull_df
        for c in ["gem", "spy_sma200"]:
            bench_loss = -Rf[c].to_numpy()
            model_loss = -Rf[["blend"]].to_numpy()
            spa = SPA(bench_loss, model_loss, block_size=BLOCK, reps=10000,
                      bootstrap="circular", seed=SEED)
            spa.compute()
            pv = spa.pvalues
            spa_rows.append({
                "cost_bps": cost, "benchmark": c, "model": "blend",
                "window": f"{Rf.index[0].date()}..{Rf.index[-1].date()}",
                "n_days": len(Rf),
                "p_lower": float(pv["lower"]), "p_consistent": float(pv["consistent"]),
                "p_upper": float(pv["upper"]),
                "mean_daily_edge_bps": float((Rf["blend"] - Rf[c]).mean() * 1e4),
                "full_sharpe_blend": float(ann_sharpe(Rf["blend"].to_numpy())),
                "full_sharpe_bench": float(ann_sharpe(Rf[c].to_numpy())),
            })
            log_trial(f"spa_blend_vs_{c}",
                      f"{Rf.index[0].date()}..{Rf.index[-1].date()}",
                      float(ann_sharpe(Rf["blend"].to_numpy())
                            - ann_sharpe(Rf[c].to_numpy())),
                      np.nan, np.nan, "spa_test",
                      f"cost={int(cost)}bps;p_consistent={float(pv['consistent']):.4f};"
                      f"block=21;reps=10000")

    pd.DataFrame(power_rows).to_csv(HERE / "power_results.csv", index=False)
    pd.DataFrame(spa_rows).to_csv(HERE / "spa_results.csv", index=False)
    pd.DataFrame(trial_rows).to_csv(HERE / "trials.csv", index=False)
    print("wrote", HERE / "power_results.csv")
    print("wrote", HERE / "spa_results.csv")
    print("wrote", HERE / "trials.csv")


if __name__ == "__main__":
    main()
