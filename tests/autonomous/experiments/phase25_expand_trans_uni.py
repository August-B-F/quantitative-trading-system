"""Phase 25: expand transition universe further, try different split in transition."""
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
        ranks = r.rank(axis=1,method="average")*w if ranks is None else ranks+r.rank(axis=1,method="average")*w
    return ranks/total

def run_rc(stable_uni, trans_uni, sig, gated_p, stable_split=(0.62,0.38), trans_split=None):
    _load(); b = _STATE["bundle"]
    cur = np.asarray(_cr(b.df).index)
    if trans_split is None: trans_split = stable_split
    def mk_eng(uni, split):
        cfg = copy.deepcopy(_STATE["cfg"])
        cfg.update({"universe":uni,"top1_weight":split[0],"top3_weight":split[1]})
        shim = types.SimpleNamespace(**{k:getattr(b,k) for k in ("df","dates","atr21","fwd21","spy_dist_sma200","is_fomc_day")})
        nr = dict(b.returns); nr[cfg["lookback_stable"]]=sig; shim.returns=nr
        return PortfolioEngine(shim, gated_p, cfg)
    eng_s = mk_eng(stable_uni, stable_split); eng_t = mk_eng(trans_uni, trans_split)
    td = _STATE["test_dates"]
    td_positions = pd.Series(eng_s.dates.get_indexer(td), index=td)
    month_last = td_positions.groupby(td.to_period("M")).tail(1)
    fomc_idx = np.where(b.is_fomc_day)[0]
    event_mask = fomc_window_mask(eng_s.n_days, fomc_idx, pre_days=0, post_days=2)
    def ret_at(eng, i):
        t1,tk = eng.pick_at(i)
        r1 = eng.fwd_arr[i,t1] if eng.spy_dist[i]>eng.sma_buffer else eng.cash_fwd[i]
        sel = eng.atr_arr[i,tk]; inv = 1.0/np.where(sel>0,sel,np.nan)
        if np.isnan(inv).all(): rk = np.nanmean(eng.fwd_arr[i,tk])
        else: w=inv/np.nansum(inv); rk=np.nansum(eng.fwd_arr[i,tk]*w)
        return eng.top1_w*r1 + eng.topk_w*rk
    rets = []
    for rd, pos in month_last.items():
        i, _ = resolve_rebalance_index(int(pos), 3, event_mask, eng_s.n_days)
        is_stable = (gated_p[i]==cur[i]) or (gated_p[i]<0)
        eng = eng_s if is_stable else eng_t
        rets.append(ret_at(eng, i))
    return compute_stats(np.array(rets))


def main():
    g = gated(0.40)
    sig = rankagg([(42,1),(63,3),(126,1)])
    log_path = HERE.parent / "LOG.md"
    ts = dt.datetime.now().isoformat(timespec="seconds")
    lines = [f"\n### phase25_expand_trans_uni  {ts}\n",
             "| name | CAGR | Sharpe | MaxDD | verdict |","|---|---|---|---|---|"]

    experiments = [
        ("P25.00_ref",                             STABLE + ["TLT","AGG"], None),
        ("P25.01_trans_+TLT_+AGG_+XLV",            STABLE + ["TLT","AGG","XLV"], None),
        ("P25.02_trans_+TLT_+AGG_+XLI",            STABLE + ["TLT","AGG","XLI"], None),
        ("P25.03_trans_+TLT_+AGG_+XLV_+XLI",       STABLE + ["TLT","AGG","XLV","XLI"], None),
        ("P25.04_trans_+TLT_+AGG_+DBC",            STABLE + ["TLT","AGG","DBC"], None),
        ("P25.05_trans_+all_extras",               STABLE + ["TLT","AGG","XLV","XLI","XLF"], None),
        ("P25.06_trans_+TLT_+AGG_defsplit",        STABLE + ["TLT","AGG"], (0.50,0.50)),
        ("P25.07_trans_+TLT_+AGG_topksplit",       STABLE + ["TLT","AGG"], (0.40,0.60)),
        ("P25.08_trans_+TLT_+AGG_aggressive",      STABLE + ["TLT","AGG"], (0.70,0.30)),
        ("P25.09_trans_+TLT_+AGG_equalsplit",      STABLE + ["TLT","AGG"], (0.55,0.45)),
    ]
    for name, tu, tsplit in experiments:
        try: s = run_rc(STABLE, tu, sig, g, trans_split=tsplit)
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
