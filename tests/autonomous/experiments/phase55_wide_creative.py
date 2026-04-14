"""Phase 55: WIDE creative batch. Test many wildly different ideas at low budget each."""
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

STABLE_DEFAULT = ["SOXX","QQQ","IGV","XLE","GLD","SHY"]
TRANS_DEFAULT = STABLE_DEFAULT + ["TLT","AGG","XLV","XLF"]

with open(HERE.parent/"cache"/"pred_proba_p46.pkl","rb") as f: PR_RAW, MP_RAW = pickle.load(f)
_load(); B = _STATE["bundle"]
CUR = np.asarray(_cr(B.df).index)
GATED = PR_RAW.copy()
_w = (PR_RAW != CUR) & (PR_RAW >= 0)
_lc = np.nan_to_num(MP_RAW, nan=0) < 0.40
GATED[_w & _lc] = CUR[_w & _lc]


def rank_signal_default():
    cm = list(B.returns[63].columns); ranks=None
    for lb,wt in [(42,1),(63,3),(126,1)]:
        r = B.returns[lb][cm].rank(axis=1,method="average")
        ranks = r*wt if ranks is None else ranks+r*wt
    return ranks/5

SIG_DEFAULT = rank_signal_default()
SPY_63 = B.returns[63]["SPY"].values
SPY_21 = B.returns[21]["SPY"].values


def mk_eng(uni, w1, fomc_pre=0, fomc_post=1, fomc_def=4, sig=None, k=3, sma_buf=-0.04, cash="SHY"):
    cfg = copy.deepcopy(_STATE["cfg"])
    cfg.update({"universe":uni,"top1_weight":w1,"top3_weight":1-w1,"top_k":k,
                "fomc_window_pre":fomc_pre,"fomc_window_after":fomc_post,"fomc_defer_days":fomc_def,
                "sma_gate_buffer":sma_buf,"cash_proxy":cash})
    shim = types.SimpleNamespace(**{kk:getattr(B,kk) for kk in ("df","dates","atr21","fwd21","spy_dist_sma200","is_fomc_day")})
    nr = dict(B.returns); nr[cfg["lookback_stable"]] = sig if sig is not None else SIG_DEFAULT
    shim.returns = nr
    return PortfolioEngine(shim, GATED, cfg)


def p54_step(rets, history, eng_default, eng_full, eng_warm, eng_dd, i, use_t):
    """Apply P54 sizing logic and append return."""
    if len(history) >= 3: cum_dd = np.prod([1+h for h in history[-3:]]) - 1
    else: cum_dd = 0.05
    if len(history) >= 6: cum_warm_h = np.prod([1+h for h in history[-6:]]) - 1
    else: cum_warm_h = 0.05
    if len(history) >= 9: cum_b = np.prod([1+h for h in history[-9:]]) - 1
    else: cum_b = 0.05
    spy_v63 = SPY_63[i] if not np.isnan(SPY_63[i]) else 0.0
    spy_v21 = SPY_21[i] if not np.isnan(SPY_21[i]) else 0.0
    row = eng_default.sf[i]
    sv = np.sort(row)[::-1]
    margin = sv[0] - sv[1] if len(sv) > 1 else 0
    if cum_dd < -0.02: eng = eng_dd
    elif cum_b > 0.30 or spy_v63 > 0.12: eng = eng_full
    elif cum_warm_h > 0.25 or spy_v21 > 0.10: eng = eng_warm
    elif margin < 0.3: eng = eng_dd
    else: eng = eng_default
    t1, tk = eng.pick_at(i)
    r1 = eng.fwd_arr[i,t1] if eng.spy_dist[i] > eng.sma_buffer else eng.cash_fwd[i]
    sel = eng.atr_arr[i,tk]; inv = 1.0/np.where(sel>0,sel,np.nan)
    if np.isnan(inv).all(): rk = np.nanmean(eng.fwd_arr[i,tk])
    else: ww=inv/np.nansum(inv); rk=np.nansum(eng.fwd_arr[i,tk]*ww)
    return eng.top1_w*r1 + eng.topk_w*rk


def run_full_backtest(stable=None, trans=None, sig=None, fomc=(0,1,4),
                       calendar_skip_months=None, every_other_month=False,
                       k=3, sma_buf=-0.04, cash="SHY"):
    """Generic runner with P54 sizing. Returns stats."""
    stable = stable or STABLE_DEFAULT
    trans = trans or TRANS_DEFAULT
    sig = sig if sig is not None else SIG_DEFAULT
    eng_s_d = mk_eng(stable, 0.62, *fomc, sig=sig, k=k, sma_buf=sma_buf, cash=cash)
    eng_s_f = mk_eng(stable, 0.75, *fomc, sig=sig, k=k, sma_buf=sma_buf, cash=cash)
    eng_s_w = mk_eng(stable, 0.70, *fomc, sig=sig, k=k, sma_buf=sma_buf, cash=cash)
    eng_s_dd = mk_eng(stable, 0.45, *fomc, sig=sig, k=k, sma_buf=sma_buf, cash=cash)
    eng_t_d = mk_eng(trans, 0.62, *fomc, sig=sig, k=k, sma_buf=sma_buf, cash=cash)
    eng_t_f = mk_eng(trans, 0.75, *fomc, sig=sig, k=k, sma_buf=sma_buf, cash=cash)
    eng_t_w = mk_eng(trans, 0.70, *fomc, sig=sig, k=k, sma_buf=sma_buf, cash=cash)
    eng_t_dd = mk_eng(trans, 0.45, *fomc, sig=sig, k=k, sma_buf=sma_buf, cash=cash)

    td = _STATE["test_dates"]
    td_positions = pd.Series(eng_s_d.dates.get_indexer(td), index=td)
    month_last = td_positions.groupby(td.to_period("M")).tail(1)
    fomc_idx = np.where(B.is_fomc_day)[0]
    event_mask = fomc_window_mask(eng_s_d.n_days, fomc_idx, pre_days=fomc[0], post_days=fomc[1])

    rets = []; history = []
    for k_idx, (rd, pos) in enumerate(month_last.items()):
        if calendar_skip_months and rd.month in calendar_skip_months:
            rets.append(0.0); history.append(0.0); continue
        if every_other_month and k_idx % 2 == 1:
            rets.append(0.0); history.append(0.0); continue
        i, _ = resolve_rebalance_index(int(pos), fomc[2], event_mask, eng_s_d.n_days)
        use_t = (PR_RAW[i] != CUR[i]) and (PR_RAW[i] >= 0) and (not np.isnan(MP_RAW[i])) and (MP_RAW[i] >= 0.50)
        eng_d = eng_t_d if use_t else eng_s_d
        eng_f = eng_t_f if use_t else eng_s_f
        eng_w = eng_t_w if use_t else eng_s_w
        eng_dd = eng_t_dd if use_t else eng_s_dd
        r = p54_step(rets, history, eng_d, eng_f, eng_w, eng_dd, i, use_t)
        history.append(r); rets.append(r)
    return compute_stats(np.array(rets))


def main():
    log_path = HERE.parent / "LOG.md"
    ts = dt.datetime.now().isoformat(timespec="seconds")
    lines = [f"\n### phase55_wide_creative  {ts}\n",
             "| name | CAGR | Sharpe | MaxDD | verdict |", "|---|---|---|---|---|"]

    print("P54 reference:", fmt(run_full_backtest()))

    tests = []

    # 1. Calendar — skip October
    tests.append(("skip_october", lambda: run_full_backtest(calendar_skip_months=[10])))
    # 2. Skip September+October
    tests.append(("skip_sep_oct", lambda: run_full_backtest(calendar_skip_months=[9,10])))
    # 3. Skip January (sometimes weak)
    tests.append(("skip_january", lambda: run_full_backtest(calendar_skip_months=[1])))
    # 4. Bi-monthly rebalance
    tests.append(("bi_monthly", lambda: run_full_backtest(every_other_month=True)))
    # 5. Drop XLE entirely
    tests.append(("no_xle_uni", lambda: run_full_backtest(
        stable=["SOXX","QQQ","IGV","GLD","SHY"], trans=["SOXX","QQQ","IGV","GLD","SHY","TLT","AGG","XLV","XLF"])))
    # 6. Add XLK back (overlap)
    tests.append(("add_xlk_back", lambda: run_full_backtest(
        stable=["SOXX","QQQ","XLK","IGV","XLE","GLD","SHY"], trans=["SOXX","QQQ","XLK","IGV","XLE","GLD","SHY","TLT","AGG","XLV","XLF"])))
    # 7. Drop GLD (the safe-haven)
    tests.append(("no_gld_uni", lambda: run_full_backtest(
        stable=["SOXX","QQQ","IGV","XLE","SHY"], trans=["SOXX","QQQ","IGV","XLE","SHY","TLT","AGG","XLV","XLF"])))
    # 8. Replace SHY with TLT as cash proxy (longer duration)
    tests.append(("tlt_as_cash", lambda: run_full_backtest(
        stable=["SOXX","QQQ","IGV","XLE","GLD","TLT"], trans=["SOXX","QQQ","IGV","XLE","GLD","TLT","AGG","XLV","XLF"], cash="TLT")))
    # 9. Replace SHY with AGG as cash proxy
    tests.append(("agg_as_cash", lambda: run_full_backtest(
        stable=["SOXX","QQQ","IGV","XLE","GLD","AGG"], trans=["SOXX","QQQ","IGV","XLE","GLD","AGG","TLT","XLV","XLF","SHY"], cash="AGG")))
    # 10. SMA buffer tighter (-2%)
    tests.append(("sma_-2pct", lambda: run_full_backtest(sma_buf=-0.02)))
    # 11. SMA buffer wider (-8%)
    tests.append(("sma_-8pct", lambda: run_full_backtest(sma_buf=-0.08)))
    # 12. SMA gate completely off
    tests.append(("sma_off", lambda: run_full_backtest(sma_buf=-1.0)))
    # 13. FOMC defer disabled (pre=0 post=0 def=0)
    tests.append(("fomc_off", lambda: run_full_backtest(fomc=(0,0,0))))
    # 14. FOMC pre=2 post=2 def=3 (canonical-ish)
    tests.append(("fomc_canon", lambda: run_full_backtest(fomc=(2,2,3))))
    # 15. top_k=2
    tests.append(("k2", lambda: run_full_backtest(k=2)))
    # 16. top_k=4
    tests.append(("k4", lambda: run_full_backtest(k=4)))
    # 17. Custom signal: 12-1 momentum (252d / 21d skip)
    def sig_12_1():
        cm = list(B.returns[63].columns)
        if 252 not in B.returns:
            r252 = pd.read_parquet(Path(__file__).resolve().parents[3]/"data/features/price/returns_252d.parquet").reindex(B.dates)
        else:
            r252 = B.returns[252]
        r21 = B.returns[21][cm]
        diff = r252[cm] - r21
        return diff.rank(axis=1, method="average")
    tests.append(("sig_12_1mom", lambda: run_full_backtest(sig=sig_12_1())))

    # 18. Tighten signal weights to (42:0.5, 63:3, 126:1.5)
    def sig_alt1():
        cm = list(B.returns[63].columns); ranks = None; total = 5
        for lb, w in [(42,0.5),(63,3),(126,1.5)]:
            r = B.returns[lb][cm].rank(axis=1, method="average")*w
            ranks = r if ranks is None else ranks + r
        return ranks / total
    tests.append(("sig_42x0.5_63x3_126x1.5", lambda: run_full_backtest(sig=sig_alt1())))

    # 19. Wider signal: (21:1, 42:1, 63:2, 126:1)
    def sig_alt2():
        cm = list(B.returns[63].columns); ranks = None; total = 5
        for lb, w in [(21,1),(42,1),(63,2),(126,1)]:
            r = B.returns[lb][cm].rank(axis=1, method="average")*w
            ranks = r if ranks is None else ranks + r
        return ranks / total
    tests.append(("sig_21_42_63_126", lambda: run_full_backtest(sig=sig_alt2())))

    # 20. Add EFA to trans (international)
    if "EFA" in B.atr21.columns:
        tests.append(("trans_+EFA", lambda: run_full_backtest(trans=TRANS_DEFAULT + ["EFA"])))

    # 21. Drop FOMC defer + use pre=0 post=3
    tests.append(("fomc_p0_a3_d2", lambda: run_full_backtest(fomc=(0,3,2))))
    # 22. fomc defer days 6
    tests.append(("fomc_p0_a1_d6", lambda: run_full_backtest(fomc=(0,1,6))))
    # 23. fomc defer days 1
    tests.append(("fomc_p0_a1_d1", lambda: run_full_backtest(fomc=(0,1,1))))

    # 24. Trans uni without GLD (force GLD to be staple)
    tests.append(("trans_no_gld", lambda: run_full_backtest(
        trans=["SOXX","QQQ","IGV","XLE","SHY","TLT","AGG","XLV","XLF"])))

    # 25. Trans uni with EEM
    tests.append(("trans_+EEM", lambda: run_full_backtest(trans=TRANS_DEFAULT + ["EEM"])))

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
