"""Phase 43: confirm P42 neighborhood and try tightening further."""
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


def run_full(sig, split, fomc, uni_tier=0.50, sig_gate=0.40, stable=None, trans=None):
    stable = stable or STABLE; trans = trans or TRANS
    with open(PROBA,"rb") as f: pr, mp = pickle.load(f)
    _load(); b = _STATE["bundle"]
    cur = np.asarray(_cr(b.df).index)
    gated = pr.copy(); w=(pr!=cur)&(pr>=0); lc = np.nan_to_num(mp,nan=0)<sig_gate
    gated[w&lc]=cur[w&lc]
    def mk_eng(uni):
        cfg = copy.deepcopy(_STATE["cfg"])
        cfg.update({"universe":uni,"top1_weight":split[0],"top3_weight":split[1],
                    "fomc_window_pre":fomc[0],"fomc_window_after":fomc[1],"fomc_defer_days":fomc[2]})
        shim = types.SimpleNamespace(**{k:getattr(b,k) for k in ("df","dates","atr21","fwd21","spy_dist_sma200","is_fomc_day")})
        nr = dict(b.returns); nr[cfg["lookback_stable"]]=sig; shim.returns=nr
        return PortfolioEngine(shim, gated, cfg)
    eng_s = mk_eng(stable); eng_t = mk_eng(trans)
    td = _STATE["test_dates"]
    td_positions = pd.Series(eng_s.dates.get_indexer(td), index=td)
    month_last = td_positions.groupby(td.to_period("M")).tail(1)
    fomc_idx = np.where(b.is_fomc_day)[0]
    event_mask = fomc_window_mask(eng_s.n_days, fomc_idx, pre_days=fomc[0], post_days=fomc[1])
    def ret_at(eng, i):
        t1,tk = eng.pick_at(i)
        r1 = eng.fwd_arr[i,t1] if eng.spy_dist[i]>eng.sma_buffer else eng.cash_fwd[i]
        sel = eng.atr_arr[i,tk]; inv = 1.0/np.where(sel>0,sel,np.nan)
        if np.isnan(inv).all(): rk = np.nanmean(eng.fwd_arr[i,tk])
        else: ww=inv/np.nansum(inv); rk=np.nansum(eng.fwd_arr[i,tk]*ww)
        return eng.top1_w*r1 + eng.topk_w*rk
    rets = []
    for rd, pos in month_last.items():
        i, _ = resolve_rebalance_index(int(pos), fomc[2], event_mask, eng_s.n_days)
        use_t = (pr[i]!=cur[i]) and (pr[i]>=0) and (not np.isnan(mp[i])) and (mp[i]>=uni_tier)
        rets.append(ret_at(eng_t if use_t else eng_s, i))
    return compute_stats(np.array(rets))


def main():
    sig = rankagg([(42,1),(63,3),(126,1)])
    log_path = HERE.parent / "LOG.md"
    ts = dt.datetime.now().isoformat(timespec="seconds")
    lines = [f"\n### phase43_neighborhood_p42  {ts}\n",
             "| name | CAGR | Sharpe | MaxDD | verdict |","|---|---|---|---|---|"]

    base_fomc = (0, 1, 4)
    base_split = (0.62, 0.38)

    experiments = []
    # Split grid around 62/38 at new FOMC
    for w1 in (0.55, 0.58, 0.60, 0.62, 0.64, 0.66, 0.68):
        experiments.append((f"P43.01_split{int(w1*100)}", sig, (w1,1-w1), base_fomc))
    # Rank weight perturbations
    for rw in [[(42,0.5),(63,3),(126,1)], [(42,1),(63,2.5),(126,1)], [(42,1),(63,3.5),(126,1)],
               [(42,1),(63,3),(126,0.5)], [(42,1),(63,3),(126,1.5)], [(42,1.5),(63,3),(126,1)]]:
        sig2 = rankagg(rw)
        nm = "_".join(f"{lb}x{w}" for lb,w in rw)
        experiments.append((f"P43.02_rw_{nm}", sig2, base_split, base_fomc))
    # Tier variations
    for t in (0.48, 0.50, 0.52):
        experiments.append((f"P43.03_tier_{int(t*100)}", sig, base_split, base_fomc))

    for name, sg, sp, fo in experiments:
        ut = 0.50
        if "tier_48" in name: ut = 0.48
        elif "tier_52" in name: ut = 0.52
        try: s = run_full(sg, sp, fo, uni_tier=ut)
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
