"""Part 1: Lookback sensitivity sweep.

Sweeps lookback_stable over 15 values using the cached classifier, computing
momentum on-the-fly from raw adjusted close prices (avoids dependence on
precomputed returns_Nd.parquet files, which only exist for {5,10,21,42,63,126,252}).

No retraining — only the momentum array is swapped per sweep value.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/model"))

from stress_harness import (  # type: ignore
    load_cache, run_strategy_from_cache, LB_STABLE, LB_TRANS, ETFS,
)

OUT_JSON = ROOT / "results/stress/lookback_curve.json"
OUT_PNG = ROOT / "results/stress/lookback_curve.png"

LOOKBACKS = [42, 45, 48, 50, 52, 55, 58, 60, 63, 66, 68, 70, 73, 76, 80]


def load_price_matrix(dates: pd.DatetimeIndex) -> np.ndarray:
    """Return (NDAYS, nETFS) matrix of adj_close aligned to `dates`."""
    P = np.full((len(dates), len(ETFS)), np.nan)
    for j, t in enumerate(ETFS):
        df = pd.read_parquet(ROOT / f"data/clean/prices/{t}.parquet")
        s = df["adj_close"].copy()
        s.index = pd.to_datetime(s.index)
        s = s.reindex(dates).ffill()
        P[:, j] = s.values
    return P


def momentum_from_prices(P: np.ndarray, lb: int) -> np.ndarray:
    """Trailing lb-day simple return aligned to each row."""
    out = np.full_like(P, np.nan)
    out[lb:] = P[lb:] / P[:-lb] - 1.0
    return out


def main():
    cache = load_cache()
    DATES = cache["DATES"]
    print(f"[part1] panel dates {DATES[0].date()} .. {DATES[-1].date()} (N={len(DATES)})")
    P = load_price_matrix(DATES)
    nan_frac = np.isnan(P).mean()
    print(f"[part1] price matrix loaded, nan_frac={nan_frac:.4f}")

    # Sanity: baseline with cached M_STABLE
    base = run_strategy_from_cache(cache)
    print(f"[part1] cached baseline: CAGR {base['stats']['cagr']*100:.2f}% "
          f"Sharpe {base['stats']['sharpe']:.2f} DD {base['stats']['max_dd']*100:.2f}%")

    # Sanity: replace M_STABLE with on-the-fly lb=63 mom -> should match baseline
    cache_swap = dict(cache)
    cache_swap["M_STABLE"] = momentum_from_prices(P, 63)
    chk = run_strategy_from_cache(cache_swap)
    print(f"[part1] on-the-fly lb=63: CAGR {chk['stats']['cagr']*100:.2f}% "
          f"Sharpe {chk['stats']['sharpe']:.2f} DD {chk['stats']['max_dd']*100:.2f}%")

    results = []
    for lb in LOOKBACKS:
        cache_swap["M_STABLE"] = momentum_from_prices(P, lb)
        r = run_strategy_from_cache(cache_swap)  # lookback_stable left default -> no rebuild attempt
        s = r["stats"]
        row = dict(lookback=lb, cagr=s["cagr"], sharpe=s["sharpe"], max_dd=s["max_dd"], n=s["n"])
        print(f"  lb={lb:3d}  CAGR {s['cagr']*100:6.2f}%  Sharpe {s['sharpe']:.2f}  "
              f"MaxDD {s['max_dd']*100:6.2f}%")
        results.append(row)

    # Curve shape diagnosis
    sharpes = np.array([r["sharpe"] for r in results])
    cagrs = np.array([r["cagr"] for r in results])
    peak_i = int(np.argmax(sharpes))
    peak_lb = LOOKBACKS[peak_i]
    peak_sh = float(sharpes[peak_i])
    # Look left/right falloff
    left = sharpes[:peak_i]
    right = sharpes[peak_i + 1:]
    left_drop = float(peak_sh - left.min()) if len(left) else 0.0
    right_drop = float(peak_sh - right.min()) if len(right) else 0.0
    # Threshold for "cliff": drop > 0.3 Sharpe
    CLIFF = 0.3
    left_cliff = left_drop >= CLIFF
    right_cliff = right_drop >= CLIFF
    if left_cliff and right_cliff:
        shape = "cliff-both-sides"
    elif left_cliff and not right_cliff:
        shape = "cliff-below-only"
    elif right_cliff and not left_cliff:
        shape = "cliff-above-only"
    else:
        shape = "smooth-plateau"

    # Plateau: contiguous lookbacks whose sharpe is within 0.1 of peak
    plat = [LOOKBACKS[i] for i, s in enumerate(sharpes) if peak_sh - s <= 0.1]

    diag = dict(
        peak_lookback=peak_lb,
        peak_sharpe=peak_sh,
        peak_cagr=float(cagrs[peak_i]),
        left_drop=left_drop,
        right_drop=right_drop,
        shape=shape,
        plateau_within_0p1_sharpe=plat,
        sharpe_min=float(sharpes.min()),
        sharpe_max=float(sharpes.max()),
        sharpe_range=float(sharpes.max() - sharpes.min()),
    )
    print("[part1] diagnosis:", json.dumps(diag, indent=2))

    payload = dict(lookbacks=LOOKBACKS, results=results, diagnosis=diag,
                   baseline_cached_stats=base["stats"])
    OUT_JSON.write_text(json.dumps(payload, indent=2, default=str))
    print(f"[part1] wrote {OUT_JSON}")

    # Plot (best-effort)
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax1 = plt.subplots(figsize=(8, 4.5))
        ax1.plot(LOOKBACKS, [r["sharpe"] for r in results], "o-", color="C0", label="Sharpe")
        ax1.set_xlabel("lookback_stable (days)")
        ax1.set_ylabel("Sharpe", color="C0")
        ax1.axvline(63, color="k", ls="--", alpha=0.4, label="baseline=63")
        ax2 = ax1.twinx()
        ax2.plot(LOOKBACKS, [r["cagr"] * 100 for r in results], "s--", color="C3", label="CAGR %")
        ax2.set_ylabel("CAGR %", color="C3")
        plt.title(f"Lookback sensitivity — shape: {shape}")
        fig.tight_layout()
        fig.savefig(OUT_PNG, dpi=120)
        print(f"[part1] wrote {OUT_PNG}")
    except Exception as e:
        print(f"[part1] plot skipped: {e}")


if __name__ == "__main__":
    main()
