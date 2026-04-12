"""Optimization block: M01..M27 modifications on top of E-R1.

Tests lookback / sizing / universe / gates / rebalancing variants of the
regime-conditional momentum strategy and reports which beat the haircut bar.

Outputs:
  results/experiments/M01.json .. M27.json
  results/OPTIMIZATION_REPORT.md
  results/OPTIMIZED_STRATEGY.md
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from model.walk_forward import ExpandingSplitter  # noqa: E402
from model.preprocessing import FeaturePreprocessor  # noqa: E402

OUT_DIR = ROOT / "results/experiments"
OUT_DIR.mkdir(parents=True, exist_ok=True)

ETFS = ["SOXX", "QQQ", "XLK", "VGT", "IGV", "XLE", "GLD", "SHY"]
N = len(ETFS)
UNIVERSE_EXTRAS = ["TLT", "DBC", "XLF", "XLI", "XLV"]

SPLIT_KW = dict(
    min_train_months=60, val_months=6, test_months=3, step_months=3,
    sample_every_n_days=5, embargo_days=5, target_horizon=21,
    decay_halflife_months=36,
)
REGIME_CLASSES = ["regime_hg_li", "regime_hg_hi", "regime_lg_li", "regime_lg_hi_stagflation"]
REGIME_FEATS = [f"regime_growth_inflation__{c}" for c in REGIME_CLASSES]

# ---------------------------------------------------------------------------
# Load
# ---------------------------------------------------------------------------
print("Loading master panel…")
df = pd.read_parquet(ROOT / "data/features/master_panel.parquet")
feature_sets = yaml.safe_load(open(ROOT / "configs/feature_sets.yaml"))
core_feats = [c for c in feature_sets["core"] if c in df.columns]
print(f"  panel: {df.shape}  core feats: {len(core_feats)}")

DATES = df.index
NDAYS = len(df)

# Load returns @ multiple lookbacks for all tickers
def load_ret(days):
    return pd.read_parquet(ROOT / f"data/features/price/returns_{days}d.parquet").reindex(DATES)

R = {d: load_ret(d) for d in (10, 21, 42, 63, 126)}
ALL_TICKERS = sorted(set(ETFS) | set(UNIVERSE_EXTRAS))

# Forward 21d returns for any ticker: shift returns_21d by -21
def fwd21(ticker):
    if f"TARGET_FWD21_{ticker}" in df.columns:
        return df[f"TARGET_FWD21_{ticker}"].values
    s = R[21][ticker].shift(-21)
    return s.reindex(DATES).values

FWD = {t: fwd21(t) for t in ALL_TICKERS}

# SHY fwd return for cash leg
shy_ret = FWD["SHY"]
spy_dist = df["quality_dist_sma200__SPY"].values

# Walk-forward folds
splitter = ExpandingSplitter(**SPLIT_KW)
folds = splitter.split(DATES)
test_dates = pd.DatetimeIndex(sorted(set(d for f in folds for d in f["test_dates"])))
te_pos = DATES.get_indexer(test_dates)
print(f"  folds: {len(folds)}  test dates: {len(test_dates)}")

# Current regime (labels)
current_reg = df[REGIME_FEATS].values.argmax(axis=1)

# ---------------------------------------------------------------------------
# Walk-forward regime classifier (re-used across all mods)
# ---------------------------------------------------------------------------
print("Training walk-forward regime classifier…")
target_col = "TARGET_TREG_growth_inflation_fwd21"
cls_to_idx = {c: i for i, c in enumerate(REGIME_CLASSES)}
pred_reg = np.full(NDAYS, -1, dtype=int)
fold_accs = []
for fold in folds:
    tr = fold["train_dates"]; te = fold["test_dates"]
    if len(tr) < 30 or len(te) < 1:
        continue
    sw = np.asarray(fold["train_sample_weights"])
    Xtr = df.loc[tr, core_feats]; ytr_raw = df.loc[tr, target_col]
    Xte = df.loc[te, core_feats]; yte_raw = df.loc[te, target_col]
    mtr = ytr_raw.notna()
    Xtr, ytr_raw, sw = Xtr[mtr], ytr_raw[mtr], sw[mtr.to_numpy()]
    if len(Xtr) < 50:
        continue
    ytr = ytr_raw.map(cls_to_idx).astype(int).to_numpy()
    pp = FeaturePreprocessor()
    Xtr_z = pp.fit_transform(Xtr, sample_weights=sw).to_numpy()
    Xte_z = pp.transform(Xte).to_numpy()
    clf = HistGradientBoostingClassifier(max_iter=200, max_depth=4, learning_rate=0.05,
                                          min_samples_leaf=20, l2_regularization=1.0, random_state=0)
    clf.fit(Xtr_z, ytr, sample_weight=sw)
    proba = clf.predict_proba(Xte_z)
    full = np.zeros((len(Xte_z), 4))
    for j, c in enumerate(clf.classes_):
        full[:, int(c)] = proba[:, j]
    pr = np.argmax(full, axis=1)
    te_pos_f = DATES.get_indexer(te)
    pred_reg[te_pos_f] = pr
    yte_m = yte_raw.map(cls_to_idx)
    if yte_m.notna().any():
        yv = yte_m.dropna().astype(int).to_numpy()
        fold_accs.append(float((pr[:len(yv)] == yv[:len(pr)]).mean()))
regime_acc = float(np.mean(fold_accs)) if fold_accs else float("nan")
print(f"  WF regime accuracy: {regime_acc:.3f}")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
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

def to_monthly(daily, dates=None):
    dates = test_dates if dates is None else dates
    s = pd.Series(daily, index=dates).dropna()
    return s.groupby(s.index.to_period("M")).tail(1)

def trend_gate(base):
    return np.where(spy_dist > -0.04, base, shy_ret)

def build_mom_array(universe, lookback):
    """Returns (NDAYS, len(universe)) array of momentum at given lookback (days)."""
    arr = np.full((NDAYS, len(universe)), np.nan)
    rdf = R[lookback]
    for j, t in enumerate(universe):
        arr[:, j] = rdf[t].reindex(DATES).values
    return arr

def build_fwd_array(universe):
    arr = np.full((NDAYS, len(universe)), np.nan)
    for j, t in enumerate(universe):
        arr[:, j] = FWD[t]
    return arr

def topk_returns(mom, fwd_arr, k):
    sf = np.where(np.isnan(mom), -np.inf, mom)
    if k == 1:
        idx = np.argmax(sf, axis=1)
        return fwd_arr[np.arange(NDAYS), idx]
    idx = np.argsort(-sf, axis=1)[:, :k]
    rows = fwd_arr[np.arange(NDAYS)[:, None], idx]
    return np.nanmean(rows, axis=1)

def topk_indices(mom, k):
    sf = np.where(np.isnan(mom), -np.inf, mom)
    return np.argsort(-sf, axis=1)[:, :k]

# Cross-sectional volatility for inverse-vol weighting (realized 21d std)
# Use atr_21d as a proxy where available — simpler and aligned to the data we have
atr21 = pd.read_parquet(ROOT / "data/features/price/atr_21d.parquet").reindex(DATES)

# ---------------------------------------------------------------------------
# Strategy builder
# ---------------------------------------------------------------------------
def build_strategy(
    universe=ETFS,
    lookback_stable=63,
    lookback_trans=21,
    blended_stable=None,   # list of lookbacks to avg, e.g. [63, 126]
    blended_trans=None,
    weight_top1=0.5,
    weight_topk=0.5,
    k=3,
    weighting="equal",      # equal, inv_vol, mom_score
    apply_trend_gate=True,
):
    """Return per-day daily-cadence strategy returns aligned to DATES."""
    fwd_arr = build_fwd_array(universe)
    n_uni = len(universe)

    # Build mom_stable (stable regime signal)
    if blended_stable:
        m_stable = np.nanmean(np.stack([build_mom_array(universe, l) for l in blended_stable]), axis=0)
    else:
        m_stable = build_mom_array(universe, lookback_stable)
    if blended_trans:
        m_trans = np.nanmean(np.stack([build_mom_array(universe, l) for l in blended_trans]), axis=0)
    else:
        m_trans = build_mom_array(universe, lookback_trans)

    # Regime-conditional combination
    use_trans = (pred_reg != -1) & (pred_reg != current_reg)
    mom = np.where(use_trans[:, None], m_trans, m_stable)

    # Top-1 leg
    sf = np.where(np.isnan(mom), -np.inf, mom)
    top1_idx = np.argmax(sf, axis=1)
    top1_ret = fwd_arr[np.arange(NDAYS), top1_idx]
    if apply_trend_gate:
        top1_ret = np.where(spy_dist > -0.04, top1_ret, shy_ret)

    # Top-k leg
    if k <= 0 or weight_topk == 0:
        topk_ret = np.zeros(NDAYS)
    else:
        idxk = np.argsort(-sf, axis=1)[:, :k]
        rowfwd = fwd_arr[np.arange(NDAYS)[:, None], idxk]
        if weighting == "equal":
            topk_ret = np.nanmean(rowfwd, axis=1)
        elif weighting == "inv_vol":
            # Build atr matrix for the universe
            atr_arr = np.full((NDAYS, n_uni), np.nan)
            for j, t in enumerate(universe):
                if t in atr21.columns:
                    atr_arr[:, j] = atr21[t].values
                else:
                    atr_arr[:, j] = np.nan
            sel_atr = atr_arr[np.arange(NDAYS)[:, None], idxk]
            inv = 1.0 / np.where(sel_atr > 0, sel_atr, np.nan)
            w = inv / np.nansum(inv, axis=1, keepdims=True)
            topk_ret = np.nansum(rowfwd * w, axis=1)
        elif weighting == "mom_score":
            sel_mom = mom[np.arange(NDAYS)[:, None], idxk]
            sel_mom = np.where(sel_mom > 0, sel_mom, 0.0)
            wsum = sel_mom.sum(axis=1, keepdims=True)
            wsum = np.where(wsum > 0, wsum, np.nan)
            w = sel_mom / wsum
            # Where all zero/neg, fall back to equal
            mask = np.isnan(w).all(axis=1)
            w = np.where(np.isnan(w), 1.0 / k, w)
            topk_ret = np.nansum(rowfwd * w, axis=1)
        else:
            raise ValueError(weighting)

    daily = weight_top1 * top1_ret + weight_topk * topk_ret
    return daily

# ---------------------------------------------------------------------------
# Soft EV gate (M19) — minimal port
# ---------------------------------------------------------------------------
MACRO_FEATS = [
    "vol_features__vix",
    "credit_features__nfci", "credit_features__hy_ig_spread", "credit_features__nfci_chg21",
    "credit_features__ted_spread",
    "quality_dist_sma200__SPY", "quality_dist_sma50__SPY",
    "returns_63d__SPY", "returns_42d__SPY", "returns_21d__SPY",
    "sp500_pe", "sp500_cape_pct_10y",
    "inflation_features__cpi_yoy_3m_trend", "inflation_features__pce_core_yoy_3m_trend",
    "activity_features__ism_pmi_3m_trend", "activity_features__oecd_cli_3m_change",
    "consumer_features__consumer_credit_yoy", "liquidity_features__m2_yoy_6m_chg",
    "atr_14d__SHY", "atr_14d__SPY",
]
MACRO_FEATS = [c for c in MACRO_FEATS if c in df.columns]
X_macro = df[MACRO_FEATS].values

def soft_ev_apply(daily_full):
    """Returns dict {date: scaled_return} for test dates only."""
    out = {}
    for fold in folds:
        tr = fold["train_dates"]; va = fold["val_dates"]; te = fold["test_dates"]
        if len(tr) < 50 or len(va) < 5 or len(te) < 1:
            continue
        sw = np.asarray(fold["train_sample_weights"])
        tr_pos = DATES.get_indexer(tr)
        va_pos = DATES.get_indexer(va)
        te_pos_f = DATES.get_indexer(te)
        ytr = daily_full[tr_pos]
        mtr = ~np.isnan(ytr)
        if mtr.sum() < 30:
            continue
        Xtr = pd.DataFrame(X_macro[tr_pos][mtr], columns=MACRO_FEATS)
        pp = FeaturePreprocessor()
        Xtr_z = pp.fit_transform(Xtr, sample_weights=sw[mtr]).to_numpy()
        Xva_z = pp.transform(pd.DataFrame(X_macro[va_pos], columns=MACRO_FEATS)).to_numpy()
        Xte_z = pp.transform(pd.DataFrame(X_macro[te_pos_f], columns=MACRO_FEATS)).to_numpy()
        m = HistGradientBoostingRegressor(max_iter=300, max_depth=4, learning_rate=0.05,
                                          min_samples_leaf=20, l2_regularization=2.0, random_state=0)
        m.fit(Xtr_z, ytr[mtr], sample_weight=sw[mtr])
        pred_va = m.predict(Xva_z)
        pred_te = m.predict(Xte_z)
        valid_va = ~np.isnan(daily_full[va_pos])
        if valid_va.sum() < 3:
            continue
        lo = float(np.quantile(pred_va[valid_va], 0.10))
        hi = float(np.quantile(pred_va[valid_va], 0.50))
        denom = max(hi - lo, 1e-6)
        for i, d in enumerate(te):
            br = daily_full[te_pos_f[i]]
            if np.isnan(br):
                continue
            w = max(0.0, min(1.0, (pred_te[i] - lo) / denom))
            out[pd.Timestamp(d)] = (1 - 0.5) * br + 0.5 * (w * br + (1 - w) * shy_ret[te_pos_f[i]])
            # Soft EV gate as a 50/50 blend with the gated version (less surgical)
            out[pd.Timestamp(d)] = w * br + (1 - w) * shy_ret[te_pos_f[i]]
    return out

# ---------------------------------------------------------------------------
# Gates / overlays
# ---------------------------------------------------------------------------
hy_z = df["credit_features__hy_ig_spread_z252"].values if "credit_features__hy_ig_spread_z252" in df.columns else np.full(NDAYS, np.nan)
vix = df["vol_features__vix"].values
yc_slope = df["yield_curve_features__yc_slope_10y_2y"].values
fomc_week = df["timing__is_fomc_week"].values.astype(bool) if "timing__is_fomc_week" in df.columns else np.zeros(NDAYS, bool)
quad_witch = df["timing__is_quad_witching_week"].values.astype(bool) if "timing__is_quad_witching_week" in df.columns else np.zeros(NDAYS, bool)

# M26 canonical spec (per results/M26_FOLLOWUP.md): defer rebalance by 3 trading days
# when rebalance date falls within [FOMC day, +2 trading days after FOMC].
# Corrected from legacy (defer 5d on any FOMC week). Asymmetric post-only window.
is_fomc_day = (df["timing__is_fomc_day"].values > 0) if "timing__is_fomc_day" in df.columns else np.zeros(NDAYS, bool)
_fomc_day_idx = np.where(is_fomc_day)[0]

def fomc_window_mask(pre_days: int = 0, post_days: int = 2) -> np.ndarray:
    """True on trading-day positions within [-pre_days, +post_days] of any FOMC day."""
    m = np.zeros(NDAYS, bool)
    for i in _fomc_day_idx:
        lo = max(0, i - pre_days)
        hi = min(NDAYS - 1, i + post_days)
        m[lo:hi + 1] = True
    return m

# Default = M26_post_3d: post-only ±(0,+2) window, defer by 3 trading days.
M26_POST_DEFAULT_DAYS = 3
M26_POST_DEFAULT_WINDOW = 2
FOMC_POST_WIN = fomc_window_mask(pre_days=0, post_days=M26_POST_DEFAULT_WINDOW)

def apply_gate(daily, scale_arr):
    """Blend daily with shy_ret using per-day scale (1=full daily, 0=full SHY)."""
    return scale_arr * daily + (1 - scale_arr) * shy_ret

def credit_gate_scale():
    s = np.ones(NDAYS)
    s[hy_z > 1.5] = 0.6
    return s

def vix_gate_scale():
    s = np.ones(NDAYS)
    s[vix > 30] = 0.5
    return s

def yc_gate_scale():
    inv = (yc_slope < 0).astype(float)
    inv = pd.Series(inv, index=DATES).rolling(63).sum().values
    s = np.ones(NDAYS)
    s[inv >= 63] = 0.7
    return s

def signal_disagreement_scale(universe):
    """ED3-style: when 63d top, 126d top, regime-favored top all disagree → scale 0.7"""
    m63 = build_mom_array(universe, 63)
    m126 = build_mom_array(universe, 126)
    sf63 = np.where(np.isnan(m63), -np.inf, m63)
    sf126 = np.where(np.isnan(m126), -np.inf, m126)
    t63 = np.argmax(sf63, axis=1)
    t126 = np.argmax(sf126, axis=1)
    REGIME_FAV = {
        0: {"SOXX","QQQ","XLK","VGT","IGV"}, 1: {"XLE","GLD","SOXX","QQQ"},
        2: {"SHY","TLT","GLD","XLV"}, 3: {"GLD","XLE","SHY"},
    }
    s = np.ones(NDAYS)
    for i in range(NDAYS):
        a = universe[t63[i]] if t63[i] < len(universe) else None
        b = universe[t126[i]] if t126[i] < len(universe) else None
        fav = REGIME_FAV.get(pred_reg[i], set()) if pred_reg[i] != -1 else set()
        if a != b and a not in fav and b not in fav and fav:
            s[i] = 0.7
    return s

# ---------------------------------------------------------------------------
# Rebalancing variants (M24..M27)
# ---------------------------------------------------------------------------
def monthly_simulate(universe, lookback_stable=63, lookback_trans=21,
                     k=3, weight_top1=0.5, weight_topk=0.5,
                     weekly_threshold=None, defer_fomc=False, defer_quad=False,
                     m26_post_days=M26_POST_DEFAULT_DAYS,
                     m26_window_post=M26_POST_DEFAULT_WINDOW,
                     weighting="equal"):
    """Walk weekly or monthly through test_dates. Returns Series of monthly returns."""
    fwd_arr = build_fwd_array(universe)
    m_stable = build_mom_array(universe, lookback_stable)
    m_trans = build_mom_array(universe, lookback_trans)
    use_trans = (pred_reg != -1) & (pred_reg != current_reg)
    mom = np.where(use_trans[:, None], m_trans, m_stable)
    sf = np.where(np.isnan(mom), -np.inf, mom)

    test_idx = te_pos
    test_d = test_dates

    # Weekly threshold simulation
    if weekly_threshold is not None:
        # Resample to weekly: pick the last test date per ISO-week
        wd = pd.Series(test_idx, index=test_d).groupby(test_d.to_period("W")).tail(1)
        held_top1 = None
        held_topk = None
        held_top1_score = -np.inf
        out = {}
        for d, i in wd.items():
            new_top1 = int(np.argmax(sf[i]))
            new_score = sf[i, new_top1]
            if held_top1 is None or new_score - held_top1_score > weekly_threshold:
                held_top1 = new_top1
                held_top1_score = new_score
                held_topk = np.argsort(-sf[i])[:k]
            r1 = fwd_arr[i, held_top1]
            r1 = r1 if spy_dist[i] > -0.04 else shy_ret[i]
            rk = np.nanmean(fwd_arr[i, held_topk])
            out[d] = weight_top1 * r1 + weight_topk * rk
        s = pd.Series(out).sort_index()
        return s.groupby(s.index.to_period("M")).tail(1)

    # Defer FOMC / Quad witching
    if defer_fomc or defer_quad:
        # M26_post_3d canonical spec: defer by m26_post_days (default 3) trading days
        # when rebalance date falls within [FOMC, FOMC + m26_window_post] trading days.
        # Quad witching retains the legacy defer-5-on-whole-week semantics.
        fomc_post_mask = fomc_window_mask(pre_days=0, post_days=m26_window_post)
        m_d = pd.Series(test_idx, index=test_d).groupby(test_d.to_period("M")).tail(1)
        # Pre-build ATR array for optional inv_vol weighting inside the M26 path
        n_uni = len(universe)
        atr_arr = np.full((NDAYS, n_uni), np.nan)
        if weighting == "inv_vol":
            for j, t in enumerate(universe):
                if t in atr21.columns:
                    atr_arr[:, j] = atr21[t].values
        out = {}
        for d, i in m_d.items():
            i = int(i)
            if defer_fomc and fomc_post_mask[i]:
                i_use = min(i + m26_post_days, NDAYS - 1)
            elif defer_quad and quad_witch[i]:
                i_use = min(i + 5, NDAYS - 1)
            else:
                i_use = i
            top1 = int(np.argmax(sf[i_use]))
            tk = np.argsort(-sf[i_use])[:k]
            r1 = fwd_arr[i_use, top1]
            r1 = r1 if spy_dist[i_use] > -0.04 else shy_ret[i_use]
            if weighting == "inv_vol":
                sel_atr = atr_arr[i_use, tk]
                inv = 1.0 / np.where(sel_atr > 0, sel_atr, np.nan)
                if np.isnan(inv).all():
                    rk = np.nanmean(fwd_arr[i_use, tk])
                else:
                    w = inv / np.nansum(inv)
                    rk = np.nansum(fwd_arr[i_use, tk] * w)
            else:
                rk = np.nanmean(fwd_arr[i_use, tk])
            out[d] = weight_top1 * r1 + weight_topk * rk
        return pd.Series(out).sort_index()

    raise ValueError("monthly_simulate called without a variant flag")

# ---------------------------------------------------------------------------
# Run mods
# ---------------------------------------------------------------------------
RESULTS = {}

def run_daily(name, daily, desc):
    s = to_monthly(daily[te_pos])
    st = stats(s.values)
    RESULTS[name] = {
        "description": desc,
        "n_monthly": int(len(s)),
        "stats": st,
        "monthly_returns": [{"date": str(d.date()), "fwd_ret": float(r)} for d, r in s.items()],
    }
    print(f"  {name}: CAGR {st['cagr']*100:5.2f}%  Sharpe {st['sharpe']:.2f}  MaxDD {st['max_dd']*100:6.2f}%")

def run_monthly(name, sm, desc):
    st = stats(sm.values)
    RESULTS[name] = {
        "description": desc,
        "n_monthly": int(len(sm)),
        "stats": st,
        "monthly_returns": [{"date": str(d.date()), "fwd_ret": float(r)} for d, r in sm.items()],
    }
    print(f"  {name}: CAGR {st['cagr']*100:5.2f}%  Sharpe {st['sharpe']:.2f}  MaxDD {st['max_dd']*100:6.2f}%")

# Control
print("\n=== Control ===")
ctrl_daily = build_strategy()
run_daily("E-R1", ctrl_daily, "Control: 63d/21d, 50% top1 + 50% top3, SMA200 gate")

# BLOCK 1
print("\n=== Block 1: lookbacks ===")
run_daily("M01", build_strategy(lookback_stable=63, lookback_trans=42), "63d/42d")
run_daily("M02", build_strategy(lookback_stable=126, lookback_trans=21), "126d/21d")
run_daily("M03", build_strategy(lookback_stable=126, lookback_trans=42), "126d/42d")
run_daily("M04", build_strategy(lookback_stable=63, lookback_trans=10), "63d/10d")
run_daily("M05", build_strategy(blended_stable=[63,126], lookback_trans=21), "avg(63,126)stable / 21d trans")
run_daily("M06", build_strategy(blended_stable=[21,63,126], blended_trans=[10,21]), "avg(21,63,126)/avg(10,21)")

# BLOCK 2
print("\n=== Block 2: position sizing ===")
run_daily("M07", build_strategy(weight_top1=0.0, weight_topk=1.0, k=3), "100% top3 EW")
run_daily("M08", build_strategy(weight_top1=0.4, weight_topk=0.6, k=3), "40% top1 / 60% top3")
run_daily("M09", build_strategy(weight_top1=0.6, weight_topk=0.4, k=3), "60% top1 / 40% top3")
run_daily("M10", build_strategy(weight_top1=0.5, weight_topk=0.5, k=2), "50% top1 / 50% top2")
run_daily("M11", build_strategy(weight_top1=0.5, weight_topk=0.5, k=3, weighting="inv_vol"), "top3 inverse-vol weighted")
run_daily("M12", build_strategy(weight_top1=0.5, weight_topk=0.5, k=3, weighting="mom_score"), "top3 momentum-score weighted")
run_daily("M13", build_strategy(weight_top1=0.5, weight_topk=0.5, k=4), "50/50 top1/top4")

# BLOCK 3
print("\n=== Block 3: universe ===")
run_daily("M14", build_strategy(universe=ETFS+["TLT"]), "+TLT (9 ETF)")
run_daily("M15", build_strategy(universe=ETFS+["DBC"]), "+DBC (9 ETF)")
run_daily("M16", build_strategy(universe=ETFS+["TLT","DBC"]), "+TLT+DBC (10 ETF)")
M17_UNI = ["SOXX","QQQ","XLE","GLD","SHY","XLF","XLI","XLV"]
run_daily("M17", build_strategy(universe=M17_UNI), "Drop XLK/VGT/IGV; +XLF/XLI/XLV")
M18_UNI = M17_UNI + ["TLT","DBC"]
run_daily("M18", build_strategy(universe=M18_UNI), "M17 + TLT + DBC (10 ETF)")

# BLOCK 4
print("\n=== Block 4: gates and overlays ===")
# M19: soft EV gate
ev_out = soft_ev_apply(ctrl_daily)
sm = pd.Series(ev_out).sort_index()
sm = sm.groupby(sm.index.to_period("M")).tail(1)
run_monthly("M19", sm, "E-R1 + soft EV gate (HistGB on macro)")
# M20..M22 simple gates
run_daily("M20", apply_gate(ctrl_daily, credit_gate_scale()), "E-R1 + HY-IG z>1.5 → 60%")
run_daily("M21", apply_gate(ctrl_daily, vix_gate_scale()), "E-R1 + VIX>30 → 50%")
run_daily("M22", apply_gate(ctrl_daily, yc_gate_scale()), "E-R1 + YC inverted 63d → 70%")
run_daily("M23", apply_gate(ctrl_daily, signal_disagreement_scale(ETFS)), "E-R1 + signal disagreement → 70%")

# BLOCK 5
print("\n=== Block 5: rebalancing timing ===")
run_monthly("M24", monthly_simulate(ETFS, weekly_threshold=0.03), "Weekly check, 3pp threshold")
run_monthly("M25", monthly_simulate(ETFS, weekly_threshold=0.05), "Weekly check, 5pp threshold")
run_monthly(
    "M26",
    monthly_simulate(ETFS, defer_fomc=True, weighting="inv_vol"),
    "M26_post_3d: defer 3d on [FOMC, FOMC+2] (inv_vol top-k)",
)
run_monthly("M27", monthly_simulate(ETFS, defer_quad=True), "Defer quad witching 5d")

# ---------------------------------------------------------------------------
# Save individual JSONs
# ---------------------------------------------------------------------------
for name, payload in RESULTS.items():
    if name.startswith("M"):
        (OUT_DIR / f"{name}.json").write_text(json.dumps(payload, indent=2, default=str))

# ---------------------------------------------------------------------------
# Haircut evaluation
# ---------------------------------------------------------------------------
ctrl_st = RESULTS["E-R1"]["stats"]
def haircut_pass(name):
    s = RESULTS[name]["stats"]
    d_cagr = s["cagr"] - ctrl_st["cagr"]
    d_sh = s["sharpe"] - ctrl_st["sharpe"]
    d_mdd = s["max_dd"] - ctrl_st["max_dd"]
    # Improvement must beat threshold AFTER 50% haircut
    cagr_ok = (d_cagr / 2) > 0.005   # 0.5pp / 2
    sh_ok = (d_sh / 2) > 0.03        # rule says >0.03 after haircut
    # Must not significantly worsen drawdown
    not_worse_dd = d_mdd > -0.02
    return (cagr_ok or sh_ok) and not_worse_dd, d_cagr, d_sh, d_mdd

# ---------------------------------------------------------------------------
# Combine passing mods incrementally
# ---------------------------------------------------------------------------
BLOCK_MODS = {
    "B1": ["M01","M02","M03","M04","M05","M06"],
    "B2": ["M07","M08","M09","M10","M11","M12","M13"],
    "B3": ["M14","M15","M16","M17","M18"],
    "B4": ["M19","M20","M21","M22","M23"],
    "B5": ["M24","M25","M26","M27"],
}
def best_pass(mods):
    pas = [m for m in mods if haircut_pass(m)[0]]
    if not pas:
        return None
    return max(pas, key=lambda m: RESULTS[m]["stats"]["sharpe"])

best_per_block = {b: best_pass(ms) for b, ms in BLOCK_MODS.items()}
print("\nBest per block (haircut-passing):", best_per_block)

# Build combined strategy spec from passing best mods
combo_spec = {
    "lookback_stable": 63, "lookback_trans": 21, "blended_stable": None, "blended_trans": None,
    "weight_top1": 0.5, "weight_topk": 0.5, "k": 3, "weighting": "equal",
    "universe": ETFS, "gate": None, "rebalance": None,
}
def apply_mod_to_spec(mod, spec):
    s = dict(spec)
    if mod == "M01": s.update(lookback_trans=42)
    elif mod == "M02": s.update(lookback_stable=126)
    elif mod == "M03": s.update(lookback_stable=126, lookback_trans=42)
    elif mod == "M04": s.update(lookback_trans=10)
    elif mod == "M05": s.update(blended_stable=[63,126])
    elif mod == "M06": s.update(blended_stable=[21,63,126], blended_trans=[10,21])
    elif mod == "M07": s.update(weight_top1=0.0, weight_topk=1.0)
    elif mod == "M08": s.update(weight_top1=0.4, weight_topk=0.6)
    elif mod == "M09": s.update(weight_top1=0.6, weight_topk=0.4)
    elif mod == "M10": s.update(k=2)
    elif mod == "M11": s.update(weighting="inv_vol")
    elif mod == "M12": s.update(weighting="mom_score")
    elif mod == "M13": s.update(k=4)
    elif mod == "M14": s.update(universe=ETFS+["TLT"])
    elif mod == "M15": s.update(universe=ETFS+["DBC"])
    elif mod == "M16": s.update(universe=ETFS+["TLT","DBC"])
    elif mod == "M17": s.update(universe=M17_UNI)
    elif mod == "M18": s.update(universe=M18_UNI)
    elif mod in ("M19","M20","M21","M22","M23"): s["gate"] = mod
    elif mod in ("M24","M25","M26","M27"): s["rebalance"] = mod
    return s

def run_combo(spec):
    daily = build_strategy(
        universe=spec["universe"],
        lookback_stable=spec["lookback_stable"], lookback_trans=spec["lookback_trans"],
        blended_stable=spec["blended_stable"], blended_trans=spec["blended_trans"],
        weight_top1=spec["weight_top1"], weight_topk=spec["weight_topk"],
        k=spec["k"], weighting=spec["weighting"],
    )
    if spec.get("gate") == "M19":
        ev_out = soft_ev_apply(daily)
        sm = pd.Series(ev_out).sort_index()
        return sm.groupby(sm.index.to_period("M")).tail(1)
    if spec.get("gate") == "M20":
        daily = apply_gate(daily, credit_gate_scale())
    if spec.get("gate") == "M21":
        daily = apply_gate(daily, vix_gate_scale())
    if spec.get("gate") == "M22":
        daily = apply_gate(daily, yc_gate_scale())
    if spec.get("gate") == "M23":
        daily = apply_gate(daily, signal_disagreement_scale(spec["universe"]))
    return to_monthly(daily[te_pos])

# Step-by-step combination
combo_steps = [("Step1_base", None)]
spec = combo_spec
for block in ["B1","B2","B3","B4","B5"]:
    m = best_per_block[block]
    if m is None:
        combo_steps.append((f"{block}_skip", None))
        continue
    new_spec = apply_mod_to_spec(m, spec)
    sm = run_combo(new_spec)
    st = stats(sm.values)
    prev_st = combo_steps[-1][2] if combo_steps[-1][1] else ctrl_st
    keep = st["sharpe"] > prev_st["sharpe"] - 0.005 and st["cagr"] > prev_st["cagr"] - 0.005
    combo_steps.append((f"{block}_+{m}", m, st, keep, new_spec))
    if keep:
        spec = new_spec
        print(f"  KEEP {m}: CAGR {st['cagr']*100:.2f}% Sharpe {st['sharpe']:.2f} MaxDD {st['max_dd']*100:.2f}%")
    else:
        print(f"  DROP {m}: CAGR {st['cagr']*100:.2f}% Sharpe {st['sharpe']:.2f} (worse than prior)")

# Final combo
final_sm = run_combo(spec)
final_st = stats(final_sm.values)
RESULTS["OPTIMIZED"] = {
    "description": "Final layered optimization (best-of-block, haircut-checked)",
    "spec": {k: (v if not isinstance(v, list) else list(v)) for k, v in spec.items()},
    "n_monthly": int(len(final_sm)),
    "stats": final_st,
    "monthly_returns": [{"date": str(d.date()), "fwd_ret": float(r)} for d, r in final_sm.items()],
}
(OUT_DIR / "OPTIMIZED.json").write_text(json.dumps(RESULTS["OPTIMIZED"], indent=2, default=str))

# ---------------------------------------------------------------------------
# OPTIMIZATION_REPORT.md
# ---------------------------------------------------------------------------
def fmt_pct(v):
    return "n/a" if v is None or v != v else f"{v*100:.1f}%"

lines = []
lines.append("# OPTIMIZATION REPORT — E-R1 Mods M01..M27\n")
lines.append(f"Walk-forward regime classifier accuracy: **{regime_acc:.3f}**\n")
lines.append("Haircut rule: improvement (after 50% reduction) must exceed +0.5pp CAGR or +0.03 Sharpe, with MaxDD not >2pp worse.\n")
lines.append("## Individual modification results\n")
lines.append("| Mod  | Description | CAGR | Sharpe | MaxDD | Δ CAGR | Δ Sharpe | Δ MaxDD | Pass haircut |")
lines.append("|---|---|---|---|---|---|---|---|---|")
mod_names = ["E-R1"] + [f"M{i:02d}" for i in range(1,28)]
for n in mod_names:
    s = RESULTS[n]["stats"]
    desc = RESULTS[n]["description"][:60]
    if n == "E-R1":
        lines.append(f"| {n} | {desc} | {fmt_pct(s['cagr'])} | {s['sharpe']:.2f} | {fmt_pct(s['max_dd'])} | -- | -- | -- | -- |")
    else:
        ok, dc, dsh, dmd = haircut_pass(n)
        lines.append(f"| {n} | {desc} | {fmt_pct(s['cagr'])} | {s['sharpe']:.2f} | {fmt_pct(s['max_dd'])} | {dc*100:+.2f}pp | {dsh:+.2f} | {dmd*100:+.2f}pp | {'PASS' if ok else 'fail'} |")

lines.append("\n## Best per block (haircut-passing)\n")
for b, m in best_per_block.items():
    if m:
        s = RESULTS[m]["stats"]
        lines.append(f"- **{b}**: {m} — CAGR {fmt_pct(s['cagr'])}, Sharpe {s['sharpe']:.2f}, MaxDD {fmt_pct(s['max_dd'])}")
    else:
        lines.append(f"- **{b}**: no modification passed haircut")

lines.append("\n## Incremental combination\n")
lines.append("| Step | Added | CAGR | Sharpe | MaxDD | Action |")
lines.append("|---|---|---|---|---|---|")
lines.append(f"| Step1 | E-R1 base | {fmt_pct(ctrl_st['cagr'])} | {ctrl_st['sharpe']:.2f} | {fmt_pct(ctrl_st['max_dd'])} | start |")
for entry in combo_steps[1:]:
    if len(entry) < 4:
        lines.append(f"| {entry[0]} | (none) | -- | -- | -- | skipped |")
        continue
    label, m, st, keep, _ = entry
    lines.append(f"| {label} | {m} | {fmt_pct(st['cagr'])} | {st['sharpe']:.2f} | {fmt_pct(st['max_dd'])} | {'KEEP' if keep else 'drop'} |")

lines.append(f"\n## Final optimized strategy\n")
lines.append(f"- CAGR: **{fmt_pct(final_st['cagr'])}**")
lines.append(f"- Sharpe: **{final_st['sharpe']:.2f}**")
lines.append(f"- MaxDD: **{fmt_pct(final_st['max_dd'])}**")
lines.append(f"- ΔCAGR vs E-R1: {(final_st['cagr']-ctrl_st['cagr'])*100:+.2f}pp")
lines.append(f"- ΔSharpe vs E-R1: {final_st['sharpe']-ctrl_st['sharpe']:+.2f}")

(ROOT / "results/OPTIMIZATION_REPORT.md").write_text("\n".join(lines), encoding="utf-8")
print("\nWrote results/OPTIMIZATION_REPORT.md")

# ---------------------------------------------------------------------------
# OPTIMIZED_STRATEGY.md
# ---------------------------------------------------------------------------
spec_lines = []
spec_lines.append("# OPTIMIZED STRATEGY SPEC\n")
spec_lines.append("Derived from incremental layering of best-of-block modifications that passed the haircut.\n")
spec_lines.append("## Final spec\n")
spec_lines.append(f"- Universe: `{spec['universe']}`")
spec_lines.append(f"- Lookback (stable regime): {spec['lookback_stable']}d" + (f" (blended {spec['blended_stable']})" if spec['blended_stable'] else ""))
spec_lines.append(f"- Lookback (transition regime): {spec['lookback_trans']}d" + (f" (blended {spec['blended_trans']})" if spec['blended_trans'] else ""))
spec_lines.append(f"- Sizing: {int(spec['weight_top1']*100)}% top-1 + {int(spec['weight_topk']*100)}% top-{spec['k']} ({spec['weighting']})")
spec_lines.append(f"- Trend gate: SMA200 −4% on top-1 leg")
spec_lines.append(f"- Regime classifier: HistGB on CORE features, 4-class growth/inflation, walk-forward")
spec_lines.append(f"- Macro/exposure gate: {spec['gate'] or 'none'}")
spec_lines.append(f"- Rebalancing variant: {spec['rebalance'] or 'monthly (last test day per month)'}")
spec_lines.append("")
spec_lines.append("## Performance\n")
spec_lines.append(f"- CAGR: **{fmt_pct(final_st['cagr'])}**")
spec_lines.append(f"- Sharpe: **{final_st['sharpe']:.2f}**")
spec_lines.append(f"- MaxDD: **{fmt_pct(final_st['max_dd'])}**")
spec_lines.append(f"- vs E-R1: ΔCAGR {(final_st['cagr']-ctrl_st['cagr'])*100:+.2f}pp, ΔSharpe {final_st['sharpe']-ctrl_st['sharpe']:+.2f}, ΔMaxDD {(final_st['max_dd']-ctrl_st['max_dd'])*100:+.2f}pp")

(ROOT / "results/OPTIMIZED_STRATEGY.md").write_text("\n".join(spec_lines), encoding="utf-8")
print("Wrote results/OPTIMIZED_STRATEGY.md")
print("\nDone.")
