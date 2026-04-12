# ARCHIVED: drawdown sandbox v2 — superseded by stress_* scripts
"""Drawdown gate v2: pick-aware features. Inject the current top-1 pick's
technical features into the row, so the model can reason about WHICH ETF is
about to be held.
"""
import sys
import numpy as np
import pandas as pd
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from model.walk_forward import ExpandingSplitter
from model.preprocessing import FeaturePreprocessor
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.linear_model import LogisticRegression

df = pd.read_parquet(ROOT / "data/features/master_panel.parquet")
ETFS = ["SOXX", "QQQ", "IGV", "XLE", "GLD", "SHY"]

# Build top-1 momentum pick per date
mom = df[[f"returns_63d__{tk}" for tk in ETFS]].copy()
mom.columns = ETFS
mom_arr = mom.values
mom_filled = np.where(np.isnan(mom_arr), -np.inf, mom_arr)
top1_idx = np.argmax(mom_filled, axis=1)
top1_tk = np.array([ETFS[i] for i in top1_idx])
fwd = df[[f"TARGET_FWD21_{tk}" for tk in ETFS]].copy()
fwd.columns = ETFS
fwd_arr = fwd.values
top1_ret = fwd_arr[np.arange(len(df)), top1_idx]
shy_ret = fwd["SHY"].values

# top-3 base
top3_idx = np.argsort(-mom_filled, axis=1)[:, :3]
top3_ret = np.array([fwd_arr[i, top3_idx[i]].mean() for i in range(len(df))])

# === Pick-aware feature construction ===
# For each ETF, gather candidate per-ETF features that exist
PER_ETF_TEMPLATES = [
    "vol_21d", "vol_42d", "vol_63d",
    "atr_14d",
    "quality_dist_sma200", "quality_dist_sma50",
    "quality_rsi_14d", "quality_rsi_28d",
    "quality_52w_high_ratio",
    "returns_5d", "returns_10d", "returns_21d", "returns_42d", "returns_63d",
    "quality_voladj_mom_42d", "quality_voladj_mom_63d", "quality_voladj_mom_126d",
    "volume_obv_slope_21d", "volume_relative_21d", "volume_trend_21_63",
    "cross_sectional_mom_zscore_63d",
]

# For each template, build a (D,) array indexed by the top-1 pick
def build_pick_feature(template_name):
    cols = {tk: f"{template_name}__{tk}" for tk in ETFS}
    avail = {tk: c for tk, c in cols.items() if c in df.columns}
    if len(avail) < len(ETFS):
        # missing some ETFs — skip
        return None
    arr = np.full(len(df), np.nan)
    for tk_i, tk in enumerate(ETFS):
        m = top1_idx == tk_i
        arr[m] = df[avail[tk]].values[m]
    return arr

pick_feats = {}
for t in PER_ETF_TEMPLATES:
    a = build_pick_feature(t)
    if a is not None and not np.all(np.isnan(a)):
        pick_feats[f"PICK__{t}"] = a

print(f"pick-aware features: {len(pick_feats)}")

# Macro features (universal)
MACRO_FEATS = [
    "sp500_pe", "sp500_cape", "sp500_cape_pct_10y", "sp500_pe_pct_10y", "sp500_earnings_yield",
    "inflation_features__pce_core_yoy_3m_trend", "inflation_features__pce_core_yoy",
    "inflation_features__cpi_core_yoy_3m_trend", "inflation_features__cpi_yoy_3m_trend",
    "inflation_features__cpi_yoy",
    "activity_features__oecd_cli", "activity_features__oecd_cli_3m_change",
    "activity_features__ism_pmi", "activity_features__ism_pmi_3m_trend",
    "activity_features__industrial_production_yoy", "activity_features__capacity_utilization",
    "consumer_features__consumer_credit_yoy", "consumer_features__umich_sentiment",
    "liquidity_features__m2_yoy", "liquidity_features__m2_yoy_6m_chg",
    "credit_features__nfci", "credit_features__hy_ig_spread", "credit_features__nfci_chg21",
    "credit_features__ted_spread",
    "vol_features__vix",
    "quality_dist_sma200__SPY", "quality_dist_sma50__SPY",
    "returns_63d__SPY", "returns_42d__SPY", "returns_21d__SPY",
]
MACRO_FEATS = [c for c in MACRO_FEATS if c in df.columns]
print(f"macro features: {len(MACRO_FEATS)}")

# Pick identity one-hot
pick_oh = np.zeros((len(df), len(ETFS)))
for i in range(len(df)):
    pick_oh[i, top1_idx[i]] = 1.0
oh_names = [f"PICKIS__{tk}" for tk in ETFS]

# Spread / relative features: how strong is top1 mom relative to top2?
sorted_mom = np.sort(-mom_filled, axis=1)
top1_minus_top2 = -sorted_mom[:, 0] - (-sorted_mom[:, 1])  # top1 - top2 mom
top1_mom_val = mom_filled[np.arange(len(df)), top1_idx]
top1_mom_val = np.where(np.isinf(top1_mom_val), np.nan, top1_mom_val)

# Build full feature matrix
pick_feat_arr = np.column_stack([pick_feats[k] for k in pick_feats])
macro_arr = df[MACRO_FEATS].values
extra = np.column_stack([top1_minus_top2, top1_mom_val])
X_full = np.hstack([macro_arr, pick_feat_arr, pick_oh, extra])
feat_names = (list(MACRO_FEATS) + list(pick_feats.keys()) + oh_names
              + ["TOP1_MINUS_TOP2", "TOP1_MOM"])
print(f"total features: {X_full.shape[1]}")

splitter = ExpandingSplitter(min_train_months=60, val_months=6, test_months=3,
                             step_months=3, sample_every_n_days=5, embargo_days=5,
                             target_horizon=21, decay_halflife_months=36)
folds = splitter.split(df.index)


def stats(r):
    r = np.asarray(r)
    r = r[~np.isnan(r)]
    eq = np.cumprod(1 + r)
    years = len(r) / 12
    cagr = eq[-1] ** (1 / years) - 1
    sd = r.std(ddof=1)
    sh = r.mean() / sd * np.sqrt(12) if sd > 0 else float("nan")
    peak = np.maximum.accumulate(eq)
    dd = (eq / peak - 1).min()
    return cagr, sh, dd


def evaluate(records, name):
    if not records:
        return
    df_r = pd.DataFrame(records, columns=["date", "base", "score", "modec"]).set_index("date")
    df_r["m"] = df_r.index.to_period("M")
    monthly = df_r.groupby("m").tail(1)
    bs = stats(monthly["base"].values)
    ms = stats(monthly["modec"].values)
    print(f"{name:55s} BASE: {bs[0]*100:5.1f}/{bs[1]:.2f}/{bs[2]*100:6.1f}%  ModeC: {ms[0]*100:5.1f}/{ms[1]:.2f}/{ms[2]*100:6.1f}%")
    return ms


def run_classifier_gate(target_arr, base_ret_arr, kind, tau, name):
    records = []
    for fold in folds:
        tr = fold["train_dates"]
        te = fold["test_dates"]
        if len(tr) < 50 or len(te) < 1:
            continue
        sw = np.asarray(fold["train_sample_weights"])
        tr_pos = df.index.get_indexer(tr)
        te_pos = df.index.get_indexer(te)
        Xtr = X_full[tr_pos]
        ytr = target_arr[tr_pos]
        mtr = ~np.isnan(ytr)
        Xtr = Xtr[mtr]
        ytr = ytr[mtr].astype(int)
        sw_tr = sw[mtr]
        if int(ytr.sum()) < 3:
            continue
        ratio = (1 - ytr).sum() / max(int(ytr.sum()), 1)
        sw_adj = sw_tr.copy()
        sw_adj[ytr == 1] *= ratio
        pp = FeaturePreprocessor()
        Xtr_z = pp.fit_transform(pd.DataFrame(Xtr, columns=feat_names),
                                 sample_weights=sw_tr).to_numpy()
        Xte = X_full[te_pos]
        Xte_z = pp.transform(pd.DataFrame(Xte, columns=feat_names)).to_numpy()
        if kind == "histgb":
            m = HistGradientBoostingClassifier(
                max_iter=300, max_depth=4, learning_rate=0.05,
                min_samples_leaf=10, l2_regularization=1.0, random_state=0,
            )
            m.fit(Xtr_z, ytr, sample_weight=sw_adj)
        else:
            m = LogisticRegression(C=0.3, class_weight="balanced",
                                   max_iter=2000, solver="lbfgs")
            m.fit(Xtr_z, ytr, sample_weight=sw_tr)
        prob = m.predict_proba(Xte_z)[:, 1]
        for i, d in enumerate(te):
            base_r = base_ret_arr[te_pos[i]]
            shy = shy_ret[te_pos[i]]
            if np.isnan(base_r):
                continue
            r = shy if prob[i] >= tau else base_r
            records.append((d, base_r, prob[i], r))
    return evaluate(records, name)


def run_regressor_gate(target_ret_arr, base_ret_arr, threshold, name):
    """Train regressor on the actual fwd return; if predicted < threshold, go SHY."""
    records = []
    for fold in folds:
        tr = fold["train_dates"]
        te = fold["test_dates"]
        if len(tr) < 50 or len(te) < 1:
            continue
        sw = np.asarray(fold["train_sample_weights"])
        tr_pos = df.index.get_indexer(tr)
        te_pos = df.index.get_indexer(te)
        Xtr = X_full[tr_pos]
        ytr = target_ret_arr[tr_pos]
        mtr = ~np.isnan(ytr)
        Xtr = Xtr[mtr]
        ytr = ytr[mtr]
        sw_tr = sw[mtr]
        if len(ytr) < 30:
            continue
        pp = FeaturePreprocessor()
        Xtr_z = pp.fit_transform(pd.DataFrame(Xtr, columns=feat_names),
                                 sample_weights=sw_tr).to_numpy()
        Xte = X_full[te_pos]
        Xte_z = pp.transform(pd.DataFrame(Xte, columns=feat_names)).to_numpy()
        m = HistGradientBoostingRegressor(
            max_iter=300, max_depth=4, learning_rate=0.05,
            min_samples_leaf=10, l2_regularization=1.0, random_state=0,
        )
        m.fit(Xtr_z, ytr, sample_weight=sw_tr)
        pred = m.predict(Xte_z)
        for i, d in enumerate(te):
            base_r = base_ret_arr[te_pos[i]]
            shy = shy_ret[te_pos[i]]
            if np.isnan(base_r):
                continue
            r = shy if pred[i] < threshold else base_r
            records.append((d, base_r, pred[i], r))
    return evaluate(records, name)


# Targets
top1_dd5 = (top1_ret < -0.05).astype(float)
top1_dd5[np.isnan(top1_ret)] = np.nan
top1_dd3 = (top1_ret < -0.03).astype(float)
top1_dd3[np.isnan(top1_ret)] = np.nan
top1_neg = (top1_ret < 0).astype(float)
top1_neg[np.isnan(top1_ret)] = np.nan

print("\n=== top-1 base, pick-aware features ===")
run_classifier_gate(top1_dd5, top1_ret, "histgb", 0.5, "top1_dd5 histgb 0.5")
run_classifier_gate(top1_dd5, top1_ret, "histgb", 0.6, "top1_dd5 histgb 0.6")
run_classifier_gate(top1_dd5, top1_ret, "histgb", 0.4, "top1_dd5 histgb 0.4")
run_classifier_gate(top1_dd3, top1_ret, "histgb", 0.5, "top1_dd3 histgb 0.5")
run_classifier_gate(top1_dd3, top1_ret, "histgb", 0.6, "top1_dd3 histgb 0.6")
run_classifier_gate(top1_neg, top1_ret, "histgb", 0.5, "top1_neg histgb 0.5")
run_classifier_gate(top1_neg, top1_ret, "histgb", 0.6, "top1_neg histgb 0.6")

print("\n=== top-1 base, regression EV gate ===")
run_regressor_gate(top1_ret, top1_ret, -0.005, "EV gate <-0.5%")
run_regressor_gate(top1_ret, top1_ret, 0.0, "EV gate <0")
run_regressor_gate(top1_ret, top1_ret, 0.005, "EV gate <+0.5%")
run_regressor_gate(top1_ret, top1_ret, 0.01, "EV gate <+1%")

# Use top-3 base too
print("\n=== top-3 base, regression EV gate (predict top-1's return) ===")
run_regressor_gate(top1_ret, top3_ret, 0.0, "EV gate <0 -> top3 base")
run_regressor_gate(top1_ret, top3_ret, 0.005, "EV gate <+0.5% -> top3")
