"""Phase 11b: sub-period validation of (42:1, 63:2.5, 126:1) rankagg."""
from __future__ import annotations
import sys, datetime as dt, copy, pickle, types
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

def gated(thr=0.40):
    with open(PROBA,"rb") as f: pr, mp = pickle.load(f)
    _load(); cur = np.asarray(_cr(_STATE["bundle"].df).index)
    out = pr.copy()
    w = (pr != cur) & (pr >= 0); lc = np.nan_to_num(mp, nan=0) < thr
    out[w & lc] = cur[w & lc]; return out

def rankagg(weights):
    _load(); b = _STATE["bundle"]
    cm = None; total = sum(w for _,w in weights); ranks = None
    for lb, w in weights:
        r = b.returns[lb]
        if cm is None: cm = list(r.columns)
        else: r = r[cm]
        ranks = r.rank(axis=1, method="average")*w if ranks is None else ranks + r.rank(axis=1, method="average")*w
    return ranks/total

def run_w(sig, ov, pred, st, en):
    _load(); cfg = copy.deepcopy(_STATE["cfg"]); cfg.update(ov or {})
    b = _STATE["bundle"]
    if sig is not None:
        shim = types.SimpleNamespace(**{k:getattr(b,k) for k in ("df","dates","atr21","fwd21","spy_dist_sma200","is_fomc_day")})
        nr = dict(b.returns); nr[cfg["lookback_stable"]] = sig; shim.returns = nr
        eng = PortfolioEngine(shim, pred, cfg)
    else:
        eng = PortfolioEngine(b, pred, cfg)
    return run_backtest(eng, _STATE["test_dates"], cfg, start=st, end=en).stats

SUBS = [
    ("full", None, None),
    ("2010_2015", "2010-01-01","2015-12-31"),
    ("2016_2020", "2016-01-01","2020-12-31"),
    ("2021_2026", "2021-01-01","2026-12-31"),
    ("first_half","2010-01-01","2017-12-31"),
    ("second_half","2018-01-01","2026-12-31"),
]

def main():
    _load(); bp = _STATE["pred_reg"]; g = gated(0.40)
    log_path = HERE.parent / "LOG.md"
    ts = dt.datetime.now().isoformat(timespec="seconds")
    lines = [f"\n### phase11b_robust_63_25  {ts}\n",
             "| candidate | period | base | cand | d_cagr | d_sharpe | d_dd |",
             "|---|---|---|---|---|---|---|"]

    cands = [
        ("rankagg_42_1_63_2p5_126_1", rankagg([(42,1),(63,2.5),(126,1)])),
        ("rankagg_42_2_63_2_126_1",   rankagg([(42,2),(63,2),(126,1)])),
        ("rankagg_42_1_63_1p5_126_1", rankagg([(42,1),(63,1.5),(126,1)])),
    ]

    for cname, sig in cands:
        for p, st, en in SUBS:
            b = run_w(None, {}, bp, st, en)
            c = run_w(sig, CHAMP, g, st, en)
            dc = (c["cagr"]-b["cagr"])*100; ds = c["sharpe"]-b["sharpe"]; dd = (c["max_dd"]-b["max_dd"])*100
            print(cname, p, fmt(c))
            lines.append(f"| {cname} | {p} | {b['cagr']*100:.2f}/{b['sharpe']:.2f}/{b['max_dd']*100:.2f} | {c['cagr']*100:.2f}/{c['sharpe']:.2f}/{c['max_dd']*100:.2f} | {dc:+.2f} | {ds:+.2f} | {dd:+.2f} |")
    with open(log_path,"a",encoding="utf-8") as f: f.write("\n".join(lines)+"\n")

if __name__ == "__main__":
    main()
