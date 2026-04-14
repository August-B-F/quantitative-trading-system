"""Phase 34: a batch of leftover ideas.

- Apply rank aggregation weights (42,1)(63,3)(126,1) on BOTH legs with fresh cross-asset features
- Tighter classifier gate threshold (explore 0.42, 0.44, 0.46)
- Exclude XLE from stable, keep in transition
- Use 5d weekly check on top1 rotation
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

def run_full(stable_uni, trans_uni, sig, sig_gate=0.40, uni_tier=0.50):
    with open(PROBA,"rb") as f: pr, mp = pickle.load(f)
    _load(); b = _STATE["bundle"]
    cur = np.asarray(_cr(b.df).index)
    gated = pr.copy(); w=(pr!=cur)&(pr>=0); lc = np.nan_to_num(mp,nan=0)<sig_gate
    gated[w&lc]=cur[w&lc]
    def mk_eng(uni):
        cfg = copy.deepcopy(_STATE["cfg"])
        cfg.update({"universe":uni,"top1_weight":0.62,"top3_weight":0.38})
        shim = types.SimpleNamespace(**{k:getattr(b,k) for k in ("df","dates","atr21","fwd21","spy_dist_sma200","is_fomc_day")})
        nr = dict(b.returns); nr[cfg["lookback_stable"]]=sig; shim.returns=nr
        return PortfolioEngine(shim, gated, cfg)
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
        else: ww=inv/np.nansum(inv); rk=np.nansum(eng.fwd_arr[i,tk]*ww)
        return eng.top1_w*r1 + eng.topk_w*rk
    rets = []
    for rd, pos in month_last.items():
        i, _ = resolve_rebalance_index(int(pos), 3, event_mask, eng_s.n_days)
        use_t = (pr[i]!=cur[i]) and (pr[i]>=0) and (not np.isnan(mp[i])) and (mp[i]>=uni_tier)
        rets.append(ret_at(eng_t if use_t else eng_s, i))
    return compute_stats(np.array(rets))

def main():
    sig = rankagg([(42,1),(63,3),(126,1)])
    log_path = HERE.parent / "LOG.md"
    ts = dt.datetime.now().isoformat(timespec="seconds")
    lines = [f"\n### phase34_alt_ideas  {ts}\n",
             "| name | CAGR | Sharpe | MaxDD | verdict |","|---|---|---|---|---|"]

    experiments = []
    # Tighter sig gate
    for sg in (0.36, 0.38, 0.40, 0.42, 0.44, 0.46, 0.48):
        experiments.append((f"P34.01_siggate_{int(sg*100)}", STABLE, TRANS, sig, sg, 0.50))
    # Tier variations
    for t in (0.46, 0.48, 0.50, 0.52, 0.54):
        experiments.append((f"P34.02_tier_{int(t*100)}", STABLE, TRANS, sig, 0.40, t))
    # Drop XLE from stable
    stable_noxle = ["SOXX","QQQ","IGV","GLD","SHY"]
    trans_noxle = stable_noxle + ["XLE","TLT","AGG","XLV"]
    experiments.append(("P34.03_no_xle_stable",  stable_noxle, trans_noxle, sig, 0.40, 0.50))
    # Alt rank weights: (21,1)(42,1)(63,3)(126,1) — add 21d
    sig_21 = rankagg([(21,1),(42,1),(63,3),(126,1)])
    experiments.append(("P34.04_add_21_to_sig", STABLE, TRANS, sig_21, 0.40, 0.50))
    sig_bigger = rankagg([(42,1),(63,4),(126,1)])
    experiments.append(("P34.05_63_x4", STABLE, TRANS, sig_bigger, 0.40, 0.50))
    sig_lower63 = rankagg([(42,2),(63,3),(126,1)])
    experiments.append(("P34.06_42_x2", STABLE, TRANS, sig_lower63, 0.40, 0.50))

    for exp in experiments:
        name, su, tu, sg_, sgate, tier = exp
        try: s = run_full(su, tu, sg_, sig_gate=sgate, uni_tier=tier)
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
