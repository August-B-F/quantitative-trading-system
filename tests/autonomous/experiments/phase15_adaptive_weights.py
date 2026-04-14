"""Phase 15: regime-adaptive horizon weights.

Idea: in high-dispersion regimes, tilt toward 126d (trend persistence); in
low-dispersion, tilt toward 42d (responsiveness).
"""
from __future__ import annotations
import sys, datetime as dt, copy, pickle, types
from pathlib import Path
import numpy as np
import pandas as pd
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
    _load(); cur = np.asarray(_cr(_STATE["bundle"].df).index)
    out = pr.copy(); w=(pr!=cur)&(pr>=0); lc = np.nan_to_num(mp,nan=0)<thr
    out[w&lc]=cur[w&lc]; return out

def adaptive_rankagg(low_w=(1,3,1), high_w=(1,3,3)):
    """Row-by-row: pick weights based on dispersion level."""
    _load(); b = _STATE["bundle"]
    disp = b.df.get("cross_sectional_dispersion_63d__dispersion")
    if disp is None:
        return None
    cm = list(b.returns[63].columns)
    r42 = b.returns[42][cm].rank(axis=1,method="average")
    r63 = b.returns[63][cm].rank(axis=1,method="average")
    r126 = b.returns[126][cm].rank(axis=1,method="average")

    thresh = disp.median()
    out = r63 * 0  # same shape
    # Low-dispersion regime
    lo_mask = disp <= thresh
    hi_mask = disp > thresh
    lw = np.array(low_w, dtype=float); lw /= lw.sum()
    hw = np.array(high_w, dtype=float); hw /= hw.sum()
    for mask, weights in [(lo_mask, lw), (hi_mask, hw)]:
        rows = mask.fillna(False).values
        out.loc[rows] = (r42.loc[rows]*weights[0] + r63.loc[rows]*weights[1] + r126.loc[rows]*weights[2]).values
    return out


def rankagg_static(weights):
    _load(); b = _STATE["bundle"]
    cm = None; total = sum(w for _,w in weights); ranks = None
    for lb, w in weights:
        r = b.returns[lb]
        if cm is None: cm = list(r.columns)
        else: r = r[cm]
        ranks = r.rank(axis=1,method="average")*w if ranks is None else ranks + r.rank(axis=1,method="average")*w
    return ranks/total


def run_sig(sig, ov, pred):
    _load(); cfg = copy.deepcopy(_STATE["cfg"]); cfg.update(ov or {})
    b = _STATE["bundle"]
    shim = types.SimpleNamespace(**{k:getattr(b,k) for k in ("df","dates","atr21","fwd21","spy_dist_sma200","is_fomc_day")})
    nr = dict(b.returns); nr[cfg["lookback_stable"]]=sig; shim.returns=nr
    eng = PortfolioEngine(shim, pred, cfg)
    return run_backtest(eng, _STATE["test_dates"], cfg).stats


def main():
    g = gated(0.40)
    log_path = HERE.parent / "LOG.md"
    ts = dt.datetime.now().isoformat(timespec="seconds")
    lines = [f"\n### phase15_adaptive_weights  {ts}\n",
             "| name | CAGR | Sharpe | MaxDD | verdict |","|---|---|---|---|---|"]

    # static champion reference
    static_champ = rankagg_static([(42,1),(63,3),(126,1)])

    experiments = [
        ("P15.00_static_ref", static_champ),
    ]
    grids = [
        ("low_42heavy_high_126heavy", ((2,3,1), (1,3,2))),
        ("low_42_3x_high_126_3x",     ((3,3,1), (1,3,3))),
        ("low_42_2x_high_equal",      ((2,3,1), (1,3,1))),
        ("low_equal_high_126_2x",     ((1,3,1), (1,3,2))),
        ("low_42_only_high_126_only", ((5,1,0.5), (0.5,1,5))),
        ("lowhigh_flipped",            ((1,3,3), (3,3,1))),  # should lose
    ]
    for name, (lw, hw) in grids:
        sig = adaptive_rankagg(lw, hw)
        experiments.append((f"P15.01_{name}", sig))

    for name, sig in experiments:
        if sig is None:
            print(name, "no dispersion data"); continue
        try: s = run_sig(sig, CHAMP, g)
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
