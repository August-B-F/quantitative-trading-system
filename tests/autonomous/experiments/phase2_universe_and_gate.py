"""Phase 2: universe mods, SMA index swaps, combinations of Phase-1 winners.

Available extras: TLT, DBC, XLF, XLI, XLV, AGG, EEM, IWM (plus SPY) — all have
precomputed returns/atr/fwd21 in the panel.
"""
from __future__ import annotations
import sys, datetime as dt
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from utils.base_test import run, fmt, haircut_verdict  # noqa: E402


BASE_UNI = ["SOXX", "QQQ", "XLK", "VGT", "IGV", "XLE", "GLD", "SHY"]
EXPERIMENTS = []

# --- Drop one tech ETF at a time ---
TECHS = ["SOXX", "QQQ", "XLK", "VGT", "IGV"]
for drop in TECHS:
    uni = [t for t in BASE_UNI if t != drop]
    EXPERIMENTS.append((f"P2.01_drop_{drop}", {"universe": uni}))

# --- Add one non-tech ETF at a time ---
for add in ["TLT", "DBC", "XLF", "XLI", "XLV", "EEM", "IWM"]:
    uni = BASE_UNI + [add]
    EXPERIMENTS.append((f"P2.02_add_{add}", {"universe": uni}))

# --- Minimal universe: tech/energy/gold/cash ---
EXPERIMENTS.append(("P2.03_min4", {"universe": ["SOXX", "XLE", "GLD", "SHY"]}))
EXPERIMENTS.append(("P2.03_min5", {"universe": ["SOXX", "QQQ", "XLE", "GLD", "SHY"]}))

# --- Drop VGT + XLK (tech overlap) ---
EXPERIMENTS.append(("P2.04_dropoverlap", {"universe": ["SOXX", "QQQ", "IGV", "XLE", "GLD", "SHY"]}))
# --- Replace SOXX with IGV-only ---
EXPERIMENTS.append(("P2.05_no_soxx", {"universe": ["QQQ", "XLK", "VGT", "IGV", "XLE", "GLD", "SHY"]}))

# --- SMA gate index swaps ---
for idx in ("QQQ", "EEM", "IWM"):
    EXPERIMENTS.append((f"P2.06_sma_on_{idx}", {"sma_gate_index": idx}))

# --- Combined winners: top_k=4 + fomc pre=1 ---
EXPERIMENTS.append(("P2.07_top4_fomc_p1", {"top_k": 4, "fomc_window_pre": 1}))
EXPERIMENTS.append(("P2.08_top4_split60_40", {"top_k": 4, "top1_weight": 0.6, "top3_weight": 0.4}))
EXPERIMENTS.append(("P2.09_top4_split40_60", {"top_k": 4, "top1_weight": 0.4, "top3_weight": 0.6}))

# --- top_k=4 with universe variants ---
EXPERIMENTS.append(("P2.10_top4_dropoverlap", {"top_k": 4, "universe": ["SOXX","QQQ","IGV","XLE","GLD","SHY"]}))
EXPERIMENTS.append(("P2.11_top4_add_XLV", {"top_k": 4, "universe": BASE_UNI + ["XLV"]}))
EXPERIMENTS.append(("P2.12_top4_add_TLT", {"top_k": 4, "universe": BASE_UNI + ["TLT"]}))

# --- top_k=5 with broader uni ---
EXPERIMENTS.append(("P2.13_top5_broad", {"top_k": 5, "universe": BASE_UNI + ["XLV", "TLT"]}))

# --- SMA on QQQ + top_k=4 combo ---
EXPERIMENTS.append(("P2.14_top4_smaQQQ", {"top_k": 4, "sma_gate_index": "QQQ"}))


def main():
    log_path = HERE.parent / "LOG.md"
    ts = dt.datetime.now().isoformat(timespec="seconds")
    lines = [f"\n### phase2_universe_and_gate  {ts}\n",
             "| name | CAGR | Sharpe | MaxDD | verdict |",
             "|---|---|---|---|---|"]
    for name, ov in EXPERIMENTS:
        try:
            s = run(ov)
        except Exception as e:
            s = {"error": str(e)}
        if "error" in s:
            print(name, "ERROR", s["error"])
            lines.append(f"| {name} |  |  |  | ERROR {s['error'][:40]} |")
            continue
        passes, _ = haircut_verdict(s)
        v = "PASS" if passes else "fail"
        print(name, fmt(s), v)
        lines.append(f"| {name} | {s['cagr']*100:.2f}% | {s['sharpe']:.2f} | {s['max_dd']*100:.2f}% | {v} |")
    with open(log_path, "a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
