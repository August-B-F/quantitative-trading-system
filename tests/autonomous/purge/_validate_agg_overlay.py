"""Fine grid + bootstrap for AGG overlay on Robust-VAR."""
from __future__ import annotations
import sys, warnings
from pathlib import Path
import numpy as np, pandas as pd
warnings.filterwarnings("ignore")
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
from _explore_batch6 import run, per_half  # noqa: E402


def bootstrap(a, b, n=10000, seed=42):
    rng = np.random.default_rng(seed)
    d = a - b
    n_obs = len(d); means = np.empty(n)
    for i in range(n):
        idx = rng.integers(0, n_obs, n_obs)
        means[i] = d[idx].mean()
    ann = ((1 + means) ** 12 - 1) * 100
    t = d.mean() / (d.std(ddof=1) / np.sqrt(n_obs))
    return dict(t=float(t), p=(means>0).mean()*100,
                ci=(float(np.percentile(ann,2.5)), float(np.percentile(ann,97.5))))


def main():
    base_ser = run()
    base = per_half(base_ser)
    print(f"baseline: Sh {base[0]['sharpe']:.3f}  A {base[1]['sharpe']:.3f}  B {base[2]['sharpe']:.3f}")
    print()
    print(f"{'variant':<30}  CAGR   Sh    A     B     dSh    t    P%   CI")
    for bond in ["AGG","TLT","SHY","GLD"]:
        for bw in [0.05, 0.08, 0.10, 0.12, 0.15]:
            ser = run(bond_overlay=bond, bond_w=bw)
            f, a, b_ = per_half(ser)
            valid = ~(base_ser.isna() | ser.isna())
            r = bootstrap(ser[valid].values, base_ser[valid].values)
            print(f"{bond} w={bw:<4}                    "
                  f"{f['cagr']*100:5.2f}% {f['sharpe']:.3f} {a['sharpe']:.3f} {b_['sharpe']:.3f} "
                  f"{f['sharpe']-base[0]['sharpe']:+.3f}  {r['t']:+.2f} {r['p']:5.1f} "
                  f"[{r['ci'][0]:+.2f},{r['ci'][1]:+.2f}]")


if __name__ == "__main__":
    main()
