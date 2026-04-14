"""Phase 1: easy parameter sweeps that don't require re-training the classifier.

All variants reuse the cached walk-forward predictions. Baseline champion:
23.61% / 1.50 / -12.94%.
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from utils.base_test import run, fmt, haircut_verdict, CHAMPION  # noqa: E402


EXPERIMENTS = []

# --- baseline sanity ---
EXPERIMENTS.append(("P1.00_baseline", {}))

# --- top_k variants ---
for k in (2, 3, 4, 5):
    EXPERIMENTS.append((f"P1.01_top{k}", {"top_k": k}))

# --- top1/topk split ratios (k=3) ---
for w1, w3 in [(0.4, 0.6), (0.5, 0.5), (0.6, 0.4), (0.7, 0.3), (0.3, 0.7), (0.0, 1.0), (1.0, 0.0)]:
    EXPERIMENTS.append((f"P1.02_split_{int(w1*100)}_{int(w3*100)}", {"top1_weight": w1, "top3_weight": w3}))

# --- SMA buffer sweep ---
for b in (-0.02, -0.03, -0.04, -0.05, -0.06, -0.08, -0.10, 0.0):
    EXPERIMENTS.append((f"P1.03_sma{int(b*100)}", {"sma_gate_buffer": b}))

# --- SMA gate disabled ---
EXPERIMENTS.append(("P1.04_sma_off", {"sma_gate_buffer": -1.0}))  # never fires

# --- Transition lookback variants (stable fixed at 63 — non-negotiable) ---
for lbt in (10, 21, 42):
    EXPERIMENTS.append((f"P1.05_trans{lbt}", {"lookback_transition": lbt}))

# --- FOMC window variants ---
for pre, post, days in [
    (0, 2, 3),    # baseline
    (0, 1, 3),
    (0, 3, 3),
    (0, 2, 2),
    (0, 2, 4),
    (0, 2, 5),
    (1, 2, 3),
    (2, 2, 3),
]:
    EXPERIMENTS.append((f"P1.06_fomc_p{pre}a{post}d{days}", {
        "fomc_window_pre": pre, "fomc_window_after": post, "fomc_defer_days": days,
    }))

# --- FOMC defer off ---
EXPERIMENTS.append(("P1.07_fomc_off", {"fomc_defer_enabled": False}))


def main():
    log_path = HERE.parent / "LOG.md"
    import datetime as dt
    ts = dt.datetime.now().isoformat(timespec="seconds")
    lines = [f"\n### phase1_basic_sweeps  {ts}\n"]
    lines.append("| name | CAGR | Sharpe | MaxDD | verdict |")
    lines.append("|---|---|---|---|---|")

    for name, ov in EXPERIMENTS:
        s = run(ov)
        if "error" in s:
            line = f"| {name} |  |  |  | ERROR {s['error']} |"
            print(name, "ERROR", s["error"])
            lines.append(line)
            continue
        passes, _ = haircut_verdict(s)
        v = "PASS" if passes else "fail"
        line = f"| {name} | {s['cagr']*100:.2f}% | {s['sharpe']:.2f} | {s['max_dd']*100:.2f}% | {v} |"
        print(name, fmt(s), v)
        lines.append(line)

    with open(log_path, "a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
