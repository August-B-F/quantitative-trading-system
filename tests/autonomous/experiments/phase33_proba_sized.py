"""Phase 33: proba-adaptive position sizing.

When classifier is very confident (proba >= 0.8) in its regime call and regime is
stable, use more concentrated top1 weight (70/30). When low confidence, use 50/50.
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

STABLE = ["SOXX","QQQ","IGV","XLE","GLD","SHY"]
TRANS  = STABLE + ["TLT","AGG","XLV"]
PROBA = HERE.parent / "cache" / "pred_proba.pkl"

def rankagg(weights):
    _load(); b = _STATE["bundle"]
    cm=None; total=sum(w for _,w in weights); ranks=None
    for lb,w in weights:
        r = b.returns[lb]
        if cm is None: cm = list(r.columns)
        else: r = r[cm]
        ranks = r.rank(axis=1,method="average")*w if ranks is None else ranks+r.rank(axis=1,method="average")*w
    return ranks/total


def run_proba_sized(sig, w1_low=0.50, w1_hi=0.70, conf_lo=0.50, conf_hi=0.85):
    with open(PROBA,"rb") as f: pr, mp = pickle.load(f)
    _load(); b = _STATE["bundle"]
    cur = np.asarray(_cr(b.df).index)
    gated = pr.copy(); w=(pr!=cur)&(pr>=0); lc = np.nan_to_num(mp,nan=0)<0.40
    gated[w&lc]=cur[w&lc]

    def mk_eng(uni, w1):
        cfg = copy.deepcopy(_STATE["cfg"])
        cfg.update({"universe":uni,"top1_weight":w1,"top3_weight":1-w1})
        shim = types.SimpleNamespace(**{k:getattr(b,k) for k in ("df","dates","atr21","fwd21","spy_dist_sma200","is_fomc_day")})
        nr = dict(b.returns); nr[cfg["lookback_stable"]]=sig; shim.returns=nr
        return PortfolioEngine(shim, gated, cfg)

    engines = {}
    for w1 in (w1_low, 0.62, w1_hi):
        engines[("s", w1)] = mk_eng(STABLE, w1)
        engines[("t", w1)] = mk_eng(TRANS, w1)

    td = _STATE["test_dates"]
    td_positions = pd.Series(engines[("s",0.62)].dates.get_indexer(td), index=td)
    month_last = td_positions.groupby(td.to_period("M")).tail(1)
    fomc_idx = np.where(b.is_fomc_day)[0]
    event_mask = fomc_window_mask(engines[("s",0.62)].n_days, fomc_idx, pre_days=0, post_days=2)

    def ret_at(eng, i):
        t1,tk = eng.pick_at(i)
        r1 = eng.fwd_arr[i,t1] if eng.spy_dist[i]>eng.sma_buffer else eng.cash_fwd[i]
        sel = eng.atr_arr[i,tk]; inv = 1.0/np.where(sel>0,sel,np.nan)
        if np.isnan(inv).all(): rk = np.nanmean(eng.fwd_arr[i,tk])
        else: ww=inv/np.nansum(inv); rk=np.nansum(eng.fwd_arr[i,tk]*ww)
        return eng.top1_w*r1 + eng.topk_w*rk

    rets = []
    for rd, pos in month_last.items():
        i, _ = resolve_rebalance_index(int(pos), 3, event_mask, engines[("s",0.62)].n_days)
        p = mp[i] if not np.isnan(mp[i]) else 0.5
        is_trans = (pr[i]!=cur[i]) and (pr[i]>=0) and (not np.isnan(mp[i])) and (mp[i]>=0.50)
        # Pick w1 based on confidence in regime stability (higher proba when regime matches cur)
        if is_trans:
            w1_pick = 0.62  # default
            uni = "t"
        else:
            if p >= conf_hi: w1_pick = w1_hi
            elif p <= conf_lo: w1_pick = w1_low
            else: w1_pick = 0.62
            uni = "s"
        eng = engines[(uni, w1_pick)]
        rets.append(ret_at(eng, i))
    return compute_stats(np.array(rets))


def main():
    sig = rankagg([(42,1),(63,3),(126,1)])
    log_path = HERE.parent / "LOG.md"
    ts = dt.datetime.now().isoformat(timespec="seconds")
    lines = [f"\n### phase33_proba_sized  {ts}\n",
             "| name | CAGR | Sharpe | MaxDD | verdict |","|---|---|---|---|---|"]
    grid = [
        ("w1_50_70_conf50_80", 0.50, 0.70, 0.50, 0.80),
        ("w1_55_70_conf50_80", 0.55, 0.70, 0.50, 0.80),
        ("w1_50_75_conf50_85", 0.50, 0.75, 0.50, 0.85),
        ("w1_50_68_conf55_80", 0.50, 0.68, 0.55, 0.80),
        ("w1_55_75_conf60_90", 0.55, 0.75, 0.60, 0.90),
        ("w1_45_72_conf50_85", 0.45, 0.72, 0.50, 0.85),
    ]
    for name, a, b, c, d in grid:
        try: s = run_proba_sized(sig, a, b, c, d)
        except Exception as e: s = {"error": str(e)}
        fn = f"P33_{name}"
        if "error" in s:
            print(fn, "ERROR", s["error"]); lines.append(f"| {fn} | | | | ERR |"); continue
        passes,_ = haircut_verdict(s)
        v = "PASS" if passes else "fail"
        print(fn, fmt(s), v)
        lines.append(f"| {fn} | {s['cagr']*100:.2f}% | {s['sharpe']:.2f} | {s['max_dd']*100:.2f}% | {v} |")
    with open(log_path,"a",encoding="utf-8") as f: f.write("\n".join(lines)+"\n")

if __name__ == "__main__":
    main()
