"""Phase 57: exotic experiments."""
from __future__ import annotations
import sys, pickle, copy, types, datetime as dt
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import numpy as np, pandas as pd
from utils.base_test import _load, _STATE, fmt
from strategy.portfolio import PortfolioEngine
from backtest.engine import compute_stats
from strategy.rebalance import fomc_window_mask, resolve_rebalance_index
from features.regime_labels import current_regime as _cr

STABLE = ["SOXX","QQQ","IGV","XLE","GLD","SHY"]
TRANS = STABLE + ["TLT","AGG","XLV","XLF"]

with open(HERE.parent/"cache"/"pred_proba_p46.pkl","rb") as f: PR_RAW, MP_RAW = pickle.load(f)
_load(); B = _STATE["bundle"]
CUR = np.asarray(_cr(B.df).index)
GATED = PR_RAW.copy()
_w = (PR_RAW != CUR) & (PR_RAW >= 0)
_lc = np.nan_to_num(MP_RAW, nan=0) < 0.40
GATED[_w & _lc] = CUR[_w & _lc]


def rank_signal():
    cm = list(B.returns[63].columns); ranks=None
    for lb,wt in [(42,1),(63,3),(126,1)]:
        r = B.returns[lb][cm].rank(axis=1,method="average")
        ranks = r*wt if ranks is None else ranks+r*wt
    return ranks/5

SIG = rank_signal()
SPY_63 = B.returns[63]["SPY"].values
SPY_21 = B.returns[21]["SPY"].values


def mk_eng(uni, w1, sma_buf=-0.04):
    cfg = copy.deepcopy(_STATE["cfg"])
    cfg.update({"universe":uni,"top1_weight":w1,"top3_weight":1-w1,
                "fomc_window_pre":0,"fomc_window_after":1,"fomc_defer_days":4,
                "sma_gate_buffer":sma_buf})
    shim = types.SimpleNamespace(**{k:getattr(B,k) for k in ("df","dates","atr21","fwd21","spy_dist_sma200","is_fomc_day")})
    nr = dict(B.returns); nr[63]=SIG; shim.returns=nr
    return PortfolioEngine(shim, GATED, cfg)


def ret_at(eng, i):
    t1,tk = eng.pick_at(i)
    r1 = eng.fwd_arr[i,t1] if eng.spy_dist[i]>eng.sma_buffer else eng.cash_fwd[i]
    sel = eng.atr_arr[i,tk]; inv = 1.0/np.where(sel>0,sel,np.nan)
    if np.isnan(inv).all(): rk = np.nanmean(eng.fwd_arr[i,tk])
    else: ww=inv/np.nansum(inv); rk=np.nansum(eng.fwd_arr[i,tk]*ww)
    return eng.top1_w*r1 + eng.topk_w*rk


def base_w1(history, i, eng_default):
    if len(history)>=3: cum_dd = np.prod([1+h for h in history[-3:]])-1
    else: cum_dd = 0.05
    if len(history)>=6: cum_warm = np.prod([1+h for h in history[-6:]])-1
    else: cum_warm = 0.05
    if len(history)>=9: cum_b = np.prod([1+h for h in history[-9:]])-1
    else: cum_b = 0.05
    spy_v63 = SPY_63[i] if not np.isnan(SPY_63[i]) else 0.0
    spy_v21 = SPY_21[i] if not np.isnan(SPY_21[i]) else 0.0
    row = eng_default.sf[i]; sv = np.sort(row)[::-1]; margin = sv[0]-sv[1] if len(sv)>1 else 0
    if cum_dd<-0.02: return 0.45
    elif cum_b>0.30 or spy_v63>0.12: return 0.75
    elif cum_warm>0.25 or spy_v21>0.10: return 0.70
    elif margin < 0.3: return 0.45
    return 0.62


def run(stable_eng_dict, trans_eng_dict, no_sma_in_trans=False, trans_eng_nosma=None):
    td = _STATE["test_dates"]
    n_days = next(iter(stable_eng_dict.values())).n_days
    td_positions = pd.Series(B.dates.get_indexer(td), index=td)
    month_last = td_positions.groupby(td.to_period("M")).tail(1)
    fomc_idx = np.where(B.is_fomc_day)[0]
    event_mask = fomc_window_mask(n_days, fomc_idx, pre_days=0, post_days=1)
    rets=[]; history=[]
    for rd, pos in month_last.items():
        i, _ = resolve_rebalance_index(int(pos), 4, event_mask, n_days)
        use_t = (PR_RAW[i] != CUR[i]) and (PR_RAW[i] >= 0) and (not np.isnan(MP_RAW[i])) and (MP_RAW[i] >= 0.50)
        eng_default = trans_eng_dict[0.62] if use_t else stable_eng_dict[0.62]
        w1 = base_w1(history, i, eng_default)
        if w1 not in stable_eng_dict: w1 = min(stable_eng_dict.keys(), key=lambda x: abs(x-w1))
        if use_t:
            target = trans_eng_nosma if no_sma_in_trans and trans_eng_nosma is not None else trans_eng_dict
        else:
            target = stable_eng_dict
        eng = target[w1]
        r = ret_at(eng, i)
        history.append(r); rets.append(r)
    return compute_stats(np.array(rets))


def main():
    log_path = HERE.parent / "LOG.md"
    ts = dt.datetime.now().isoformat(timespec="seconds")
    lines = [f"\n### phase57_exotic  {ts}\n",
             "| name | CAGR | Sharpe | MaxDD | verdict |", "|---|---|---|---|---|"]
    WS = [0.45, 0.62, 0.70, 0.75]
    ENGS_S = {w: mk_eng(STABLE, w) for w in WS}
    ENGS_T = {w: mk_eng(TRANS, w) for w in WS}
    ENGS_T_NOSMA = {w: mk_eng(TRANS, w, sma_buf=-1.0) for w in WS}

    print("P54 ref:", fmt(run(ENGS_S, ENGS_T)))
    print()

    # 1. No SMA gate in trans regime — let momentum/inv-vol pick defensives
    s = run(ENGS_S, ENGS_T, no_sma_in_trans=True, trans_eng_nosma=ENGS_T_NOSMA)
    print(f"  no_sma_in_trans: {fmt(s)}")
    lines.append(f"| no_sma_in_trans | {s['cagr']*100:.2f}% | {s['sharpe']:.2f} | {s['max_dd']*100:.2f}% | {'PASS' if s['cagr']>0.3023 and s['sharpe']>=1.89 else 'fail'} |")

    # 2. Wider stable universe — add XLV permanently
    STABLE_XLV = STABLE + ["XLV"]
    ES_XLV = {w: mk_eng(STABLE_XLV, w) for w in WS}
    ET_XLV = {w: mk_eng(STABLE_XLV + ["TLT","AGG","XLF"], w) for w in WS}
    s = run(ES_XLV, ET_XLV)
    print(f"  stable_+XLV: {fmt(s)}")
    lines.append(f"| stable_+XLV | {s['cagr']*100:.2f}% | {s['sharpe']:.2f} | {s['max_dd']*100:.2f}% | {'PASS' if s['cagr']>0.3023 and s['sharpe']>=1.89 else 'fail'} |")

    # 3. Use TLT in stable universe
    STABLE_TLT = STABLE + ["TLT"]
    ES_TLT = {w: mk_eng(STABLE_TLT, w) for w in WS}
    ET_TLT = {w: mk_eng(STABLE_TLT + ["AGG","XLV","XLF"], w) for w in WS}
    s = run(ES_TLT, ET_TLT)
    print(f"  stable_+TLT: {fmt(s)}")
    lines.append(f"| stable_+TLT | {s['cagr']*100:.2f}% | {s['sharpe']:.2f} | {s['max_dd']*100:.2f}% | {'PASS' if s['cagr']>0.3023 and s['sharpe']>=1.89 else 'fail'} |")

    # 4. Stable+XLF
    STABLE_XLF = STABLE + ["XLF"]
    ES_XLF = {w: mk_eng(STABLE_XLF, w) for w in WS}
    ET_XLF = {w: mk_eng(STABLE_XLF + ["TLT","AGG","XLV"], w) for w in WS}
    s = run(ES_XLF, ET_XLF)
    print(f"  stable_+XLF: {fmt(s)}")
    lines.append(f"| stable_+XLF | {s['cagr']*100:.2f}% | {s['sharpe']:.2f} | {s['max_dd']*100:.2f}% | {'PASS' if s['cagr']>0.3023 and s['sharpe']>=1.89 else 'fail'} |")

    # 5. Stable with TLT replacing GLD
    STABLE_NO_GLD = ["SOXX","QQQ","IGV","XLE","TLT","SHY"]
    ES_NG = {w: mk_eng(STABLE_NO_GLD, w) for w in WS}
    ET_NG = {w: mk_eng(STABLE_NO_GLD + ["GLD","AGG","XLV","XLF"], w) for w in WS}
    s = run(ES_NG, ET_NG)
    print(f"  swap_GLD_TLT: {fmt(s)}")
    lines.append(f"| swap_GLD_TLT | {s['cagr']*100:.2f}% | {s['sharpe']:.2f} | {s['max_dd']*100:.2f}% | {'PASS' if s['cagr']>0.3023 and s['sharpe']>=1.89 else 'fail'} |")

    # 6. Add IWM (small caps) to trans
    s = run(ENGS_S, {w: mk_eng(TRANS + ["IWM"], w) for w in WS})
    print(f"  trans_+IWM: {fmt(s)}")
    lines.append(f"| trans_+IWM | {s['cagr']*100:.2f}% | {s['sharpe']:.2f} | {s['max_dd']*100:.2f}% | {'PASS' if s['cagr']>0.3023 and s['sharpe']>=1.89 else 'fail'} |")

    # 7. Universe = all 11 ETFs in both regimes (no regime-conditional)
    BIG = ["SOXX","QQQ","IGV","XLE","GLD","SHY","TLT","AGG","XLV","XLF","XLI"]
    EBIG = {w: mk_eng(BIG, w) for w in WS}
    s = run(EBIG, EBIG)
    print(f"  big_uni_constant: {fmt(s)}")
    lines.append(f"| big_uni_constant | {s['cagr']*100:.2f}% | {s['sharpe']:.2f} | {s['max_dd']*100:.2f}% | {'PASS' if s['cagr']>0.3023 and s['sharpe']>=1.89 else 'fail'} |")

    # 8. Drop XLF (test reverse of P47)
    TR2 = ["SOXX","QQQ","IGV","XLE","GLD","SHY","TLT","AGG","XLV"]
    s = run(ENGS_S, {w: mk_eng(TR2, w) for w in WS})
    print(f"  trans_no_xlf: {fmt(s)}")
    lines.append(f"| trans_no_xlf | {s['cagr']*100:.2f}% | {s['sharpe']:.2f} | {s['max_dd']*100:.2f}% | {'PASS' if s['cagr']>0.3023 and s['sharpe']>=1.89 else 'fail'} |")

    # 9. Add MTUM (momentum factor) — but it's not in panel; skip
    # 10. trans + DBC (commodities)
    s = run(ENGS_S, {w: mk_eng(TRANS + ["DBC"], w) for w in WS})
    print(f"  trans_+DBC: {fmt(s)}")
    lines.append(f"| trans_+DBC | {s['cagr']*100:.2f}% | {s['sharpe']:.2f} | {s['max_dd']*100:.2f}% | {'PASS' if s['cagr']>0.3023 and s['sharpe']>=1.89 else 'fail'} |")

    # 11. trans + EEM
    s = run(ENGS_S, {w: mk_eng(TRANS + ["EEM"], w) for w in WS})
    print(f"  trans_+EEM: {fmt(s)}")
    lines.append(f"| trans_+EEM | {s['cagr']*100:.2f}% | {s['sharpe']:.2f} | {s['max_dd']*100:.2f}% | {'PASS' if s['cagr']>0.3023 and s['sharpe']>=1.89 else 'fail'} |")

    # 12. trans + XLI
    s = run(ENGS_S, {w: mk_eng(TRANS + ["XLI"], w) for w in WS})
    print(f"  trans_+XLI: {fmt(s)}")
    lines.append(f"| trans_+XLI | {s['cagr']*100:.2f}% | {s['sharpe']:.2f} | {s['max_dd']*100:.2f}% | {'PASS' if s['cagr']>0.3023 and s['sharpe']>=1.89 else 'fail'} |")

    with open(log_path, "a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
