"""Phase 5: transaction costs on champion, drop_QQQ combos, and a tiny adaptive sizing test."""
from __future__ import annotations
import sys, datetime as dt, copy
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from utils.base_test import _load, _STATE, fmt, haircut_verdict  # noqa: E402
from strategy.portfolio import PortfolioEngine  # noqa: E402
from backtest.engine import run_backtest  # noqa: E402

BASE_UNI = ["SOXX","QQQ","XLK","VGT","IGV","XLE","GLD","SHY"]
DROPOVERLAP = ["SOXX","QQQ","IGV","XLE","GLD","SHY"]

CHAMP = {"universe": DROPOVERLAP, "top1_weight":0.60, "top3_weight":0.40}


def run_cost(ov, cost_bps):
    _load()
    cfg = copy.deepcopy(_STATE["cfg"]); cfg.update(ov or {})
    engine = PortfolioEngine(_STATE["bundle"], _STATE["pred_reg"], cfg)
    res = run_backtest(engine, _STATE["test_dates"], cfg, cost_bps=cost_bps)
    return res.stats


def main():
    log_path = HERE.parent / "LOG.md"
    ts = dt.datetime.now().isoformat(timespec="seconds")
    lines = [f"\n### phase5_cost_and_more  {ts}\n",
             "| name | CAGR | Sharpe | MaxDD | verdict |",
             "|---|---|---|---|---|"]

    experiments = []
    # Transaction cost sensitivity (champion vs baseline)
    for c in (0, 5, 10, 20, 30):
        experiments.append((f"P5.01_base_cost{c}", {}, c))
        experiments.append((f"P5.02_champ_cost{c}", CHAMP, c))

    # drop QQQ with 60/40
    experiments.append(("P5.03_dropQQQ_60_40",
                        {"universe": [t for t in BASE_UNI if t != "QQQ"], "top1_weight":0.60, "top3_weight":0.40}, 0))
    # drop QQQ + dropoverlap flavors
    experiments.append(("P5.04_do_noQQQ_60_40",
                        {"universe": ["SOXX","IGV","XLE","GLD","SHY"], "top1_weight":0.60, "top3_weight":0.40}, 0))
    experiments.append(("P5.05_do_noQQQ_50_50",
                        {"universe": ["SOXX","IGV","XLE","GLD","SHY"]}, 0))

    for name, ov, c in experiments:
        try: s = run_cost(ov, c)
        except Exception as e: s = {"error": str(e)}
        if "error" in s:
            print(name, "ERROR", s["error"])
            lines.append(f"| {name} | | | | ERR |"); continue
        passes, _ = haircut_verdict(s)
        v = "PASS" if passes else "fail"
        print(name, fmt(s), v)
        lines.append(f"| {name} | {s['cagr']*100:.2f}% | {s['sharpe']:.2f} | {s['max_dd']*100:.2f}% | {v} |")
    with open(log_path, "a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
