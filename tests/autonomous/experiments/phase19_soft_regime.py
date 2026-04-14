"""Phase 19: soft regime signal blending.

Instead of a hard 63/21 switch based on argmax class, blend the rankagg(63,...)
stable signal with the 21d transition signal by classifier probability.
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
from backtest.engine import compute_stats  # noqa: E402
from strategy.rebalance import fomc_window_mask, resolve_rebalance_index  # noqa: E402
from features.regime_labels import current_regime as _cr  # noqa: E402

CHAMP = {"universe": ["SOXX","QQQ","IGV","XLE","GLD","SHY"], "top1_weight":0.62, "top3_weight":0.38}
PROBA = HERE.parent / "cache" / "pred_proba.pkl"


def run_soft(cfg_ov, stable_rank, pred_reg, pred_maxp):
    """At each rebalance, compute final signal as:
       if current == predicted: use stable_rank
       else: blend stable_rank with 21d rank by (1 - p_predicted)
    This softens the hard switch.
    """
    _load(); cfg = copy.deepcopy(_STATE["cfg"]); cfg.update(cfg_ov or {})
    b = _STATE["bundle"]
    cur = np.asarray(_cr(b.df).index)

    # 21d rank signal
    cm = list(b.returns[21].columns)
    r21_rank = b.returns[21][cm].rank(axis=1, method="average")
    stable_rank_a = stable_rank[cm]

    engine = PortfolioEngine(b, pred_reg, cfg)  # just for arrays/paths
    td = _STATE["test_dates"]
    td_positions = pd.Series(engine.dates.get_indexer(td), index=td)
    month_last = td_positions.groupby(td.to_period("M")).tail(1)
    defer_enabled = bool(cfg.get("fomc_defer_enabled", True))
    defer_days = int(cfg.get("fomc_defer_days", 3))
    pre = int(cfg.get("fomc_window_pre", 0)); post = int(cfg.get("fomc_window_after", 2))
    fomc_idx = np.where(b.is_fomc_day)[0]
    event_mask = fomc_window_mask(engine.n_days, fomc_idx, pre_days=pre, post_days=post) if defer_enabled else None

    rets = []
    universe = list(cfg["universe"])
    u_idx = [cm.index(t) for t in universe]

    stable_vals = stable_rank_a.values
    r21_vals = r21_rank.values

    for rd, pos in month_last.items():
        i, _ = resolve_rebalance_index(int(pos), defer_days if defer_enabled else 0, event_mask, engine.n_days)
        p_pred = pred_maxp[i] if not np.isnan(pred_maxp[i]) else 0.5
        pr = pred_reg[i]
        if pr == cur[i] or pr < 0:
            row = stable_vals[i, u_idx]
        else:
            # soft blend: weight stable by (1-p), transition by p — MORE transition when confident it's different
            row = (1 - p_pred) * stable_vals[i, u_idx] + p_pred * r21_vals[i, u_idx]
        row = np.where(np.isnan(row), -np.inf, row)
        top1 = int(np.argmax(row))
        tk = np.argsort(-row)[: engine.k]
        # map back to bundle universe indices for fwd_arr (engine.universe)
        # engine uses CHAMP universe order so these indices are directly usable
        r1 = engine.fwd_arr[i, top1] if engine.spy_dist[i] > engine.sma_buffer else engine.cash_fwd[i]
        sel_atr = engine.atr_arr[i, tk]
        inv = 1.0 / np.where(sel_atr > 0, sel_atr, np.nan)
        if np.isnan(inv).all():
            rk = np.nanmean(engine.fwd_arr[i, tk])
        else:
            w = inv / np.nansum(inv); rk = np.nansum(engine.fwd_arr[i, tk] * w)
        rets.append(engine.top1_w * r1 + engine.topk_w * rk)
    return compute_stats(np.array(rets))


def rankagg(weights):
    _load(); b = _STATE["bundle"]
    cm=None; total=sum(w for _,w in weights); ranks=None
    for lb,w in weights:
        r = b.returns[lb]
        if cm is None: cm = list(r.columns)
        else: r = r[cm]
        ranks = r.rank(axis=1,method="average")*w if ranks is None else ranks + r.rank(axis=1,method="average")*w
    return ranks/total


def main():
    with open(PROBA,"rb") as f: pr, mp = pickle.load(f)
    stable = rankagg([(42,1),(63,3),(126,1)])
    _load()
    log_path = HERE.parent / "LOG.md"
    ts = dt.datetime.now().isoformat(timespec="seconds")
    lines = [f"\n### phase19_soft_regime  {ts}\n",
             "| name | CAGR | Sharpe | MaxDD | verdict |","|---|---|---|---|---|"]

    experiments = [
        ("P19.01_soft_blend", stable, pr, mp),
    ]
    for name, ss, prs, mps in experiments:
        try: s = run_soft(CHAMP, ss, prs, mps)
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
