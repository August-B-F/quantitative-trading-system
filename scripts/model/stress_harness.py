"""Stress-testing harness for the OPTIMIZED strategy (E-R1 + M11 inv_vol + M26_post_3d).

Builds a cache of walk-forward regime classifier predictions, daily/monthly
strategy return streams, and per-month top-1 / top-k holdings so perturbation
tests can re-simulate without retraining.

Canonical baseline target (results/M26_FOLLOWUP.md — M26_post_3d):
    CAGR 23.61%  Sharpe 1.50  MaxDD -12.94%

Usage:
    py scripts/model/stress_harness.py --build        # train + cache
    py scripts/model/stress_harness.py --validate     # reproduce baseline
    then import from other scripts:
        from stress_harness import load_cache, run_strategy_from_cache, stats
"""
from __future__ import annotations

import argparse
import json
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

CACHE_DIR = ROOT / "results/stress"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
CACHE_PATH = CACHE_DIR / "cache.pkl"

# ---- Strategy constants (OPTIMIZED = E-R1 + M11 inv_vol) --------------------
ETFS = ["SOXX", "QQQ", "XLK", "VGT", "IGV", "XLE", "GLD", "SHY"]
LB_STABLE = 63
LB_TRANS = 21
K = 3
W_TOP1 = 0.5
W_TOPK = 0.5
SMA_GATE = -0.04

SPLIT_KW = dict(
    min_train_months=60, val_months=6, test_months=3, step_months=3,
    sample_every_n_days=5, embargo_days=5, target_horizon=21,
    decay_halflife_months=36,
)
REGIME_CLASSES = ["regime_hg_li", "regime_hg_hi", "regime_lg_li", "regime_lg_hi_stagflation"]
REGIME_FEATS = [f"regime_growth_inflation__{c}" for c in REGIME_CLASSES]

# M26_post_3d canonical defaults
M26_POST_DAYS = 3
M26_WINDOW_POST = 2


# ============================================================================
# Cache build (run once)
# ============================================================================
def build_cache() -> dict:
    from sklearn.ensemble import HistGradientBoostingClassifier

    from model.walk_forward import ExpandingSplitter  # type: ignore
    from model.preprocessing import FeaturePreprocessor  # type: ignore

    print("[build] Loading master panel...")
    df = pd.read_parquet(ROOT / "data/features/master_panel.parquet")
    feature_sets = yaml.safe_load(open(ROOT / "configs/feature_sets.yaml"))
    core_feats = [c for c in feature_sets["core"] if c in df.columns]
    DATES = df.index
    NDAYS = len(df)
    print(f"  panel {df.shape}  core feats {len(core_feats)}")

    def load_ret(days):
        return pd.read_parquet(ROOT / f"data/features/price/returns_{days}d.parquet").reindex(DATES)

    R = {d: load_ret(d) for d in (21, 63)}

    def fwd21(t):
        col = f"TARGET_FWD21_{t}"
        if col in df.columns:
            return df[col].values
        return R[21][t].shift(-21).reindex(DATES).values

    FWD = {t: fwd21(t) for t in ETFS}
    FWD_ARR = np.full((NDAYS, len(ETFS)), np.nan)
    for j, t in enumerate(ETFS):
        FWD_ARR[:, j] = FWD[t]

    shy_ret = FWD["SHY"]
    spy_dist = df["quality_dist_sma200__SPY"].values

    # Walk-forward folds
    splitter = ExpandingSplitter(**SPLIT_KW)
    folds = splitter.split(DATES)
    test_dates = pd.DatetimeIndex(sorted(set(d for f in folds for d in f["test_dates"])))
    te_pos = DATES.get_indexer(test_dates)
    print(f"  folds {len(folds)}  test dates {len(test_dates)}")

    # Train walk-forward regime classifier (expensive — happens once)
    target_col = "TARGET_TREG_growth_inflation_fwd21"
    cls_to_idx = {c: i for i, c in enumerate(REGIME_CLASSES)}
    current_reg = df[REGIME_FEATS].values.argmax(axis=1)
    pred_reg = np.full(NDAYS, -1, dtype=int)
    print("[build] Training walk-forward regime classifier...")
    for k_i, fold in enumerate(folds):
        tr = fold["train_dates"]; te = fold["test_dates"]
        if len(tr) < 30 or len(te) < 1:
            continue
        sw = np.asarray(fold["train_sample_weights"])
        Xtr = df.loc[tr, core_feats]; ytr_raw = df.loc[tr, target_col]
        Xte = df.loc[te, core_feats]
        mtr = ytr_raw.notna()
        Xtr, ytr_raw, sw = Xtr[mtr], ytr_raw[mtr], sw[mtr.to_numpy()]
        if len(Xtr) < 50:
            continue
        ytr = ytr_raw.map(cls_to_idx).astype(int).to_numpy()
        pp = FeaturePreprocessor()
        Xtr_z = pp.fit_transform(Xtr, sample_weights=sw).to_numpy()
        Xte_z = pp.transform(Xte).to_numpy()
        clf = HistGradientBoostingClassifier(
            max_iter=200, max_depth=4, learning_rate=0.05,
            min_samples_leaf=20, l2_regularization=1.0, random_state=0,
        )
        clf.fit(Xtr_z, ytr, sample_weight=sw)
        proba = clf.predict_proba(Xte_z)
        full = np.zeros((len(Xte_z), 4))
        for j, c in enumerate(clf.classes_):
            full[:, int(c)] = proba[:, j]
        pr = np.argmax(full, axis=1)
        pred_reg[DATES.get_indexer(te)] = pr
        if (k_i + 1) % 10 == 0:
            print(f"    fold {k_i + 1}/{len(folds)}")

    # Momentum arrays
    def mom_arr(lb):
        a = np.full((NDAYS, len(ETFS)), np.nan)
        rdf = R[lb]
        for j, t in enumerate(ETFS):
            a[:, j] = rdf[t].reindex(DATES).values
        return a

    M_STABLE = mom_arr(LB_STABLE)
    M_TRANS = mom_arr(LB_TRANS)

    # ATR
    atr21 = pd.read_parquet(ROOT / "data/features/price/atr_21d.parquet").reindex(DATES)
    ATR = np.full((NDAYS, len(ETFS)), np.nan)
    atr14 = pd.read_parquet(ROOT / "data/features/price/atr_14d.parquet").reindex(DATES)
    ATR14 = np.full((NDAYS, len(ETFS)), np.nan)
    for j, t in enumerate(ETFS):
        if t in atr21.columns:
            ATR[:, j] = atr21[t].values
        if t in atr14.columns:
            ATR14[:, j] = atr14[t].values

    # Event masks
    is_fomc_day = (df["timing__is_fomc_day"].values > 0)
    fomc_day_idx = np.where(is_fomc_day)[0]
    vix = df["vol_features__vix"].values

    # SPY monthly returns for Monte Carlo / regime bucket comparisons
    spy_ret_21d = R[21]["SPY"].reindex(DATES).values  # trailing 21d return

    cache = {
        "DATES": DATES,
        "NDAYS": NDAYS,
        "ETFS": ETFS,
        "FWD_ARR": FWD_ARR,
        "shy_ret": shy_ret,
        "spy_dist": spy_dist,
        "spy_ret_21d": spy_ret_21d,
        "vix": vix,
        "test_dates": test_dates,
        "te_pos": te_pos,
        "pred_reg": pred_reg,
        "current_reg": current_reg,
        "M_STABLE": M_STABLE,
        "M_TRANS": M_TRANS,
        "ATR": ATR,
        "ATR14": ATR14,
        "fomc_day_idx": fomc_day_idx,
        "is_fomc_day": is_fomc_day,
    }
    with open(CACHE_PATH, "wb") as f:
        pickle.dump(cache, f)
    print(f"[build] Wrote cache: {CACHE_PATH}")
    return cache


def load_cache() -> dict:
    if not CACHE_PATH.exists():
        return build_cache()
    with open(CACHE_PATH, "rb") as f:
        return pickle.load(f)


# ============================================================================
# Stats helpers
# ============================================================================
def stats(r):
    r = np.asarray(r, float)
    r = r[~np.isnan(r)]
    if len(r) == 0:
        return dict(cagr=float("nan"), sharpe=float("nan"), max_dd=float("nan"), n=0)
    eq = np.cumprod(1 + r)
    yrs = len(r) / 12.0
    cagr = float(eq[-1] ** (1 / yrs) - 1)
    sd = r.std(ddof=1) if len(r) > 1 else 0.0
    sh = float(r.mean() / sd * np.sqrt(12)) if sd > 0 else float("nan")
    peak = np.maximum.accumulate(eq)
    dd = float((eq / peak - 1).min())
    return dict(cagr=cagr, sharpe=sh, max_dd=dd, n=int(len(r)))


def daily_stats(daily_r):
    r = np.asarray(daily_r, float)
    r = r[~np.isnan(r)]
    if len(r) == 0:
        return dict(cagr=float("nan"), sharpe=float("nan"), max_dd=float("nan"), n=0)
    eq = np.cumprod(1 + r)
    yrs = len(r) / 252.0
    cagr = float(eq[-1] ** (1 / yrs) - 1) if yrs > 0 else float("nan")
    sd = r.std(ddof=1) if len(r) > 1 else 0.0
    sh = float(r.mean() / sd * np.sqrt(252)) if sd > 0 else float("nan")
    peak = np.maximum.accumulate(eq)
    dd = float((eq / peak - 1).min())
    return dict(cagr=cagr, sharpe=sh, max_dd=dd, n=int(len(r)))


def fomc_window_mask_from_idx(fomc_day_idx, NDAYS, pre_days=0, post_days=2):
    m = np.zeros(NDAYS, bool)
    for i in fomc_day_idx:
        lo = max(0, i - pre_days)
        hi = min(NDAYS - 1, i + post_days)
        m[lo:hi + 1] = True
    return m


# ============================================================================
# The workhorse simulator
# ============================================================================
def run_strategy_from_cache(
    cache: dict,
    *,
    lookback_stable: int = LB_STABLE,
    lookback_trans: int = LB_TRANS,
    weight_top1: float = W_TOP1,
    weight_topk: float = W_TOPK,
    k: int = K,
    sma_gate: float = SMA_GATE,
    m26_post_days: int = M26_POST_DAYS,
    m26_window_post: int = M26_WINDOW_POST,
    atr_window: int = 21,             # 21 (default) or 14
    flip_mask: np.ndarray | None = None,   # boolean over te_pos — flip pred_reg at these rebal positions
    year_exclude: list[int] | None = None,
    date_range: tuple[str, str] | None = None,
    cost_bps: float = 0.0,
    return_picks: bool = False,
    pred_reg_override: np.ndarray | None = None,
):
    """Re-simulate the OPTIMIZED strategy with optional perturbations.

    Returns a dict with 'monthly' (pd.Series), 'stats' (dict), and optionally
    'picks' (DataFrame of per-month holdings), 'turnover' (annual), 'gross'
    (monthly before cost).
    """
    DATES = cache["DATES"]
    NDAYS = cache["NDAYS"]
    ETFS_ = cache["ETFS"]
    FWD_ARR = cache["FWD_ARR"]
    shy_ret = cache["shy_ret"]
    spy_dist = cache["spy_dist"]
    test_dates = cache["test_dates"]
    te_pos = cache["te_pos"]
    pred_reg = cache["pred_reg"].copy() if pred_reg_override is None else pred_reg_override.copy()
    current_reg = cache["current_reg"]
    M_STABLE = cache["M_STABLE"]
    M_TRANS = cache["M_TRANS"]
    ATR = cache["ATR"] if atr_window == 21 else cache["ATR14"]
    fomc_day_idx = cache["fomc_day_idx"]

    # Allow non-default lookbacks by rebuilding momentum arrays from returns files.
    # (Expensive — only triggered when the caller deviates from 63/21.)
    if lookback_stable != LB_STABLE or lookback_trans != LB_TRANS:
        def _load_mom(lb):
            f = ROOT / f"data/features/price/returns_{lb}d.parquet"
            if not f.exists():
                raise FileNotFoundError(f"No returns_{lb}d.parquet; supported lookbacks depend on feature precompute")
            rdf = pd.read_parquet(f).reindex(DATES)
            a = np.full((NDAYS, len(ETFS_)), np.nan)
            for j, t in enumerate(ETFS_):
                a[:, j] = rdf[t].values
            return a
        if lookback_stable != LB_STABLE:
            M_STABLE = _load_mom(lookback_stable)
        if lookback_trans != LB_TRANS:
            M_TRANS = _load_mom(lookback_trans)

    use_trans = (pred_reg != -1) & (pred_reg != current_reg)
    MOM = np.where(use_trans[:, None], M_TRANS, M_STABLE)
    SF = np.where(np.isnan(MOM), -np.inf, MOM)

    # Monthly rebalance positions (last test day per month)
    s_idx = pd.Series(te_pos, index=test_dates)
    month_last = s_idx.groupby(test_dates.to_period("M")).tail(1)

    # M26_post_3d window
    fomc_post = fomc_window_mask_from_idx(fomc_day_idx, NDAYS,
                                          pre_days=0, post_days=m26_window_post)

    out = {}
    picks_rows = []
    flip_lookup = None
    if flip_mask is not None:
        # flip_mask aligned to the rebalance sequence length
        flip_lookup = flip_mask

    for idx_m, (d, i) in enumerate(month_last.items()):
        i = int(i)
        deferred = False
        if m26_post_days > 0 and fomc_post[i]:
            i_use = min(i + m26_post_days, NDAYS - 1)
            deferred = True
        else:
            i_use = i

        # Optional classifier-decision flip: force top1 to be a random other ETF
        sf_i = SF[i_use]
        top1 = int(np.argmax(sf_i))
        tk = np.argsort(-sf_i)[:k]

        if flip_lookup is not None and idx_m < len(flip_lookup) and flip_lookup[idx_m]:
            # Flip: pick the _second_-best as top1 (deterministic alternative);
            # this mimics "classifier was wrong" without random seed leakage
            order = np.argsort(-sf_i)
            top1 = int(order[1]) if len(order) > 1 else top1
            tk = order[:k]

        r1_raw = FWD_ARR[i_use, top1]
        if spy_dist[i_use] > sma_gate:
            r1 = r1_raw
        else:
            r1 = shy_ret[i_use]

        # top-k inv-vol
        sel_atr = ATR[i_use, tk]
        inv = 1.0 / np.where(sel_atr > 0, sel_atr, np.nan)
        if np.isnan(inv).all():
            rk = np.nanmean(FWD_ARR[i_use, tk])
            w = np.full(len(tk), 1.0 / max(len(tk), 1))
        else:
            w = inv / np.nansum(inv)
            rk = np.nansum(FWD_ARR[i_use, tk] * w)

        ret = weight_top1 * r1 + weight_topk * rk
        out[d] = ret
        picks_rows.append({
            "rebal_date": d,
            "orig_i": i,
            "used_i": i_use,
            "deferred": deferred,
            "top1": ETFS_[top1],
            "topk": [ETFS_[j] for j in tk],
            "topk_w": list(w),
            "gross_ret": float(ret),
            "spy_gated": bool(spy_dist[i_use] <= sma_gate),
        })

    s = pd.Series(out).sort_index()
    s.index = s.index.to_timestamp("M") if hasattr(s.index, "to_timestamp") else s.index

    # Filters
    if date_range is not None:
        s = s[(s.index >= date_range[0]) & (s.index <= date_range[1])]
    if year_exclude:
        s = s[~s.index.year.isin(year_exclude)]

    gross = s.copy()

    # Transaction costs: compute per-rebalance turnover from top1 switching + topk weights
    turnover_series = None
    if cost_bps != 0.0 and picks_rows:
        picks_df = pd.DataFrame(picks_rows)
        # weight vectors per rebal over full ETF set
        n_rebals = len(picks_df)
        W = np.zeros((n_rebals, len(ETFS_)))
        for r_i, row in picks_df.iterrows():
            # top1 weight
            top1_j = ETFS_.index(row["top1"]) if not row["spy_gated"] else ETFS_.index("SHY")
            W[r_i, top1_j] += weight_top1
            for name, wv in zip(row["topk"], row["topk_w"]):
                W[r_i, ETFS_.index(name)] += weight_topk * (wv if not np.isnan(wv) else 1.0 / k)
        dW = np.abs(np.diff(W, axis=0, prepend=np.zeros((1, W.shape[1]))))
        turnover = dW.sum(axis=1)  # per rebal [0, 2]
        # Apply cost to the same months (turnover-weighted)
        cost_per_month = (cost_bps / 1e4) * turnover
        picks_df["cost"] = cost_per_month
        picks_df["rebal_date"] = pd.to_datetime(picks_df["rebal_date"].astype(str))
        cost_series = pd.Series(cost_per_month,
                                index=pd.PeriodIndex(picks_df["rebal_date"], freq="M").to_timestamp("M"))
        cost_series = cost_series.groupby(cost_series.index).sum()
        s = s.copy()
        s_vals = s.values.astype(float).copy()  # writable
        s_idx_yr = s.index.year
        s_idx_mo = s.index.month
        for dt, c in cost_series.items():
            mask = (s_idx_yr == dt.year) & (s_idx_mo == dt.month)
            if mask.any():
                s_vals[mask] = s_vals[mask] - float(c)
        s = pd.Series(s_vals, index=s.index)
        turnover_series = pd.Series(turnover, index=[r["rebal_date"] for r in picks_rows])

    result = {
        "monthly": s,
        "gross": gross,
        "stats": stats(s.values),
        "picks": pd.DataFrame(picks_rows) if return_picks or cost_bps != 0 else None,
        "turnover": turnover_series,
    }
    return result


# ============================================================================
# Validation
# ============================================================================
TARGET_BASELINE = dict(cagr=0.2361, sharpe=1.50, max_dd=-0.1294)


def validate(cache: dict, tol_cagr_pp: float = 0.5) -> tuple[bool, dict]:
    r = run_strategy_from_cache(cache)
    st = r["stats"]
    print("\n=== VALIDATE baseline (M26_post_3d) ===")
    print(f"  actual : CAGR {st['cagr']*100:.2f}%  Sharpe {st['sharpe']:.2f}  MaxDD {st['max_dd']*100:.2f}%")
    print(f"  target : CAGR 23.61%  Sharpe 1.50  MaxDD -12.94%")
    d_cagr = abs(st["cagr"] - TARGET_BASELINE["cagr"]) * 100
    d_sh = abs(st["sharpe"] - TARGET_BASELINE["sharpe"])
    d_dd = abs(st["max_dd"] - TARGET_BASELINE["max_dd"]) * 100
    print(f"  diff   : dCAGR {d_cagr:.2f}pp  dSharpe {d_sh:.2f}  dMaxDD {d_dd:.2f}pp")
    ok = d_cagr <= tol_cagr_pp
    print(f"  verdict: {'PASS' if ok else 'FAIL (outside tol)'}")
    return ok, st


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--validate", action="store_true")
    ap.add_argument("--rebuild", action="store_true", help="Force rebuild")
    args = ap.parse_args()

    if args.rebuild and CACHE_PATH.exists():
        CACHE_PATH.unlink()

    if args.build or args.rebuild or not CACHE_PATH.exists():
        cache = build_cache()
    else:
        cache = load_cache()

    if args.validate or args.build or args.rebuild:
        ok, st = validate(cache)
        (CACHE_DIR / "validation.json").write_text(json.dumps(
            {"stats": st, "target": TARGET_BASELINE, "pass": ok}, indent=2, default=str))
        if not ok:
            sys.exit(2)


if __name__ == "__main__":
    main()
