"""Bootstrap SHARPE ratio difference for overlay variants (not mean diff)."""
from __future__ import annotations
import sys, warnings
from pathlib import Path
import numpy as np, pandas as pd
warnings.filterwarnings("ignore")
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
from _explore_batch6 import run, per_half  # noqa: E402
from backtest.engine import compute_stats  # noqa: E402


def sharpe(x):
    x = x[~np.isnan(x)]
    if len(x) < 2 or x.std(ddof=1) == 0:
        return 0.0
    return float(x.mean() / x.std(ddof=1) * np.sqrt(12))


def bootstrap_sharpe_diff(a, b, n=5000, seed=42):
    """Block bootstrap on paired observations."""
    rng = np.random.default_rng(seed)
    n_obs = len(a)
    diffs = np.empty(n)
    for i in range(n):
        idx = rng.integers(0, n_obs, n_obs)
        diffs[i] = sharpe(a[idx]) - sharpe(b[idx])
    t_sh = diffs.mean() / diffs.std(ddof=1)
    return dict(
        mean_diff=float(diffs.mean()),
        t=float(t_sh),
        p=float((diffs > 0).mean() * 100),
        ci=(float(np.percentile(diffs, 2.5)), float(np.percentile(diffs, 97.5))),
    )


def main():
    base_ser = run()
    base = per_half(base_ser)
    print(f"baseline: Sh {base[0]['sharpe']:.3f}")
    print()
    print(f"{'variant':<25}  pt_Sh   A-Sh   B-Sh   boot_mean   P>0   CI_low  CI_high")
    for bond in ["AGG","TLT","SHY","GLD"]:
        for bw in [0.05, 0.08, 0.10, 0.12, 0.15]:
            ser = run(bond_overlay=bond, bond_w=bw)
            f, a, b_ = per_half(ser)
            valid = ~(base_ser.isna() | ser.isna())
            r = bootstrap_sharpe_diff(ser[valid].values, base_ser[valid].values)
            mark = "  **" if r['ci'][0] > 0 else ""
            print(f"{bond} w={bw:<6}             "
                  f"{f['sharpe']:.3f}  {a['sharpe']:.3f}  {b_['sharpe']:.3f}  "
                  f"{r['mean_diff']:+.4f}  {r['p']:5.1f}  "
                  f"{r['ci'][0]:+.3f}  {r['ci'][1]:+.3f}{mark}")


if __name__ == "__main__":
    main()
