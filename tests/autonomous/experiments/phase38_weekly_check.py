"""Phase 38: weekly-check rebalance rule on champion.

Default: rotate monthly on month-end.
Alt: only rotate top1 if the new leader's rank-agg score exceeds the CURRENT
held top1 by X% (margin). This should reduce noise and turnover.

We simulate by: at each month-end, compare new top1 score vs current (held from
previous rebalance). If margin < X, KEEP current top1.
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


def run_inertia(margin, sig):
    with open(PROBA,"rb") as f: pr, mp = pickle.load(f)
    _load(); b = _STATE["bundle"]
    cur = np.asarray(_cr(b.df).index)
    gated = pr.copy(); w=(pr!=cur)&(pr>=0); lc = np.nan_to_num(mp,nan=0)<0.40
    gated[w&lc]=cur[w&lc]
    def mk_eng(uni):
        cfg = copy.deepcopy(_STATE["cfg"])
        cfg.update({"universe":uni,"top1_weight":0.62,"top3_weight":0.38})
        shim = types.SimpleNamespace(**{k:getattr(b,k) for k in ("df","dates","atr21","fwd21","spy_dist_sma200","is_fomc_day")})
        nr = dict(b.returns); nr[cfg["lookback_stable"]]=sig; shim.returns=nr
        return PortfolioEngine(shim, gated, cfg)
    eng_s = mk_eng(STABLE); eng_t = mk_eng(TRANS)
    td = _STATE["test_dates"]
    td_positions = pd.Series(eng_s.dates.get_indexer(td), index=td)
    month_last = td_positions.groupby(td.to_period("M")).tail(1)
    fomc_idx = np.where(b.is_fomc_day)[0]
    event_mask = fomc_window_mask(eng_s.n_days, fomc_idx, pre_days=0, post_days=2)

    rets = []
    held_top1 = None  # index within current engine universe
    for rd, pos in month_last.items():
        i, _ = resolve_rebalance_index(int(pos), 3, event_mask, eng_s.n_days)
        use_t = (pr[i]!=cur[i]) and (pr[i]>=0) and (not np.isnan(mp[i])) and (mp[i]>=0.50)
        eng = eng_t if use_t else eng_s
        # Signal row
        row = eng.sf[i]
        new_top1 = int(np.argmax(row))
        tk = np.argsort(-row)[: eng.k]
        # Apply inertia: if held_top1 still in universe and score margin small, keep it
        if held_top1 is not None and isinstance(held_top1, str) and held_top1 in eng.universe:
            held_idx = eng.universe.index(held_top1)
            if np.isfinite(row[held_idx]):
                top1_score = row[new_top1]; held_score = row[held_idx]
                if (top1_score - held_score) < margin:
                    new_top1 = held_idx
                    if held_idx not in tk:
                        tk = np.concatenate(([held_idx], tk[:-1]))
        held_top1 = eng.universe[new_top1]
        # compute return
        r1 = eng.fwd_arr[i, new_top1] if eng.spy_dist[i] > eng.sma_buffer else eng.cash_fwd[i]
        sel_atr = eng.atr_arr[i, tk]
        inv = 1.0 / np.where(sel_atr > 0, sel_atr, np.nan)
        if np.isnan(inv).all():
            rk = np.nanmean(eng.fwd_arr[i, tk])
        else:
            w = inv / np.nansum(inv); rk = np.nansum(eng.fwd_arr[i, tk] * w)
        rets.append(eng.top1_w * r1 + eng.topk_w * rk)
    return compute_stats(np.array(rets))


def main():
    sig = rankagg([(42,1),(63,3),(126,1)])
    log_path = HERE.parent / "LOG.md"
    ts = dt.datetime.now().isoformat(timespec="seconds")
    lines = [f"\n### phase38_weekly_check  {ts}\n",
             "| name | CAGR | Sharpe | MaxDD | verdict |","|---|---|---|---|---|"]
    for m in (0.0, 0.1, 0.2, 0.3, 0.5, 0.7, 1.0, 1.5):
        try: s = run_inertia(m, sig)
        except Exception as e: s = {"error": str(e)}
        name = f"P38_inertia_m{m}"
        if "error" in s:
            print(name, "ERROR", s["error"]); lines.append(f"| {name} | | | | ERR |"); continue
        passes,_ = haircut_verdict(s)
        v = "PASS" if passes else "fail"
        print(name, fmt(s), v)
        lines.append(f"| {name} | {s['cagr']*100:.2f}% | {s['sharpe']:.2f} | {s['max_dd']*100:.2f}% | {v} |")
    with open(log_path,"a",encoding="utf-8") as f: f.write("\n".join(lines)+"\n")

if __name__ == "__main__":
    main()
