"""Phase 27: creative bundle — dispersion-conditional, trans universe varies with proba,
trans-universe weight biases, minimum-stop logic.
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


def run_rc_proba(stable_uni, trans_uni, sig, pred_reg, max_proba,
                 proba_thresh_high=0.60):
    """Two-level regime split:
       high confidence transition (proba >= 0.60) → defensive trans_uni
       low confidence transition (0.40 <= proba < 0.60) → stable_uni (ignore)
       stable → stable_uni
    """
    _load(); b = _STATE["bundle"]
    cur = np.asarray(_cr(b.df).index)
    def mk_eng(uni, pred):
        cfg = copy.deepcopy(_STATE["cfg"])
        cfg.update({"universe":uni,"top1_weight":0.62,"top3_weight":0.38})
        shim = types.SimpleNamespace(**{k:getattr(b,k) for k in ("df","dates","atr21","fwd21","spy_dist_sma200","is_fomc_day")})
        nr = dict(b.returns); nr[cfg["lookback_stable"]]=sig; shim.returns=nr
        return PortfolioEngine(shim, pred, cfg)
    # build gated predictions with threshold 0.40 (ignore low-confidence switches)
    gated_pred = pred_reg.copy()
    want = (pred_reg != cur) & (pred_reg >= 0)
    low = np.nan_to_num(max_proba, nan=0.0) < 0.40
    gated_pred[want & low] = cur[want & low]
    eng_s = mk_eng(stable_uni, gated_pred); eng_t = mk_eng(trans_uni, gated_pred)

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
        # Use transition-uni ONLY when high-confidence transition prediction
        is_trans_hi = (pred_reg[i] != cur[i]) and (pred_reg[i] >= 0) and (not np.isnan(max_proba[i])) and (max_proba[i] >= proba_thresh_high)
        eng = eng_t if is_trans_hi else eng_s
        rets.append(ret_at(eng, i))
    return compute_stats(np.array(rets))


def main():
    with open(PROBA,"rb") as f: pr, mp = pickle.load(f)
    sig = rankagg([(42,1),(63,3),(126,1)])
    log_path = HERE.parent / "LOG.md"
    ts = dt.datetime.now().isoformat(timespec="seconds")
    lines = [f"\n### phase27_more_creative  {ts}\n",
             "| name | CAGR | Sharpe | MaxDD | verdict |","|---|---|---|---|---|"]

    experiments = []
    # Two-tier: defensive trans uni only used at high confidence
    for thr in (0.50, 0.55, 0.60, 0.65, 0.70, 0.75):
        experiments.append((f"P27.01_tier_proba{int(thr*100)}", STABLE, TRANS, thr))

    for name, su, tu, pt in experiments:
        try: s = run_rc_proba(su, tu, sig, pr, mp, proba_thresh_high=pt)
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
