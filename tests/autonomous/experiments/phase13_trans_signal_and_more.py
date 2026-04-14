"""Phase 13:
- Apply rankagg-style aggregation to the TRANSITION signal too (shorter horizons)
- Top_k variants on the new champion
- Revisit SMA buffer on new champion
- 50/50 split sanity (maybe 62/38 was optimal for pure-63 but 50/50 is better with rankagg)
- Apply rankagg but with LOG returns instead of rank aggregation? Skip — rank is ordinal-stable, log is what bundle.returns already has
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
STABLE_W = [(42,1),(63,3),(126,1)]

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

def run_sig(stable_sig, ov, pred, trans_sig=None):
    _load(); cfg = copy.deepcopy(_STATE["cfg"]); cfg.update(ov or {})
    b = _STATE["bundle"]
    shim = types.SimpleNamespace(**{k:getattr(b,k) for k in ("df","dates","atr21","fwd21","spy_dist_sma200","is_fomc_day")})
    nr = dict(b.returns); nr[cfg["lookback_stable"]] = stable_sig
    if trans_sig is not None:
        nr[cfg["lookback_transition"]] = trans_sig
    shim.returns = nr
    eng = PortfolioEngine(shim, pred, cfg)
    return run_backtest(eng, _STATE["test_dates"], cfg).stats

def main():
    g = gated(0.40)
    stable_sig = rankagg(STABLE_W)
    log_path = HERE.parent / "LOG.md"
    ts = dt.datetime.now().isoformat(timespec="seconds")
    lines = [f"\n### phase13_trans_signal_and_more  {ts}\n",
             "| name | CAGR | Sharpe | MaxDD | verdict |","|---|---|---|---|---|"]

    experiments = []
    # Transition signal rankagg variants: uses shorter horizons
    trans_variants = [
        ("T1_10_21_42",   [(10,1),(21,2),(42,1)]),
        ("T2_10_21",      [(10,1),(21,2)]),
        ("T3_21_42",      [(21,2),(42,1)]),
        ("T4_21only",     [(21,1)]),  # same as baseline
        ("T5_21_2_42_1",  [(21,2),(42,1)]),
        ("T6_21_3_10_1",  [(21,3),(10,1)]),
        ("T7_21_2_10_1_42_1", [(10,1),(21,2),(42,1)]),
    ]
    for name, w in trans_variants:
        tsig = rankagg(w)
        experiments.append((f"P13.01_{name}", stable_sig, CHAMP, g, tsig))

    # Top_k variants
    for k in (2, 4, 5):
        ov = dict(CHAMP); ov["top_k"] = k
        experiments.append((f"P13.02_topk_{k}", stable_sig, ov, g, None))

    # Split variants (test if rankagg changes optimal split)
    for w1 in (0.50, 0.55, 0.58, 0.60, 0.62, 0.65, 0.68, 0.70):
        ov = dict(CHAMP); ov["top1_weight"] = w1; ov["top3_weight"] = 1-w1
        experiments.append((f"P13.03_split_{int(w1*100)}", stable_sig, ov, g, None))

    # SMA buffer variants
    for b in (-0.02, -0.03, -0.05, -0.06, -0.08):
        ov = dict(CHAMP); ov["sma_gate_buffer"] = b
        experiments.append((f"P13.04_sma{int(b*100)}", stable_sig, ov, g, None))

    # Gate threshold variants on new champion
    for thr in (0.30, 0.35, 0.40, 0.45, 0.50):
        g2 = gated(thr)
        experiments.append((f"P13.05_gate_{int(thr*100)}", stable_sig, CHAMP, g2, None))

    # FOMC variants
    for pre, post, dd in [(0,2,3),(1,2,3),(0,3,3),(0,2,4),(0,2,5)]:
        ov = dict(CHAMP); ov["fomc_window_pre"]=pre; ov["fomc_window_after"]=post; ov["fomc_defer_days"]=dd
        experiments.append((f"P13.06_fomc_p{pre}a{post}d{dd}", stable_sig, ov, g, None))

    for name, ss, ov, pr, ts in experiments:
        try: s = run_sig(ss, ov, pr, ts)
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
