"""Phase 20: alternative multi-horizon aggregators."""
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


def rankagg(weights):
    _load(); b = _STATE["bundle"]
    cm=None; total=sum(w for _,w in weights); ranks=None
    for lb,w in weights:
        r = b.returns[lb]
        if cm is None: cm = list(r.columns)
        else: r = r[cm]
        ranks = r.rank(axis=1,method="average")*w if ranks is None else ranks + r.rank(axis=1,method="average")*w
    return ranks/total


def returnagg_mean(lbs):
    _load(); b = _STATE["bundle"]
    cm = list(b.returns[lbs[0]].columns)
    frames = [b.returns[lb][cm] for lb in lbs]
    return sum(frames) / len(frames)


def zscore_agg(lbs):
    """Sum of z-scored returns across horizons."""
    _load(); b = _STATE["bundle"]
    cm = list(b.returns[lbs[0]].columns)
    out = None
    for lb in lbs:
        r = b.returns[lb][cm]
        z = (r.sub(r.mean(axis=1), axis=0)).div(r.std(axis=1), axis=0)
        out = z if out is None else out + z
    return out


def median_rank(lbs):
    _load(); b = _STATE["bundle"]
    cm = list(b.returns[lbs[0]].columns)
    rs = [b.returns[lb][cm].rank(axis=1,method="average") for lb in lbs]
    # stack and take median
    arr = np.stack([r.values for r in rs], axis=0)
    med = np.median(arr, axis=0)
    return pd.DataFrame(med, index=rs[0].index, columns=cm)


def min_rank_consensus(lbs):
    """Use MIN rank across horizons (worst-case consensus)."""
    _load(); b = _STATE["bundle"]
    cm = list(b.returns[lbs[0]].columns)
    rs = [b.returns[lb][cm].rank(axis=1,method="average") for lb in lbs]
    arr = np.stack([r.values for r in rs], axis=0)
    mn = arr.min(axis=0)
    return pd.DataFrame(mn, index=rs[0].index, columns=cm)


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
    lines = [f"\n### phase20_alt_aggregators  {ts}\n",
             "| name | CAGR | Sharpe | MaxDD | verdict |","|---|---|---|---|---|"]

    experiments = [
        ("P20.00_rank_1_3_1_ref", rankagg([(42,1),(63,3),(126,1)])),
        ("P20.01_returnmean_42_63_126", returnagg_mean([42,63,126])),
        ("P20.02_returnmean_63_126",    returnagg_mean([63,126])),
        ("P20.03_zscore_42_63_126",     zscore_agg([42,63,126])),
        ("P20.04_median_rank_42_63_126", median_rank([42,63,126])),
        ("P20.05_min_rank_42_63_126",   min_rank_consensus([42,63,126])),
        ("P20.06_rank_1_3_1_21_1",      rankagg([(21,1),(42,1),(63,3),(126,1)])),
        ("P20.07_rank_42_3_63_3_126_1", rankagg([(42,3),(63,3),(126,1)])),
        ("P20.08_rank_42_2_63_4_126_1", rankagg([(42,2),(63,4),(126,1)])),
        ("P20.09_rank_42_1_63_3_126_2", rankagg([(42,1),(63,3),(126,2)])),
    ]
    for name, sig in experiments:
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
