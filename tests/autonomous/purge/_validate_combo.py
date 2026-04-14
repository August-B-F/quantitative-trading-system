"""Bootstrap Sharpe-diff for promising combos vs Robust-VAR."""
from __future__ import annotations
import sys, warnings
from pathlib import Path
import numpy as np
warnings.filterwarnings("ignore")
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
from _explore_combos import run, per_half  # noqa: E402


def sharpe(x):
    x = x[~np.isnan(x)]
    if len(x) < 2 or x.std(ddof=1) == 0: return 0.0
    return float(x.mean() / x.std(ddof=1) * np.sqrt(12))


def boot_sh_diff(a, b, n=10000, seed=42):
    rng = np.random.default_rng(seed)
    m = len(a); diffs = np.empty(n)
    for i in range(n):
        idx = rng.integers(0, m, m)
        diffs[i] = sharpe(a[idx]) - sharpe(b[idx])
    return dict(mean=float(diffs.mean()), p=float((diffs>0).mean()*100),
                ci=(float(np.percentile(diffs,2.5)), float(np.percentile(diffs,97.5))),
                t=float(diffs.mean()/diffs.std(ddof=1)))


def main():
    base_ser = run()
    base = per_half(base_ser)
    print(f"baseline: Sh {base[0]['sharpe']:.3f}  A {base[1]['sharpe']:.3f}  B {base[2]['sharpe']:.3f}")
    print()
    print(f"{'variant':<40}  Sh      A       B       boot_mean  P%    CI_low  CI_high   sig?")
    variants = {
        "p=3 gld=0.08":                     dict(p_exp=3.0, gld_w=0.08),
        "p=2.5 gld=0.08":                   dict(p_exp=2.5, gld_w=0.08),
        "p=2.5 gld=0.05 wn=0.45":           dict(p_exp=2.5, gld_w=0.05, w_norm=0.45),
        "p=2.5 agg=0.05 wn=0.45":           dict(p_exp=2.5, agg_w=0.05, w_norm=0.45),
        "p=2.5 agg=0.1":                    dict(p_exp=2.5, agg_w=0.10),
        "p=3 gld=0.05":                     dict(p_exp=3.0, gld_w=0.05),
        "p=3 agg=0.05":                     dict(p_exp=3.0, agg_w=0.05),
    }
    for name, cfg in variants.items():
        ser = run(**cfg)
        f, a, b_ = per_half(ser)
        valid = ~(base_ser.isna() | ser.isna())
        r = boot_sh_diff(ser[valid].values, base_ser[valid].values)
        mark = "  SIG" if r['ci'][0] > 0 else ""
        print(f"{name:<40}  {f['sharpe']:.3f}  {a['sharpe']:.3f}  {b_['sharpe']:.3f}  "
              f"{r['mean']:+.4f}    {r['p']:5.1f}  {r['ci'][0]:+.3f}  {r['ci'][1]:+.3f}{mark}")


if __name__ == "__main__":
    main()
