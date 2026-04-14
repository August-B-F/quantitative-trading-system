"""Phase 7: sub-period robustness of the new champion (gate40 + dropoverlap + 62/38)."""
from __future__ import annotations
import sys, datetime as dt, copy, pickle
from pathlib import Path
import numpy as np
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from utils.base_test import _load, _STATE, fmt  # noqa: E402
from strategy.portfolio import PortfolioEngine  # noqa: E402
from backtest.engine import run_backtest  # noqa: E402
from features.regime_labels import current_regime as _cr  # noqa: E402

CHAMP = {"universe": ["SOXX","QQQ","IGV","XLE","GLD","SHY"], "top1_weight":0.62, "top3_weight":0.38}
PROBA = HERE.parent / "cache" / "pred_proba.pkl"

SUBPERIODS = [
    ("full", None, None),
    ("2010_2015", "2010-01-01", "2015-12-31"),
    ("2016_2020", "2016-01-01", "2020-12-31"),
    ("2021_2026", "2021-01-01", "2026-12-31"),
]


def get_gated_pred(thr=0.40):
    with open(PROBA, "rb") as f:
        pred_reg, maxp = pickle.load(f)
    _load()
    cur = np.asarray(_cr(_STATE["bundle"].df).index)
    out = pred_reg.copy()
    want = (pred_reg != cur) & (pred_reg >= 0)
    low = np.nan_to_num(maxp, nan=0.0) < thr
    out[want & low] = cur[want & low]
    return out


def run_w(pr, ov, st, en):
    _load()
    cfg = copy.deepcopy(_STATE["cfg"]); cfg.update(ov or {})
    engine = PortfolioEngine(_STATE["bundle"], pr, cfg)
    res = run_backtest(engine, _STATE["test_dates"], cfg, start=st, end=en)
    return res.stats


def main():
    gated = get_gated_pred(0.40)
    _load()
    base_pred = _STATE["pred_reg"]

    log_path = HERE.parent / "LOG.md"
    ts = dt.datetime.now().isoformat(timespec="seconds")
    lines = [f"\n### phase7_robustness_new_champ  {ts}\n",
             "Sub-period walk-forward stats: baseline (canonical) vs new champion.\n",
             "| period | baseline | new champ (gate40+do+62/38) | Δ CAGR | Δ Sharpe | Δ MaxDD |",
             "|---|---|---|---|---|---|"]
    for p, st, en in SUBPERIODS:
        b = run_w(base_pred, {}, st, en)
        c = run_w(gated, CHAMP, st, en)
        dc = (c["cagr"]-b["cagr"])*100
        ds = c["sharpe"]-b["sharpe"]
        dd = (c["max_dd"]-b["max_dd"])*100
        print(p, "base", fmt(b), "| champ", fmt(c), f"d_cagr={dc:+.2f}")
        lines.append(f"| {p} | {b['cagr']*100:.2f}/{b['sharpe']:.2f}/{b['max_dd']*100:.2f} | {c['cagr']*100:.2f}/{c['sharpe']:.2f}/{c['max_dd']*100:.2f} | {dc:+.2f}pp | {ds:+.2f} | {dd:+.2f}pp |")
    with open(log_path, "a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

if __name__ == "__main__":
    main()
