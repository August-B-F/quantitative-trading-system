"""Phase 23: regime-conditional universe.

In transition regime (predicted != current), restrict universe to defensive subset.
In stable regime, use full 6-ETF dropoverlap universe.
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

STABLE_UNI = ["SOXX","QQQ","IGV","XLE","GLD","SHY"]
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


def run_regime_uni(stable_uni, trans_uni, stable_sig, pred, gated_pred):
    """At each rebalance: if regime is stable (pred==cur), use stable_uni; else trans_uni.

    Since the engine is tied to a single universe, we'll construct TWO engines
    and pick the appropriate fwd return at each rebalance.
    """
    _load(); b = _STATE["bundle"]
    cur = np.asarray(_cr(b.df).index)

    cfg_s = copy.deepcopy(_STATE["cfg"])
    cfg_s.update({"universe": stable_uni, "top1_weight":0.62, "top3_weight":0.38})
    shim_s = types.SimpleNamespace(**{k:getattr(b,k) for k in ("df","dates","atr21","fwd21","spy_dist_sma200","is_fomc_day")})
    nr = dict(b.returns); nr[cfg_s["lookback_stable"]] = stable_sig; shim_s.returns = nr
    eng_s = PortfolioEngine(shim_s, gated_pred, cfg_s)

    cfg_t = copy.deepcopy(_STATE["cfg"])
    cfg_t.update({"universe": trans_uni, "top1_weight":0.62, "top3_weight":0.38})
    shim_t = types.SimpleNamespace(**{k:getattr(b,k) for k in ("df","dates","atr21","fwd21","spy_dist_sma200","is_fomc_day")})
    shim_t.returns = nr
    eng_t = PortfolioEngine(shim_t, gated_pred, cfg_t)

    td = _STATE["test_dates"]
    td_positions = pd.Series(eng_s.dates.get_indexer(td), index=td)
    month_last = td_positions.groupby(td.to_period("M")).tail(1)

    defer_enabled = True; defer_days = 3; pre = 0; post = 2
    fomc_idx = np.where(b.is_fomc_day)[0]
    event_mask = fomc_window_mask(eng_s.n_days, fomc_idx, pre_days=pre, post_days=post)

    def ret_at(engine, i):
        top1, tk = engine.pick_at(i)
        r1 = engine.fwd_arr[i, top1] if engine.spy_dist[i] > engine.sma_buffer else engine.cash_fwd[i]
        sel_atr = engine.atr_arr[i, tk]
        inv = 1.0 / np.where(sel_atr > 0, sel_atr, np.nan)
        if np.isnan(inv).all():
            rk = np.nanmean(engine.fwd_arr[i, tk])
        else:
            w = inv / np.nansum(inv); rk = np.nansum(engine.fwd_arr[i, tk] * w)
        return engine.top1_w * r1 + engine.topk_w * rk

    rets = []
    for rd, pos in month_last.items():
        i, _ = resolve_rebalance_index(int(pos), defer_days, event_mask, eng_s.n_days)
        is_stable = (gated_pred[i] == cur[i]) or (gated_pred[i] < 0)
        eng = eng_s if is_stable else eng_t
        rets.append(ret_at(eng, i))
    return compute_stats(np.array(rets))


def main():
    g = gated(0.40)
    sig = rankagg([(42,1),(63,3),(126,1)])

    log_path = HERE.parent / "LOG.md"
    ts = dt.datetime.now().isoformat(timespec="seconds")
    lines = [f"\n### phase23_regime_universe  {ts}\n",
             "| name | CAGR | Sharpe | MaxDD | verdict |","|---|---|---|---|---|"]

    experiments = [
        ("P23.01_stable_6_trans_defensive",  STABLE_UNI, ["SOXX","GLD","SHY","TLT"]),
        ("P23.02_stable_6_trans_tech+gold",  STABLE_UNI, ["SOXX","QQQ","GLD","SHY"]),
        ("P23.03_stable_6_trans_min",        STABLE_UNI, ["GLD","SHY","TLT"]),
        ("P23.04_stable_6_trans_gld_shy",    STABLE_UNI, ["GLD","SHY"]),
        ("P23.05_stable_6_trans_noenergy",   STABLE_UNI, ["SOXX","QQQ","IGV","GLD","SHY"]),
        ("P23.06_stable_6_trans_full_plus_tlt", STABLE_UNI, STABLE_UNI + ["TLT"]),
    ]
    for name, su, tu in experiments:
        try: s = run_regime_uni(su, tu, sig, _STATE["pred_reg"], g)
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
