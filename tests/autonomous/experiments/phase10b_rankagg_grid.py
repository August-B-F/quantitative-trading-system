"""Phase 10b: rank aggregation weight grid on champion config."""
from __future__ import annotations
import sys, datetime as dt, copy, pickle
from pathlib import Path
import numpy as np
import pandas as pd
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from utils.base_test import _load, _STATE, fmt, haircut_verdict  # noqa: E402
from strategy.portfolio import PortfolioEngine  # noqa: E402
from backtest.engine import run_backtest  # noqa: E402
from features.regime_labels import current_regime as _cr  # noqa: E402
import types

CHAMP = {"universe": ["SOXX","QQQ","IGV","XLE","GLD","SHY"], "top1_weight":0.62, "top3_weight":0.38}
PROBA = HERE.parent / "cache" / "pred_proba.pkl"

def get_gated_pred(thr=0.40):
    with open(PROBA,"rb") as f: pr, mp = pickle.load(f)
    _load()
    cur = np.asarray(_cr(_STATE["bundle"].df).index)
    out = pr.copy()
    w = (pr != cur) & (pr >= 0); lc = np.nan_to_num(mp, nan=0) < thr
    out[w & lc] = cur[w & lc]
    return out

def rankagg(weights):
    _load()
    bundle = _STATE["bundle"]
    ranks_sum = None; wsum = 0; cm = None
    for lb, w in weights:
        r = bundle.returns[lb]
        if cm is None: cm = list(r.columns)
        else: r = r[cm]
        ranked = r.rank(axis=1, method="average")
        ranks_sum = ranked*w if ranks_sum is None else ranks_sum + ranked*w
        wsum += w
    return ranks_sum / wsum

def run_sig(sig, ov, pred):
    _load()
    cfg = copy.deepcopy(_STATE["cfg"]); cfg.update(ov or {})
    bundle = _STATE["bundle"]
    shim = types.SimpleNamespace(**{k: getattr(bundle,k) for k in ("df","dates","atr21","fwd21","spy_dist_sma200","is_fomc_day")})
    nr = dict(bundle.returns); nr[cfg["lookback_stable"]] = sig
    shim.returns = nr
    eng = PortfolioEngine(shim, pred, cfg)
    return run_backtest(eng, _STATE["test_dates"], cfg).stats

def main():
    gated = get_gated_pred(0.40)
    log_path = HERE.parent / "LOG.md"
    ts = dt.datetime.now().isoformat(timespec="seconds")
    lines = [f"\n### phase10b_rankagg_grid  {ts}\n",
             "| name | CAGR | Sharpe | MaxDD | verdict |","|---|---|---|---|---|"]
    grids = [
        ("21_1_63_1_126_1", [(21,1),(63,1),(126,1)]),
        ("21_1_63_2_126_1", [(21,1),(63,2),(126,1)]),
        ("21_1_63_3_126_1", [(21,1),(63,3),(126,1)]),
        ("21_1_63_2_126_0", [(21,1),(63,2)]),
        ("21_0_63_2_126_1", [(63,2),(126,1)]),
        ("21_1_63_2_126_2", [(21,1),(63,2),(126,2)]),
        ("21_2_63_3_126_1", [(21,2),(63,3),(126,1)]),
        ("21_1_42_1_63_2_126_1", [(21,1),(42,1),(63,2),(126,1)]),
        ("42_1_63_2_126_1", [(42,1),(63,2),(126,1)]),
        ("42_1_63_1_126_0", [(42,1),(63,1)]),
    ]
    experiments = [(f"P10b_{name}", rankagg(w), CHAMP, gated) for name, w in grids]
    # also on simpler baseline (no gate, no dropoverlap) for attribution
    experiments.append(("P10b_21_1_63_2_126_1_BASE", rankagg([(21,1),(63,2),(126,1)]), {}, _STATE["pred_reg"]))
    for name, sig, ov, pr in experiments:
        try: s = run_sig(sig, ov, pr)
        except Exception as e: s = {"error": str(e)}
        if "error" in s:
            print(name, "ERROR", s["error"]); lines.append(f"| {name} | | | | ERR |"); continue
        passes,_ = haircut_verdict(s)
        v = "PASS" if passes else "fail"
        print(name, fmt(s), v)
        lines.append(f"| {name} | {s['cagr']*100:.2f}% | {s['sharpe']:.2f} | {s['max_dd']*100:.2f}% | {v} |")
    with open(log_path,"a",encoding="utf-8") as f: f.write("\n".join(lines)+"\n")

if __name__ == "__main__":
    main()
