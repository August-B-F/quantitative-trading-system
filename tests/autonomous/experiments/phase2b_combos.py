"""Phase 2b: combine the two winning directions (drop-overlap universe + top_k=4)
and explore adjacent variants.
"""
from __future__ import annotations
import sys, datetime as dt
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from utils.base_test import run, fmt, haircut_verdict  # noqa: E402

DROPOVERLAP = ["SOXX", "QQQ", "IGV", "XLE", "GLD", "SHY"]
DO_NO_QQQ = ["SOXX", "IGV", "XLE", "GLD", "SHY"]
DO_NO_SOXX = ["QQQ", "IGV", "XLE", "GLD", "SHY"]
DO_NO_IGV = ["SOXX", "QQQ", "XLE", "GLD", "SHY"]
EXPERIMENTS = []

# dropoverlap cross-product with top_k/splits
for k in (2, 3, 4, 5):
    EXPERIMENTS.append((f"P2b.01_do_top{k}", {"universe": DROPOVERLAP, "top_k": k}))

for w1, w3 in [(0.4,0.6),(0.5,0.5),(0.6,0.4),(0.7,0.3),(0.3,0.7)]:
    EXPERIMENTS.append((f"P2b.02_do_split{int(w1*100)}_{int(w3*100)}",
                        {"universe": DROPOVERLAP, "top1_weight": w1, "top3_weight": w3}))

# dropoverlap + k=4 + split variants
for w1, w3 in [(0.4,0.6),(0.6,0.4),(0.7,0.3)]:
    EXPERIMENTS.append((f"P2b.03_do_k4_{int(w1*100)}_{int(w3*100)}",
                        {"universe": DROPOVERLAP, "top_k": 4, "top1_weight": w1, "top3_weight": w3}))

# Further drops from dropoverlap
EXPERIMENTS.append(("P2b.04_do_no_qqq", {"universe": DO_NO_QQQ}))
EXPERIMENTS.append(("P2b.05_do_no_soxx", {"universe": DO_NO_SOXX}))
EXPERIMENTS.append(("P2b.06_do_no_igv", {"universe": DO_NO_IGV}))

# dropoverlap + adds (re-add one non-tech)
for add in ("XLV", "XLI", "XLF", "TLT", "IWM"):
    EXPERIMENTS.append((f"P2b.07_do_add_{add}", {"universe": DROPOVERLAP + [add]}))

# dropoverlap + SMA buffer sweep (maybe diff interaction)
for b in (-0.02, -0.03, -0.05, -0.06, -0.08):
    EXPERIMENTS.append((f"P2b.08_do_sma{int(b*100)}", {"universe": DROPOVERLAP, "sma_gate_buffer": b}))

# dropoverlap + SMA gate off
EXPERIMENTS.append(("P2b.09_do_sma_off", {"universe": DROPOVERLAP, "sma_gate_buffer": -1.0}))

# dropoverlap + transition lookback variants
for lbt in (10, 42):
    EXPERIMENTS.append((f"P2b.10_do_trans{lbt}", {"universe": DROPOVERLAP, "lookback_transition": lbt}))

# dropoverlap + FOMC window tweaks
EXPERIMENTS.append(("P2b.11_do_fomc_p1", {"universe": DROPOVERLAP, "fomc_window_pre": 1}))

# DOUBLE drop: drop VGT/XLK AND drop QQQ+top_k=4 (minimal highest-Sharpe)
EXPERIMENTS.append(("P2b.12_min_k4", {"universe": DO_NO_QQQ, "top_k": 4}))
EXPERIMENTS.append(("P2b.13_min_k3_40_60", {"universe": DO_NO_QQQ, "top1_weight":0.4, "top3_weight":0.6}))


def main():
    log_path = HERE.parent / "LOG.md"
    ts = dt.datetime.now().isoformat(timespec="seconds")
    lines = [f"\n### phase2b_combos  {ts}\n",
             "| name | CAGR | Sharpe | MaxDD | verdict |",
             "|---|---|---|---|---|"]
    for name, ov in EXPERIMENTS:
        try: s = run(ov)
        except Exception as e: s = {"error": str(e)}
        if "error" in s:
            print(name, "ERROR", s["error"])
            lines.append(f"| {name} |  |  |  | ERROR |")
            continue
        passes, _ = haircut_verdict(s)
        v = "PASS" if passes else "fail"
        print(name, fmt(s), v)
        lines.append(f"| {name} | {s['cagr']*100:.2f}% | {s['sharpe']:.2f} | {s['max_dd']*100:.2f}% | {v} |")
    with open(log_path, "a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
