# ARCHIVED: drawdown sandbox v1 — superseded by stress_* scripts
"""ML drawdown gate sandbox: top-K base + macro feature gate."""
import sys
import numpy as np
import pandas as pd
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from model.walk_forward import ExpandingSplitter
from model.preprocessing import FeaturePreprocessor
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression

df = pd.read_parquet(ROOT / "data/features/master_panel.parquet")
ETFS_AVAIL = ["SOXX", "QQQ", "IGV", "XLE", "GLD", "SHY"]

MACRO_FEATS = [
    "sp500_pe", "sp500_cape", "sp500_cape_pct_10y", "sp500_pe_pct_10y", "sp500_earnings_yield",
    "inflation_features__pce_core_yoy_3m_trend", "inflation_features__pce_core_yoy",
    "inflation_features__cpi_core_yoy_3m_trend", "inflation_features__cpi_yoy_3m_trend",
    "inflation_features__cpi_yoy", "inflation_features__cpi_core_yoy",
    "activity_features__oecd_cli", "activity_features__oecd_cli_3m_change",
    "activity_features__ism_pmi", "activity_features__ism_pmi_3m_trend",
    "activity_features__industrial_production_yoy", "activity_features__capacity_utilization",
    "activity_rail_traffic__rail_traffic_yoy", "activity_airline_passengers__airline_pax_yoy",
    "activity_electricity__electricity_yoy",
    "consumer_features__consumer_credit_yoy", "consumer_features__housing_starts_yoy",
    "consumer_features__umich_sentiment",
    "liquidity_features__m2_yoy", "liquidity_features__m2_yoy_6m_chg",
    "credit_features__nfci", "credit_features__hy_ig_spread", "credit_features__nfci_chg21",
    "credit_features__ted_spread",
    "vol_features__vix", "quality_dist_sma200__SPY", "quality_dist_sma50__SPY",
    "returns_63d__SPY", "returns_42d__SPY",
    "atr_14d__SHY",
]
MACRO_FEATS = [c for c in MACRO_FEATS if c in df.columns]
print("macro feats:", len(MACRO_FEATS))

mom = df[[f"returns_63d__{tk}" for tk in ETFS_AVAIL]].copy()
mom.columns = ETFS_AVAIL
fwd = df[[f"TARGET_FWD21_{tk}" for tk in ETFS_AVAIL]].copy()
fwd.columns = ETFS_AVAIL
mom_arr = mom.values
fwd_arr = fwd.values
mom_filled = np.where(np.isnan(mom_arr), -np.inf, mom_arr)

top3_idx = np.argsort(-mom_filled, axis=1)[:, :3]
top3_ret_all = np.array([fwd_arr[i, top3_idx[i]].mean() for i in range(len(df))])
top1_idx_all = np.argmax(mom_filled, axis=1)
top1_ret_all = fwd_arr[np.arange(len(df)), top1_idx_all]
shy_all = fwd["SHY"].values

top3_dd_target = (top3_ret_all < -0.03).astype(float)
top3_dd_target[np.isnan(top3_ret_all)] = np.nan
top1_dd_target = (top1_ret_all < -0.05).astype(float)
top1_dd_target[np.isnan(top1_ret_all)] = np.nan
print("top3 dd_3pct base rate:", float(np.nanmean(top3_dd_target)))
print("top1 dd_5pct base rate:", float(np.nanmean(top1_dd_target)))

splitter = ExpandingSplitter(min_train_months=60, val_months=6, test_months=3,
                             step_months=3, sample_every_n_days=5, embargo_days=5,
                             target_horizon=21, decay_halflife_months=36)
folds = splitter.split(df.index)


def run_dd_model(target_arr, base_ret, model_kind="histgb", tau=0.5, blend_rule="binary"):
    test_records = []
    for fold in folds:
        tr_d = fold["train_dates"]
        te_d = fold["test_dates"]
        if len(tr_d) < 50 or len(te_d) < 1:
            continue
        sw = np.asarray(fold["train_sample_weights"])
        Xtr = df.loc[tr_d, MACRO_FEATS]
        ytr = pd.Series(target_arr, index=df.index).loc[tr_d]
        mtr = ytr.notna()
        Xtr = Xtr[mtr]
        ytr = ytr[mtr].astype(int)
        sw = sw[mtr.to_numpy()]
        if int(ytr.sum()) < 3:
            continue
        ratio = (1 - ytr).sum() / max(int(ytr.sum()), 1)
        sw_adj = sw.copy()
        sw_adj[ytr.to_numpy() == 1] *= ratio
        pp = FeaturePreprocessor()
        Xtr_z = pp.fit_transform(Xtr, sample_weights=sw)
        Xte = df.loc[te_d, MACRO_FEATS]
        Xte_z = pp.transform(Xte)
        if model_kind == "histgb":
            m = HistGradientBoostingClassifier(
                max_iter=200, max_depth=4, learning_rate=0.05,
                min_samples_leaf=15, l2_regularization=1.0, random_state=0,
            )
            m.fit(Xtr_z.to_numpy(), ytr.to_numpy(), sample_weight=sw_adj)
        else:
            m = LogisticRegression(C=0.5, class_weight="balanced", max_iter=2000, solver="lbfgs")
            m.fit(Xtr_z.to_numpy(), ytr.to_numpy(), sample_weight=sw)
        prob = m.predict_proba(Xte_z.to_numpy())[:, 1]
        for i, d in enumerate(te_d):
            base = base_ret[df.index.get_loc(d)]
            shy_r = shy_all[df.index.get_loc(d)]
            if np.isnan(base):
                continue
            if blend_rule == "binary":
                r = shy_r if prob[i] >= tau else base
            else:  # soft
                w = max(0.0, min(1.0, (prob[i] - 0.3) / 0.4))
                r = (1 - w) * base + w * shy_r
            test_records.append((d, base, prob[i], r))
    return test_records


def evaluate_records(records, name):
    if not records:
        print(name, "EMPTY")
        return
    df_r = pd.DataFrame(records, columns=["date", "base", "prob", "modec"]).set_index("date")
    df_r["m"] = df_r.index.to_period("M")
    monthly = df_r.groupby("m").tail(1)
    base_m = monthly["base"].values
    modec_m = monthly["modec"].values

    def stats(r):
        eq = np.cumprod(1 + r)
        years = len(r) / 12
        cagr = eq[-1] ** (1 / years) - 1
        sd = r.std(ddof=1)
        sh = r.mean() / sd * np.sqrt(12) if sd > 0 else float("nan")
        peak = np.maximum.accumulate(eq)
        dd = (eq / peak - 1).min()
        return cagr, sh, dd

    bs = stats(base_m)
    ms = stats(modec_m)
    print(f"{name:55s} BASE: {bs[0]*100:5.1f}/{bs[1]:.2f}/{bs[2]*100:6.1f}%  ModeC: {ms[0]*100:5.1f}/{ms[1]:.2f}/{ms[2]*100:6.1f}%")


print("\n--- top-1 base, T4_5pct ---")
t4_5 = df["TARGET_T4_drawdown_gt_5pct"].values
for tau in [0.4, 0.5, 0.6, 0.7]:
    r = run_dd_model(t4_5, top1_ret_all, "histgb", tau, "binary")
    evaluate_records(r, f"T4_5pct histgb tau={tau}")
for tau in [0.4, 0.5, 0.6, 0.7]:
    r = run_dd_model(t4_5, top1_ret_all, "logreg", tau, "binary")
    evaluate_records(r, f"T4_5pct logreg tau={tau}")

print("\n--- top-1 base, custom top1_dd_5pct ---")
for tau in [0.4, 0.5, 0.6]:
    r = run_dd_model(top1_dd_target, top1_ret_all, "histgb", tau, "binary")
    evaluate_records(r, f"top1_dd histgb tau={tau}")

print("\n--- top-3 base, T4_5pct (original drawdown signal) ---")
for tau in [0.4, 0.5, 0.6]:
    r = run_dd_model(t4_5, top3_ret_all, "histgb", tau, "binary")
    evaluate_records(r, f"T4_5pct->top3 histgb tau={tau}")
r = run_dd_model(t4_5, top3_ret_all, "histgb", 0.5, "soft")
evaluate_records(r, "T4_5pct->top3 histgb soft")

print("\n--- top-3 base, custom top3_dd_3pct ---")
for tau in [0.4, 0.5, 0.6]:
    r = run_dd_model(top3_dd_target, top3_ret_all, "histgb", tau, "binary")
    evaluate_records(r, f"top3_dd histgb tau={tau}")
r = run_dd_model(top3_dd_target, top3_ret_all, "histgb", 0.5, "soft")
evaluate_records(r, "top3_dd histgb soft")
r = run_dd_model(top3_dd_target, top3_ret_all, "logreg", 0.5, "soft")
evaluate_records(r, "top3_dd logreg soft")

print("\n--- top-3 base, T4_3pct ---")
t4_3 = df["TARGET_T4_drawdown_gt_3pct"].values
for tau in [0.4, 0.5, 0.6]:
    r = run_dd_model(t4_3, top3_ret_all, "histgb", tau, "binary")
    evaluate_records(r, f"T4_3pct->top3 histgb tau={tau}")
r = run_dd_model(t4_3, top3_ret_all, "histgb", 0.5, "soft")
evaluate_records(r, "T4_3pct->top3 histgb soft")
