"""TEST 1: Leave-one-out layer ablation."""
from __future__ import annotations
import sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
from _runner import run, default_config, fmt_stats

LAYERS = [f"L{i}" for i in range(1, 11)]


def main():
    # Full stack reference
    cfg_full = default_config()
    stats_full, _ = run(cfg_full)
    print(f"None (full P59): {fmt_stats(stats_full)}")

    rows = [("None", stats_full, 0, 0)]
    for L in LAYERS:
        cfg = default_config()
        cfg[L] = False
        try:
            stats, _ = run(cfg)
        except Exception as e:
            print(f"  {L}: ERROR {e}")
            continue
        d_cagr = (stats["cagr"] - stats_full["cagr"]) * 100
        d_sharpe = stats["sharpe"] - stats_full["sharpe"]
        print(f"  -{L}: {fmt_stats(stats)}  d_cagr={d_cagr:+.2f}pp  d_sharpe={d_sharpe:+.3f}")
        rows.append((L, stats, d_cagr, d_sharpe))

    # Markdown output
    lines = ["# TEST 1 — Leave-one-out layer ablation\n",
             "Full P59 stack: CAGR 30.73% / Sharpe 1.88 / MaxDD -12.66%\n",
             "| Removed | CAGR | Sharpe | MaxDD | Δ CAGR | Δ Sharpe | Verdict |",
             "|---------|------|--------|-------|--------|----------|---------|"]
    for name, s, dc, ds in rows:
        if name == "None":
            verdict = "full stack"
        elif ds < -0.05:
            verdict = "**KEEP** (load-bearing)"
        elif ds < -0.02:
            verdict = "UNCERTAIN"
        elif ds > 0.02:
            verdict = "**REMOVE** (improves without it)"
        else:
            verdict = "REMOVE (dead weight)"
        lines.append(f"| {name} | {s['cagr']*100:.2f}% | {s['sharpe']:.2f} | {s['max_dd']*100:.2f}% | {dc:+.2f} | {ds:+.3f} | {verdict} |")
    out = "\n".join(lines) + "\n"
    with open(HERE / "TEST1_ablation.md", "w", encoding="utf-8") as f:
        f.write(out)
    print("\nSaved TEST1_ablation.md")


if __name__ == "__main__":
    main()
