"""Phase 50: class-specific transition universe.

Instead of one transition universe [+TLT, +AGG, +XLV] regardless of predicted class,
use a different expansion based on WHICH regime class the classifier predicts:

REGIME_CLASSES = ['regime_hg_li', 'regime_hg_hi', 'regime_lg_li', 'regime_lg_hi_stagflation']
                    idx 0           idx 1         idx 2          idx 3

- idx 0 HG_LI: tech-favorable — minimal expansion
- idx 1 HG_HI: commodity rally — XLE, DBC, lumber proxies
- idx 2 LG_LI: bond rally — TLT, AGG, XLV (defensive equities)
- idx 3 LG_HI stagflation: gold, short duration — GLD emphasis, TLT
"""
from __future__ import annotations
import sys, pickle, copy, types
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import numpy as np, pandas as pd
from utils.base_test import _load, _STATE, fmt, haircut_verdict
from strategy.portfolio import PortfolioEngine
from backtest.engine import compute_stats
from strategy.rebalance import fomc_window_mask, resolve_rebalance_index
from features.regime_labels import current_regime as _cr

STABLE = ["SOXX","QQQ","IGV","XLE","GLD","SHY"]


def rankagg(weights):
    _load(); b = _STATE["bundle"]
    cm=None; total=sum(w for _,w in weights); ranks=None
    for lb,w in weights:
        r = b.returns[lb]
        if cm is None: cm = list(r.columns)
        else: r = r[cm]
        ranks = r.rank(axis=1,method="average")*w if ranks is None else ranks+r.rank(axis=1,method="average")*w
    return ranks/total


def run_class_specific(class_universes, sig):
    """class_universes: dict of class_idx -> list of extra tickers to add to STABLE."""
    with open(HERE.parent / "cache" / "pred_proba_p46.pkl", "rb") as f:
        pr, mp = pickle.load(f)
    _load(); b = _STATE["bundle"]
    cur = np.asarray(_cr(b.df).index)
    gated = pr.copy(); w=(pr!=cur)&(pr>=0); lc = np.nan_to_num(mp,nan=0)<0.40
    gated[w&lc]=cur[w&lc]

    def mk_eng(uni):
        cfg = copy.deepcopy(_STATE["cfg"])
        cfg.update({"universe":uni,"top1_weight":0.62,"top3_weight":0.38,
                    "fomc_window_pre":0,"fomc_window_after":1,"fomc_defer_days":4})
        shim = types.SimpleNamespace(**{k:getattr(b,k) for k in ("df","dates","atr21","fwd21","spy_dist_sma200","is_fomc_day")})
        nr = dict(b.returns); nr[cfg["lookback_stable"]]=sig; shim.returns=nr
        return PortfolioEngine(shim, gated, cfg)

    # Build one engine per class universe + stable engine
    eng_s = mk_eng(STABLE)
    class_engs = {}
    for cls_idx, extras in class_universes.items():
        uni = STABLE + [t for t in extras if t not in STABLE]
        class_engs[cls_idx] = mk_eng(uni)

    td = _STATE["test_dates"]
    td_positions = pd.Series(eng_s.dates.get_indexer(td), index=td)
    month_last = td_positions.groupby(td.to_period("M")).tail(1)
    fomc_idx = np.where(b.is_fomc_day)[0]
    event_mask = fomc_window_mask(eng_s.n_days, fomc_idx, pre_days=0, post_days=1)

    def ret_at(eng, i):
        t1,tk = eng.pick_at(i)
        r1 = eng.fwd_arr[i,t1] if eng.spy_dist[i]>eng.sma_buffer else eng.cash_fwd[i]
        sel = eng.atr_arr[i,tk]; inv = 1.0/np.where(sel>0,sel,np.nan)
        if np.isnan(inv).all(): rk = np.nanmean(eng.fwd_arr[i,tk])
        else: ww=inv/np.nansum(inv); rk=np.nansum(eng.fwd_arr[i,tk]*ww)
        return eng.top1_w*r1 + eng.topk_w*rk

    rets = []
    class_counts = {c: 0 for c in class_universes}
    for rd, pos in month_last.items():
        i, _ = resolve_rebalance_index(int(pos), 4, event_mask, eng_s.n_days)
        use_t = (pr[i]!=cur[i]) and (pr[i]>=0) and (not np.isnan(mp[i])) and (mp[i]>=0.50)
        if use_t and pr[i] in class_engs:
            eng = class_engs[pr[i]]
            class_counts[pr[i]] += 1
        else:
            eng = eng_s
        rets.append(ret_at(eng, i))
    return compute_stats(np.array(rets)), class_counts


def main():
    sig = rankagg([(42,1),(63,3),(126,1)])

    # Reference: current P46 uses uniform [TLT, AGG, XLV] for all trans predictions
    REF_UNIFORM = {0:["TLT","AGG","XLV"], 1:["TLT","AGG","XLV"], 2:["TLT","AGG","XLV"], 3:["TLT","AGG","XLV"]}

    # Candidate class-specific configurations
    V1 = {
        0: [],  # HG_LI (tech favored) — no expansion
        1: ["XLE","DBC"],  # HG_HI commodity rally
        2: ["TLT","AGG","XLV"],  # LG_LI bond rally
        3: ["TLT","DBC"],  # LG_HI stagflation (gold hedge already in STABLE)
    }
    V2 = {
        0: ["XLV"],
        1: ["XLE","DBC","XLI"],
        2: ["TLT","AGG"],
        3: ["TLT","DBC","GLD"],
    }
    V3 = {
        0: [],
        1: ["DBC","XLE"],
        2: ["TLT","AGG","XLV"],
        3: ["TLT","DBC"],
    }
    V4 = {
        0: ["XLV"],  # small defensive even in HG_LI
        1: ["DBC"],  # commodities in HG_HI
        2: ["TLT","AGG","XLV"],
        3: ["TLT","AGG"],  # stagflation: both bonds + stable + gold in STABLE
    }
    V5 = {  # very asymmetric: skip expansion in HG_LI entirely
        0: [],
        1: ["XLE","DBC","XLV"],
        2: ["TLT","AGG","XLV"],
        3: ["TLT","DBC","XLV"],
    }

    configs = [("ref_uniform", REF_UNIFORM), ("V1_minimal", V1), ("V2_broad", V2), ("V3_balanced", V3),
               ("V4_smalldef", V4), ("V5_asymm", V5)]

    log_path = HERE.parent / "LOG.md"
    import datetime as dt
    ts = dt.datetime.now().isoformat(timespec="seconds")
    lines = [f"\n### phase50_class_specific_universe  {ts}\n",
             "| name | CAGR | Sharpe | MaxDD | verdict |", "|---|---|---|---|---|"]

    for name, cu in configs:
        try:
            s, counts = run_class_specific(cu, sig)
        except Exception as e:
            s = {"error": str(e)}; counts = {}
        if "error" in s:
            print(name, "ERROR", s["error"])
            lines.append(f"| {name} | | | | ERR |"); continue
        passes,_ = haircut_verdict(s)
        v = "PASS" if passes else "fail"
        print(name, fmt(s), f"class counts: {counts}", v)
        lines.append(f"| {name} | {s['cagr']*100:.2f}% | {s['sharpe']:.2f} | {s['max_dd']*100:.2f}% | {v} |")
    with open(log_path, "a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
