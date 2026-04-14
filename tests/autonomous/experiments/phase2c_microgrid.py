"""Phase 2c: fine grid around current champion to see if we can push further.
Current: dropoverlap + 60/40 split.
"""
from __future__ import annotations
import sys, datetime as dt
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from utils.base_test import run, fmt, haircut_verdict  # noqa: E402

DROPOVERLAP = ["SOXX", "QQQ", "IGV", "XLE", "GLD", "SHY"]
EXPERIMENTS = []

# fine split grid around 60/40 on dropoverlap
for w1 in (0.55, 0.58, 0.60, 0.62, 0.65, 0.68):
    EXPERIMENTS.append((f"P2c.01_do_w1_{int(w1*100)}", {
        "universe": DROPOVERLAP, "top1_weight": w1, "top3_weight": 1.0 - w1
    }))

# fine SMA buffer x split 60/40 on dropoverlap
for b in (-0.03, -0.04, -0.05, -0.06):
    EXPERIMENTS.append((f"P2c.02_do_60_sma{int(b*100)}", {
        "universe": DROPOVERLAP, "top1_weight": 0.60, "top3_weight": 0.40,
        "sma_gate_buffer": b
    }))

# add XLF/IWM (adjacent wins) with 60/40
for add in ("XLF", "IWM"):
    EXPERIMENTS.append((f"P2c.03_do_60_add_{add}", {
        "universe": DROPOVERLAP + [add], "top1_weight": 0.60, "top3_weight": 0.40
    }))

# top_k variants on 60/40
for k in (2, 4, 5):
    EXPERIMENTS.append((f"P2c.04_do_60_top{k}", {
        "universe": DROPOVERLAP, "top_k": k, "top1_weight": 0.60, "top3_weight": 0.40
    }))

# FOMC pre=1 with champion
EXPERIMENTS.append(("P2c.05_do_60_fomc_p1", {
    "universe": DROPOVERLAP, "top1_weight": 0.60, "top3_weight": 0.40, "fomc_window_pre": 1
}))
# FOMC defer_days variants
for d in (2, 4, 5):
    EXPERIMENTS.append((f"P2c.06_do_60_def{d}", {
        "universe": DROPOVERLAP, "top1_weight": 0.60, "top3_weight": 0.40, "fomc_defer_days": d
    }))

# champion + transition lookback 42 (known loss) as sanity
# already tested; skip

# 63-only (disable classifier by forcing lookback_transition = 63)
EXPERIMENTS.append(("P2c.07_do_60_63only", {
    "universe": DROPOVERLAP, "top1_weight": 0.60, "top3_weight": 0.40, "lookback_transition": 63
}))


def main():
    log_path = HERE.parent / "LOG.md"
    ts = dt.datetime.now().isoformat(timespec="seconds")
    lines = [f"\n### phase2c_microgrid  {ts}\n",
             "| name | CAGR | Sharpe | MaxDD | verdict |",
             "|---|---|---|---|---|"]
    for name, ov in EXPERIMENTS:
        try: s = run(ov)
        except Exception as e: s = {"error": str(e)}
        if "error" in s:
            print(name, "ERROR", s["error"]); lines.append(f"| {name} | | | | ERR |"); continue
        passes, _ = haircut_verdict(s)
        v = "PASS" if passes else "fail"
        print(name, fmt(s), v)
        lines.append(f"| {name} | {s['cagr']*100:.2f}% | {s['sharpe']:.2f} | {s['max_dd']*100:.2f}% | {v} |")
    with open(log_path, "a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

if __name__ == "__main__":
    main()
