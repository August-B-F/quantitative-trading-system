"""Phase 6b: fine grid around the 0.40 confidence threshold."""
from __future__ import annotations
import sys, datetime as dt, copy, pickle
from pathlib import Path
import numpy as np
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from utils.base_test import _load, _STATE, fmt, haircut_verdict  # noqa: E402
from strategy.portfolio import PortfolioEngine  # noqa: E402
from backtest.engine import run_backtest  # noqa: E402
from features.regime_labels import current_regime as _cr  # noqa: E402

CHAMP = {"universe": ["SOXX","QQQ","IGV","XLE","GLD","SHY"], "top1_weight":0.60, "top3_weight":0.40}
PROBA = HERE.parent / "cache" / "pred_proba.pkl"

def make_gated(pred_reg, maxp, cur_reg, thr):
    out = pred_reg.copy()
    want = (pred_reg != cur_reg) & (pred_reg >= 0)
    lc = np.nan_to_num(maxp, nan=0.0) < thr
    out[want & lc] = cur_reg[want & lc]
    return out


def run_w(pr, ov):
    _load()
    cfg = copy.deepcopy(_STATE["cfg"]); cfg.update(ov or {})
    engine = PortfolioEngine(_STATE["bundle"], pr, cfg)
    return run_backtest(engine, _STATE["test_dates"], cfg).stats


def main():
    with open(PROBA, "rb") as f:
        pred_reg, maxp = pickle.load(f)
    _load()
    cur = np.asarray(_cr(_STATE["bundle"].df).index)

    log_path = HERE.parent / "LOG.md"
    ts = dt.datetime.now().isoformat(timespec="seconds")
    lines = [f"\n### phase6b_gate_microgrid  {ts}\n",
             "| name | CAGR | Sharpe | MaxDD | verdict |","|---|---|---|---|---|"]

    experiments = []
    # Fine threshold sweep on champion
    for t in (0.36, 0.37, 0.38, 0.39, 0.40, 0.41, 0.42, 0.43, 0.44):
        experiments.append((f"P6b.01_t{int(t*100)}_champ", make_gated(pred_reg, maxp, cur, t), CHAMP))
    # Also on baseline for attribution
    for t in (0.38, 0.40, 0.42):
        experiments.append((f"P6b.02_t{int(t*100)}_base", make_gated(pred_reg, maxp, cur, t), {}))
    # Gate40 × split variants on dropoverlap
    for w in (0.55, 0.58, 0.62, 0.65, 0.68):
        ov = {"universe": CHAMP["universe"], "top1_weight": w, "top3_weight": 1-w}
        experiments.append((f"P6b.03_t40_w{int(w*100)}", make_gated(pred_reg, maxp, cur, 0.40), ov))
    # Gate40 × top_k variants
    for k in (2, 4, 5):
        ov = dict(CHAMP); ov["top_k"] = k
        experiments.append((f"P6b.04_t40_k{k}", make_gated(pred_reg, maxp, cur, 0.40), ov))

    for name, pr, ov in experiments:
        try: s = run_w(pr, ov)
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
