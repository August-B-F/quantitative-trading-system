"""TEST 6: Bootstrap comparison of canonical / robust / full P59."""
from __future__ import annotations
import sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
import numpy as np, pandas as pd
from _runner import run, default_config, canonical_config, fmt_stats


def boot_edge(strategy_m, base_m, label, n_iter=10000):
    df = pd.DataFrame({"s": strategy_m, "b": base_m}).dropna()
    diff = (df["s"] - df["b"]).values
    mean = diff.mean(); std = diff.std(ddof=1)
    t = mean / (std / np.sqrt(len(diff)))
    rng = np.random.default_rng(42)
    n = len(diff)
    bs = np.array([diff[rng.integers(0, n, n)].mean() for _ in range(n_iter)])
    p_pos = (bs > 0).mean() * 100
    lo, hi = np.percentile(bs, [2.5, 97.5])
    return dict(label=label, n=n, mean_mo=mean * 100,
                t=t, p_pos=p_pos,
                ci_lo_ann=((1 + lo) ** 12 - 1) * 100,
                ci_hi_ann=((1 + hi) ** 12 - 1) * 100,
                mean_ann=((1 + mean) ** 12 - 1) * 100)


def main():
    # Canonical
    stats_b, m_b = run(canonical_config())
    # Full P59
    stats_full, m_full = run(default_config())
    # Robust stack (from Test 5)
    robust_cfg = canonical_config()
    for L in ["L1", "L3", "L4", "L5", "L6", "L9"]:
        robust_cfg[L] = True
    stats_rob, m_rob = run(robust_cfg)

    print(f"Canonical  : {fmt_stats(stats_b)}")
    print(f"Robust     : {fmt_stats(stats_rob)}")
    print(f"Full P59   : {fmt_stats(stats_full)}")
    print()

    e_rob = boot_edge(m_rob, m_b, "Robust vs baseline")
    e_full = boot_edge(m_full, m_b, "Full P59 vs baseline")
    e_rob_vs_full = boot_edge(m_rob, m_full, "Robust vs Full P59")

    for e in (e_rob, e_full, e_rob_vs_full):
        print(f"{e['label']}: t={e['t']:+.3f}  P(edge>0)={e['p_pos']:.2f}%  "
              f"mean_ann={e['mean_ann']:+.2f}pp  CI ann [{e['ci_lo_ann']:+.2f}, {e['ci_hi_ann']:+.2f}]")

    lines = ["# TEST 6 — Bootstrap comparison\n",
             "| Strategy | CAGR | Sharpe | MaxDD |",
             "|----------|------|--------|-------|",
             f"| Canonical | {stats_b['cagr']*100:.2f}% | {stats_b['sharpe']:.3f} | {stats_b['max_dd']*100:.2f}% |",
             f"| **Robust** | **{stats_rob['cagr']*100:.2f}%** | **{stats_rob['sharpe']:.3f}** | **{stats_rob['max_dd']*100:.2f}%** |",
             f"| Full P59 | {stats_full['cagr']*100:.2f}% | {stats_full['sharpe']:.3f} | {stats_full['max_dd']*100:.2f}% |",
             "",
             "## Paired bootstrap (10,000 iterations, 188-month sample)",
             "",
             "| Comparison | t-stat | P(edge>0) | Mean ann edge | 95% CI ann |",
             "|------------|--------|-----------|---------------|------------|"]
    for e in (e_rob, e_full, e_rob_vs_full):
        lines.append(f"| {e['label']} | {e['t']:+.3f} | {e['p_pos']:.2f}% | {e['mean_ann']:+.2f}pp/yr | [{e['ci_lo_ann']:+.2f}, {e['ci_hi_ann']:+.2f}] pp/yr |")

    lines.append("")
    lines.append("## Interpretation")
    lines.append("")
    if e_rob["ci_lo_ann"] > 0:
        lines.append(f"- **Robust stack has statistically significant forward edge** over baseline (95% CI lower bound {e_rob['ci_lo_ann']:+.2f}pp/yr).")
    else:
        lines.append("- Robust stack CI lower bound includes zero — edge not statistically significant at 95%.")
    # Full vs robust
    if e_rob_vs_full["t"] > 0 and e_rob_vs_full["p_pos"] > 95:
        lines.append("- **Robust STRICTLY dominates Full P59** on bootstrap — the stripped layers actively hurt.")
    elif e_rob_vs_full["t"] > 0:
        lines.append("- Robust edges out Full P59 on mean, but not significantly — layers stripped were mostly noise.")
    elif abs(e_rob_vs_full["t"]) < 1.0:
        lines.append("- Robust and Full P59 are statistically indistinguishable — stripped layers added nothing real.")
    else:
        lines.append("- Full P59 slightly beats Robust on bootstrap mean, but the gap is small.")

    with open(HERE / "TEST6_bootstrap.md", "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("\nSaved TEST6_bootstrap.md")


if __name__ == "__main__":
    main()
