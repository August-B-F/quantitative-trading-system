"""Phase 22: quality/momentum filters applied before ranking.

- Only rank ETFs with positive 63d return
- Only rank ETFs with 14d RSI > 50
- Only rank ETFs above their 200d SMA
- Multiplicative: momentum rank * (some quality score)
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

def rankagg(weights):
    _load(); b = _STATE["bundle"]
    cm=None; total=sum(w for _,w in weights); ranks=None
    for lb,w in weights:
        r = b.returns[lb]
        if cm is None: cm = list(r.columns)
        else: r = r[cm]
        ranks = r.rank(axis=1,method="average")*w if ranks is None else ranks + r.rank(axis=1,method="average")*w
    return ranks/total

def apply_filter(sig, filter_fn):
    """Apply filter: set signal to -inf where filter is False."""
    _load(); b = _STATE["bundle"]
    out = sig.copy()
    mask = filter_fn(b)
    # mask is DataFrame same shape as sig; True means keep, False means mask out
    mask = mask.reindex(index=out.index, columns=out.columns).fillna(True)
    out = out.where(mask, other=np.nan)  # NaN → -inf in engine
    return out

def filter_pos_63d(b):
    return b.returns[63] > 0

def filter_pos_42d(b):
    return b.returns[42] > 0

def filter_pos_21d(b):
    return b.returns[21] > 0

def filter_rsi_above(thr):
    def _f(b):
        r = b.df.filter(regex=r"^quality_rsi_14d__")
        r.columns = [c.split("__",1)[1] for c in r.columns]
        return r > thr
    return _f

def filter_sma200_above(b):
    r = b.df.filter(regex=r"^quality_dist_sma200__")
    r.columns = [c.split("__",1)[1] for c in r.columns]
    return r > 0  # above SMA200


def run_sig(sig, ov, pred):
    _load(); cfg = copy.deepcopy(_STATE["cfg"]); cfg.update(ov or {})
    b = _STATE["bundle"]
    shim = types.SimpleNamespace(**{k:getattr(b,k) for k in ("df","dates","atr21","fwd21","spy_dist_sma200","is_fomc_day")})
    nr = dict(b.returns); nr[cfg["lookback_stable"]]=sig; shim.returns=nr
    eng = PortfolioEngine(shim, pred, cfg)
    return run_backtest(eng, _STATE["test_dates"], cfg).stats


def main():
    g = gated(0.40)
    base_sig = rankagg([(42,1),(63,3),(126,1)])

    log_path = HERE.parent / "LOG.md"
    ts = dt.datetime.now().isoformat(timespec="seconds")
    lines = [f"\n### phase22_quality_filters  {ts}\n",
             "| name | CAGR | Sharpe | MaxDD | verdict |","|---|---|---|---|---|"]

    experiments = [
        ("P22.00_ref", base_sig),
        ("P22.01_filter_pos_63d", apply_filter(base_sig, filter_pos_63d)),
        ("P22.02_filter_pos_42d", apply_filter(base_sig, filter_pos_42d)),
        ("P22.03_filter_pos_21d", apply_filter(base_sig, filter_pos_21d)),
        ("P22.04_filter_sma200", apply_filter(base_sig, filter_sma200_above)),
        ("P22.05_filter_rsi40", apply_filter(base_sig, filter_rsi_above(40))),
        ("P22.06_filter_rsi50", apply_filter(base_sig, filter_rsi_above(50))),
        ("P22.07_filter_rsi30", apply_filter(base_sig, filter_rsi_above(30))),
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
