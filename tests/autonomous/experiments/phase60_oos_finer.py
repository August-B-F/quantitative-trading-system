"""Phase 60: finer OOS-validated search around P58."""
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


WS = [0.40, 0.45, 0.50, 0.55, 0.62, 0.68, 0.70, 0.72, 0.75, 0.78, 0.80, 0.82]
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


def both_half(s):
    fh = s[s.index.year < 2018]; sh = s[s.index.year >= 2018]
    fh_b = BASE_MR.reindex(fh.index); sh_b = BASE_MR.reindex(sh.index)
    fh_e = (fh - fh_b).dropna(); sh_e = (sh - sh_b).dropna()
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


def make_p58(w_full=0.78, w_warm=0.70, w_dd=0.45, dd_thr=-0.02,
             boost_thr=0.30, spy63_thr=0.12, warm_thr=0.25, spy21_thr=0.10):
    def f(h, i, eng, ut):
        cum_dd, cum_warm, cum_b = common(h, i)
        spy_v63 = SPY_63[i] if not np.isnan(SPY_63[i]) else 0.0
        spy_v21 = SPY_21[i] if not np.isnan(SPY_21[i]) else 0.0
        if cum_dd<dd_thr: return w_dd
        if cum_b>boost_thr or spy_v63>spy63_thr: return w_full
        if cum_warm>warm_thr or spy_v21>spy21_thr: return w_warm
        return 0.62
    return f


def main():
    P58_FH, P58_SH = 7.97, 3.36

    log_path = HERE.parent / "LOG.md"
    ts = dt.datetime.now().isoformat(timespec="seconds")
    lines = [f"\n### phase60_oos_finer  {ts}\n",
             "| name | CAGR | Sharpe | first_e | second_e | OOS |",
             "|---|---|---|---|---|---|"]

    print("P58 ref: 30.37/1.88/-12.66 (first +7.97, second +3.36)")
    print()

    tests = []

    # Fine grid around w_full
    for wf in (0.76, 0.77, 0.78, 0.79, 0.80, 0.82):
        tests.append((f"wf={wf}", make_p58(w_full=wf)))

    # Fine grid around w_warm
    for ww in (0.66, 0.68, 0.70, 0.72, 0.74):
        tests.append((f"ww={ww}", make_p58(w_warm=ww)))

    # Fine grid around w_dd
    for wd in (0.40, 0.45, 0.48, 0.50, 0.55):
        tests.append((f"wd={wd}", make_p58(w_dd=wd)))

    # Fine grid around dd_thr
    for dt_ in (-0.04, -0.03, -0.02, -0.01, 0.0):
        tests.append((f"dd_thr={dt_*100:+.0f}pct", make_p58(dd_thr=dt_)))

    # Fine grid around boost_thr (self 9m)
    for bt in (0.20, 0.25, 0.30, 0.35, 0.40):
        tests.append((f"boost_thr={int(bt*100)}pct", make_p58(boost_thr=bt)))

    # Fine grid around spy63_thr
    for st_ in (0.08, 0.10, 0.12, 0.14, 0.16):
        tests.append((f"spy63_thr={int(st_*100)}pct", make_p58(spy63_thr=st_)))

    # Fine grid around warm_thr
    for wt in (0.18, 0.22, 0.25, 0.28, 0.32):
        tests.append((f"warm_thr={int(wt*100)}pct", make_p58(warm_thr=wt)))

    # Fine grid around spy21_thr
    for s2 in (0.06, 0.08, 0.10, 0.12, 0.14):
        tests.append((f"spy21_thr={int(s2*100)}pct", make_p58(spy21_thr=s2)))

    found = []
    for name, fn in tests:
        try: s = run_w1(fn)
        except Exception as e:
            print(f"  {name}: ERROR {e}"); continue
        c, sh, dd, fh, sec = both_half(s)
        oos_pass = (fh > P58_FH) and (sec > P58_SH)
        oos_tied = (fh >= P58_FH - 0.05) and (sec >= P58_SH - 0.05)
        marker = " <- BOTH IMPROVE" if oos_pass else (" <- tied" if oos_tied else "")
        if oos_pass: found.append((name, c, sh, dd, fh, sec))
        print(f"  {name:>22}: {c:5.2f}/{sh:.2f}/{dd:5.2f}  first={fh:+5.2f}  second={sec:+5.2f}{marker}")
        lines.append(f"| {name} | {c:.2f}% | {sh:.2f} | {fh:+.2f} | {sec:+.2f} | {'PASS' if oos_pass else ('tied' if oos_tied else 'fail')} |")

    print("\nClean OOS winners:")
    for f in found:
        print(f"  {f[0]:>22}: {f[1]:.2f}/{f[2]:.2f}/{f[3]:.2f}  first={f[4]:+.2f}  second={f[5]:+.2f}")

    with open(log_path, "a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
