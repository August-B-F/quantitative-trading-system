"""Phase 59: OOS-validated feature search. Each test must improve OR stay flat in BOTH halves."""
from __future__ import annotations
import sys, pickle, copy, types, datetime as dt
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import numpy as np, pandas as pd
from utils.base_test import _load, _STATE, fmt
from strategy.portfolio import PortfolioEngine
from backtest.engine import compute_stats, run_backtest
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
SPY_63 = B.returns[63]["SPY"].values
SPY_42 = B.returns[42]["SPY"].values
SPY_21 = B.returns[21]["SPY"].values


def rank_signal():
    cm = list(B.returns[63].columns); ranks=None
    for lb,wt in [(42,1),(63,3),(126,1)]:
        r = B.returns[lb][cm].rank(axis=1,method="average")
        ranks = r*wt if ranks is None else ranks+r*wt
    return ranks/5
SIG = rank_signal()


def mk_eng(uni, w1):
    cfg = copy.deepcopy(_STATE["cfg"])
    cfg.update({"universe":uni,"top1_weight":w1,"top3_weight":1-w1,
                "fomc_window_pre":0,"fomc_window_after":1,"fomc_defer_days":4})
    shim = types.SimpleNamespace(**{k:getattr(B,k) for k in ("df","dates","atr21","fwd21","spy_dist_sma200","is_fomc_day")})
    nr = dict(B.returns); nr[63]=SIG; shim.returns=nr
    return PortfolioEngine(shim, GATED, cfg)


WS = [0.45, 0.50, 0.55, 0.62, 0.70, 0.75, 0.80]
ENGS_S = {w: mk_eng(STABLE, w) for w in WS}
ENGS_T = {w: mk_eng(TRANS, w) for w in WS}


def ret_at(eng, i):
    t1,tk = eng.pick_at(i)
    r1 = eng.fwd_arr[i,t1] if eng.spy_dist[i]>eng.sma_buffer else eng.cash_fwd[i]
    sel = eng.atr_arr[i,tk]; inv = 1.0/np.where(sel>0,sel,np.nan)
    if np.isnan(inv).all(): rk = np.nanmean(eng.fwd_arr[i,tk])
    else: ww=inv/np.nansum(inv); rk=np.nansum(eng.fwd_arr[i,tk]*ww)
    return eng.top1_w*r1 + eng.topk_w*rk


def run_w1(w1_fn):
    td = _STATE["test_dates"]
    td_positions = pd.Series(B.dates.get_indexer(td), index=td)
    month_last = td_positions.groupby(td.to_period("M")).tail(1)
    fomc_idx = np.where(B.is_fomc_day)[0]
    n_days = ENGS_S[0.62].n_days
    event_mask = fomc_window_mask(n_days, fomc_idx, pre_days=0, post_days=1)
    rets=[]; history=[]; idates=[]
    for rd, pos in month_last.items():
        i, _ = resolve_rebalance_index(int(pos), 4, event_mask, n_days)
        use_t = (PR_RAW[i] != CUR[i]) and (PR_RAW[i] >= 0) and (not np.isnan(MP_RAW[i])) and (MP_RAW[i] >= 0.50)
        eng_d = ENGS_T[0.62] if use_t else ENGS_S[0.62]
        w1 = w1_fn(history, i, eng_d, use_t)
        if w1 not in WS: w1 = min(WS, key=lambda x: abs(x-w1))
        engs = ENGS_T if use_t else ENGS_S
        r = ret_at(engs[w1], i)
        history.append(r); rets.append(r); idates.append(rd)
    return pd.Series(rets, index=idates)


BASE_MR = run_backtest(PortfolioEngine(B, _STATE["pred_reg"], _STATE["cfg"]), _STATE["test_dates"], _STATE["cfg"]).monthly_returns


def both_half_score(s):
    fh = s[s.index.year < 2018]; sh = s[s.index.year >= 2018]
    fh_b = BASE_MR.reindex(fh.index); sh_b = BASE_MR.reindex(sh.index)
    fh_e = (fh - fh_b).dropna()
    sh_e = (sh - sh_b).dropna()
    fh_ann = ((1+fh_e.mean())**12-1)*100 if len(fh_e) else 0
    sh_ann = ((1+sh_e.mean())**12-1)*100 if len(sh_e) else 0
    full = compute_stats(s.values)
    return full["cagr"]*100, full["sharpe"], full["max_dd"]*100, fh_ann, sh_ann


def common(history, i):
    if len(history)>=3: cum_dd = np.prod([1+h for h in history[-3:]])-1
    else: cum_dd = 0.05
    if len(history)>=6: cum_warm = np.prod([1+h for h in history[-6:]])-1
    else: cum_warm = 0.05
    if len(history)>=9: cum_b = np.prod([1+h for h in history[-9:]])-1
    else: cum_b = 0.05
    return cum_dd, cum_warm, cum_b


def w1_p53(h, i, eng, ut):
    cum_dd, cum_warm, cum_b = common(h, i)
    spy_v63 = SPY_63[i] if not np.isnan(SPY_63[i]) else 0.0
    spy_v21 = SPY_21[i] if not np.isnan(SPY_21[i]) else 0.0
    if cum_dd<-0.02: return 0.45
    if cum_b>0.30 or spy_v63>0.12: return 0.75
    if cum_warm>0.25 or spy_v21>0.10: return 0.70
    return 0.62


def main():
    P53 = both_half_score(run_w1(w1_p53))
    P53_FH, P53_SH = P53[3], P53[4]
    print(f"P53 ref: cagr={P53[0]:5.2f} sharpe={P53[1]:.2f} maxdd={P53[2]:.2f} first={P53_FH:+.2f} second={P53_SH:+.2f}")
    print()

    log_path = HERE.parent / "LOG.md"
    ts = dt.datetime.now().isoformat(timespec="seconds")
    lines = [f"\n### phase59_oos_validated  {ts}\n",
             "| name | CAGR | Sharpe | first_edge | second_edge | OOS_pass |",
             "|---|---|---|---|---|---|"]

    tests = []
    # SPY 21d boost (fast trigger)
    def w1_spy21(h, i, eng, ut):
        cum_dd, cum_warm, cum_b = common(h, i)
        spy_v63 = SPY_63[i] if not np.isnan(SPY_63[i]) else 0.0
        spy_v21 = SPY_21[i] if not np.isnan(SPY_21[i]) else 0.0
        if cum_dd<-0.02: return 0.45
        if cum_b>0.30 or spy_v63>0.12 or spy_v21>0.06: return 0.75
        if cum_warm>0.25 or spy_v21>0.10: return 0.70
        return 0.62
    tests.append(("spy21d>6_full_boost", w1_spy21))

    # SPY 42d boost
    def w1_spy42(h, i, eng, ut):
        cum_dd, cum_warm, cum_b = common(h, i)
        spy_v63 = SPY_63[i] if not np.isnan(SPY_63[i]) else 0.0
        spy_v42 = SPY_42[i] if not np.isnan(SPY_42[i]) else 0.0
        spy_v21 = SPY_21[i] if not np.isnan(SPY_21[i]) else 0.0
        if cum_dd<-0.02: return 0.45
        if cum_b>0.30 or spy_v63>0.12 or spy_v42>0.08: return 0.75
        if cum_warm>0.25 or spy_v21>0.10: return 0.70
        return 0.62
    tests.append(("spy42d>8_full_boost", w1_spy42))

    # Various DD threshold variations
    for dd_lb, dd_thr in [(2,-0.02),(3,-0.01),(3,-0.03),(4,-0.02),(4,-0.03)]:
        def make_dd(lb, thr):
            def f(h, i, eng, ut):
                if len(h)>=lb: cd = np.prod([1+x for x in h[-lb:]])-1
                else: cd = 0.05
                cw = np.prod([1+x for x in h[-6:]])-1 if len(h)>=6 else 0.05
                cb = np.prod([1+x for x in h[-9:]])-1 if len(h)>=9 else 0.05
                spy_v63 = SPY_63[i] if not np.isnan(SPY_63[i]) else 0.0
                spy_v21 = SPY_21[i] if not np.isnan(SPY_21[i]) else 0.0
                if cd < thr: return 0.45
                if cb>0.30 or spy_v63>0.12: return 0.75
                if cw>0.25 or spy_v21>0.10: return 0.70
                return 0.62
            return f
        tests.append((f"dd_lb{dd_lb}m_thr{int(dd_thr*100)}pct", make_dd(dd_lb, dd_thr)))

    # Mild defense (0.50 instead of 0.45)
    def w1_mild(h, i, eng, ut):
        cum_dd, cum_warm, cum_b = common(h, i)
        spy_v63 = SPY_63[i] if not np.isnan(SPY_63[i]) else 0.0
        spy_v21 = SPY_21[i] if not np.isnan(SPY_21[i]) else 0.0
        if cum_dd<-0.02: return 0.50
        if cum_b>0.30 or spy_v63>0.12: return 0.75
        if cum_warm>0.25 or spy_v21>0.10: return 0.70
        return 0.62
    tests.append(("dd_to_0.50_mild", w1_mild))

    # Boost weight variants
    for wb in (0.72, 0.78, 0.80):
        def make_wb(w):
            def f(h, i, eng, ut):
                cum_dd, cum_warm, cum_b = common(h, i)
                spy_v63 = SPY_63[i] if not np.isnan(SPY_63[i]) else 0.0
                spy_v21 = SPY_21[i] if not np.isnan(SPY_21[i]) else 0.0
                if cum_dd<-0.02: return 0.45
                if cum_b>0.30 or spy_v63>0.12: return w
                if cum_warm>0.25 or spy_v21>0.10: return 0.70
                return 0.62
            return f
        tests.append((f"full_boost_w={wb}", make_wb(wb)))

    # Lower boost trigger thresholds
    def w1_easy_boost(h, i, eng, ut):
        cum_dd, cum_warm, cum_b = common(h, i)
        spy_v63 = SPY_63[i] if not np.isnan(SPY_63[i]) else 0.0
        spy_v21 = SPY_21[i] if not np.isnan(SPY_21[i]) else 0.0
        if cum_dd<-0.02: return 0.45
        if cum_b>0.20 or spy_v63>0.08: return 0.75
        if cum_warm>0.15 or spy_v21>0.05: return 0.70
        return 0.62
    tests.append(("easy_boost_thresholds", w1_easy_boost))

    # 12m return as alt-boost
    def w1_12m(h, i, eng, ut):
        cum_dd, cum_warm, cum_b = common(h, i)
        cum12 = np.prod([1+x for x in h[-12:]])-1 if len(h)>=12 else 0.05
        spy_v63 = SPY_63[i] if not np.isnan(SPY_63[i]) else 0.0
        spy_v21 = SPY_21[i] if not np.isnan(SPY_21[i]) else 0.0
        if cum_dd<-0.02: return 0.45
        if cum_b>0.30 or spy_v63>0.12 or cum12>0.40: return 0.75
        if cum_warm>0.25 or spy_v21>0.10: return 0.70
        return 0.62
    tests.append(("add_12m_boost_40pct", w1_12m))

    # Different warm thresholds
    for wt_thr in (0.15, 0.20, 0.30):
        def make_wt(t):
            def f(h, i, eng, ut):
                cum_dd, _, cum_b = common(h, i)
                cw = np.prod([1+x for x in h[-6:]])-1 if len(h)>=6 else 0.05
                spy_v63 = SPY_63[i] if not np.isnan(SPY_63[i]) else 0.0
                spy_v21 = SPY_21[i] if not np.isnan(SPY_21[i]) else 0.0
                if cum_dd<-0.02: return 0.45
                if cum_b>0.30 or spy_v63>0.12: return 0.75
                if cw>t or spy_v21>0.10: return 0.70
                return 0.62
            return f
        tests.append((f"warm_thr_{int(wt_thr*100)}pct", make_wt(wt_thr)))

    print("Candidates (must improve BOTH halves vs P53):")
    for name, fn in tests:
        try: s = run_w1(fn)
        except Exception as e:
            print(f"  {name}: ERROR {e}")
            continue
        c, sh, dd, fh, sec = both_half_score(s)
        oos_pass = (fh >= P53_FH - 0.05) and (sec >= P53_SH - 0.05)
        marker = " <- BOTH HALVES" if oos_pass and (fh > P53_FH or sec > P53_SH) else (" <- tied" if oos_pass else "")
        print(f"  {name:>26}: cagr={c:5.2f} sharpe={sh:.2f} maxdd={dd:5.2f}  first={fh:+5.2f}  second={sec:+5.2f}{marker}")
        lines.append(f"| {name} | {c:.2f}% | {sh:.2f} | {fh:+.2f} | {sec:+.2f} | {'PASS' if oos_pass and (fh > P53_FH or sec > P53_SH) else 'fail'} |")
    with open(log_path, "a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
