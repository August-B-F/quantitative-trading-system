"""STUDY 2 — rebalance timing luck & tranching. Engineering measurement.

Runs GEM and ROT63 (63d top-3 inverse-vol on the 8-ETF live universe)
through the daily-ledger engine at monthly rebalance offsets k trading days
after month-end, then builds 2- and 4-tranche staggered books from the same
per-offset ledger runs. Nothing is tuned; no offset is selected.

Outputs (all inside this droplet folder):
  offset_results.csv   one row per (rule, offset, cost_bps) ledger run
  tranche_results.csv  one row per (rule, scheme, cost_bps) combined book
  summary.txt          distribution stats + tranching regret/cost numbers
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from backtest.ledger import load_prices, run_ledger_backtest  # noqa: E402
from strategy.sleeves import gem_weights  # noqa: E402

OUT = Path(__file__).resolve().parent
TRADING_DAYS = 252
CAL_DAYS = 365.25

ROT_UNIVERSE = ["SOXX", "QQQ", "XLK", "VGT", "IGV", "XLE", "GLD", "SHY"]
GEM_CORE = ["SPY", "EFA", "AGG"]  # calendar tickers (SHV joins later, 2007+)
CASH = "SHV"

OFFSETS_GRID = list(range(0, 20, 2))          # the measured lottery
OFFSETS_SUPPORT = [5, 15]                      # extra runs for the 4-tranche book
COSTS = [10.0, 20.0]
NAV_START = "2005-04-01"                       # every offset has a decision before this
DECISIONS_FROM = "2005-01-01"


def rot63_weights(prices: dict, as_of: pd.Timestamp) -> dict | None:
    """Top-3 by 63d adj_close return, inverse-63d-vol weighted. Untuned."""
    mom: dict[str, float] = {}
    for t in ROT_UNIVERSE:
        s = prices[t]["adj_close"].loc[:as_of].dropna()
        if len(s) < 64:
            continue
        mom[t] = float(s.iloc[-1] / s.iloc[-64] - 1.0)
    if len(mom) < 3:
        return None
    top = sorted(mom, key=mom.get, reverse=True)[:3]
    inv_vol: dict[str, float] = {}
    for t in top:
        s = prices[t]["adj_close"].loc[:as_of].dropna()
        daily = s.iloc[-64:].pct_change().dropna()
        v = float(daily.std(ddof=1) * np.sqrt(TRADING_DAYS))
        if np.isfinite(v) and v > 0:
            inv_vol[t] = 1.0 / v
    if not inv_vol:
        return None
    tot = sum(inv_vol.values())
    return {t: w / tot for t, w in inv_vol.items()}


def offset_schedule(prices: dict, cal_tickers: list[str], fn, k: int):
    """Monthly decisions at the k-th trading day after each month-end."""
    cal = None
    for t in cal_tickers:
        idx = prices[t].index
        cal = idx if cal is None else cal.intersection(idx)
    cal = cal[cal >= pd.Timestamp(DECISIONS_FROM)]
    month_end_pos = (
        pd.Series(np.arange(len(cal)), index=cal)
        .groupby(cal.to_period("M"))
        .last()
        .to_numpy()
    )
    schedule = []
    for pos in month_end_pos:
        p = pos + k
        if p >= len(cal):
            continue
        d = cal[p]
        w = fn(prices, pd.Timestamp(d))
        if w is not None:
            schedule.append((pd.Timestamp(d), w))
    return schedule


def nav_stats(nav: pd.Series) -> dict:
    """Same formulas as ledger._compute_stats (CAGR calendar-years, rf=0)."""
    years = (nav.index[-1] - nav.index[0]).days / CAL_DAYS
    cagr = float((nav.iloc[-1] / nav.iloc[0]) ** (1.0 / years) - 1.0)
    daily = (nav / nav.shift(1) - 1.0).dropna()
    sd = float(daily.std(ddof=1))
    sharpe = float(daily.mean() / sd * np.sqrt(TRADING_DAYS)) if sd > 0 else np.nan
    max_dd = float((nav / nav.cummax() - 1.0).min())
    return {"cagr": cagr, "sharpe": sharpe, "max_dd": max_dd, "years": years}


def combined_turnover(results: list, years: float) -> tuple[float, float, float]:
    """(ann_turnover, ann_cost_drag, trades_per_year) of the equal-split
    multi-sub-account book. Traded fraction of combined NAV per trade =
    notional_frac_tranche * nav_tranche / sum(nav_tranches), using close NAV
    of the trade date (open NAV unavailable; error is one intraday move)."""
    n = len(results)
    navs = [r.nav for r in results]
    comb = sum(navs)  # unnormalized combined (each tranche starts at 1.0)
    tot_frac = 0.0
    tot_cost = 0.0
    n_trades = 0
    for r in results:
        tr = r.trades
        if tr.empty:
            continue
        nav_j = r.nav.reindex(pd.DatetimeIndex(tr["date"])).to_numpy()
        nav_c = comb.reindex(pd.DatetimeIndex(tr["date"])).to_numpy()
        frac = tr["notional_frac"].to_numpy() * nav_j / nav_c
        tot_frac += float(frac.sum())
        tot_cost += float((tr["cost_frac"].to_numpy() * nav_j / nav_c).sum())
        n_trades += len(tr)
    return tot_frac / years, tot_cost / years, n_trades / years


def main() -> None:
    tickers = sorted(set(ROT_UNIVERSE + GEM_CORE + [CASH]))
    prices = load_prices(ROOT, tickers)

    rules = {
        "gem": (GEM_CORE, lambda p, d: gem_weights(p, d)),
        "rot63": (ROT_UNIVERSE, rot63_weights),
    }

    all_offsets = sorted(set(OFFSETS_GRID + OFFSETS_SUPPORT))
    offset_rows = []
    runs: dict[tuple, object] = {}  # (rule, k, cost) -> LedgerResult

    for rule, (cal_tickers, fn) in rules.items():
        schedules = {k: offset_schedule(prices, cal_tickers, fn, k) for k in all_offsets}
        for k in all_offsets:
            for cost in COSTS:
                res = run_ledger_backtest(
                    schedules[k], prices, cost_bps=cost, cash_ticker=CASH,
                    start=NAV_START, end=None, benchmarks=(),
                )
                runs[(rule, k, cost)] = res
                s = res.stats
                offset_rows.append({
                    "rule": rule, "offset": k, "cost_bps": cost,
                    "cagr": s["cagr"], "sharpe": s["sharpe"], "max_dd": s["max_dd"],
                    "ann_turnover": s["ann_turnover"],
                    "ann_cost_drag_bps": s["ann_cost_drag"] * 1e4,
                    "trades_per_year": len(res.trades) / s_years(s),
                    "n_rebalances": s["n_rebalances"],
                    "start": s["start"].date(), "end": s["end"].date(),
                    "in_grid": k in OFFSETS_GRID,
                })
                print(f"{rule} k={k:2d} cost={cost:.0f}: CAGR={s['cagr']*100:6.2f}%  "
                      f"Sharpe={s['sharpe']:.3f}  MaxDD={s['max_dd']*100:6.1f}%  "
                      f"turn={s['ann_turnover']:.2f}x", flush=True)

    df = pd.DataFrame(offset_rows)
    df.to_csv(OUT / "offset_results.csv", index=False)

    schemes = {"tranche2": [0, 10], "tranche4": [0, 5, 10, 15]}
    tranche_rows = []
    for rule in rules:
        for scheme, ks in schemes.items():
            for cost in COSTS:
                parts = [runs[(rule, k, cost)] for k in ks]
                comb = sum(p.nav for p in parts) / len(parts)
                st = nav_stats(comb)
                turn, cost_drag, tpy = combined_turnover(parts, st["years"])
                tranche_rows.append({
                    "rule": rule, "scheme": scheme, "cost_bps": cost,
                    "cagr": st["cagr"], "sharpe": st["sharpe"], "max_dd": st["max_dd"],
                    "ann_turnover": turn, "ann_cost_drag_bps": cost_drag * 1e4,
                    "trades_per_year": tpy,
                })
                print(f"{rule} {scheme} cost={cost:.0f}: CAGR={st['cagr']*100:6.2f}%  "
                      f"Sharpe={st['sharpe']:.3f}  MaxDD={st['max_dd']*100:6.1f}%  "
                      f"turn={turn:.2f}x  trades/yr={tpy:.0f}", flush=True)
    tf = pd.DataFrame(tranche_rows)
    tf.to_csv(OUT / "tranche_results.csv", index=False)

    # Save NAVs (10 bps) for reproducibility / downstream checks.
    for rule in rules:
        navs = pd.DataFrame({k: runs[(rule, k, 10.0)].nav for k in all_offsets})
        navs.columns = [f"k{k}" for k in all_offsets]
        navs.to_parquet(OUT / f"navs_{rule}_10bps.parquet")

    # DISPERSION REMOVED: phase-shifted tranche books built from existing
    # runs (pure arithmetic recombination — no new configs). The std of
    # outcomes across phase shifts is the residual timing luck AFTER
    # tranching; compare with the single-date std.
    pairs2 = [(0, 10), (2, 12), (4, 14), (6, 16), (8, 18)]
    quads4 = [(0, 5, 10, 15), (2, 6, 12, 16), (4, 8, 14, 18)]
    phase_rows = []
    for rule in rules:
        for cost in COSTS:
            for label, combos in [("2tr", pairs2), ("4tr", quads4)]:
                for ks in combos:
                    comb = sum(runs[(rule, k, cost)].nav for k in ks) / len(ks)
                    st = nav_stats(comb)
                    phase_rows.append({
                        "rule": rule, "cost_bps": cost, "n_tranches": label,
                        "offsets": "+".join(map(str, ks)),
                        "cagr": st["cagr"], "sharpe": st["sharpe"],
                        "max_dd": st["max_dd"],
                    })
    pf = pd.DataFrame(phase_rows)
    pf.to_csv(OUT / "phase_shift_results.csv", index=False)

    lines = []
    for rule in rules:
        for cost in COSTS:
            g = df[(df.rule == rule) & (df.cost_bps == cost) & df.in_grid]
            for m in ["cagr", "sharpe", "max_dd"]:
                v = g[m].to_numpy()
                lines.append(
                    f"{rule} cost={cost:.0f} {m}: min={v.min():.4f} "
                    f"p5={np.percentile(v, 5):.4f} median={np.median(v):.4f} "
                    f"max={v.max():.4f} std={v.std(ddof=1):.4f} "
                    f"spread={v.max()-v.min():.4f}"
                )
            med_c, p5_c = np.median(g.cagr), np.percentile(g.cagr, 5)
            med_s, p5_s = np.median(g.sharpe), np.percentile(g.sharpe, 5)
            lines.append(
                f"{rule} cost={cost:.0f} regret_avoided: cagr={med_c-p5_c:.4f} "
                f"sharpe={med_s-p5_s:.4f}"
            )
            for scheme in schemes:
                r = tf[(tf.rule == rule) & (tf.scheme == scheme) & (tf.cost_bps == cost)].iloc[0]
                lines.append(
                    f"{rule} cost={cost:.0f} {scheme}: cagr={r.cagr:.4f} "
                    f"sharpe={r.sharpe:.4f} max_dd={r.max_dd:.4f} "
                    f"turn={r.ann_turnover:.3f} cost_drag_bps={r.ann_cost_drag_bps:.2f} "
                    f"trades/yr={r.trades_per_year:.1f} "
                    f"sharpe_vs_median={r.sharpe - med_s:+.4f}"
                )
    for rule in rules:
        for cost in COSTS:
            g = df[(df.rule == rule) & (df.cost_bps == cost) & df.in_grid]
            for label in ["2tr", "4tr"]:
                q = pf[(pf.rule == rule) & (pf.cost_bps == cost) & (pf.n_tranches == label)]
                lines.append(
                    f"{rule} cost={cost:.0f} {label} phase-shift books (n={len(q)}): "
                    f"sharpe mean={q.sharpe.mean():.4f} std={q.sharpe.std(ddof=1):.4f} "
                    f"(single-date std={g.sharpe.std(ddof=1):.4f}); "
                    f"cagr mean={q.cagr.mean():.4f} std={q.cagr.std(ddof=1):.4f} "
                    f"(single-date std={g.cagr.std(ddof=1):.4f})"
                )
    (OUT / "summary.txt").write_text("\n".join(lines))
    print("\n".join(lines))


def s_years(s: dict) -> float:
    return (s["end"] - s["start"]).days / CAL_DAYS


if __name__ == "__main__":
    main()
