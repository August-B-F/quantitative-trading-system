"""Phase 58: alternative state variables for sizing."""
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
SPY_63 = B.returns[63]["SPY"].values
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


WS = [0.45, 0.55, 0.62, 0.70, 0.75]
ENGS_S = {w: mk_eng(STABLE, w) for w in WS}
ENGS_T = {w: mk_eng(TRANS, w) for w in WS}


def ret_at(eng, i):
    t1,tk = eng.pick_at(i)
    r1 = eng.fwd_arr[i,t1] if eng.spy_dist[i]>eng.sma_buffer else eng.cash_fwd[i]
    sel = eng.atr_arr[i,tk]; inv = 1.0/np.where(sel>0,sel,np.nan)
    if np.isnan(inv).all(): rk = np.nanmean(eng.fwd_arr[i,tk])
    else: ww=inv/np.nansum(inv); rk=np.nansum(eng.fwd_arr[i,tk]*ww)
    return eng.top1_w*r1 + eng.topk_w*rk


def common_state(history, i):
    if len(history)>=3: cum_dd = np.prod([1+h for h in history[-3:]])-1
    else: cum_dd = 0.05
    if len(history)>=6: cum_warm = np.prod([1+h for h in history[-6:]])-1
    else: cum_warm = 0.05
    if len(history)>=9: cum_b = np.prod([1+h for h in history[-9:]])-1
    else: cum_b = 0.05
    spy_v63 = SPY_63[i] if not np.isnan(SPY_63[i]) else 0.0
    spy_v21 = SPY_21[i] if not np.isnan(SPY_21[i]) else 0.0
    return cum_dd, cum_warm, cum_b, spy_v63, spy_v21


def base_w1(history, i, eng, use_t):
    """P55 base sizing."""
    cum_dd, cum_warm, cum_b, spy_v63, spy_v21 = common_state(history, i)
    row = eng.sf[i]; sv = np.sort(row)[::-1]; margin = sv[0]-sv[1] if len(sv)>1 else 0
    if CUR[i] == 3: return 0.45
    if cum_dd<-0.02: return 0.45
    if cum_b>0.30 or spy_v63>0.12: return 0.75
    if cum_warm>0.25 or spy_v21>0.10: return 0.70
    if margin<0.3: return 0.45
    return 0.62


def run_w1(w1_fn):
    td = _STATE["test_dates"]
    td_positions = pd.Series(B.dates.get_indexer(td), index=td)
    month_last = td_positions.groupby(td.to_period("M")).tail(1)
    fomc_idx = np.where(B.is_fomc_day)[0]
    n_days = ENGS_S[0.62].n_days
    event_mask = fomc_window_mask(n_days, fomc_idx, pre_days=0, post_days=1)
    rets=[]; history=[]
    for rd, pos in month_last.items():
        i, _ = resolve_rebalance_index(int(pos), 4, event_mask, n_days)
        use_t = (PR_RAW[i] != CUR[i]) and (PR_RAW[i] >= 0) and (not np.isnan(MP_RAW[i])) and (MP_RAW[i] >= 0.50)
        eng_d = ENGS_T[0.62] if use_t else ENGS_S[0.62]
        w1 = w1_fn(history, i, eng_d, use_t)
        if w1 not in WS: w1 = min(WS, key=lambda x: abs(x-w1))
        engs = ENGS_T if use_t else ENGS_S
        r = ret_at(engs[w1], i)
        history.append(r); rets.append(r)
    return compute_stats(np.array(rets))


def main():
    log_path = HERE.parent / "LOG.md"
    ts = dt.datetime.now().isoformat(timespec="seconds")
    lines = [f"\n### phase58_alt_states  {ts}\n",
             "| name | CAGR | Sharpe | MaxDD | verdict |", "|---|---|---|---|---|"]
    print("P55 ref:", fmt(run_w1(base_w1)))

    def w1_own_vol(history, i, eng, use_t):
        base = base_w1(history, i, eng, use_t)
        if base != 0.62: return base
        if len(history) >= 12:
            v = float(np.std(history[-12:]) * np.sqrt(12))
            if v < 0.12: return 0.75
            if v > 0.25: return 0.45
        return base

    def w1_dd_depth(history, i, eng, use_t):
        base = base_w1(history, i, eng, use_t)
        if base != 0.62: return base
        if len(history) >= 6:
            eq = np.cumprod([1+h for h in history])
            peak = float(np.maximum.accumulate(eq)[-1])
            cur_dd = (eq[-1]/peak) - 1
            if cur_dd < -0.05: return 0.45
        return base

    def w1_streak(history, i, eng, use_t):
        base = base_w1(history, i, eng, use_t)
        if base != 0.62: return base
        streak = 0
        for h in reversed(history):
            if h > 0: streak += 1
            else: break
        if streak >= 6: return 0.75
        return base

    def w1_vol_expand(history, i, eng, use_t):
        base = base_w1(history, i, eng, use_t)
        if base != 0.62: return base
        if len(history) >= 12:
            recent = float(np.std(history[-6:]))
            prior = float(np.std(history[-12:-6]))
            if prior > 0 and recent > prior * 1.5: return 0.45
        return base

    def w1_hg_hi_trans_def(history, i, eng, use_t):
        base = base_w1(history, i, eng, use_t)
        if base != 0.62: return base
        if CUR[i] == 1 and use_t: return 0.55
        return base

    def w1_pred_stag(history, i, eng, use_t):
        base = base_w1(history, i, eng, use_t)
        if base != 0.62: return base
        if PR_RAW[i] == 3 and not np.isnan(MP_RAW[i]) and MP_RAW[i] > 0.5: return 0.45
        return base

    def w1_high_conf_trans(history, i, eng, use_t):
        base = base_w1(history, i, eng, use_t)
        if use_t and not np.isnan(MP_RAW[i]) and MP_RAW[i] > 0.85: return 0.45
        return base

    def w1_hg_li_boost(history, i, eng, use_t):
        base = base_w1(history, i, eng, use_t)
        if base == 0.62 and CUR[i] == 0: return 0.70
        return base

    tests = [
        ("own_vol_regime", w1_own_vol),
        ("dd_depth_5pct", w1_dd_depth),
        ("positive_streak_6", w1_streak),
        ("vol_expansion_defend", w1_vol_expand),
        ("hg_hi_trans_defend", w1_hg_hi_trans_def),
        ("pred_stag_defend", w1_pred_stag),
        ("high_conf_trans_defend", w1_high_conf_trans),
        ("hg_li_mild_boost", w1_hg_li_boost),
    ]
    for name, fn in tests:
        try: s = run_w1(fn)
        except Exception as e: s = {"error": str(e)}
        if "error" in s:
            print(f"  {name}: ERROR {s['error'][:80]}"); continue
        verdict = "PASS" if s["cagr"] > 0.3027 and s["sharpe"] >= 1.89 and s["max_dd"] >= -0.1266 else "fail"
        marker = " <-" if verdict == "PASS" else ""
        print(f"  {name}: {fmt(s)}{marker}")
        lines.append(f"| {name} | {s['cagr']*100:.2f}% | {s['sharpe']:.2f} | {s['max_dd']*100:.2f}% | {verdict} |")
    with open(log_path, "a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
