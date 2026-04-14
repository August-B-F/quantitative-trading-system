"""Phase 10:
- Multi-horizon rank aggregation (avg ranks across 21, 42, 63, 126)
- Regime-conditional universe (full in stable, defensive in transition)
- Soft proba-weighted lookback interpolation (not available without signal-level blend)
"""
from __future__ import annotations
import sys, datetime as dt, copy, pickle
from pathlib import Path
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from utils.base_test import _load, _STATE, fmt, haircut_verdict  # noqa: E402
from utils.custom_engine import run_custom  # noqa: E402
from strategy.portfolio import PortfolioEngine  # noqa: E402
from backtest.engine import compute_stats  # noqa: E402
from strategy.rebalance import fomc_window_mask, resolve_rebalance_index  # noqa: E402
from features.regime_labels import current_regime as _cr  # noqa: E402

CHAMP = {"universe": ["SOXX","QQQ","IGV","XLE","GLD","SHY"], "top1_weight":0.62, "top3_weight":0.38}
PROBA = HERE.parent / "cache" / "pred_proba.pkl"


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


def rank_aggregate(lbs_weights):
    """Sum of per-ticker rank across multiple lookbacks (higher = better)."""
    _load()
    bundle = _STATE["bundle"]
    ranks_sum = None
    wsum = 0
    cols_master = None
    for lb, w in lbs_weights:
        r = bundle.returns[lb]
        if cols_master is None:
            cols_master = list(r.columns)
        else:
            r = r[cols_master]
        ranked = r.rank(axis=1, method="average")  # higher = better
        if ranks_sum is None:
            ranks_sum = ranked * w
        else:
            ranks_sum = ranks_sum + ranked * w
        wsum += w
    return ranks_sum / wsum  # this is "rank score" — higher is better — pass as signal


def run_with_rank_signal(signal_df, overrides, pred_reg):
    _load()
    cfg = copy.deepcopy(_STATE["cfg"]); cfg.update(overrides or {})
    bundle = _STATE["bundle"]
    import types
    shim = types.SimpleNamespace(**{k: getattr(bundle, k) for k in ("df","dates","atr21","fwd21","spy_dist_sma200","is_fomc_day")})
    new_ret = dict(bundle.returns); new_ret[cfg["lookback_stable"]] = signal_df
    shim.returns = new_ret
    engine = PortfolioEngine(shim, pred_reg, cfg)
    from backtest.engine import run_backtest
    return run_backtest(engine, _STATE["test_dates"], cfg).stats


def main():
    log_path = HERE.parent / "LOG.md"
    ts = dt.datetime.now().isoformat(timespec="seconds")
    lines = [f"\n### phase10_aggregation_regime_uni  {ts}\n",
             "| name | CAGR | Sharpe | MaxDD | verdict |","|---|---|---|---|---|"]

    _load()
    gated = get_gated_pred(0.40)
    base_pred = _STATE["pred_reg"]

    # rank aggregation signals
    sig_21_63 = rank_aggregate([(21,1),(63,1)])
    sig_42_63_126 = rank_aggregate([(42,1),(63,1),(126,1)])
    sig_63_126 = rank_aggregate([(63,1),(126,1)])
    sig_21_63_126 = rank_aggregate([(21,1),(63,1),(126,1)])
    sig_weighted = rank_aggregate([(21,1),(63,2),(126,1)])

    experiments = [
        ("P10.01_rankagg_21_63_champ",  sig_21_63, CHAMP, gated),
        ("P10.02_rankagg_42_63_126_champ", sig_42_63_126, CHAMP, gated),
        ("P10.03_rankagg_63_126_champ", sig_63_126, CHAMP, gated),
        ("P10.04_rankagg_21_63_126_champ", sig_21_63_126, CHAMP, gated),
        ("P10.05_rankagg_weighted_champ", sig_weighted, CHAMP, gated),
        ("P10.06_rankagg_21_63_base", sig_21_63, {}, base_pred),
    ]

    for name, sig, ov, pr in experiments:
        try: s = run_with_rank_signal(sig, ov, pr)
        except Exception as e: s = {"error": str(e)}
        if "error" in s:
            print(name, "ERROR", s["error"]); lines.append(f"| {name} | | | | ERR |"); continue
        passes, _ = haircut_verdict(s)
        v = "PASS" if passes else "fail"
        print(name, fmt(s), v)
        lines.append(f"| {name} | {s['cagr']*100:.2f}% | {s['sharpe']:.2f} | {s['max_dd']*100:.2f}% | {v} |")
    with open(log_path, "a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

if __name__ == "__main__":
    main()
