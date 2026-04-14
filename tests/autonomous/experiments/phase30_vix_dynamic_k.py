"""Phase 30: VIX-dynamic top_k.

High VIX → diversify (top_k=4 or 5)
Low VIX → concentrate (top_k=2 or 3)
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


def run_dynamic_k(stable_uni, trans_uni, sig, vix_lo, vix_hi, k_lo, k_hi):
    """k_lo used when VIX < vix_lo, k_hi when VIX > vix_hi, linear middle."""
    with open(PROBA,"rb") as f: pr, mp = pickle.load(f)
    _load(); b = _STATE["bundle"]
    cur = np.asarray(_cr(b.df).index)
    gated = pr.copy(); w=(pr!=cur)&(pr>=0); lc = np.nan_to_num(mp,nan=0)<0.40
    gated[w&lc]=cur[w&lc]

    vix = b.df.get("vol_features__vix")
    if vix is None: return {"error": "no vix"}
    vix = vix.values

    def mk_eng(uni, k):
        cfg = copy.deepcopy(_STATE["cfg"])
        cfg.update({"universe":uni,"top1_weight":0.62,"top3_weight":0.38,"top_k":k})
        shim = types.SimpleNamespace(**{k2:getattr(b,k2) for k2 in ("df","dates","atr21","fwd21","spy_dist_sma200","is_fomc_day")})
        nr = dict(b.returns); nr[cfg["lookback_stable"]]=sig; shim.returns=nr
        return PortfolioEngine(shim, gated, cfg)

    # build two engines per regime (stable/trans) per k level
    engines = {}
    for uni_name, uni in [("s", stable_uni), ("t", trans_uni)]:
        for k in (k_lo, k_hi):
            engines[(uni_name, k)] = mk_eng(uni, k)

    td = _STATE["test_dates"]
    td_positions = pd.Series(engines[("s",k_lo)].dates.get_indexer(td), index=td)
    month_last = td_positions.groupby(td.to_period("M")).tail(1)
    fomc_idx = np.where(b.is_fomc_day)[0]
    event_mask = fomc_window_mask(engines[("s",k_lo)].n_days, fomc_idx, pre_days=0, post_days=2)

    def ret_at(eng, i):
        t1,tk = eng.pick_at(i)
        r1 = eng.fwd_arr[i,t1] if eng.spy_dist[i]>eng.sma_buffer else eng.cash_fwd[i]
        sel = eng.atr_arr[i,tk]; inv = 1.0/np.where(sel>0,sel,np.nan)
        if np.isnan(inv).all(): rk = np.nanmean(eng.fwd_arr[i,tk])
        else: ww=inv/np.nansum(inv); rk=np.nansum(eng.fwd_arr[i,tk]*ww)
        return eng.top1_w*r1 + eng.topk_w*rk

    rets = []
    for rd, pos in month_last.items():
        i, _ = resolve_rebalance_index(int(pos), 3, event_mask, engines[("s",k_lo)].n_days)
        use_t = (pr[i]!=cur[i]) and (pr[i]>=0) and (not np.isnan(mp[i])) and (mp[i]>=0.50)
        v = vix[i] if not np.isnan(vix[i]) else (vix_lo + vix_hi)/2
        k = k_lo if v <= vix_lo else (k_hi if v >= vix_hi else (k_lo if abs(v-vix_lo) < abs(v-vix_hi) else k_hi))
        uni_n = "t" if use_t else "s"
        eng = engines[(uni_n, k)]
        rets.append(ret_at(eng, i))
    return compute_stats(np.array(rets))


def main():
    sig = rankagg([(42,1),(63,3),(126,1)])
    log_path = HERE.parent / "LOG.md"
    ts = dt.datetime.now().isoformat(timespec="seconds")
    lines = [f"\n### phase30_vix_dynamic_k  {ts}\n",
             "| name | CAGR | Sharpe | MaxDD | verdict |","|---|---|---|---|---|"]
    grid = [
        ("lowvix15_hi25_k2_k4", 15, 25, 2, 4),
        ("lowvix18_hi25_k2_k4", 18, 25, 2, 4),
        ("lowvix20_hi30_k2_k4", 20, 30, 2, 4),
        ("lowvix15_hi25_k3_k4", 15, 25, 3, 4),
        ("lowvix15_hi20_k3_k4", 15, 20, 3, 4),
        ("flipped_lowk4_hik3",  15, 25, 4, 3),
        ("flipped_lowk4_hik2",  15, 25, 4, 2),
    ]
    for name, lo, hi, kl, kh in grid:
        try: s = run_dynamic_k(STABLE, TRANS, sig, lo, hi, kl, kh)
        except Exception as e: s = {"error": str(e)}
        fn = f"P30_{name}"
        if "error" in s:
            print(fn, "ERROR", s["error"]); lines.append(f"| {fn} | | | | ERR |"); continue
        passes,_ = haircut_verdict(s)
        v = "PASS" if passes else "fail"
        print(fn, fmt(s), v)
        lines.append(f"| {fn} | {s['cagr']*100:.2f}% | {s['sharpe']:.2f} | {s['max_dd']*100:.2f}% | {v} |")
    with open(log_path,"a",encoding="utf-8") as f: f.write("\n".join(lines)+"\n")

if __name__ == "__main__":
    main()
