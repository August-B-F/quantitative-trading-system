"""Validate inv-variance basket weighting vs inv-ATR baseline.

Steps:
  1. Reproduce Robust baseline and inv-var variant monthly returns.
  2. Paired bootstrap (10k) for significance vs baseline.
  3. Cost sensitivity at 0,2,5,10,20 bps/side (turnover re-used from baseline).
  4. Per-half check re-confirm.
"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

# Reuse run() from batch2
sys.path.insert(0, str(HERE))
from _explore_batch2 import run, per_half  # noqa: E402
from backtest.engine import compute_stats  # noqa: E402


def bootstrap_edge(a, b, n_iter=10000, seed=42):
    rng = np.random.default_rng(seed)
    diff = a - b
    n = len(diff)
    means = np.empty(n_iter)
    for i in range(n_iter):
        idx = rng.integers(0, n, n)
        means[i] = diff[idx].mean()
    ann = ((1 + means) ** 12 - 1) * 100
    p_pos = (means > 0).mean()
    ci = np.percentile(ann, [2.5, 97.5])
    t = diff.mean() / (diff.std(ddof=1) / np.sqrt(n))
    return {"t": float(t), "p_pos": float(p_pos),
            "mean_ann": float(((1+diff.mean())**12 - 1)*100),
            "ci_low": float(ci[0]), "ci_high": float(ci[1])}


def main():
    base = run(wscheme="inv_atr")
    cand = run(wscheme="inv_var")
    # Drop trailing NaN boundary months
    valid = ~(base.isna() | cand.isna())
    base = base[valid]; cand = cand[valid]
    b_full, b_a, b_b = per_half(base)
    c_full, c_a, c_b = per_half(cand)
    print("                     CAGR    Sharpe   MaxDD   A-Sh   B-Sh")
    print(f"inv-ATR (baseline)  {b_full['cagr']*100:6.2f}%  {b_full['sharpe']:.3f}   "
          f"{b_full['max_dd']*100:6.2f}%  {b_a['sharpe']:.3f}  {b_b['sharpe']:.3f}")
    print(f"inv-VAR             {c_full['cagr']*100:6.2f}%  {c_full['sharpe']:.3f}   "
          f"{c_full['max_dd']*100:6.2f}%  {c_a['sharpe']:.3f}  {c_b['sharpe']:.3f}")

    # Bootstrap
    res = bootstrap_edge(cand.values, base.values)
    print()
    print(f"Bootstrap (inv-var vs inv-atr, paired):")
    print(f"  t = {res['t']:+.3f}")
    print(f"  P(edge>0) = {res['p_pos']*100:.2f}%")
    print(f"  Mean ann edge = {res['mean_ann']:+.2f} pp/yr")
    print(f"  95% CI ann = [{res['ci_low']:+.2f}, {res['ci_high']:+.2f}] pp/yr")

    # Per-half significance
    for name, mask in [("A (pre-2018)", base.index.map(lambda d: d.year < 2018)),
                        ("B (2018+)", base.index.map(lambda d: d.year >= 2018))]:
        m = np.array(list(mask))
        res_h = bootstrap_edge(cand.values[m], base.values[m])
        print(f"  {name}: t={res_h['t']:+.3f} P={res_h['p_pos']*100:.1f}% "
              f"ann={res_h['mean_ann']:+.2f} CI[{res_h['ci_low']:+.2f},{res_h['ci_high']:+.2f}]")

    # Per-year edge
    print()
    print("Per-year edge (inv_var - inv_atr, sum of monthly diffs):")
    diff = cand - base
    by_y = diff.groupby(diff.index.map(lambda d: d.year)).sum() * 100
    for y, v in by_y.items():
        print(f"  {y}: {v:+6.2f} pp")


if __name__ == "__main__":
    main()
