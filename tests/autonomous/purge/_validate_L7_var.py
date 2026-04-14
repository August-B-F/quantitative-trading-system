"""Bootstrap + combinations for L7 tight-FOMC on Robust-VAR."""
from __future__ import annotations
import sys, warnings
from pathlib import Path
import numpy as np, pandas as pd
warnings.filterwarnings("ignore")
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
from _recheck_purged import run, per_half  # noqa: E402


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


def show(label, ser, base):
    from backtest.engine import compute_stats
    f, a, b_ = per_half(ser)
    f0, a0, b0 = base
    print(f"{label:<44}  CAGR {f['cagr']*100:6.2f}%  Sh {f['sharpe']:.3f}  "
          f"A {a['sharpe']:.3f}  B {b_['sharpe']:.3f}  "
          f"dSh {f['sharpe']-f0['sharpe']:+.3f}")


def main():
    base_ser = run()
    base = per_half(base_ser)
    print(f"baseline Robust-VAR: CAGR {base[0]['cagr']*100:.2f}%  Sh {base[0]['sharpe']:.3f}  A {base[1]['sharpe']:.3f}  B {base[2]['sharpe']:.3f}")
    print()

    variants = {
        "L7 tight FOMC (0,1,4)": run(L7=True),
        "L7 FOMC (0,1,5)":       run(L7=False, fomc_p=0, fomc_q=1, fomc_d=5),
        "L7 FOMC (1,1,4)":       run(L7=False, fomc_p=1, fomc_q=1, fomc_d=4),
        "L7 FOMC (0,3,3)":       run(L7=False, fomc_p=0, fomc_q=3, fomc_d=3),
        "L7 FOMC (1,2,3)":       run(L7=False, fomc_p=1, fomc_q=2, fomc_d=3),
        "L10 lb=4 thr=0.20":     run(L10=True, warm_lb=4, warm_thr=0.20),
        "L7 + L10(4,0.20)":      run(L7=True, L10=True, warm_lb=4, warm_thr=0.20),
        "L7 + L8(3,-0.01)":      run(L7=True, L8=True, dd_lb=3, dd_thr=-0.01),
    }
    for name, ser in variants.items():
        show(name, ser, base)

    print()
    print("=== bootstraps vs Robust-VAR baseline ===")
    for name, ser in variants.items():
        valid = ~(base_ser.isna() | ser.isna())
        a = ser[valid].values; b = base_ser[valid].values
        res = bootstrap(a, b)
        print(f"{name:<30}  t={res['t']:+.3f}  P={res['p']:.1f}%  "
              f"CI[{res['ci'][0]:+.2f}, {res['ci'][1]:+.2f}]")


if __name__ == "__main__":
    main()
