"""Phase 26: push on the successful XLV addition. Try XLV in stable universe too, and more combos."""
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

STABLE6 = ["SOXX","QQQ","IGV","XLE","GLD","SHY"]
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

def run_rc(stable_uni, trans_uni, sig, gated_p):
    _load(); b = _STATE["bundle"]
    cur = np.asarray(_cr(b.df).index)
    def mk_eng(uni):
        cfg = copy.deepcopy(_STATE["cfg"])
        cfg.update({"universe":uni,"top1_weight":0.62,"top3_weight":0.38})
        shim = types.SimpleNamespace(**{k:getattr(b,k) for k in ("df","dates","atr21","fwd21","spy_dist_sma200","is_fomc_day")})
        nr = dict(b.returns); nr[cfg["lookback_stable"]]=sig; shim.returns=nr
        return PortfolioEngine(shim, gated_p, cfg)
    eng_s = mk_eng(stable_uni); eng_t = mk_eng(trans_uni)
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
        rets.append(ret_at(eng_s if is_stable else eng_t, i))
    return compute_stats(np.array(rets))

def main():
    g = gated(0.40)
    sig = rankagg([(42,1),(63,3),(126,1)])
    log_path = HERE.parent / "LOG.md"
    ts = dt.datetime.now().isoformat(timespec="seconds")
    lines = [f"\n### phase26_more_expansions  {ts}\n",
             "| name | CAGR | Sharpe | MaxDD | verdict |","|---|---|---|---|---|"]

    # stable=7 (add XLV), trans=7+TLT+AGG
    S7 = STABLE6 + ["XLV"]
    experiments = [
        ("P26.00_ref27.50", STABLE6, STABLE6 + ["TLT","AGG","XLV"]),
        ("P26.01_stable+XLV_trans+TLT_AGG",          S7, S7 + ["TLT","AGG"]),
        ("P26.02_stable+XLV_trans+TLT_AGG_+XLF",     S7, S7 + ["TLT","AGG","XLF"]),
        ("P26.03_stable6_trans+TLT_AGG_XLV_XLF",     STABLE6, STABLE6 + ["TLT","AGG","XLV","XLF"]),
        ("P26.04_stable6_trans+TLT_AGG_XLV_IWM",     STABLE6, STABLE6 + ["TLT","AGG","XLV","IWM"]),
        ("P26.05_stable6_trans+TLT_AGG_XLV_noenergy",STABLE6, ["SOXX","QQQ","IGV","GLD","SHY","TLT","AGG","XLV"]),
        ("P26.06_stable6_trans+TLT_AGG_XLV_noqqq",   STABLE6, ["SOXX","IGV","XLE","GLD","SHY","TLT","AGG","XLV"]),
        ("P26.07_stable7XLV_trans+TLT_AGG_DBC",      S7, S7 + ["TLT","AGG","DBC"]),
        ("P26.08_stable5(noXLK)_trans+TLT_AGG_XLV",  ["SOXX","QQQ","XLE","GLD","SHY"], ["SOXX","QQQ","XLE","GLD","SHY","TLT","AGG","XLV"]),
    ]
    for name, su, tu in experiments:
        try: s = run_rc(su, tu, sig, g)
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
