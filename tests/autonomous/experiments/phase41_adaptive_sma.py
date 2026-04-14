"""Phase 41: classifier-adaptive SMA gate buffer.

When classifier is highly confident in STABLE regime (proba >= 0.80 and pred==cur),
relax the SMA gate (-6% or -8%). When low confidence or transition, tighten to -2%.
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
TRANS = STABLE + ["TLT","AGG","XLV"]
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


def run_adaptive_sma(sig, buf_conf, buf_unsure, conf_thresh):
    with open(PROBA,"rb") as f: pr, mp = pickle.load(f)
    _load(); b = _STATE["bundle"]
    cur = np.asarray(_cr(b.df).index)
    gated = pr.copy(); w=(pr!=cur)&(pr>=0); lc = np.nan_to_num(mp,nan=0)<0.40
    gated[w&lc]=cur[w&lc]

    def mk_eng(uni, sma):
        cfg = copy.deepcopy(_STATE["cfg"])
        cfg.update({"universe":uni,"top1_weight":0.62,"top3_weight":0.38,"sma_gate_buffer":sma})
        shim = types.SimpleNamespace(**{k:getattr(b,k) for k in ("df","dates","atr21","fwd21","spy_dist_sma200","is_fomc_day")})
        nr = dict(b.returns); nr[cfg["lookback_stable"]]=sig; shim.returns=nr
        return PortfolioEngine(shim, gated, cfg)

    engines = {}
    for uni_name, uni in [("s", STABLE), ("t", TRANS)]:
        for sma in (buf_conf, buf_unsure):
            engines[(uni_name, sma)] = mk_eng(uni, sma)

    td = _STATE["test_dates"]
    td_positions = pd.Series(engines[("s", buf_conf)].dates.get_indexer(td), index=td)
    month_last = td_positions.groupby(td.to_period("M")).tail(1)
    fomc_idx = np.where(b.is_fomc_day)[0]
    event_mask = fomc_window_mask(engines[("s", buf_conf)].n_days, fomc_idx, pre_days=0, post_days=2)

    def ret_at(eng, i):
        t1,tk = eng.pick_at(i)
        r1 = eng.fwd_arr[i,t1] if eng.spy_dist[i]>eng.sma_buffer else eng.cash_fwd[i]
        sel = eng.atr_arr[i,tk]; inv = 1.0/np.where(sel>0,sel,np.nan)
        if np.isnan(inv).all(): rk = np.nanmean(eng.fwd_arr[i,tk])
        else: ww=inv/np.nansum(inv); rk=np.nansum(eng.fwd_arr[i,tk]*ww)
        return eng.top1_w*r1 + eng.topk_w*rk

    rets = []
    for rd, pos in month_last.items():
        i, _ = resolve_rebalance_index(int(pos), 3, event_mask, engines[("s", buf_conf)].n_days)
        use_t = (pr[i]!=cur[i]) and (pr[i]>=0) and (not np.isnan(mp[i])) and (mp[i]>=0.50)
        uni_name = "t" if use_t else "s"
        # Pick SMA buffer
        p = mp[i] if not np.isnan(mp[i]) else 0.5
        # High confidence in stable (same as current) → relax
        if not use_t and p >= conf_thresh:
            sma = buf_conf
        else:
            sma = buf_unsure
        eng = engines[(uni_name, sma)]
        rets.append(ret_at(eng, i))
    return compute_stats(np.array(rets))


def main():
    sig = rankagg([(42,1),(63,3),(126,1)])
    log_path = HERE.parent / "LOG.md"
    ts = dt.datetime.now().isoformat(timespec="seconds")
    lines = [f"\n### phase41_adaptive_sma  {ts}\n",
             "| name | CAGR | Sharpe | MaxDD | verdict |","|---|---|---|---|---|"]

    grid = [
        ("relax_-06_-04_conf80", -0.06, -0.04, 0.80),
        ("relax_-06_-04_conf70", -0.06, -0.04, 0.70),
        ("relax_-08_-04_conf80", -0.08, -0.04, 0.80),
        ("relax_-08_-04_conf85", -0.08, -0.04, 0.85),
        ("tight_-02_-04_conf50", -0.02, -0.04, 0.50),
        ("tight_-03_-05_conf70", -0.03, -0.05, 0.70),
    ]
    for name, bc, bu, ct in grid:
        try: s = run_adaptive_sma(sig, bc, bu, ct)
        except Exception as e: s = {"error": str(e)}
        fn = f"P41_{name}"
        if "error" in s:
            print(fn, "ERROR", s["error"]); lines.append(f"| {fn} | | | | ERR |"); continue
        passes,_ = haircut_verdict(s)
        v = "PASS" if passes else "fail"
        print(fn, fmt(s), v)
        lines.append(f"| {fn} | {s['cagr']*100:.2f}% | {s['sharpe']:.2f} | {s['max_dd']*100:.2f}% | {v} |")
    with open(log_path,"a",encoding="utf-8") as f: f.write("\n".join(lines)+"\n")

if __name__ == "__main__":
    main()
