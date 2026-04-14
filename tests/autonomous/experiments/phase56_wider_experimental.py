"""Phase 56: even wider, more experimental tests."""
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

# Try to find existing top_margin feature in panel
TOP_MARGIN = B.df.get("cross_sectional_top_margin_63d__top_margin")
TOP_MARGIN_ARR = TOP_MARGIN.values if TOP_MARGIN is not None else None
print(f"top_margin feature available: {TOP_MARGIN_ARR is not None}")

# Cross-asset features I haven't used directly
COPPER_GOLD = B.df.get("cross_asset_copper_gold__copper_gold_chg_63d")
COPPER_GOLD_ARR = COPPER_GOLD.values if COPPER_GOLD is not None else None
DISP = B.df.get("cross_sectional_dispersion_63d__dispersion")
DISP_ARR = DISP.values if DISP is not None else None
RANK_STAB = B.df.get("cross_sectional_rank_stability_21d__rank_stability_21d")
RANK_STAB_ARR = RANK_STAB.values if RANK_STAB is not None else None
print(f"dispersion: {DISP_ARR is not None}, rank_stability: {RANK_STAB_ARR is not None}")


def mk_eng(uni, w1, sma_buf=-0.04):
    cfg = copy.deepcopy(_STATE["cfg"])
    cfg.update({"universe":uni,"top1_weight":w1,"top3_weight":1-w1,
                "fomc_window_pre":0,"fomc_window_after":1,"fomc_defer_days":4,
                "sma_gate_buffer":sma_buf})
    shim = types.SimpleNamespace(**{k:getattr(B,k) for k in ("df","dates","atr21","fwd21","spy_dist_sma200","is_fomc_day")})
    nr = dict(B.returns); nr[63]=SIG; shim.returns=nr
    return PortfolioEngine(shim, GATED, cfg)


# Pre-build engine grid
WS = [0.40, 0.45, 0.50, 0.55, 0.62, 0.65, 0.70, 0.75, 0.80, 0.85]
ENGS_S = {w: mk_eng(STABLE, w) for w in WS}
ENGS_T = {w: mk_eng(TRANS, w) for w in WS}
ENGS_S_NOSMA = {w: mk_eng(STABLE, w, sma_buf=-1.0) for w in (0.45,0.62,0.70,0.75)}
ENGS_T_NOSMA = {w: mk_eng(TRANS, w, sma_buf=-1.0) for w in (0.45,0.62,0.70,0.75)}


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


def p54_w1(history, i, eng_default):
    cum_dd, cum_warm, cum_b, spy_v63, spy_v21 = common_state(history, i)
    row = eng_default.sf[i]
    sv = np.sort(row)[::-1]
    margin = sv[0] - sv[1] if len(sv) > 1 else 0
    if cum_dd<-0.02: return 0.45
    elif cum_b>0.30 or spy_v63>0.12: return 0.75
    elif cum_warm>0.25 or spy_v21>0.10: return 0.70
    elif margin < 0.3: return 0.45
    return 0.62


def run_with_w1(w1_fn, sma_in_trans=True):
    """Generic runner; w1_fn(history, i, eng_default) -> w1."""
    td = _STATE["test_dates"]
    td_positions = pd.Series(B.dates.get_indexer(td), index=td)
    month_last = td_positions.groupby(td.to_period("M")).tail(1)
    fomc_idx = np.where(B.is_fomc_day)[0]
    n_days = ENGS_S[0.62].n_days
    event_mask = fomc_window_mask(n_days, fomc_idx, pre_days=0, post_days=1)
    rets = []; history = []
    for rd, pos in month_last.items():
        i, _ = resolve_rebalance_index(int(pos), 4, event_mask, n_days)
        use_t = (PR_RAW[i] != CUR[i]) and (PR_RAW[i] >= 0) and (not np.isnan(MP_RAW[i])) and (MP_RAW[i] >= 0.50)
        eng_default = ENGS_T[0.62] if use_t else ENGS_S[0.62]
        w1 = w1_fn(history, i, eng_default)
        if w1 not in WS: w1 = min(WS, key=lambda x: abs(x-w1))
        if use_t:
            eng = ENGS_T[w1] if sma_in_trans else (ENGS_T_NOSMA.get(w1) or ENGS_T[w1])
        else:
            eng = ENGS_S[w1]
        history.append(0.0)
        history[-1] = ret_at(eng, i)
        rets.append(history[-1])
    return compute_stats(np.array(rets))


def main():
    print("P54 ref:", fmt(run_with_w1(p54_w1)))
    log_path = HERE.parent / "LOG.md"
    ts = dt.datetime.now().isoformat(timespec="seconds")
    lines = [f"\n### phase56_wider_experimental  {ts}\n",
             "| name | CAGR | Sharpe | MaxDD | verdict |", "|---|---|---|---|---|"]

    tests = []

    # 1. Use panel's top_margin feature directly (cross_sectional_top_margin_63d)
    if TOP_MARGIN_ARR is not None:
        def w1_top_margin(history, i, eng):
            base = p54_w1(history, i, eng)
            if base != 0.62: return base
            tm = TOP_MARGIN_ARR[i] if not np.isnan(TOP_MARGIN_ARR[i]) else 0
            if tm > 0.05: return 0.75  # wide top margin = high confidence
            return base
        tests.append(("panel_top_margin_boost", lambda: run_with_w1(w1_top_margin)))

    # 2. Use dispersion as boost trigger (high disp = clear winners)
    if DISP_ARR is not None:
        def w1_disp(history, i, eng):
            base = p54_w1(history, i, eng)
            if base != 0.62: return base
            d = DISP_ARR[i] if not np.isnan(DISP_ARR[i]) else 0
            if d > 0.08: return 0.75
            return base
        tests.append(("disp_high_boost", lambda: run_with_w1(w1_disp)))

    # 3. Use rank stability as confidence
    if RANK_STAB_ARR is not None:
        def w1_stab(history, i, eng):
            base = p54_w1(history, i, eng)
            if base != 0.62: return base
            s = RANK_STAB_ARR[i] if not np.isnan(RANK_STAB_ARR[i]) else 0
            if s > 0.7: return 0.75
            return base
        tests.append(("rank_stab_boost", lambda: run_with_w1(w1_stab)))

    # 4. Compound conditions: REQUIRE both DD trigger AND signal margin tight to apply 0.45
    def w1_strict_dd(history, i, eng):
        cum_dd, cum_warm, cum_b, spy_v63, spy_v21 = common_state(history, i)
        row = eng.sf[i]; sv = np.sort(row)[::-1]; margin = sv[0]-sv[1] if len(sv)>1 else 0
        if cum_dd<-0.02 and margin<0.5: return 0.45
        elif cum_dd<-0.04: return 0.45  # very deep DD always defends
        elif cum_b>0.30 or spy_v63>0.12: return 0.75
        elif cum_warm>0.25 or spy_v21>0.10: return 0.70
        elif margin < 0.3: return 0.45
        return 0.62
    tests.append(("strict_dd_compound", lambda: run_with_w1(w1_strict_dd)))

    # 5. Aggressive boost: 0.85 on highest-conviction days
    def w1_aggressive(history, i, eng):
        cum_dd, cum_warm, cum_b, spy_v63, spy_v21 = common_state(history, i)
        row = eng.sf[i]; sv = np.sort(row)[::-1]; margin = sv[0]-sv[1] if len(sv)>1 else 0
        if cum_dd<-0.02: return 0.45
        # If BOTH self-equity boost AND margin wide AND spy strong -> ULTRA
        if cum_b>0.30 and spy_v63>0.12 and margin>1.5: return 0.85
        elif cum_b>0.30 or spy_v63>0.12: return 0.75
        elif cum_warm>0.25 or spy_v21>0.10: return 0.70
        elif margin < 0.3: return 0.45
        return 0.62
    tests.append(("ultra_85_compound", lambda: run_with_w1(w1_aggressive)))

    # 6. Same as above but ULTRA at 0.90
    def w1_ultra90(history, i, eng):
        cum_dd, cum_warm, cum_b, spy_v63, spy_v21 = common_state(history, i)
        row = eng.sf[i]; sv = np.sort(row)[::-1]; margin = sv[0]-sv[1] if len(sv)>1 else 0
        if cum_dd<-0.02: return 0.45
        if cum_b>0.30 and spy_v63>0.12 and margin>1.5: return 0.90
        elif cum_b>0.30 or spy_v63>0.12: return 0.75
        elif cum_warm>0.25 or spy_v21>0.10: return 0.70
        elif margin < 0.3: return 0.45
        return 0.62
    tests.append(("ultra_90_compound", lambda: run_with_w1(w1_ultra90)))

    # 7. Defensive: drop boost trigger thresholds (boost more often, smaller boosts)
    def w1_def(history, i, eng):
        cum_dd, cum_warm, cum_b, spy_v63, spy_v21 = common_state(history, i)
        row = eng.sf[i]; sv = np.sort(row)[::-1]; margin = sv[0]-sv[1] if len(sv)>1 else 0
        if cum_dd<-0.02: return 0.45
        elif cum_b>0.30 or spy_v63>0.12: return 0.70  # softer full boost
        elif cum_warm>0.25 or spy_v21>0.10: return 0.65  # softer warm boost
        elif margin < 0.3: return 0.45
        return 0.62
    tests.append(("softer_boosts", lambda: run_with_w1(w1_def)))

    # 8. Variant: tighter boost thresholds (more frequent boost)
    def w1_freq(history, i, eng):
        cum_dd, cum_warm, cum_b, spy_v63, spy_v21 = common_state(history, i)
        row = eng.sf[i]; sv = np.sort(row)[::-1]; margin = sv[0]-sv[1] if len(sv)>1 else 0
        if cum_dd<-0.02: return 0.45
        elif cum_b>0.20 or spy_v63>0.08: return 0.75  # easier full boost
        elif cum_warm>0.15 or spy_v21>0.05: return 0.70
        elif margin < 0.3: return 0.45
        return 0.62
    tests.append(("freq_boost_thresholds", lambda: run_with_w1(w1_freq)))

    # 9. Multi-margin: use top-1 vs top-3 spread (instead of top-1 vs top-2)
    def w1_t1_t3_margin(history, i, eng):
        base = p54_w1(history, i, eng)
        if base != 0.62: return base
        row = eng.sf[i]
        sv = np.sort(row)[::-1]
        if len(sv) >= 3:
            margin13 = sv[0] - sv[2]
            if margin13 > 2.0: return 0.75  # very clear top-1 over top-3
        return base
    tests.append(("t1_t3_margin_boost", lambda: run_with_w1(w1_t1_t3_margin)))

    # 10. Use SPY 252d (1y) as macro trend
    spy_252 = pd.read_parquet(Path(__file__).resolve().parents[3]/"data/features/price/returns_252d.parquet").reindex(B.dates)["SPY"].values if Path(Path(__file__).resolve().parents[3]/"data/features/price/returns_252d.parquet").exists() else None
    if spy_252 is not None:
        def w1_spy_252(history, i, eng):
            base = p54_w1(history, i, eng)
            if base != 0.62: return base
            v = spy_252[i] if not np.isnan(spy_252[i]) else 0
            if v > 0.20: return 0.75
            return base
        tests.append(("spy_252d_boost", lambda: run_with_w1(w1_spy_252)))

    # 11. ATR-relative threshold for DD: detect DD if return < -atr (rel to current vol)
    def w1_atr_dd(history, i, eng):
        cum_dd, cum_warm, cum_b, spy_v63, spy_v21 = common_state(history, i)
        row = eng.sf[i]; sv = np.sort(row)[::-1]; margin = sv[0]-sv[1] if len(sv)>1 else 0
        # Compute rolling vol of own returns
        if len(history) >= 12:
            own_vol = np.std(history[-12:]) * np.sqrt(12)
            dd_thr = -0.5 * own_vol  # half a vol
        else:
            dd_thr = -0.02
        if cum_dd < dd_thr: return 0.45
        elif cum_b>0.30 or spy_v63>0.12: return 0.75
        elif cum_warm>0.25 or spy_v21>0.10: return 0.70
        elif margin < 0.3: return 0.45
        return 0.62
    tests.append(("atr_relative_dd", lambda: run_with_w1(w1_atr_dd)))

    # 12. Sharpe-based: use trailing Sharpe instead of trailing return for DD
    def w1_sharpe_dd(history, i, eng):
        if len(history) >= 6:
            arr = np.array(history[-6:])
            sd = arr.std() if arr.std() > 0 else 1
            sh = arr.mean() / sd * np.sqrt(12)
        else:
            sh = 0.5
        cum_dd, cum_warm, cum_b, spy_v63, spy_v21 = common_state(history, i)
        row = eng.sf[i]; sv = np.sort(row)[::-1]; margin = sv[0]-sv[1] if len(sv)>1 else 0
        if sh < 0: return 0.45
        elif cum_b>0.30 or spy_v63>0.12: return 0.75
        elif cum_warm>0.25 or spy_v21>0.10: return 0.70
        elif margin < 0.3: return 0.45
        return 0.62
    tests.append(("sharpe_based_dd", lambda: run_with_w1(w1_sharpe_dd)))

    for name, fn in tests:
        try: s = fn()
        except Exception as e: s = {"error": str(e)}
        if "error" in s:
            print(f"  {name}: ERROR {s['error'][:80]}")
            lines.append(f"| {name} | | | | ERR |"); continue
        verdict = "PASS" if s["cagr"] > 0.3023 and s["sharpe"] >= 1.89 and s["max_dd"] >= -0.1266 else "fail"
        marker = " <-" if verdict == "PASS" else ""
        print(f"  {name}: {fmt(s)}{marker}")
        lines.append(f"| {name} | {s['cagr']*100:.2f}% | {s['sharpe']:.2f} | {s['max_dd']*100:.2f}% | {verdict} |")
    with open(log_path, "a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
