"""Zoom into w_norm neighborhood under Robust-VAR baseline.
Also test combos w_norm x w_full and w_norm x spy_thr.
"""
from __future__ import annotations
import sys, warnings
from pathlib import Path
import numpy as np, pandas as pd

warnings.filterwarnings("ignore")
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
from _explore_batch3 import run, per_half  # noqa: E402
from backtest.engine import compute_stats  # noqa: E402


def show(label, ser, base):
    f,a,b_=per_half(ser)
    f0,a0,b0=base
    dSh=f['sharpe']-f0['sharpe']; dA=a['sharpe']-a0['sharpe']; dB=b_['sharpe']-b0['sharpe']
    tag=""
    if dA>=-0.02 and dB>=-0.02 and dSh>=0.04: tag="  PASS"
    elif dA>=-0.02 and dB>=-0.02 and dSh>=0:  tag="  +"
    print(f"{label:<44}  {f['cagr']*100:>6.2f}%  Sh {f['sharpe']:.3f}  "
          f"A {a['sharpe']:.3f}  B {b_['sharpe']:.3f}  dSh {dSh:+.3f}{tag}")


def bootstrap_edge(a, b, n=10000, seed=42):
    rng = np.random.default_rng(seed)
    d = a - b
    n_obs = len(d); means = np.empty(n)
    for i in range(n):
        idx = rng.integers(0, n_obs, n_obs)
        means[i] = d[idx].mean()
    ann = ((1 + means) ** 12 - 1) * 100
    t = d.mean() / (d.std(ddof=1) / np.sqrt(n_obs))
    return t, (means>0).mean(), np.percentile(ann,[2.5,97.5])


def main():
    base_ser = run()
    base = per_half(base_ser)
    print(f"baseline (Robust-VAR): CAGR {base[0]['cagr']*100:.2f}%  Sh {base[0]['sharpe']:.3f}  A {base[1]['sharpe']:.3f}  B {base[2]['sharpe']:.3f}")
    print()

    print("=== fine w_norm sweep ===")
    for wn in [0.40,0.42,0.44,0.45,0.46,0.48,0.50]:
        show(f"w_norm={wn}", run(w_norm=wn), base)

    print()
    print("=== w_norm x w_full combos ===")
    for wn in [0.44,0.45,0.46,0.48]:
        for wf in [0.82,0.85,0.88]:
            show(f"wn={wn} wf={wf}", run(w_norm=wn,w_full=wf), base)

    print()
    print("=== w_norm x spy_thr combos ===")
    for wn in [0.45,0.46,0.48,0.50]:
        for st in [0.12,0.14,0.16]:
            show(f"wn={wn} st={st}", run(w_norm=wn,spy_thr=st), base)

    print()
    print("=== BOOTSTRAP ===")
    for label, ser in [
        ("w_norm=0.45",             run(w_norm=0.45)),
        ("w_norm=0.45 + st=0.16",   run(w_norm=0.45, spy_thr=0.16)),
        ("spy_thr=0.16",            run(spy_thr=0.16)),
    ]:
        # Align
        valid = ~(base_ser.isna() | ser.isna())
        a = ser[valid].values; b = base_ser[valid].values
        t, p_pos, ci = bootstrap_edge(a, b)
        print(f"{label:<30}  t={t:+.3f}  P>0={p_pos*100:.1f}%  ann CI[{ci[0]:+.2f},{ci[1]:+.2f}]")


if __name__ == "__main__":
    main()
