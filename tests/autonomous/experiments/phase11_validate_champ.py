"""Phase 11: validate new champion against cost, weight perturbation, and
attribution of each component.
"""
from __future__ import annotations
import sys, datetime as dt, copy, pickle, types
from pathlib import Path
import numpy as np
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from utils.base_test import _load, _STATE, fmt, haircut_verdict  # noqa: E402
from strategy.portfolio import PortfolioEngine  # noqa: E402
from backtest.engine import run_backtest  # noqa: E402
from features.regime_labels import current_regime as _cr  # noqa: E402

CHAMP = {"universe": ["SOXX","QQQ","IGV","XLE","GLD","SHY"], "top1_weight":0.62, "top3_weight":0.38}
PROBA = HERE.parent / "cache" / "pred_proba.pkl"

def gated(thr=0.40):
    with open(PROBA,"rb") as f: pr, mp = pickle.load(f)
    _load()
    cur = np.asarray(_cr(_STATE["bundle"].df).index)
    out = pr.copy()
    w = (pr != cur) & (pr >= 0); lc = np.nan_to_num(mp, nan=0) < thr
    out[w & lc] = cur[w & lc]
    return out

def rankagg(weights):
    _load()
    b = _STATE["bundle"]
    cm = None; total = sum(w for _,w in weights); ranks = None
    for lb, w in weights:
        r = b.returns[lb]
        if cm is None: cm = list(r.columns)
        else: r = r[cm]
        ranked = r.rank(axis=1, method="average")
        ranks = ranked*w if ranks is None else ranks + ranked*w
    return ranks / total

def run_sig(sig, ov, pred, cost_bps=0.0):
    _load()
    cfg = copy.deepcopy(_STATE["cfg"]); cfg.update(ov or {})
    b = _STATE["bundle"]
    if sig is not None:
        shim = types.SimpleNamespace(**{k:getattr(b,k) for k in ("df","dates","atr21","fwd21","spy_dist_sma200","is_fomc_day")})
        nr = dict(b.returns); nr[cfg["lookback_stable"]] = sig
        shim.returns = nr
        eng = PortfolioEngine(shim, pred, cfg)
    else:
        eng = PortfolioEngine(b, pred, cfg)
    return run_backtest(eng, _STATE["test_dates"], cfg, cost_bps=cost_bps).stats

def main():
    log_path = HERE.parent / "LOG.md"
    ts = dt.datetime.now().isoformat(timespec="seconds")
    lines = [f"\n### phase11_validate_champ  {ts}\n",
             "| name | CAGR | Sharpe | MaxDD | verdict |","|---|---|---|---|---|"]

    _load(); base_pred = _STATE["pred_reg"]
    g = gated(0.40)
    sig = rankagg([(42,1),(63,2),(126,1)])

    # Cost sensitivity on new champion
    for c in (0, 5, 10, 20, 30):
        experiments = [(f"P11.01_champ_c{c}", sig, CHAMP, g, c),
                       (f"P11.01_base_c{c}", None, {}, base_pred, c)]
        for name, sg, ov, pr, cost in experiments:
            try: s = run_sig(sg, ov, pr, cost)
            except Exception as e: s = {"error": str(e)}
            if "error" in s:
                print(name, "ERROR", s["error"]); continue
            passes,_ = haircut_verdict(s)
            v = "PASS" if passes else "fail"
            print(name, fmt(s), v)
            lines.append(f"| {name} | {s['cagr']*100:.2f}% | {s['sharpe']:.2f} | {s['max_dd']*100:.2f}% | {v} |")

    # Component attribution: add pieces one at a time over baseline
    attr = [
        ("A0_baseline", None, {}, base_pred),
        ("A1_+dropoverlap", None, {"universe": CHAMP["universe"]}, base_pred),
        ("A2_+do_+62_38", None, CHAMP, base_pred),
        ("A3_+do_+62_38_+gate40", None, CHAMP, g),
        ("A4_+do_+62_38_+gate40_+rankagg", sig, CHAMP, g),
    ]
    for name, sg, ov, pr in attr:
        try: s = run_sig(sg, ov, pr)
        except Exception as e: s = {"error": str(e)}
        if "error" in s: continue
        passes,_ = haircut_verdict(s)
        print(name, fmt(s))
        lines.append(f"| {name} | {s['cagr']*100:.2f}% | {s['sharpe']:.2f} | {s['max_dd']*100:.2f}% | - |")

    # Weight perturbation around (42,1)(63,2)(126,1)
    perturbations = [
        [(42,1),(63,2),(126,1)],
        [(42,1),(63,2),(126,2)],
        [(42,2),(63,2),(126,1)],
        [(42,1),(63,2),(126,0.5)],
        [(42,0.5),(63,2),(126,1)],
        [(42,1),(63,1.5),(126,1)],
        [(42,1),(63,2.5),(126,1)],
        [(42,1),(63,4),(126,1)],
    ]
    for pw in perturbations:
        name = "P11_pert_" + "_".join(f"{lb}x{w}" for lb,w in pw)
        sg = rankagg(pw)
        try: s = run_sig(sg, CHAMP, g)
        except Exception as e: s = {"error": str(e)}
        if "error" in s: continue
        passes,_ = haircut_verdict(s)
        v = "PASS" if passes else "fail"
        print(name, fmt(s), v)
        lines.append(f"| {name} | {s['cagr']*100:.2f}% | {s['sharpe']:.2f} | {s['max_dd']*100:.2f}% | {v} |")

    with open(log_path,"a",encoding="utf-8") as f:
        f.write("\n".join(lines)+"\n")

if __name__ == "__main__":
    main()
