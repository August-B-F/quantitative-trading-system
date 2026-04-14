"""Phase 12: wider rankagg weight exploration + add 21/10/252 horizons."""
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
    _load(); cur = np.asarray(_cr(_STATE["bundle"].df).index)
    out = pr.copy(); w=(pr!=cur)&(pr>=0); lc = np.nan_to_num(mp,nan=0)<thr
    out[w&lc] = cur[w&lc]; return out

def rankagg(weights):
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
    nr = dict(b.returns); nr[cfg["lookback_stable"]] = sig; shim.returns = nr
    eng = PortfolioEngine(shim, pred, cfg)
    return run_backtest(eng, _STATE["test_dates"], cfg).stats

def main():
    g = gated(0.40)
    log_path = HERE.parent / "LOG.md"
    ts = dt.datetime.now().isoformat(timespec="seconds")
    lines = [f"\n### phase12_wider_rankagg  {ts}\n",
             "| name | CAGR | Sharpe | MaxDD | verdict |","|---|---|---|---|---|"]
    # Available: 10, 21, 42, 63, 126 (from load_panel)
    grids = [
        ("W1_21_42_63_126_balanced", [(21,1),(42,1),(63,2.5),(126,1)]),
        ("W2_21_42_63_126_less21",    [(21,0.5),(42,1),(63,2.5),(126,1)]),
        ("W3_10_42_63_126",          [(10,0.5),(42,1),(63,2.5),(126,1)]),
        ("W4_42_63_126_wide63_3",    [(42,1),(63,3),(126,1)]),
        ("W5_42_63_126_wide63_4",    [(42,1),(63,4),(126,1)]),
        ("W6_42_63_126_eq_emph63",   [(42,1),(63,2.5),(126,1.5)]),
        ("W7_42_63_126_42heavy",     [(42,1.5),(63,2.5),(126,1)]),
        ("W8_42_63_126_126heavy",    [(42,1),(63,2.5),(126,1.5)]),
        ("W9_42_63_126_42_2",        [(42,2),(63,2.5),(126,1)]),
        ("W10_42_63_126_42_2_126_0", [(42,2),(63,2.5)]),
        ("W11_21_63_126",            [(21,1),(63,2.5),(126,1)]),
        ("W12_21_42_63_126_shortheavy",[(21,1),(42,1),(63,2),(126,0.5)]),
        ("W13_63_only_25_like",      [(63,2.5)]),
        ("W14_42_63_2p8_126",        [(42,1),(63,2.8),(126,1)]),
        ("W15_42_63_2p2_126",        [(42,1),(63,2.2),(126,1)]),
    ]
    for name, w in grids:
        sig = rankagg(w)
        try: s = run_sig(sig, CHAMP, g)
        except Exception as e: s = {"error": str(e)}
        if "error" in s: print(name, "ERROR", s["error"]); lines.append(f"| {name} | | | | ERR |"); continue
        passes,_ = haircut_verdict(s)
        v = "PASS" if passes else "fail"
        print(name, fmt(s), v)
        lines.append(f"| {name} | {s['cagr']*100:.2f}% | {s['sharpe']:.2f} | {s['max_dd']*100:.2f}% | {v} |")
    with open(log_path,"a",encoding="utf-8") as f: f.write("\n".join(lines)+"\n")

if __name__ == "__main__":
    main()
