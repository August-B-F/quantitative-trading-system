"""TEST 4: Parameter neighborhood test.

For each tuned parameter in P59, test 5 nearby values (about -40%, -20%, base, +20%, +40%).
If performance is smooth (all nearby values still improve over no-layer baseline), the
parameter is in a robust region. If only the exact tested value helps: overfit.
"""
from __future__ import annotations
import sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
import numpy as np
from _runner import run, default_config, fmt_stats


def full_sharpe(cfg):
    s, _ = run(cfg)
    return s["sharpe"], s["cagr"]


def full_cagr_sharpe(cfg):
    s, _ = run(cfg)
    return s["cagr"] * 100, s["sharpe"]


def main():
    # Baseline full stack
    s_full, c_full = full_sharpe(default_config())
    print(f"Full P59: cagr={c_full*100:.2f} sharpe={s_full:.3f}")
    print()

    # Also compute the "no-layer" baseline for each param — the full stack with ONLY
    # that layer off. This is what Test 1 did. We'll use Test 1 numbers for reference.
    no_layer = {}
    for L in [f"L{i}" for i in range(1, 11)]:
        cfg_off = default_config()
        cfg_off[L] = False
        s_off, _ = full_sharpe(cfg_off)
        no_layer[L] = s_off

    tests = []
    # L2: top1 split (base 0.62, neighborhood 0.50, 0.55, 0.62, 0.68, 0.75)
    tests.append(("L2_top1", "L2", [0.50, 0.55, 0.62, 0.68, 0.75], "L2_top1"))
    # L3: gate threshold (base 0.40, neighborhood 0.24, 0.32, 0.40, 0.48, 0.56)
    tests.append(("L3_gate", "L3", [0.24, 0.32, 0.40, 0.48, 0.56], "L3_gate"))
    # L4: 63d weight in rank agg (base 3, neighborhood 1.8, 2.4, 3.0, 3.6, 4.2)
    # Encoded as L4_weights override
    tests.append(("L4_63d_weight", "L4", [1.8, 2.4, 3.0, 3.6, 4.2], "L4_weights_63"))
    # L4: 42d weight (base 1, neighborhood 0.6, 0.8, 1.0, 1.2, 1.4)
    tests.append(("L4_42d_weight", "L4", [0.6, 0.8, 1.0, 1.2, 1.4], "L4_weights_42"))
    # L4: 126d weight (base 1, neighborhood 0.6, 0.8, 1.0, 1.2, 1.4)
    tests.append(("L4_126d_weight", "L4", [0.6, 0.8, 1.0, 1.2, 1.4], "L4_weights_126"))
    # L5: tier threshold (base 0.50, neighborhood 0.30, 0.40, 0.50, 0.60, 0.70)
    tests.append(("L5_tier", "L5", [0.30, 0.40, 0.50, 0.60, 0.70], "L5_tier"))
    # L7: fomc_post (base 1, neighborhood 0, 1, 2, 3)
    tests.append(("L7_fomc_post", "L7", [0, 1, 2, 3], "L7_post"))
    # L7: fomc_defer (base 4, neighborhood 2, 3, 4, 5, 6)
    tests.append(("L7_fomc_defer", "L7", [2, 3, 4, 5, 6], "L7_defer"))
    # L8: dd_thr (base -0.02, neighborhood -0.04, -0.03, -0.02, -0.01, 0)
    tests.append(("L8_dd_thr", "L8", [-0.04, -0.03, -0.02, -0.01, 0.0], "L8_dd_thr"))
    # L8: w_dd (base 0.40, neighborhood 0.30, 0.35, 0.40, 0.45, 0.55)
    tests.append(("L8_w_dd", "L8", [0.30, 0.35, 0.40, 0.45, 0.55], "L8_wdd"))
    # L9: boost_thr (base 0.30, neighborhood 0.15, 0.22, 0.30, 0.37, 0.45)
    tests.append(("L9_boost_thr", "L9", [0.15, 0.22, 0.30, 0.37, 0.45], "L9_boost_thr"))
    # L9: spy_thr (base 0.12, neighborhood 0.06, 0.09, 0.12, 0.15, 0.18)
    tests.append(("L9_spy_thr", "L9", [0.06, 0.09, 0.12, 0.15, 0.18], "L9_spy_thr"))
    # L9: w_full (base 0.82, neighborhood 0.62, 0.72, 0.82, 0.88, 0.92)
    tests.append(("L9_w_full", "L9", [0.62, 0.72, 0.82, 0.88, 0.92], "L9_wfull"))
    # L10: warm_thr (0.15, 0.20, 0.25, 0.30, 0.35)
    tests.append(("L10_warm_thr", "L10", [0.15, 0.20, 0.25, 0.30, 0.35], "L10_warm_thr"))
    # L10: w_warm (base 0.70, nb 0.62, 0.66, 0.70, 0.74, 0.78)
    tests.append(("L10_w_warm", "L10", [0.62, 0.66, 0.70, 0.74, 0.78], "L10_wwarm"))

    rows = []
    for tname, L, vals, key in tests:
        series = []
        for v in vals:
            cfg = default_config()
            if key == "L2_top1":
                cfg["L2_top1"] = v
            elif key == "L3_gate":
                cfg["L3_gate"] = v
            elif key == "L4_weights_63":
                cfg["L4_weights"] = [(42, 1), (63, v), (126, 1)]
            elif key == "L4_weights_42":
                cfg["L4_weights"] = [(42, v), (63, 3), (126, 1)]
            elif key == "L4_weights_126":
                cfg["L4_weights"] = [(42, 1), (63, 3), (126, v)]
            elif key == "L5_tier":
                cfg["L5_tier"] = v
            elif key == "L7_post":
                cfg["L7_fomc"] = (0, int(v), 4)
            elif key == "L7_defer":
                cfg["L7_fomc"] = (0, 1, int(v))
            elif key == "L8_dd_thr":
                cfg["L8_dd_thr"] = v
            elif key == "L8_wdd":
                cfg["L8_wdd"] = v
            elif key == "L9_boost_thr":
                cfg["L9_boost_thr"] = v
            elif key == "L9_spy_thr":
                cfg["L9_spy_thr"] = v
            elif key == "L9_wfull":
                cfg["L9_wfull"] = v
            elif key == "L10_warm_thr":
                cfg["L10_warm_thr"] = v
            elif key == "L10_wwarm":
                cfg["L10_wwarm"] = v
            s, c = full_sharpe(cfg)
            series.append((v, s, c))
        ref = no_layer[L]
        # Count how many of the values give Sharpe above the no-layer reference
        count_above = sum(1 for _, s, _ in series if s > ref)
        smooth = "smooth" if count_above == len(series) else f"not smooth ({count_above}/{len(series)})"
        vals_str = "  ".join(f"{v:>6}:{s:.3f}" for v, s, _ in series)
        print(f"{tname:>18} (no-{L} ref Sharpe {ref:.3f}): {vals_str}  -> {smooth}")
        rows.append((tname, L, ref, series, count_above, smooth))

    # Markdown
    lines = ["# TEST 4 — Parameter neighborhood test\n",
             f"Full P59: Sharpe {s_full:.3f}, CAGR {c_full*100:.2f}%\n",
             "For each tuned parameter, we test 5 nearby values. 'Smooth' = all 5 values still improve Sharpe over the no-L variant from Test 1.\n",
             "| Param | Layer | No-L ref | Values (sharpe) | Above-ref count | Smooth? |",
             "|-------|-------|----------|-----------------|-----------------|---------|"]
    for tname, L, ref, series, cnt, smooth in rows:
        vstr = " / ".join(f"{v}→{s:.3f}" for v, s, _ in series)
        lines.append(f"| {tname} | {L} | {ref:.3f} | {vstr} | {cnt}/{len(series)} | {smooth} |")
    out = "\n".join(lines) + "\n"
    with open(HERE / "TEST4_parameter_neighborhood.md", "w", encoding="utf-8") as f:
        f.write(out)
    print("\nSaved TEST4_parameter_neighborhood.md")


if __name__ == "__main__":
    main()
