"""Phase 10c: robustness sub-period test of the rankagg 42/63/126 champion candidate."""
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
    _load()
    cur = np.asarray(_cr(_STATE["bundle"].df).index)
    out = pr.copy()
    w = (pr != cur) & (pr >= 0); lc = np.nan_to_num(mp, nan=0) < thr
    out[w & lc] = cur[w & lc]
    return out

def rankagg(weights):
    _load()
    bundle = _STATE["bundle"]
    ranks_sum = None; cm = None
    total = sum(w for _, w in weights)
    for lb, w in weights:
        r = bundle.returns[lb]
        if cm is None: cm = list(r.columns)
        else: r = r[cm]
        ranked = r.rank(axis=1, method="average")
        ranks_sum = ranked*w if ranks_sum is None else ranks_sum + ranked*w
    return ranks_sum / total

def run_w(sig, ov, pred, st, en):
    _load()
    cfg = copy.deepcopy(_STATE["cfg"]); cfg.update(ov or {})
    bundle = _STATE["bundle"]
    if sig is not None:
        shim = types.SimpleNamespace(**{k:getattr(bundle,k) for k in ("df","dates","atr21","fwd21","spy_dist_sma200","is_fomc_day")})
        nr = dict(bundle.returns); nr[cfg["lookback_stable"]] = sig
        shim.returns = nr
        eng = PortfolioEngine(shim, pred, cfg)
    else:
        eng = PortfolioEngine(bundle, pred, cfg)
    res = run_backtest(eng, _STATE["test_dates"], cfg, start=st, end=en)
    return res.stats

SUBPERIODS = [
    ("full", None, None),
    ("2010_2015", "2010-01-01", "2015-12-31"),
    ("2016_2020", "2016-01-01", "2020-12-31"),
    ("2021_2026", "2021-01-01", "2026-12-31"),
    ("first_half", "2010-01-01", "2017-12-31"),
    ("second_half", "2018-01-01", "2026-12-31"),
]

def main():
    g = gated(0.40)
    _load(); base_pred = _STATE["pred_reg"]
    sig_42_63_126 = rankagg([(42,1),(63,2),(126,1)])
    sig_21_42_63_126 = rankagg([(21,1),(42,1),(63,2),(126,1)])

    log_path = HERE.parent / "LOG.md"
    ts = dt.datetime.now().isoformat(timespec="seconds")
    lines = [f"\n### phase10c_robust_rankagg  {ts}\n",
             "Sub-period validation of rankagg candidates.\n",
             "| cand | period | baseline | cand | d_cagr | d_sharpe | d_dd |",
             "|---|---|---|---|---|---|---|"]

    cands = [
        ("rankagg_42_63_126", sig_42_63_126),
        ("rankagg_21_42_63_126", sig_21_42_63_126),
    ]

    for cname, csig in cands:
        for p, st, en in SUBPERIODS:
            b = run_w(None, {}, base_pred, st, en)
            c = run_w(csig, CHAMP, g, st, en)
            dc = (c["cagr"]-b["cagr"])*100
            ds = c["sharpe"]-b["sharpe"]
            dd = (c["max_dd"]-b["max_dd"])*100
            line = f"| {cname} | {p} | {b['cagr']*100:.2f}/{b['sharpe']:.2f}/{b['max_dd']*100:.2f} | {c['cagr']*100:.2f}/{c['sharpe']:.2f}/{c['max_dd']*100:.2f} | {dc:+.2f}pp | {ds:+.2f} | {dd:+.2f}pp |"
            print(cname, p, fmt(c))
            lines.append(line)
    with open(log_path,"a",encoding="utf-8") as f: f.write("\n".join(lines)+"\n")

if __name__ == "__main__":
    main()
