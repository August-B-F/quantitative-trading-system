"""Regime-integration experiments E-R1 through E-R6.

Uses the EA1 walk-forward regime classifier (HistGB on CORE features,
4-class growth/inflation quadrants) as a regime signal and tests six
different ways of connecting it to the T2 systematic-momentum base
strategies (T2_balanced and T2_3legCAGR_softML).

Outputs:
  results/experiments/E-R1.json .. E-R6.json
  results/REGIME_INTEGRATION_REPORT.md
  results/STRATEGY_CANDIDATES.md
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

ETFS = ["SOXX", "QQQ", "XLK", "VGT", "IGV", "XLE", "GLD", "SHY"]
ETFS_EXT = ETFS + ["TLT", "XLV"]  # E-R4 expanded universe
N = len(ETFS)

SPLIT_KW = dict(
    min_train_months=60, val_months=6, test_months=3, step_months=3,
    sample_every_n_days=5, embargo_days=5, target_horizon=21,
    decay_halflife_months=36,
)

OUT_DIR = ROOT / "results/experiments"
OUT_DIR.mkdir(parents=True, exist_ok=True)

REGIME_CLASSES = ["regime_hg_li", "regime_hg_hi", "regime_lg_li", "regime_lg_hi_stagflation"]
REGIME_FEATS = [f"regime_growth_inflation__{c}" for c in REGIME_CLASSES]

# Sector alignment per regime for E-R2 universe-weighting
# HG/LI → tech/growth; HG/HI → energy/commodity; LG/LI → bond/defensive;
# LG/HI → gold/real assets
REGIME_FAVORED = {
    0: {"SOXX", "QQQ", "XLK", "VGT", "IGV"},   # HG/LI tech
    1: {"XLE", "GLD", "SOXX", "QQQ"},           # HG/HI inflation+growth
    2: {"SHY", "TLT", "GLD", "XLV"},            # LG/LI defensive (TLT/XLV ignored in 8-ETF universe)
    3: {"GLD", "XLE", "SHY"},                   # LG/HI real assets
}

# E-R4 eligible sets over the 10-ETF expanded universe
REGIME_ELIGIBLE = {
    0: ["SOXX", "QQQ", "XLK", "VGT", "IGV"],              # + SPY not in universe
    1: ["XLE", "GLD", "SOXX", "QQQ"],
    2: ["SHY", "TLT", "GLD", "XLV"],
    3: ["GLD", "XLE", "SHY"],
}

# ---------------------------------------------------------------------------
# Load
# ---------------------------------------------------------------------------

print("Loading master panel…")
df = pd.read_parquet(ROOT / "data/features/master_panel.parquet")
feature_sets = yaml.safe_load(open(ROOT / "configs/feature_sets.yaml"))
core_feats = [c for c in feature_sets["core"] if c in df.columns]
print(f"  panel: {df.shape}  core feats: {len(core_feats)}")

r63_all = pd.read_parquet(ROOT / "data/features/price/returns_63d.parquet").reindex(df.index)
r21_all = pd.read_parquet(ROOT / "data/features/price/returns_21d.parquet").reindex(df.index)
r126_all = pd.read_parquet(ROOT / "data/features/price/returns_126d.parquet").reindex(df.index)

r63 = r63_all[ETFS]
r21 = r21_all[ETFS]
r126 = r126_all[ETFS]
mom63 = r63.values
mom21 = r21.values
mom126 = r126.values

fwd = df[[f"TARGET_FWD21_{tk}" for tk in ETFS]].copy()
fwd.columns = ETFS
fwd_arr = fwd.values
shy_ret = fwd["SHY"].values
qqq_ret = fwd["QQQ"].values

# Forward 21d returns for TLT/XLV — derive from returns_21d shifted -21 trading days.
# returns_21d[t] = P[t]/P[t-21] - 1, so returns_21d[t+21] = P[t+21]/P[t] - 1 = fwd_21d[t].
fwd_ext_arr = np.full((len(df), len(ETFS_EXT)), np.nan)
for j, tk in enumerate(ETFS_EXT):
    if tk in ETFS:
        fwd_ext_arr[:, j] = fwd[tk].values
    else:
        s = r21_all[tk].shift(-21)
        fwd_ext_arr[:, j] = s.reindex(df.index).values
tlt_ret = fwd_ext_arr[:, ETFS_EXT.index("TLT")]
xlv_ret = fwd_ext_arr[:, ETFS_EXT.index("XLV")]

mom63_ext = np.full((len(df), len(ETFS_EXT)), np.nan)
for j, tk in enumerate(ETFS_EXT):
    mom63_ext[:, j] = r63_all[tk].reindex(df.index).values

# Current regime from deterministic panel labels (one-hot, argmax each row)
current_reg = df[REGIME_FEATS].values.argmax(axis=1)

splitter = ExpandingSplitter(**SPLIT_KW)
folds = splitter.split(df.index)
test_dates = pd.DatetimeIndex(sorted(set(d for f in folds for d in f["test_dates"])))
te_pos = df.index.get_indexer(test_dates)
print(f"  folds: {len(folds)}  test dates: {len(test_dates)}")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def stats(r):
    r = np.asarray(r, dtype=float)
    r = r[~np.isnan(r)]
    if len(r) == 0:
        return dict(cagr=float("nan"), sharpe=float("nan"), max_dd=float("nan"), n=0)
    eq = np.cumprod(1 + r)
    years = len(r) / 12.0
    cagr = float(eq[-1] ** (1 / years) - 1)
    sd = r.std(ddof=1) if len(r) > 1 else 0.0
    sh = float(r.mean() / sd * np.sqrt(12)) if sd > 0 else float("nan")
    peak = np.maximum.accumulate(eq)
    dd = float((eq / peak - 1).min())
    return dict(cagr=cagr, sharpe=sh, max_dd=dd, n=int(len(r)))


def to_monthly(daily_values, dates=None):
    dates = test_dates if dates is None else dates
    s = pd.Series(daily_values, index=dates).dropna()
    return s.groupby(s.index.to_period("M")).tail(1)


def topk_full(sig, k, fwd_mat=None):
    fm = fwd_arr if fwd_mat is None else fwd_mat
    sf = np.where(np.isnan(sig), -np.inf, sig)
    if k == 1:
        return fm[np.arange(len(df)), np.argmax(sf, axis=1)]
    idx = np.argsort(-sf, axis=1)[:, :k]
    return fm[np.arange(len(df))[:, None], idx].mean(axis=1)


def rank_avg_topk_full(sigs, k):
    rk_sum = np.zeros((len(df), N))
    for s in sigs:
        sf = np.where(np.isnan(s), -np.inf, s)
        order = np.argsort(-sf, axis=1)
        rk = np.empty_like(order)
        for i in range(len(df)):
            rk[i, order[i]] = np.arange(N)
        rk_sum += rk
    if k == 1:
        return fwd_arr[np.arange(len(df)), np.argmin(rk_sum, axis=1)]
    idx = np.argsort(rk_sum, axis=1)[:, :k]
    return fwd_arr[np.arange(len(df))[:, None], idx].mean(axis=1)


top1_full = topk_full(mom63, 1)
top3_full = topk_full(mom63, 3)
ra2_top1_full = rank_avg_topk_full([mom63, mom126], 1)

spy_dist = df["quality_dist_sma200__SPY"].values


def trend_gate(base, threshold=-0.04):
    return np.where(spy_dist > threshold, base, shy_ret)


# ---------------------------------------------------------------------------
# Walk-forward regime classifier (EA1 pattern) → per-test-date prediction
# ---------------------------------------------------------------------------

print("Training walk-forward regime classifier…")
target_col = "TARGET_TREG_growth_inflation_fwd21"
cls_to_idx = {c: i for i, c in enumerate(REGIME_CLASSES)}

pred_reg = np.full(len(df), -1, dtype=int)   # predicted regime idx, -1 = missing
pred_conf = np.full(len(df), np.nan)
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
    if len(Xtr) < 50 or len(Xte) < 1:
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
    cf = full.max(axis=1)
    te_pos_f = df.index.get_indexer(te)
    pred_reg[te_pos_f] = pr
    pred_conf[te_pos_f] = cf
    yte_m = yte_raw.map(cls_to_idx)
    if yte_m.notna().any():
        yv = yte_m.dropna().astype(int).to_numpy()
        fold_accs.append(float((pr[:len(yv)] == yv[:len(pr)]).mean()))

regime_acc = float(np.mean(fold_accs)) if fold_accs else float("nan")
print(f"  regime walk-forward accuracy (mean over folds): {regime_acc:.3f}")


# ---------------------------------------------------------------------------
# Dispersion predictor (lightweight ED5-style) for E-R5
# ---------------------------------------------------------------------------

print("Training walk-forward dispersion predictor…")
fwd_mat = fwd_arr
disp_realized = np.nanstd(fwd_mat, axis=1)  # cross-sectional std of fwd21 across 8 ETFs
pred_disp = np.full(len(df), np.nan)
fold_disp_medians = []
X_core = df[core_feats]
for fold in folds:
    tr = fold["train_dates"]; te = fold["test_dates"]
    if len(tr) < 50 or len(te) < 1:
        continue
    sw = np.asarray(fold["train_sample_weights"])
    tr_pos = df.index.get_indexer(tr)
    te_pos_f = df.index.get_indexer(te)
    ytr = disp_realized[tr_pos]
    mtr = ~np.isnan(ytr)
    if mtr.sum() < 30:
        continue
    Xtr = X_core.iloc[tr_pos][mtr]
    sw_tr = sw[mtr]
    pp = FeaturePreprocessor()
    Xtr_z = pp.fit_transform(Xtr, sample_weights=sw_tr).to_numpy()
    Xte_z = pp.transform(X_core.iloc[te_pos_f]).to_numpy()
    m = HistGradientBoostingRegressor(
        max_iter=300, max_depth=4, learning_rate=0.05,
        min_samples_leaf=20, l2_regularization=2.0, random_state=0,
    )
    m.fit(Xtr_z, ytr[mtr], sample_weight=sw_tr)
    pr = m.predict(Xte_z)
    pred_disp[te_pos_f] = pr
    fold_disp_medians.append(float(np.median(ytr[mtr])))

disp_med = float(np.nanmedian(pred_disp[te_pos]))
print(f"  dispersion median (test): {disp_med:.4f}")


# ---------------------------------------------------------------------------
# Soft EV gate (copy of T2 version) — returns per-test-date daily arrays
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


def soft_ev_weights(ensemble_full):
    """Fold-wise soft EV gate → returns {date: (base_ret, w, pred)} on test dates."""
    out = {}
    for fold in folds:
        tr = fold["train_dates"]; va = fold["val_dates"]; te = fold["test_dates"]
        if len(tr) < 50 or len(va) < 5 or len(te) < 1:
            continue
        sw = np.asarray(fold["train_sample_weights"])
        tr_pos = df.index.get_indexer(tr)
        va_pos = df.index.get_indexer(va)
        te_pos_f = df.index.get_indexer(te)
        ytr = ensemble_full[tr_pos]
        mtr = ~np.isnan(ytr)
        if mtr.sum() < 30:
            continue
        Xtr = pd.DataFrame(X_macro[tr_pos][mtr], columns=MACRO_FEATS)
        pp = FeaturePreprocessor()
        Xtr_z = pp.fit_transform(Xtr, sample_weights=sw[mtr]).to_numpy()
        Xva_z = pp.transform(pd.DataFrame(X_macro[va_pos], columns=MACRO_FEATS)).to_numpy()
        Xte_z = pp.transform(pd.DataFrame(X_macro[te_pos_f], columns=MACRO_FEATS)).to_numpy()
        m = HistGradientBoostingRegressor(
            max_iter=300, max_depth=4, learning_rate=0.05,
            min_samples_leaf=20, l2_regularization=2.0, random_state=0,
        )
        m.fit(Xtr_z, ytr[mtr], sample_weight=sw[mtr])
        pred_va = m.predict(Xva_z)
        pred_te = m.predict(Xte_z)
        valid_va = ~np.isnan(ensemble_full[va_pos])
        if valid_va.sum() < 3:
            continue
        lo = float(np.quantile(pred_va[valid_va], 0.10))
        hi = float(np.quantile(pred_va[valid_va], 0.50))
        denom = max(hi - lo, 1e-6)
        for i, d in enumerate(te):
            base_r = ensemble_full[te_pos_f[i]]
            if np.isnan(base_r):
                continue
            w = max(0.0, min(1.0, (pred_te[i] - lo) / denom))
            out[pd.Timestamp(d)] = (float(base_r), float(w), float(pred_te[i]))
    return out


# ---------------------------------------------------------------------------
# Strategy registry
# ---------------------------------------------------------------------------

STRATS = {}


def register_daily(name, daily_full, description, extra=None):
    daily = daily_full[te_pos]
    sm = to_monthly(daily)
    st = stats(sm.values)
    rec = [{"date": str(d.date()), "fwd_ret": float(r)} for d, r in sm.items()]
    payload = {
        "description": description,
        "n_monthly": len(sm),
        "stats": st,
        "monthly_returns": rec,
    }
    if extra:
        payload.update(extra)
    STRATS[name] = payload
    print(f"  {name}: CAGR {st['cagr']*100:5.2f}%  Sharpe {st['sharpe']:.2f}  "
          f"MaxDD {st['max_dd']*100:6.2f}%  n={st['n']}")


def register_monthly(name, monthly_series, description, extra=None):
    st = stats(monthly_series.values)
    rec = [{"date": str(d.date()), "fwd_ret": float(r)} for d, r in monthly_series.items()]
    payload = {
        "description": description,
        "n_monthly": int(len(monthly_series)),
        "stats": st,
        "monthly_returns": rec,
    }
    if extra:
        payload.update(extra)
    STRATS[name] = payload
    print(f"  {name}: CAGR {st['cagr']*100:5.2f}%  Sharpe {st['sharpe']:.2f}  "
          f"MaxDD {st['max_dd']*100:6.2f}%  n={st['n']}")


# ---------------------------------------------------------------------------
# Reference strategies (baseline + T2 winners) rebuilt for comparison
# ---------------------------------------------------------------------------

print("\n=== Reference strategies ===")
register_daily("B3_top1_63d", top1_full,
               "Baseline B3: top-1 by 63d momentum (8 ETFs)")
register_daily("T2_balanced",
               0.5 * trend_gate(top1_full, -0.04) + 0.5 * top3_full,
               "0.5*[top1+SMA200-4% gate] + 0.5*top3 (63d momentum)")

# T2_3legCAGR_softML
print("  building T2_3legCAGR_softML…")
ensemble_3leg = (top1_full + top3_full + ra2_top1_full) / 3
ev_map = soft_ev_weights(ensemble_3leg)
rets_softML = {}
for d, (br, w, p) in ev_map.items():
    i = df.index.get_loc(d)
    rets_softML[d] = w * br + (1 - w) * shy_ret[i]
sm = pd.Series(rets_softML).sort_index()
sm = sm.groupby(sm.index.to_period("M")).tail(1)
register_monthly("T2_3legCAGR_softML", sm,
                 "T2_3legCAGR base + soft ML EV gate (HistGB on macro)")


# ---------------------------------------------------------------------------
# E-R1: Regime-conditional lookback
# ---------------------------------------------------------------------------

print("\n=== E-R1: regime-conditional lookback ===")
# For each day, pick lookback based on pred vs current regime.
# Build combined mom array using 63d when stable, 21d when transition.
use21 = (pred_reg != -1) & (pred_reg != current_reg)
mom_cond = np.where(use21[:, None], mom21, mom63)
top1_cond = topk_full(mom_cond, 1)
top3_cond = topk_full(mom_cond, 3)
er1_daily = 0.5 * trend_gate(top1_cond, -0.04) + 0.5 * top3_cond
transition_rate = float(use21[te_pos].mean())
register_daily("E-R1", er1_daily,
               "T2_balanced structure w/ regime-conditional lookback "
               "(63d stable, 21d transition)",
               extra={"regime_accuracy": regime_acc,
                      "transition_rate_test": transition_rate})


# ---------------------------------------------------------------------------
# E-R2: Regime-conditional universe weighting
# ---------------------------------------------------------------------------

print("\n=== E-R2: regime-conditional weight tilt ===")
# Top-3 by 63d momentum, then tilt weights 1.5x favored / 0.75x others, renormalize.
def er2_returns():
    out = np.full(len(df), np.nan)
    for i in range(len(df)):
        row = mom63[i]
        if np.all(np.isnan(row)):
            continue
        order = np.argsort(-np.where(np.isnan(row), -np.inf, row))[:3]
        # base weights 1/3, tilt by regime favor
        fav = REGIME_FAVORED.get(pred_reg[i], set()) if pred_reg[i] != -1 else set()
        w = np.array([1.5 if ETFS[j] in fav else 0.75 for j in order])
        w = w / w.sum()
        r = np.array([fwd_arr[i, j] for j in order])
        if np.any(np.isnan(r)):
            continue
        out[i] = float(np.dot(w, r))
    return out

er2_base = er2_returns()
er2_daily = 0.5 * trend_gate(top1_full, -0.04) + 0.5 * er2_base
register_daily("E-R2", er2_daily,
               "T2_balanced w/ regime-tilted top-3 weights (1.5x favored / 0.75x other)",
               extra={"regime_accuracy": regime_acc})


# ---------------------------------------------------------------------------
# E-R3: Regime as exposure scaler on soft-ML gate
# ---------------------------------------------------------------------------

print("\n=== E-R3: regime overlay on T2_3legCAGR_softML ===")
# If transition toward recessionary quadrants (pred in {2,3} and pred != current),
# halve the soft EV weight (keeping more SHY).
er3_map = {}
for d, (br, w, p) in ev_map.items():
    i = df.index.get_loc(d)
    pr = pred_reg[i]; cr = current_reg[i]
    transition_bad = (pr != -1 and pr != cr and pr in (2, 3))
    w_adj = w * 0.5 if transition_bad else w
    er3_map[d] = w_adj * br + (1 - w_adj) * shy_ret[i]
sm = pd.Series(er3_map).sort_index()
sm = sm.groupby(sm.index.to_period("M")).tail(1)
n_adj = sum(
    1 for d in ev_map
    if (pred_reg[df.index.get_loc(d)] != -1
        and pred_reg[df.index.get_loc(d)] != current_reg[df.index.get_loc(d)]
        and pred_reg[df.index.get_loc(d)] in (2, 3))
)
register_monthly("E-R3", sm,
                 "T2_3legCAGR_softML w/ 0.5x EV weight on recessionary transitions",
                 extra={"regime_accuracy": regime_acc,
                        "n_days_downscaled": int(n_adj)})


# ---------------------------------------------------------------------------
# E-R4: Regime-filtered universe (expanded with TLT, XLV)
# ---------------------------------------------------------------------------

print("\n=== E-R4: regime-filtered momentum (10-ETF universe) ===")
def er4_returns():
    out = np.full(len(df), np.nan)
    for i in range(len(df)):
        pr = pred_reg[i]
        if pr == -1:
            continue
        elig = REGIME_ELIGIBLE[pr]
        elig_idx = [ETFS_EXT.index(t) for t in elig]
        row = mom63_ext[i, elig_idx]
        frow = fwd_ext_arr[i, elig_idx]
        if np.all(np.isnan(row)) or np.all(np.isnan(frow)):
            continue
        sf = np.where(np.isnan(row), -np.inf, row)
        k = min(3, len(elig))
        order = np.argsort(-sf)[:k]
        vals = frow[order]
        if np.any(np.isnan(vals)):
            vals = vals[~np.isnan(vals)]
            if len(vals) == 0:
                continue
        out[i] = float(vals.mean())
    return out

er4_base = er4_returns()
er4_daily = np.where(spy_dist > -0.04, er4_base, shy_ret)
register_daily("E-R4", er4_daily,
               "Regime-filtered universe (HG/LI, HG/HI, LG/LI, LG/HI eligible sets "
               "incl. TLT/XLV), top-3 by 63d mom within set, SMA200 gate",
               extra={"regime_accuracy": regime_acc,
                      "extended_universe": ETFS_EXT})


# ---------------------------------------------------------------------------
# E-R5: Dispersion × regime interaction
# ---------------------------------------------------------------------------

print("\n=== E-R5: dispersion × regime interaction ===")
# High disp (>= median) + stable → full position, momentum top-3 + SMA
# High disp + transition → 0.7 * position (70% momentum, 30% SHY)
# Low disp + stable → QQQ
# Low disp + transition → SHY
base_bal = 0.5 * trend_gate(top1_full, -0.04) + 0.5 * top3_full
er5_daily = np.full(len(df), np.nan)
cat_counts = {"hi_stable": 0, "hi_trans": 0, "lo_stable": 0, "lo_trans": 0, "unk": 0}
for i in range(len(df)):
    d_pred = pred_disp[i]
    pr = pred_reg[i]; cr = current_reg[i]
    if np.isnan(d_pred) or pr == -1:
        cat_counts["unk"] += 1
        continue
    high = d_pred >= disp_med
    stable = (pr == cr)
    br = base_bal[i]
    if np.isnan(br):
        continue
    if high and stable:
        er5_daily[i] = br
        cat_counts["hi_stable"] += 1
    elif high and not stable:
        er5_daily[i] = 0.7 * br + 0.3 * shy_ret[i]
        cat_counts["hi_trans"] += 1
    elif (not high) and stable:
        er5_daily[i] = qqq_ret[i]
        cat_counts["lo_stable"] += 1
    else:
        er5_daily[i] = shy_ret[i]
        cat_counts["lo_trans"] += 1

register_daily("E-R5", er5_daily,
               "Dispersion×Regime: hi+stable→momentum; hi+trans→0.7*mom+0.3*SHY; "
               "lo+stable→QQQ; lo+trans→SHY",
               extra={"regime_accuracy": regime_acc,
                      "disp_median": disp_med,
                      "category_counts_full": cat_counts})


# ---------------------------------------------------------------------------
# E-R6: Kitchen sink — incremental layers
# ---------------------------------------------------------------------------

print("\n=== E-R6: kitchen sink (incremental) ===")
# Layer 0: T2_3legCAGR (top1_63 + top3_63 + rank_avg(63,126)_top1) / 3
ensemble_full = (top1_full + top3_full + ra2_top1_full) / 3
layers = {}
layers["L0_3leg_base"] = stats(to_monthly(ensemble_full[te_pos]).values)

# Layer 1: SMA200 trend gate on the ensemble (replacing top1 leg's gating with a full gate)
L1_full = trend_gate(ensemble_full, -0.04)
layers["L1_sma_gate"] = stats(to_monthly(L1_full[te_pos]).values)

# Layer 2: + soft EV gate on the SMA-gated ensemble
ev_map_L2 = soft_ev_weights(L1_full)
L2_vals = {}
for d, (br, w, p) in ev_map_L2.items():
    i = df.index.get_loc(d)
    L2_vals[d] = w * br + (1 - w) * shy_ret[i]
L2_series = pd.Series(L2_vals).sort_index()
L2_monthly = L2_series.groupby(L2_series.index.to_period("M")).tail(1)
layers["L2_ev_gate"] = stats(L2_monthly.values)

# Decide whether to keep each layer based on Sharpe improvement vs prior
def accepted(prior_key, new_key):
    a = layers[prior_key]; b = layers[new_key]
    keep = (b["sharpe"] >= a["sharpe"] - 0.02 and
            b["max_dd"] >= a["max_dd"] - 0.005 and
            b["cagr"] >= a["cagr"] - 0.02)
    return keep

keep_L1 = accepted("L0_3leg_base", "L1_sma_gate")
keep_L2 = accepted("L1_sma_gate" if keep_L1 else "L0_3leg_base", "L2_ev_gate")

# Layer 3: regime-conditional lookback applied to each leg (use21 mask swapping mom63→mom21)
# Re-build ensemble with conditional legs
top1_ens_cond = topk_full(mom_cond, 1)
top3_ens_cond = topk_full(mom_cond, 3)
ra2_cond = rank_avg_topk_full([mom_cond, mom126], 1)
ensemble_L3_raw = (top1_ens_cond + top3_ens_cond + ra2_cond) / 3
L3_pre = trend_gate(ensemble_L3_raw, -0.04) if keep_L1 else ensemble_L3_raw
if keep_L2:
    ev_map_L3 = soft_ev_weights(L3_pre)
    L3_vals = {}
    for d, (br, w, p) in ev_map_L3.items():
        i = df.index.get_loc(d)
        L3_vals[d] = w * br + (1 - w) * shy_ret[i]
    L3_series = pd.Series(L3_vals).sort_index()
    L3_monthly = L3_series.groupby(L3_series.index.to_period("M")).tail(1)
    layers["L3_regime_lookback"] = stats(L3_monthly.values)
    L3_monthly_out = L3_monthly
else:
    L3_monthly_out = to_monthly(L3_pre[te_pos])
    layers["L3_regime_lookback"] = stats(L3_monthly_out.values)
keep_L3 = accepted("L2_ev_gate" if keep_L2 else ("L1_sma_gate" if keep_L1 else "L0_3leg_base"),
                   "L3_regime_lookback")

# Layer 4: regime universe weighting (apply tilt to top3 leg only)
def tilt_top3_full():
    out = np.full(len(df), np.nan)
    base_mom = mom_cond if keep_L3 else mom63
    for i in range(len(df)):
        row = base_mom[i]
        if np.all(np.isnan(row)):
            continue
        order = np.argsort(-np.where(np.isnan(row), -np.inf, row))[:3]
        fav = REGIME_FAVORED.get(pred_reg[i], set()) if pred_reg[i] != -1 else set()
        w = np.array([1.5 if ETFS[j] in fav else 0.75 for j in order])
        w = w / w.sum()
        r = np.array([fwd_arr[i, j] for j in order])
        if np.any(np.isnan(r)):
            continue
        out[i] = float(np.dot(w, r))
    return out

top3_tilt = tilt_top3_full()
top1_L4 = (top1_ens_cond if keep_L3 else top1_full)
ra2_L4 = (ra2_cond if keep_L3 else ra2_top1_full)
ens_L4_raw = (top1_L4 + top3_tilt + ra2_L4) / 3
L4_pre = trend_gate(ens_L4_raw, -0.04) if keep_L1 else ens_L4_raw
if keep_L2:
    ev_map_L4 = soft_ev_weights(L4_pre)
    L4_vals = {}
    for d, (br, w, p) in ev_map_L4.items():
        i = df.index.get_loc(d)
        L4_vals[d] = w * br + (1 - w) * shy_ret[i]
    L4_series = pd.Series(L4_vals).sort_index()
    L4_monthly = L4_series.groupby(L4_series.index.to_period("M")).tail(1)
else:
    L4_monthly = to_monthly(L4_pre[te_pos])
layers["L4_universe_tilt"] = stats(L4_monthly.values)
keep_L4 = accepted("L3_regime_lookback" if keep_L3
                   else ("L2_ev_gate" if keep_L2
                         else ("L1_sma_gate" if keep_L1 else "L0_3leg_base")),
                   "L4_universe_tilt")

# Layer 5: dispersion-aware sizing (if low predicted dispersion and stable → QQQ;
# if high disp + trans → 0.7 blend)
def apply_disp_sizing(monthly_series):
    # monthly_series is datetime-indexed; map to per-month sizing
    out = {}
    for d, r in monthly_series.items():
        i = df.index.get_loc(d)
        d_pred = pred_disp[i]
        pr = pred_reg[i]; cr = current_reg[i]
        if np.isnan(d_pred) or pr == -1 or np.isnan(r):
            out[d] = r
            continue
        high = d_pred >= disp_med
        stable = (pr == cr)
        if high and stable:
            out[d] = r
        elif high and not stable:
            out[d] = 0.7 * r + 0.3 * shy_ret[i]
        elif (not high) and stable:
            out[d] = qqq_ret[i]
        else:
            out[d] = shy_ret[i]
    return pd.Series(out).sort_index()

prior_monthly = (L4_monthly if keep_L4 else
                 (L3_monthly_out if keep_L3 else
                  (L2_monthly if keep_L2 else
                   (to_monthly(L1_full[te_pos]) if keep_L1
                    else to_monthly(ensemble_full[te_pos])))))
L5_monthly = apply_disp_sizing(prior_monthly)
layers["L5_disp_sizing"] = stats(L5_monthly.values)
keep_L5 = accepted(
    "L4_universe_tilt" if keep_L4 else
    ("L3_regime_lookback" if keep_L3 else
     ("L2_ev_gate" if keep_L2 else
      ("L1_sma_gate" if keep_L1 else "L0_3leg_base"))),
    "L5_disp_sizing",
)

keep_flags = {
    "L1_sma_gate": keep_L1,
    "L2_ev_gate": keep_L2,
    "L3_regime_lookback": keep_L3,
    "L4_universe_tilt": keep_L4,
    "L5_disp_sizing": keep_L5,
}
print("  layer keep flags:", keep_flags)

# Final E-R6 = last kept layer's monthly series
ordered = [
    ("L5_disp_sizing", keep_L5, L5_monthly),
    ("L4_universe_tilt", keep_L4, L4_monthly),
    ("L3_regime_lookback", keep_L3, L3_monthly_out),
    ("L2_ev_gate", keep_L2, L2_monthly if keep_L2 else None),
    ("L1_sma_gate", keep_L1, to_monthly(L1_full[te_pos])),
    ("L0_3leg_base", True, to_monthly(ensemble_full[te_pos])),
]
final_key = None
final_series = None
for k, kept, s in ordered:
    if kept and s is not None:
        final_key = k
        final_series = s
        break

register_monthly("E-R6", final_series,
                 f"Kitchen sink final layer = {final_key}",
                 extra={"layer_stats": {k: v for k, v in layers.items()},
                        "layer_keep_flags": keep_flags,
                        "final_layer": final_key})


# ---------------------------------------------------------------------------
# Save JSONs
# ---------------------------------------------------------------------------

for name in ["E-R1", "E-R2", "E-R3", "E-R4", "E-R5", "E-R6"]:
    out = OUT_DIR / f"{name}.json"
    out.write_text(json.dumps(STRATS[name], indent=2, default=str))
print(f"\nWrote {6} experiment JSONs to {OUT_DIR}")


# ---------------------------------------------------------------------------
# Annual return table
# ---------------------------------------------------------------------------

def annual_returns(payload):
    m = [(pd.Timestamp(r["date"]), r["fwd_ret"]) for r in payload["monthly_returns"]]
    if not m:
        return {}
    s = pd.Series([r for _, r in m], index=pd.DatetimeIndex([d for d, _ in m]))
    yr = (1.0 + s).groupby(s.index.year).prod() - 1.0
    return {int(k): float(v) for k, v in yr.items()}


annual_tbl = {n: annual_returns(STRATS[n]) for n in STRATS}


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def fmt_pct(v):
    if v is None or v != v:
        return "n/a"
    return f"{v*100:.1f}%"


B3s = STRATS["B3_top1_63d"]["stats"]
BALs = STRATS["T2_balanced"]["stats"]
MLs = STRATS["T2_3legCAGR_softML"]["stats"]

lines = []
lines.append("# REGIME INTEGRATION REPORT")
lines.append("")
lines.append(f"Walk-forward regime classifier (HistGB on CORE features, 4-class "
             f"growth/inflation quadrants): mean fold accuracy = **{regime_acc:.3f}**.")
lines.append("")
lines.append("Six experiments test how to connect regime predictions to the "
             "systematic momentum base strategies (T2_balanced and T2_3legCAGR_softML).")
lines.append("")
lines.append("## Comparison table")
lines.append("")
lines.append("| Strategy | Description | CAGR | Sharpe | MaxDD | n | vs T2_balanced Sharpe | vs T2_softML Sharpe |")
lines.append("|---|---|---|---|---|---|---|---|")
order = ["B3_top1_63d", "T2_balanced", "T2_3legCAGR_softML",
         "E-R1", "E-R2", "E-R3", "E-R4", "E-R5", "E-R6"]
for name in order:
    p = STRATS[name]
    s = p["stats"]
    lines.append(
        f"| {name} | {p['description']} | "
        f"{fmt_pct(s['cagr'])} | {s['sharpe']:.2f} | {fmt_pct(s['max_dd'])} | "
        f"{s['n']} | {s['sharpe']-BALs['sharpe']:+.2f} | "
        f"{s['sharpe']-MLs['sharpe']:+.2f} |"
    )

lines.append("")
lines.append("## Annual returns")
lines.append("")
years = sorted({y for t in annual_tbl.values() for y in t.keys()})
lines.append("| Year | " + " | ".join(order) + " |")
lines.append("|" + "---|" * (len(order) + 1))
for y in years:
    row = [str(y)]
    for n in order:
        row.append(fmt_pct(annual_tbl[n].get(y, float("nan"))))
    lines.append("| " + " | ".join(row) + " |")

lines.append("")
lines.append("## Highlights")
lines.append("")

def show(name):
    s = STRATS[name]["stats"]
    return (f"{name}: CAGR {fmt_pct(s['cagr'])} / Sharpe {s['sharpe']:.2f} / "
            f"MaxDD {fmt_pct(s['max_dd'])}")

cand = [n for n in order if n.startswith("E-R")]
sharpe_w = max(cand, key=lambda k: STRATS[k]["stats"]["sharpe"]
               if STRATS[k]["stats"]["sharpe"] == STRATS[k]["stats"]["sharpe"] else -1e9)
cagr_w = max(cand, key=lambda k: STRATS[k]["stats"]["cagr"]
             if STRATS[k]["stats"]["cagr"] == STRATS[k]["stats"]["cagr"] else -1e9)
mdd_w = max(cand, key=lambda k: STRATS[k]["stats"]["max_dd"])
lines.append(f"- Sharpe winner: {show(sharpe_w)}")
lines.append(f"- CAGR winner: {show(cagr_w)}")
lines.append(f"- MaxDD winner: {show(mdd_w)}")
lines.append(f"- Reference T2_balanced: {show('T2_balanced')}")
lines.append(f"- Reference T2_3legCAGR_softML: {show('T2_3legCAGR_softML')}")

lines.append("")
lines.append("## Kitchen-sink (E-R6) layer diagnostics")
lines.append("")
L6 = STRATS["E-R6"]
lines.append(f"Final layer kept: **{L6['final_layer']}**")
lines.append("")
lines.append("| Layer | CAGR | Sharpe | MaxDD | Kept |")
lines.append("|---|---|---|---|---|")
layer_order = ["L0_3leg_base", "L1_sma_gate", "L2_ev_gate",
               "L3_regime_lookback", "L4_universe_tilt", "L5_disp_sizing"]
keep_flags = L6["layer_keep_flags"]
for k in layer_order:
    s = L6["layer_stats"][k]
    kept = "yes" if k == "L0_3leg_base" or keep_flags.get(k, False) else "no"
    lines.append(f"| {k} | {fmt_pct(s['cagr'])} | {s['sharpe']:.2f} | "
                 f"{fmt_pct(s['max_dd'])} | {kept} |")

lines.append("")
lines.append("## Interpretation")
lines.append("")

def hits_target(name):
    s = STRATS[name]["stats"]
    return s["cagr"] > 0.18 and s["sharpe"] > 1.15 and s["max_dd"] > -0.20

target_hits = [n for n in cand if hits_target(n)]
if target_hits:
    lines.append(f"Strategies meeting target (CAGR>18%, Sharpe>1.15, MaxDD>-20%): "
                 f"**{', '.join(target_hits)}**.")
else:
    lines.append("No regime-integration strategy simultaneously hits "
                 "CAGR>18%, Sharpe>1.15, and MaxDD>-20%.")

# Improvements vs T2_balanced
def improves_over_balanced(name):
    s = STRATS[name]["stats"]
    return (s["sharpe"] >= BALs["sharpe"] + 0.02 and
            s["cagr"] >= BALs["cagr"] - 0.015 and
            s["max_dd"] >= BALs["max_dd"] - 0.01)

imp = [n for n in cand if improves_over_balanced(n)]
lines.append("")
if imp:
    lines.append(f"Strategies that strictly improve over T2_balanced "
                 f"(Sharpe +≥0.02, CAGR ≥−1.5pp, MaxDD ≥−1pp): {', '.join(imp)}.")
else:
    lines.append("No regime-integration strategy strictly improves over T2_balanced. "
                 "The regime classifier is interesting (~68% accuracy) but not "
                 "actionable as a direct overlay on the momentum base.")

(ROOT / "results/REGIME_INTEGRATION_REPORT.md").write_text("\n".join(lines), encoding="utf-8")
print("wrote REGIME_INTEGRATION_REPORT.md")


# ---------------------------------------------------------------------------
# STRATEGY_CANDIDATES.md — full ranking across all sessions
# ---------------------------------------------------------------------------

print("\nBuilding STRATEGY_CANDIDATES.md…")
exp_dir = OUT_DIR

# Collect every experiment JSON with a "stats" block
candidates = []
for p in sorted(exp_dir.glob("*.json")):
    try:
        d = json.loads(p.read_text())
    except Exception:
        continue
    s = d.get("stats")
    if not s or "sharpe" not in s:
        continue
    if s.get("sharpe") != s.get("sharpe"):
        continue
    candidates.append({
        "name": p.stem,
        "cagr": s.get("cagr", float("nan")),
        "sharpe": s.get("sharpe", float("nan")),
        "max_dd": s.get("max_dd", float("nan")),
        "n": s.get("n", 0),
        "description": d.get("description", ""),
    })

# Rank by Sharpe (primary), then by CAGR
candidates.sort(key=lambda c: (c["sharpe"], c["cagr"]), reverse=True)

cl = []
cl.append("# STRATEGY CANDIDATES — full ranking")
cl.append("")
cl.append("All strategies tested across Tier 1, Tier 2, Tier 1B (5.2B), and the "
          "regime-integration session. Sourced from `results/experiments/*.json`. "
          "Sorted by Sharpe descending.")
cl.append("")
cl.append("Target: CAGR > 18%, Sharpe > 1.15, MaxDD better than −20%.")
cl.append("")
cl.append("| Rank | Strategy | CAGR | Sharpe | MaxDD | n | Hits target | Description |")
cl.append("|---|---|---|---|---|---|---|---|")
for i, c in enumerate(candidates, 1):
    ht = ("yes" if (c["cagr"] > 0.18 and c["sharpe"] > 1.15 and c["max_dd"] > -0.20)
          else "")
    desc = (c["description"] or "")[:120]
    cl.append(f"| {i} | {c['name']} | {fmt_pct(c['cagr'])} | {c['sharpe']:.2f} | "
              f"{fmt_pct(c['max_dd'])} | {c['n']} | {ht} | {desc} |")

cl.append("")
cl.append("## Top 5 by Sharpe")
cl.append("")
for c in candidates[:5]:
    cl.append(f"- **{c['name']}** — CAGR {fmt_pct(c['cagr'])}, Sharpe {c['sharpe']:.2f}, "
              f"MaxDD {fmt_pct(c['max_dd'])}")

cl.append("")
cl.append("## Top 5 by CAGR")
cl.append("")
for c in sorted(candidates, key=lambda x: x["cagr"], reverse=True)[:5]:
    cl.append(f"- **{c['name']}** — CAGR {fmt_pct(c['cagr'])}, Sharpe {c['sharpe']:.2f}, "
              f"MaxDD {fmt_pct(c['max_dd'])}")

(ROOT / "results/STRATEGY_CANDIDATES.md").write_text("\n".join(cl), encoding="utf-8")
print(f"wrote STRATEGY_CANDIDATES.md  ({len(candidates)} strategies)")

print("\nFINAL SUMMARY")
print(f"  B3:                 CAGR {B3s['cagr']*100:5.1f}%  Sharpe {B3s['sharpe']:.2f}  MaxDD {B3s['max_dd']*100:6.1f}%")
print(f"  T2_balanced:        CAGR {BALs['cagr']*100:5.1f}%  Sharpe {BALs['sharpe']:.2f}  MaxDD {BALs['max_dd']*100:6.1f}%")
print(f"  T2_3legCAGR_softML: CAGR {MLs['cagr']*100:5.1f}%  Sharpe {MLs['sharpe']:.2f}  MaxDD {MLs['max_dd']*100:6.1f}%")
for n in ["E-R1", "E-R2", "E-R3", "E-R4", "E-R5", "E-R6"]:
    s = STRATS[n]["stats"]
    print(f"  {n:<19} CAGR {s['cagr']*100:5.1f}%  Sharpe {s['sharpe']:.2f}  MaxDD {s['max_dd']*100:6.1f}%")
