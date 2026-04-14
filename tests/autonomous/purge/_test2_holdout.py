"""TEST 2: Forward walk holdout — each layer's effect on Period A (2010-2017) vs B (2018-2026)."""
from __future__ import annotations
import sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
import numpy as np, pandas as pd
from _runner import run, default_config, fmt_stats
from backtest.engine import compute_stats

LAYERS = [f"L{i}" for i in range(1, 11)]


def half_sharpe(monthly):
    fh = monthly[monthly.index.year < 2018]
    sh = monthly[monthly.index.year >= 2018]
    fh_s = compute_stats(fh.values) if len(fh) else None
    sh_s = compute_stats(sh.values) if len(sh) else None
    return fh_s, sh_s


def main():
    # Full stack baseline per half
    cfg_full = default_config()
    stats_full, m_full = run(cfg_full)
    fh_full, sh_full = half_sharpe(m_full)
    print(f"Full P59   per-half Sharpe  A={fh_full['sharpe']:.3f}  B={sh_full['sharpe']:.3f}")

    rows = []
    for L in LAYERS:
        cfg = default_config()
        cfg[L] = False
        try:
            stats, monthly = run(cfg)
        except Exception as e:
            print(f"  -{L}: ERROR {e}")
            continue
        fh, sh = half_sharpe(monthly)
        dA = fh_full["sharpe"] - fh["sharpe"]   # how much does removing the layer hurt A?
        dB = sh_full["sharpe"] - sh["sharpe"]   # how much does removing the layer hurt B?
        # If both dA > 0 and dB > 0: layer helps BOTH halves → survives
        # If one is negative: layer hurts that half → overfit in the other
        if dA > 0 and dB > 0:
            verdict = "**KEEP** — helps both"
        elif dA > 0 and dB <= 0:
            verdict = "REMOVE — only helps A (2010-2017)"
        elif dA <= 0 and dB > 0:
            verdict = "REMOVE — only helps B (2018-2026)"
        else:
            verdict = "REMOVE — helps neither"
        print(f"  -{L}: A Sharpe {fh['sharpe']:.3f} (delta vs full: +{dA:.3f})  B Sharpe {sh['sharpe']:.3f} (delta: +{dB:.3f})  {verdict}")
        rows.append((L, fh["sharpe"], sh["sharpe"], dA, dB, verdict))

    # Markdown output
    lines = ["# TEST 2 — Forward walk holdout per layer\n",
             f"Full stack per-half Sharpe: A (2010-17) {fh_full['sharpe']:.3f}, B (2018-26) {sh_full['sharpe']:.3f}\n",
             "`dA = full_A_sharpe - variant_A_sharpe` — positive means the layer helps Period A.\n",
             "| Layer | A Sharpe (no-L) | B Sharpe (no-L) | dA | dB | Both positive? | Verdict |",
             "|-------|-----------------|-----------------|----|----|----------------|---------|"]
    for L, a, b, dA, dB, v in rows:
        both = "yes" if dA > 0 and dB > 0 else "no"
        lines.append(f"| {L} | {a:.3f} | {b:.3f} | {dA:+.3f} | {dB:+.3f} | {both} | {v} |")
    out = "\n".join(lines) + "\n"
    with open(HERE / "TEST2_holdout.md", "w", encoding="utf-8") as f:
        f.write(out)
    print("\nSaved TEST2_holdout.md")


if __name__ == "__main__":
    main()
