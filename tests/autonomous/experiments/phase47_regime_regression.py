"""Phase 47: regress P46 monthly alpha on macro factor changes.

Decompose champion alpha vs baseline into systematic factor loadings.
If alpha is explained by macro factor changes, it is "beta in disguise"
and could be hedged or replicated cheaply. If it survives after controlling
for factors, it is genuine timing skill.
"""
from __future__ import annotations
import sys, pickle, copy, types
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import numpy as np, pandas as pd
from utils.base_test import _load, _STATE, fmt
from strategy.portfolio import PortfolioEngine
from backtest.engine import run_backtest
from strategy.rebalance import fomc_window_mask, resolve_rebalance_index
from features.regime_labels import current_regime as _cr

STABLE = ["SOXX","QQQ","IGV","XLE","GLD","SHY"]; TRANS = STABLE + ["TLT","AGG","XLV"]


def build_p46_monthly():
    """Return P46 monthly return series."""
    _load(); b = _STATE["bundle"]
    with open(HERE.parent / "cache" / "pred_proba_p46.pkl", "rb") as f:
        pr, mp = pickle.load(f)
    cur = np.asarray(_cr(b.df).index)
    gated = pr.copy(); w=(pr!=cur)&(pr>=0); lc = np.nan_to_num(mp,nan=0)<0.40
    gated[w&lc]=cur[w&lc]
    cm = list(b.returns[63].columns); ranks=None
    for lb,wt in [(42,1),(63,3),(126,1)]:
        r = b.returns[lb][cm].rank(axis=1,method="average")
        ranks = r*wt if ranks is None else ranks+r*wt
    sig = ranks/5

    def mk_eng(uni):
        cfg = copy.deepcopy(_STATE["cfg"])
        cfg.update({"universe":uni,"top1_weight":0.62,"top3_weight":0.38,
                    "fomc_window_pre":0,"fomc_window_after":1,"fomc_defer_days":4})
        shim = types.SimpleNamespace(**{k:getattr(b,k) for k in ("df","dates","atr21","fwd21","spy_dist_sma200","is_fomc_day")})
        nr = dict(b.returns); nr[63]=sig; shim.returns=nr
        return PortfolioEngine(shim, gated, cfg)
    eng_s = mk_eng(STABLE); eng_t = mk_eng(TRANS)
    td = _STATE["test_dates"]
    td_positions = pd.Series(eng_s.dates.get_indexer(td), index=td)
    month_last = td_positions.groupby(td.to_period("M")).tail(1)
    fomc_idx = np.where(b.is_fomc_day)[0]
    event_mask = fomc_window_mask(eng_s.n_days, fomc_idx, pre_days=0, post_days=1)

    def ret_at(eng, i):
        t1,tk = eng.pick_at(i)
        r1 = eng.fwd_arr[i,t1] if eng.spy_dist[i]>eng.sma_buffer else eng.cash_fwd[i]
        sel = eng.atr_arr[i,tk]; inv = 1.0/np.where(sel>0,sel,np.nan)
        if np.isnan(inv).all(): rk = np.nanmean(eng.fwd_arr[i,tk])
        else: ww=inv/np.nansum(inv); rk=np.nansum(eng.fwd_arr[i,tk]*ww)
        return eng.top1_w*r1 + eng.topk_w*rk
    rets = []; dd = []
    for rd, pos in month_last.items():
        i, _ = resolve_rebalance_index(int(pos), 4, event_mask, eng_s.n_days)
        use_t = (pr[i]!=cur[i]) and (pr[i]>=0) and (not np.isnan(mp[i])) and (mp[i]>=0.50)
        rets.append(ret_at(eng_t if use_t else eng_s, i)); dd.append(rd)
    return pd.Series(rets, index=dd)


def main():
    p46 = build_p46_monthly()
    _load(); b = _STATE["bundle"]; df = b.df
    cfg_base = _STATE["cfg"]
    eng_base = PortfolioEngine(b, _STATE["pred_reg"], cfg_base)
    base_mr = run_backtest(eng_base, _STATE["test_dates"], cfg_base).monthly_returns

    # Macro factor changes — compute monthly deltas
    td_idx = p46.index

    factors_df = pd.DataFrame(index=td_idx)
    # CPI YoY change (21d change from panel)
    factors_df["cpi_yoy_chg21"] = df.get("inflation_features__cpi_yoy").reindex(td_idx).diff(1)  # monthly diff of already-21d-aligned series
    # 10y-2y yield curve slope change
    factors_df["yc_slope_chg21"] = df.get("yield_curve_features__yc_slope_10y_2y_chg21").reindex(td_idx)
    # Copper/gold change (63d — proxy for monthly)
    factors_df["copper_gold_chg63"] = df.get("cross_asset_copper_gold__copper_gold_chg_63d").reindex(td_idx)
    # HY-IG credit spread change
    factors_df["hy_ig_chg21"] = df.get("credit_features__hy_ig_spread_chg21").reindex(td_idx)
    # SPY 21d return (market beta)
    factors_df["spy_21d"] = df.get("returns_21d__SPY").reindex(td_idx) if "returns_21d__SPY" in df.columns else (
        b.returns[21]["SPY"].reindex(td_idx) if 21 in b.returns and "SPY" in b.returns[21].columns else None
    )
    # VIX change
    factors_df["vix_chg"] = df.get("vol_features__vix").reindex(td_idx).diff(1)

    # Alpha series
    alpha = (p46 - base_mr.reindex(td_idx))
    y = alpha.dropna()
    X = factors_df.reindex(y.index).dropna()
    y = y.reindex(X.index)

    print(f"n aligned: {len(y)}")
    print(f"Mean alpha: {y.mean()*100:.4f}pp/mo  annualized: {((1+y.mean())**12-1)*100:+.2f}pp/yr")
    print(f"Factors: {list(X.columns)}")

    # Simple OLS without intercept adjustment
    import numpy.linalg as la
    X_with_c = np.column_stack([np.ones(len(X)), X.values])
    coefs, res, rank, sv = la.lstsq(X_with_c, y.values, rcond=None)
    names = ["intercept"] + list(X.columns)
    resid = y.values - X_with_c @ coefs
    n_obs = len(y); p_vars = X_with_c.shape[1]
    ss_res = (resid ** 2).sum()
    ss_tot = ((y.values - y.values.mean()) ** 2).sum()
    r2 = 1 - ss_res / ss_tot
    sigma2 = ss_res / (n_obs - p_vars)
    try:
        cov = sigma2 * la.inv(X_with_c.T @ X_with_c)
        se = np.sqrt(np.diag(cov))
    except la.LinAlgError:
        se = np.full(len(coefs), np.nan)
    t_stats = coefs / se

    print(f"\nR² = {r2:.3f}")
    print(f"\n{'factor':<25} {'coef':>12} {'se':>12} {'t':>8}")
    for nm, c, s, t in zip(names, coefs, se, t_stats):
        print(f"{nm:<25} {c:>+12.6f} {s:>12.6f} {t:>+8.2f}")

    print("\nInterpretation:")
    print("  - intercept (pp/mo) is the part of alpha NOT explained by factors.")
    print("  - If intercept > 0 and t > 2: meaningful skill remains after factor control.")
    print("  - If intercept ≈ 0 with strong factor loadings: alpha is macro beta in disguise.")

    # Log
    log_path = HERE.parent / "LOG.md"
    import datetime as dt
    ts = dt.datetime.now().isoformat(timespec="seconds")
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"\n### phase47_regime_regression  {ts}\n")
        f.write(f"- R² = {r2:.3f}, n={n_obs}, mean alpha = {y.mean()*100:.4f}pp/mo\n")
        f.write("| factor | coef | se | t |\n|---|---|---|---|\n")
        for nm, c, s, t in zip(names, coefs, se, t_stats):
            f.write(f"| {nm} | {c:+.6f} | {s:.6f} | {t:+.2f} |\n")


if __name__ == "__main__":
    main()
