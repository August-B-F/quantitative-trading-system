"""ML overlay on the winning ensemble: train a regression model to predict
short-horizon return of the ensemble itself, use it to scale exposure.
"""
import sys
import numpy as np
import pandas as pd
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from model.walk_forward import ExpandingSplitter
from model.preprocessing import FeaturePreprocessor
from sklearn.ensemble import HistGradientBoostingRegressor, HistGradientBoostingClassifier
from sklearn.linear_model import Ridge, LogisticRegression

df = pd.read_parquet(ROOT / "data/features/master_panel.parquet")
r63 = pd.read_parquet(ROOT / "data/features/price/returns_63d.parquet")
r126 = pd.read_parquet(ROOT / "data/features/price/returns_126d.parquet")
r42 = pd.read_parquet(ROOT / "data/features/price/returns_42d.parquet")

ETFS = ["SOXX", "QQQ", "XLK", "VGT", "IGV", "XLE", "GLD", "SHY"]
mom = r63[ETFS].reindex(df.index).values
mom126 = r126[ETFS].reindex(df.index).values
mom42 = r42[ETFS].reindex(df.index).values
fwd = df[[f"TARGET_FWD21_{tk}" for tk in ETFS]].copy(); fwd.columns = ETFS
fwd_arr = fwd.values
shy_ret = fwd["SHY"].values

splitter = ExpandingSplitter(min_train_months=60, val_months=6, test_months=3,
                             step_months=3, sample_every_n_days=5, embargo_days=5,
                             target_horizon=21, decay_halflife_months=36)
folds = splitter.split(df.index)

# Build the ensemble base on the FULL panel (all dates), then extract test slice per fold
def topk_full(sig, k):
    sf = np.where(np.isnan(sig), -np.inf, sig)
    if k == 1:
        return fwd_arr[np.arange(len(df)), np.argmax(sf, axis=1)]
    idx = np.argsort(-sf, axis=1)[:, :k]
    return fwd_arr[np.arange(len(df))[:, None], idx].mean(axis=1)


def rank_avg_topk_full(sigs, k):
    rk_sum = np.zeros((len(df), len(ETFS)))
    for s in sigs:
        sf = np.where(np.isnan(s), -np.inf, s)
        order = np.argsort(-sf, axis=1)
        rk = np.empty_like(order)
        for i in range(len(df)):
            rk[i, order[i]] = np.arange(len(ETFS))
        rk_sum += rk
    if k == 1:
        return fwd_arr[np.arange(len(df)), np.argmin(rk_sum, axis=1)]
    idx = np.argsort(rk_sum, axis=1)[:, :k]
    return fwd_arr[np.arange(len(df))[:, None], idx].mean(axis=1)


top1_full = topk_full(mom, 1)
top3_full = topk_full(mom, 3)
ra2_top1_full = rank_avg_topk_full([mom, mom126], 1)
ra3_top3_full = rank_avg_topk_full([mom, mom126, mom42], 3)

# Trend gate
spy_dist = df["quality_dist_sma200__SPY"].values
def trend_gate_full(base, threshold=-0.04):
    return np.where(spy_dist > threshold, base, shy_ret)

# Define the best ensembles
ensembles = {
    "B3_top1": top1_full,
    "TIER2_balanced": 0.5 * trend_gate_full(top1_full, -0.04) + 0.5 * top3_full,
    "TIER2_balanced_ra": 0.4 * trend_gate_full(top1_full, -0.04) + 0.6 * top3_full,
    "TIER2_3leg": (top1_full + top3_full + ra3_top3_full) / 3,
    "TIER2_3leg_gated": (trend_gate_full(top1_full, -0.04) + top3_full + ra3_top3_full) / 3,
    "TIER2_cagr": 0.5 * top1_full + 0.5 * ra2_top1_full,
    "TIER2_3legCAGR": (top1_full + top3_full + ra2_top1_full) / 3,
}

test_dates = pd.DatetimeIndex(sorted(set(d for f in folds for d in f["test_dates"])))
te_pos = df.index.get_indexer(test_dates)


def stats(r):
    r = np.asarray(r); r = r[~np.isnan(r)]
    eq = np.cumprod(1 + r); years = len(r) / 12
    cagr = eq[-1] ** (1 / years) - 1
    sd = r.std(ddof=1)
    sh = r.mean() / sd * np.sqrt(12) if sd > 0 else float("nan")
    peak = np.maximum.accumulate(eq); dd = (eq / peak - 1).min()
    return cagr, sh, dd


def to_monthly(daily):
    s = pd.Series(daily, index=test_dates).dropna()
    return s.groupby(s.index.to_period("M")).tail(1)


def evaluate(name, daily):
    sm = to_monthly(daily)
    s = stats(sm.values)
    print(f"{name:55s} CAGR={s[0]*100:5.1f}%  Sharpe={s[1]:4.2f}  MaxDD={s[2]*100:6.1f}%")
    return s, sm


print("=== Reference ensembles (all walk-forward) ===")
for name, full in ensembles.items():
    evaluate(name, full[te_pos])

# === ML EXPECTATION-OF-RETURN GATE ON ENSEMBLE ===
# Train regression on ensemble's return using macro+market features.
# When predicted return < threshold, scale down to SHY.
MACRO = [
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
MACRO = [c for c in MACRO if c in df.columns]
print(f"\nmacro features: {len(MACRO)}")

X = df[MACRO].values


def ev_gate(ensemble_full, name, target_arr=None):
    """Train HistGB regressor on (X[train], target=ensemble_returns[train]),
    then for each test sample: if pred < val-tuned threshold, hold SHY instead.
    """
    if target_arr is None:
        target_arr = ensemble_full
    records = []
    for fold in folds:
        tr = fold["train_dates"]; va = fold["val_dates"]; te = fold["test_dates"]
        if len(tr) < 50 or len(va) < 5 or len(te) < 1: continue
        sw = np.asarray(fold["train_sample_weights"])
        tr_pos = df.index.get_indexer(tr)
        va_pos = df.index.get_indexer(va)
        te_pos_f = df.index.get_indexer(te)
        ytr = target_arr[tr_pos]
        mtr = ~np.isnan(ytr)
        Xtr = X[tr_pos][mtr]; ytr = ytr[mtr]; sw_tr = sw[mtr]
        if len(ytr) < 30: continue
        pp = FeaturePreprocessor()
        Xtr_z = pp.fit_transform(pd.DataFrame(Xtr, columns=MACRO),
                                 sample_weights=sw_tr).to_numpy()
        Xva_z = pp.transform(pd.DataFrame(X[va_pos], columns=MACRO)).to_numpy()
        Xte_z = pp.transform(pd.DataFrame(X[te_pos_f], columns=MACRO)).to_numpy()
        m = HistGradientBoostingRegressor(
            max_iter=300, max_depth=4, learning_rate=0.05,
            min_samples_leaf=20, l2_regularization=2.0, random_state=0,
        )
        m.fit(Xtr_z, ytr, sample_weight=sw_tr)
        pred_va = m.predict(Xva_z)
        pred_te = m.predict(Xte_z)
        # Validate threshold: pick threshold maximizing the gated Sharpe on val
        va_base = ensemble_full[va_pos]
        va_shy = shy_ret[va_pos]
        valid_va = ~np.isnan(va_base)
        candidates = np.quantile(pred_va[valid_va], np.linspace(0.0, 0.30, 7))
        best_thr = -1e9; best_sc = -1e9
        for thr in candidates:
            gated = np.where(pred_va < thr, va_shy, va_base)[valid_va]
            sd = gated.std(ddof=1)
            sh = gated.mean() / sd if sd > 0 else -1e9
            if sh > best_sc:
                best_sc = sh; best_thr = thr
        for i, d in enumerate(te):
            base_r = ensemble_full[te_pos_f[i]]
            shy = shy_ret[te_pos_f[i]]
            if np.isnan(base_r): continue
            r = shy if pred_te[i] < best_thr else base_r
            records.append((d, base_r, pred_te[i], r))
    if not records: return None
    dfr = pd.DataFrame(records, columns=["date","base","pred","modec"]).set_index("date")
    dfr["m"] = dfr.index.to_period("M")
    monthly = dfr.groupby("m").tail(1)
    bs = stats(monthly["base"].values)
    ms = stats(monthly["modec"].values)
    print(f"{name:55s} BASE: {bs[0]*100:5.1f}/{bs[1]:.2f}/{bs[2]*100:6.1f}%  MODEC: {ms[0]*100:5.1f}/{ms[1]:.2f}/{ms[2]*100:6.1f}%")
    return monthly


print("\n=== ML EV-gate on ensembles ===")
for name in ["TIER2_balanced", "TIER2_3leg", "TIER2_3legCAGR", "TIER2_cagr"]:
    ev_gate(ensembles[name], f"EV-gate {name}")

# Soft EV gate using continuous weight
def ev_gate_soft(ensemble_full, name):
    records = []
    for fold in folds:
        tr = fold["train_dates"]; va = fold["val_dates"]; te = fold["test_dates"]
        if len(tr) < 50 or len(va) < 5 or len(te) < 1: continue
        sw = np.asarray(fold["train_sample_weights"])
        tr_pos = df.index.get_indexer(tr)
        va_pos = df.index.get_indexer(va)
        te_pos_f = df.index.get_indexer(te)
        ytr = ensemble_full[tr_pos]
        mtr = ~np.isnan(ytr)
        Xtr = X[tr_pos][mtr]; ytr = ytr[mtr]; sw_tr = sw[mtr]
        if len(ytr) < 30: continue
        pp = FeaturePreprocessor()
        Xtr_z = pp.fit_transform(pd.DataFrame(Xtr, columns=MACRO),
                                 sample_weights=sw_tr).to_numpy()
        Xte_z = pp.transform(pd.DataFrame(X[te_pos_f], columns=MACRO)).to_numpy()
        Xva_z = pp.transform(pd.DataFrame(X[va_pos], columns=MACRO)).to_numpy()
        m = HistGradientBoostingRegressor(
            max_iter=300, max_depth=4, learning_rate=0.05,
            min_samples_leaf=20, l2_regularization=2.0, random_state=0,
        )
        m.fit(Xtr_z, ytr, sample_weight=sw_tr)
        pred_te = m.predict(Xte_z)
        pred_va = m.predict(Xva_z)
        # determine quantile bounds from val
        valid_va = ~np.isnan(ensemble_full[va_pos])
        lo = np.quantile(pred_va[valid_va], 0.10)
        hi = np.quantile(pred_va[valid_va], 0.50)
        for i, d in enumerate(te):
            base_r = ensemble_full[te_pos_f[i]]
            shy = shy_ret[te_pos_f[i]]
            if np.isnan(base_r): continue
            w = max(0.0, min(1.0, (pred_te[i] - lo) / max(hi - lo, 1e-6)))
            r = w * base_r + (1 - w) * shy
            records.append((d, base_r, pred_te[i], r))
    if not records: return None
    dfr = pd.DataFrame(records, columns=["date","base","pred","modec"]).set_index("date")
    dfr["m"] = dfr.index.to_period("M")
    monthly = dfr.groupby("m").tail(1)
    bs = stats(monthly["base"].values)
    ms = stats(monthly["modec"].values)
    print(f"{name:55s} BASE: {bs[0]*100:5.1f}/{bs[1]:.2f}/{bs[2]*100:6.1f}%  MODEC: {ms[0]*100:5.1f}/{ms[1]:.2f}/{ms[2]*100:6.1f}%")
    return monthly


print("\n=== Soft EV gate on ensembles ===")
for name in ["TIER2_balanced", "TIER2_3leg", "TIER2_3legCAGR"]:
    ev_gate_soft(ensembles[name], f"EV-soft {name}")
