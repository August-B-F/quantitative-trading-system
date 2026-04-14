"""TEST 5: Rebuild from scratch.

Start from canonical baseline. Add layers back one at a time in order of
Test 1 Sharpe impact, but only layers that showed signs of life in Tests 1-4.
After each addition, verify the layer STILL helps on top of current stack.
"""
from __future__ import annotations
import sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
from _runner import run, default_config, canonical_config, fmt_stats
from backtest.engine import compute_stats

# Rebuild order: Test 1 Sharpe-loss magnitude from largest to smallest,
# excluding L2 (improves when off) and L10 (noise per Test 3). L7 removed
# per Test 4 fragile. Others included for re-evaluation in stack context.
REBUILD_ORDER = ["L1", "L4", "L6", "L5", "L3", "L9", "L8"]


def main():
    cfg = canonical_config()
    s_base, _ = run(cfg)
    print(f"Canonical baseline: {fmt_stats(s_base)}")

    current = "baseline"
    current_cfg = dict(cfg)  # shallow copy
    history = [("baseline", s_base)]

    lines = ["# TEST 5 — Rebuild from scratch\n",
             "Start from canonical baseline and add layers one at a time.\n"
             "Add order: Test 1 Sharpe-loss magnitude (biggest first), skipping\n"
             "already-rejected layers (L2, L7, L10).\n"
             "After each addition, check if the layer still helps on top of the\n"
             "accumulating stack.\n",
             "| Step | Layer added | CAGR | Sharpe | MaxDD | Keep? |",
             "|------|-------------|------|--------|-------|-------|"]
    lines.append(f"| 0 | (baseline) | {s_base['cagr']*100:.2f}% | {s_base['sharpe']:.3f} | {s_base['max_dd']*100:.2f}% | -- |")

    prev_sharpe = s_base["sharpe"]
    accepted = set()
    for L in REBUILD_ORDER:
        trial_cfg = dict(current_cfg)
        trial_cfg[L] = True
        s, _ = run(trial_cfg)
        d = s["sharpe"] - prev_sharpe
        keep = d > 0.005  # tiny tolerance
        verdict = "KEEP" if keep else "DROP"
        print(f"  try +{L}: {fmt_stats(s)}  dSharpe={d:+.3f}  -> {verdict}")
        lines.append(f"| +{L} | {L} | {s['cagr']*100:.2f}% | {s['sharpe']:.3f} | {s['max_dd']*100:.2f}% | {verdict} |")
        if keep:
            current_cfg = trial_cfg
            prev_sharpe = s["sharpe"]
            accepted.add(L)
            history.append((f"+{L}", s))

    final_s, _ = run(current_cfg)
    print(f"\nFinal robust stack: {sorted(accepted)}")
    print(f"Final stats: {fmt_stats(final_s)}")

    lines.append("")
    lines.append(f"## Final robust stack: {sorted(accepted)}")
    lines.append(f"Stats: CAGR {final_s['cagr']*100:.2f}%, Sharpe {final_s['sharpe']:.3f}, MaxDD {final_s['max_dd']*100:.2f}%")
    lines.append("")
    # Compare to full and canonical
    full_s, _ = run(default_config())
    lines.append(f"- Canonical baseline: {s_base['cagr']*100:.2f}% / {s_base['sharpe']:.3f} / {s_base['max_dd']*100:.2f}%")
    lines.append(f"- Robust stack:       {final_s['cagr']*100:.2f}% / {final_s['sharpe']:.3f} / {final_s['max_dd']*100:.2f}%")
    lines.append(f"- Full P59 stack:     {full_s['cagr']*100:.2f}% / {full_s['sharpe']:.3f} / {full_s['max_dd']*100:.2f}%")

    with open(HERE / "TEST5_rebuild.md", "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    # Save the robust config for Test 6 comparison
    import json
    with open(HERE / "_robust_cfg.json", "w", encoding="utf-8") as f:
        clean = {k: v for k, v in current_cfg.items() if not isinstance(v, list)}
        json.dump({"accepted": sorted(accepted), "cfg_layers": [k for k in current_cfg if k.startswith("L") and len(k) <= 3 and current_cfg[k] is True]}, f, indent=2)
    print("\nSaved TEST5_rebuild.md and _robust_cfg.json")


if __name__ == "__main__":
    main()
