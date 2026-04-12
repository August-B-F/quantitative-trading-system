"""Combine the winning ideas: top-3 base + ML soft gate + regression EV gate
calibrated on validation fold.
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

mom = df[[f"returns_63d__{tk}" for tk in ETFS]].copy()
mom.columns = ETFS
mom_arr = mom.values
mom_filled = np.where(np.isnan(mom_arr), -np.inf, mom_arr)
top1_idx = np.argmax(mom_filled, axis=1)
top3_idx = np.argsort(-mom_filled, axis=1)[:, :3]
fwd = df[[f"TARGET_FWD21_{tk}" for tk in ETFS]].copy()
fwd.columns = ETFS
fwd_arr = fwd.values
top1_ret = fwd_arr[np.arange(len(df)), top1_idx]
top3_ret = np.array([fwd_arr[i, top3_idx[i]].mean() for i in range(len(df))])
shy_ret = fwd["SHY"].values

# Realized vol of top-1 pick
vol_pick = np.full(len(df), np.nan)
for i, tk in enumerate(ETFS):
    for v in ["vol_42d", "vol_21d", "vol_63d"]:
        c = f"{v}__{tk}"
        if c in df.columns:
            m = top1_idx == i
            vol_pick[m] = df[c].values[m]
            break

# Feature set: macro + pick-aware (per-pick technicals) + top-3 vol
PER_ETF_TEMPLATES = ["vol_21d", "vol_42d", "vol_63d", "atr_14d",
                     "quality_dist_sma200", "quality_dist_sma50",
                     "quality_rsi_14d", "quality_rsi_28d",
                     "quality_52w_high_ratio",
                     "returns_5d", "returns_10d", "returns_21d", "returns_42d", "returns_63d",
                     "quality_voladj_mom_42d", "quality_voladj_mom_63d",
                     "volume_relative_21d"]

def build_pick_feature(template_name):
    arr = np.full(len(df), np.nan)
    ok = True
    for tk_i, tk in enumerate(ETFS):
        col = f"{template_name}__{tk}"
        if col not in df.columns:
            ok = False
            break
        m = top1_idx == tk_i
        arr[m] = df[col].values[m]
    return arr if ok else None

pick_feats = {}
for t in PER_ETF_TEMPLATES:
    a = build_pick_feature(t)
    if a is not None:
        pick_feats[f"PICK__{t}"] = a

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

pick_oh = np.zeros((len(df), len(ETFS)))
for i in range(len(df)):
    pick_oh[i, top1_idx[i]] = 1.0
oh_names = [f"PICKIS__{tk}" for tk in ETFS]

sorted_mom = np.sort(-mom_filled, axis=1)
top1_minus_top2 = -sorted_mom[:, 0] - (-sorted_mom[:, 1])
top1_mom_val = mom_filled[np.arange(len(df)), top1_idx]
top1_mom_val = np.where(np.isinf(top1_mom_val), 0.0, top1_mom_val)
top1_minus_top2 = np.where(np.isinf(top1_minus_top2) | np.isnan(top1_minus_top2),
                            0.0, top1_minus_top2)

pick_feat_arr = np.column_stack([pick_feats[k] for k in pick_feats])
macro_arr = df[MACRO_FEATS].values
extra = np.column_stack([top1_minus_top2, top1_mom_val])
X_full = np.hstack([macro_arr, pick_feat_arr, pick_oh, extra])
feat_names = (list(MACRO_FEATS) + list(pick_feats.keys()) + oh_names
              + ["TOP1_MINUS_TOP2", "TOP1_MOM"])
print(f"features: {X_full.shape[1]}")

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
    if not records: return None
    df_r = pd.DataFrame(records, columns=["date", "base", "pred", "modec"]).set_index("date")
    df_r["m"] = df_r.index.to_period("M")
    monthly = df_r.groupby("m").tail(1)
    bs = stats(monthly["base"].values)
    ms = stats(monthly["modec"].values)
    print(f"{name:55s} BASE: {bs[0]*100:5.1f}/{bs[1]:.2f}/{bs[2]*100:6.1f}%  ModeC: {ms[0]*100:5.1f}/{ms[1]:.2f}/{ms[2]*100:6.1f}%")
    return ms


def run_regressor_with_val_threshold(target_arr, base_ret, name, max_quantile=0.30):
    """Train regressor on train, calibrate threshold on val to maximize Sharpe of ModeC.
    Then apply to test.
    """
    records = []
    for fold in folds:
        tr = fold["train_dates"]; va = fold["val_dates"]; te = fold["test_dates"]
        if len(tr) < 50 or len(va) < 5 or len(te) < 1: continue
        sw = np.asarray(fold["train_sample_weights"])
        tr_pos = df.index.get_indexer(tr)
        va_pos = df.index.get_indexer(va)
        te_pos = df.index.get_indexer(te)
        Xtr = X_full[tr_pos]; ytr = target_arr[tr_pos]
        mtr = ~np.isnan(ytr)
        Xtr = Xtr[mtr]; ytr = ytr[mtr]; sw_tr = sw[mtr]
        if len(ytr) < 30: continue
        pp = FeaturePreprocessor()
        Xtr_z = pp.fit_transform(pd.DataFrame(Xtr, columns=feat_names),
                                 sample_weights=sw_tr).to_numpy()
        Xva_z = pp.transform(pd.DataFrame(X_full[va_pos], columns=feat_names)).to_numpy()
        Xte_z = pp.transform(pd.DataFrame(X_full[te_pos], columns=feat_names)).to_numpy()
        m = HistGradientBoostingRegressor(
            max_iter=300, max_depth=4, learning_rate=0.05,
            min_samples_leaf=15, l2_regularization=2.0, random_state=0,
        )
        m.fit(Xtr_z, ytr, sample_weight=sw_tr)
        pred_va = m.predict(Xva_z)
        pred_te = m.predict(Xte_z)
        # calibrate threshold on validation: find threshold that gives best Sharpe of (gated returns)
        va_base = base_ret[va_pos]
        va_shy = shy_ret[va_pos]
        valid = ~np.isnan(va_base)
        candidates = np.quantile(pred_va[valid], np.linspace(0.0, max_quantile, 7))
        best_thr = -1e9; best_sharpe = -1e9
        for thr in candidates:
            gated = np.where(pred_va < thr, va_shy, va_base)
            gated = gated[valid]
            if len(gated) < 5: continue
            sd = gated.std(ddof=1)
            sh = gated.mean() / sd * np.sqrt(252/21) if sd > 0 else -1e9
            if sh > best_sharpe:
                best_sharpe = sh; best_thr = thr
        for i, d in enumerate(te):
            base_r = base_ret[te_pos[i]]
            shy = shy_ret[te_pos[i]]
            if np.isnan(base_r): continue
            r = shy if pred_te[i] < best_thr else base_r
            records.append((d, base_r, pred_te[i], r))
    return evaluate(records, name)


# Targets
top3_dd3 = (top3_ret < -0.03).astype(float); top3_dd3[np.isnan(top3_ret)] = np.nan
top1_dd3 = (top1_ret < -0.03).astype(float); top1_dd3[np.isnan(top1_ret)] = np.nan
top1_dd5 = (top1_ret < -0.05).astype(float); top1_dd5[np.isnan(top1_ret)] = np.nan

print("\n=== Regression EV with VAL-tuned threshold ===")
run_regressor_with_val_threshold(top1_ret, top1_ret, "EV->top1 (val-tuned)")
run_regressor_with_val_threshold(top1_ret, top3_ret, "EV->top3 base (val-tuned)")
run_regressor_with_val_threshold(top3_ret, top3_ret, "EV(top3)->top3 (val-tuned)")


def run_classifier_soft(target_arr, base_ret, name, model_kind="histgb", lo=0.40, hi=0.70):
    """Soft blend: between lo and hi, linearly shift to SHY."""
    records = []
    for fold in folds:
        tr = fold["train_dates"]; te = fold["test_dates"]
        if len(tr) < 50 or len(te) < 1: continue
        sw = np.asarray(fold["train_sample_weights"])
        tr_pos = df.index.get_indexer(tr)
        te_pos = df.index.get_indexer(te)
        Xtr = X_full[tr_pos]; ytr = target_arr[tr_pos]
        mtr = ~np.isnan(ytr)
        Xtr = Xtr[mtr]; ytr = ytr[mtr].astype(int); sw_tr = sw[mtr]
        if int(ytr.sum()) < 3: continue
        ratio = (1 - ytr).sum() / max(int(ytr.sum()), 1)
        sw_adj = sw_tr.copy(); sw_adj[ytr == 1] *= ratio
        pp = FeaturePreprocessor()
        Xtr_z = pp.fit_transform(pd.DataFrame(Xtr, columns=feat_names),
                                 sample_weights=sw_tr).to_numpy()
        Xte_z = pp.transform(pd.DataFrame(X_full[te_pos], columns=feat_names)).to_numpy()
        if model_kind == "histgb":
            mdl = HistGradientBoostingClassifier(
                max_iter=300, max_depth=4, learning_rate=0.05,
                min_samples_leaf=15, l2_regularization=2.0, random_state=0,
            )
            mdl.fit(Xtr_z, ytr, sample_weight=sw_adj)
        else:
            mdl = LogisticRegression(C=0.3, class_weight="balanced", max_iter=2000)
            mdl.fit(Xtr_z, ytr, sample_weight=sw_tr)
        prob = mdl.predict_proba(Xte_z)[:, 1]
        for i, d in enumerate(te):
            base_r = base_ret[te_pos[i]]
            shy = shy_ret[te_pos[i]]
            if np.isnan(base_r): continue
            w = max(0.0, min(1.0, (prob[i] - lo) / (hi - lo)))
            r = (1 - w) * base_r + w * shy
            records.append((d, base_r, prob[i], r))
    return evaluate(records, name)


print("\n=== Soft classifier gate ===")
run_classifier_soft(top3_dd3, top3_ret, "top3_dd3 histgb soft 0.4-0.7", lo=0.4, hi=0.7)
run_classifier_soft(top3_dd3, top3_ret, "top3_dd3 histgb soft 0.5-0.8", lo=0.5, hi=0.8)
run_classifier_soft(top1_dd5, top1_ret, "top1_dd5 histgb soft 0.4-0.7", lo=0.4, hi=0.7)
run_classifier_soft(top1_dd5, top1_ret, "top1_dd5 histgb soft 0.5-0.8", lo=0.5, hi=0.8)
run_classifier_soft(top1_dd3, top1_ret, "top1_dd3 histgb soft 0.5-0.8", lo=0.5, hi=0.8)
run_classifier_soft(top1_dd3, top3_ret, "top1_dd3->top3 soft 0.4-0.7", lo=0.4, hi=0.7)
run_classifier_soft(top1_dd5, top3_ret, "top1_dd5->top3 soft 0.4-0.7", lo=0.4, hi=0.7)
