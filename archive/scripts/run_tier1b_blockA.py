# ARCHIVED: tier1b block A — superseded by run_tier2
"""Tier 1B Block A — DIFFERENT QUESTIONS.

E-A1: Regime (4-class) prediction → ETF mapping
E-A2: Leadership-change binary (will #1 momentum ETF stay #1?)
E-A3: 42d forward return regression
E-A4: 63d forward return regression
E-A5: Weekly risk signal (QQQ loses >3% in 5d)

All use ExpandingSplitter walk-forward, monthly aggregation.
Outputs: results/experiments/EA*.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts" / "model"))

from model.walk_forward import ExpandingSplitter  # noqa: E402
from model.preprocessing import FeaturePreprocessor  # noqa: E402
from run_tier1 import (  # noqa: E402
    ROT, N_TK, SPLIT_KW,
    load_panel, load_feature_sets,
    split_features_by_ticker, build_expanded_matrix,
    backtest_stats, annual_returns_from_monthly,
    aggregate_rotation, metrics_for_rotation, systematic_picks,
)


OUT = ROOT / "results/experiments"
OUT.mkdir(parents=True, exist_ok=True)


# ---- Experiment E-A1: Regime prediction ---------------------------------

REGIME_CLASSES = ["regime_hg_li", "regime_hg_hi", "regime_lg_li", "regime_lg_hi_stagflation"]
REGIME_TO_ETF = {
    "regime_hg_li": "SOXX",   # high growth / low inflation → growth/tech
    "regime_hg_hi": "XLE",    # high growth / high inflation → energy
    "regime_lg_li": "SHY",    # low growth / low inflation → cash-like
    "regime_lg_hi_stagflation": "GLD",  # stagflation → gold
}


def run_EA1(df, feature_sets):
    print("E-A1 Regime prediction HistGB CORE")
    feats = [c for c in feature_sets["core"] if c in df.columns]
    target_col = "TARGET_TREG_growth_inflation_fwd21"
    cls_to_idx = {c: i for i, c in enumerate(REGIME_CLASSES)}
    splitter = ExpandingSplitter(**SPLIT_KW)
    folds = splitter.split(df.index)

    records = []
    fold_records = []
    for fold in folds:
        tr = fold["train_dates"]; te = fold["test_dates"]
        if len(tr) < 30 or len(te) < 1:
            continue
        sw = np.asarray(fold["train_sample_weights"])
        Xtr = df.loc[tr, feats]; ytr_raw = df.loc[tr, target_col]
        Xte = df.loc[te, feats]; yte_raw = df.loc[te, target_col]
        mtr = ytr_raw.notna(); mte = yte_raw.notna()
        Xtr, ytr_raw, sw = Xtr[mtr], ytr_raw[mtr], sw[mtr.to_numpy()]
        Xte, yte_raw = Xte[mte], yte_raw[mte]
        te_used = te[mte.to_numpy()]
        if len(Xtr) < 50 or len(Xte) < 1:
            continue
        ytr = ytr_raw.map(cls_to_idx).astype(int).to_numpy()
        yte = yte_raw.map(cls_to_idx).astype(int).to_numpy()
        pp = FeaturePreprocessor()
        Xtr_z = pp.fit_transform(Xtr, sample_weights=sw).to_numpy()
        Xte_z = pp.transform(Xte).to_numpy()
        clf = HistGradientBoostingClassifier(
            max_iter=200, max_depth=4, learning_rate=0.05,
            min_samples_leaf=20, l2_regularization=1.0, random_state=0,
        )
        clf.fit(Xtr_z, ytr, sample_weight=sw)
        proba = clf.predict_proba(Xte_z)
        # Align to 4 classes
        full = np.zeros((len(Xte_z), 4))
        for j, c in enumerate(clf.classes_):
            full[:, int(c)] = proba[:, j]
        pred = np.argmax(full, axis=1)
        for i in range(len(te_used)):
            records.append({
                "date": pd.Timestamp(te_used[i]),
                "fold_id": fold["fold_id"],
                "pred_regime_idx": int(pred[i]),
                "pred_regime": REGIME_CLASSES[int(pred[i])],
                "actual_regime": REGIME_CLASSES[int(yte[i])],
                "confidence": float(full[i].max()),
                "correct": int(pred[i] == yte[i]),
            })
        fold_records.append({
            "fold_id": fold["fold_id"],
            "n": len(te_used),
            "acc": float((pred == yte).mean()),
        })

    if not records:
        return None
    sr = pd.DataFrame(records).set_index("date").sort_index()
    sr["__m"] = sr.index.to_period("M")
    monthly = sr.groupby("__m").tail(1).drop(columns="__m")
    monthly.index = monthly.index.to_period("M").to_timestamp("M")

    # Backtest: at each month, hold the ETF mapped from predicted regime,
    # using the sample date (last in month) to look up TARGET_FWD21.
    last = sr.groupby(sr.index.to_period("M")).tail(1).drop(columns="__m", errors="ignore")
    fwd = []
    picks = []
    for d, row in last.iterrows():
        tk = REGIME_TO_ETF[row["pred_regime"]]
        picks.append(tk)
        try:
            fwd.append(float(df.loc[d, f"TARGET_FWD21_{tk}"]))
        except KeyError:
            fwd.append(np.nan)
    fwd = np.array(fwd)
    last_m_idx = last.index.to_period("M").to_timestamp("M")
    stats = backtest_stats(fwd)
    annual = annual_returns_from_monthly(last_m_idx, fwd)

    acc = float(monthly["correct"].mean())
    # What ETF B2 would hold now → compare to regime-picked ETF at same date
    res = {
        "experiment": "EA1_regime_classifier",
        "n_monthly": int(len(monthly)),
        "regime_accuracy": acc,
        "wf_cagr": stats["cagr"],
        "wf_sharpe": stats["sharpe"],
        "wf_max_dd": stats["max_dd"],
        "annual_returns": annual,
        "n_folds_used": len(fold_records),
        "fold_records": fold_records,
        "pick_distribution": {tk: int(picks.count(tk)) for tk in set(picks)},
        "monthly_predictions": [
            {"date": str(pd.Timestamp(d).date()),
             "fold_id": int(last.loc[d, "fold_id"]),
             "pred_regime": last.loc[d, "pred_regime"],
             "actual_regime": last.loc[d, "actual_regime"],
             "pick": picks[i],
             "confidence": float(last.loc[d, "confidence"]),
             "fwd_ret": float(fwd[i]) if not np.isnan(fwd[i]) else None}
            for i, d in enumerate(last.index)
        ],
    }
    (OUT / "EA1.json").write_text(json.dumps(res, indent=2, default=str))
    print(f"  EA1: acc={acc:.3f} CAGR={stats['cagr']:.3f} Sharpe={stats['sharpe']:.2f}")
    return res


# ---- Experiment E-A2: Leadership persistence ----------------------------

def build_leadership_target(df):
    """Binary: will the 63d-momentum #1 ETF today still be #1 in 21 days?

    Uses only tickers that have a returns_63d column (XLK/VGT are missing).
    """
    avail = [tk for tk in ROT if f"returns_63d__{tk}" in df.columns]
    mom_cols = [f"returns_63d__{tk}" for tk in avail]
    mom = df[mom_cols].to_numpy(dtype=float)
    mom_filled = np.where(np.isnan(mom), -np.inf, mom)
    rank1_today = np.argmax(mom_filled, axis=1)
    # rank1 in 21 days: shift up by 21 rows
    rank1_fwd = np.roll(rank1_today, -21)
    rank1_fwd[-21:] = -1  # invalid tail
    target = (rank1_today == rank1_fwd).astype(float)
    target[-21:] = np.nan
    # Also emit helper features
    order = np.argsort(-mom_filled, axis=1)
    top2_gap = np.zeros(len(df))
    for i in range(len(df)):
        a, b = order[i, 0], order[i, 1]
        top2_gap[i] = mom_filled[i, a] - mom_filled[i, b]
    # rank stability over last 42 days
    stab = np.zeros(len(df))
    for i in range(42, len(df)):
        past = np.argmax(mom_filled[i - 42:i + 1], axis=1)
        stab[i] = (past == rank1_today[i]).mean()
    # VIX direction: vix - vix_21d_ma (already in panel as vix_vs_21d_ma)
    return target, rank1_today, top2_gap, stab


def run_EA2(df, feature_sets):
    print("E-A2 Leadership persistence HistGB CORE+helpers")
    target, rank1, gap, stab = build_leadership_target(df)
    avail = [tk for tk in ROT if f"returns_63d__{tk}" in df.columns]
    df2 = df.copy()
    df2["_lead_gap"] = gap
    df2["_lead_stab"] = stab
    # Add the pre-existing VIX change feature if present, as a helper
    helpers = ["_lead_gap", "_lead_stab"]
    if "vol_features__vix_chg21" in df2.columns:
        helpers.append("vol_features__vix_chg21")
    feats = [c for c in feature_sets["core"] if c in df2.columns] + helpers
    # dedup
    feats = list(dict.fromkeys(feats))

    splitter = ExpandingSplitter(**SPLIT_KW)
    folds = splitter.split(df2.index)

    records = []
    fold_records = []
    for fold in folds:
        tr = fold["train_dates"]; te = fold["test_dates"]
        if len(tr) < 30 or len(te) < 1:
            continue
        sw = np.asarray(fold["train_sample_weights"])
        tr_mask = df2.index.isin(tr)
        te_mask = df2.index.isin(te)
        ytr_full = target[tr_mask]
        yte_full = target[te_mask]
        Xtr = df2.loc[tr, feats]
        Xte = df2.loc[te, feats]
        mtr = ~np.isnan(ytr_full); mte = ~np.isnan(yte_full)
        Xtr = Xtr.iloc[mtr]; ytr = ytr_full[mtr].astype(int)
        Xte = Xte.iloc[mte]; yte = yte_full[mte].astype(int)
        sw_tr = sw[mtr]
        te_used = te[mte]
        rank1_te = rank1[te_mask][mte]
        if len(Xtr) < 50 or len(Xte) < 1:
            continue
        pp = FeaturePreprocessor()
        Xtr_z = pp.fit_transform(Xtr, sample_weights=sw_tr).to_numpy()
        Xte_z = pp.transform(Xte).to_numpy()
        clf = HistGradientBoostingClassifier(
            max_iter=200, max_depth=4, learning_rate=0.05,
            min_samples_leaf=20, l2_regularization=1.0, random_state=0,
        )
        clf.fit(Xtr_z, ytr, sample_weight=sw_tr)
        prob_full = clf.predict_proba(Xte_z)
        # probability of class 1 (stays)
        if 1 in clf.classes_:
            prob = prob_full[:, list(clf.classes_).index(1)]
        else:
            prob = np.zeros(len(Xte_z))
        pred = (prob >= 0.5).astype(int)
        for i in range(len(te_used)):
            records.append({
                "date": pd.Timestamp(te_used[i]),
                "fold_id": fold["fold_id"],
                "prob_stable": float(prob[i]),
                "pred": int(pred[i]),
                "actual": int(yte[i]),
                "rank1_idx": int(rank1_te[i]),
            })
        fold_records.append({
            "fold_id": fold["fold_id"],
            "n": len(te_used),
            "acc": float((pred == yte).mean()),
            "base_rate": float(ytr.mean()),
        })

    if not records:
        return None
    sr = pd.DataFrame(records).set_index("date").sort_index()
    sr["__m"] = sr.index.to_period("M")
    monthly = sr.groupby("__m").tail(1).drop(columns="__m")
    last = monthly.copy()
    last.index = last.index.to_period("M").to_timestamp("M")

    # Binary metrics
    pred = monthly["pred"].to_numpy()
    actual = monthly["actual"].to_numpy()
    prob = monthly["prob_stable"].to_numpy()
    acc = float((pred == actual).mean())
    tp = int(((pred == 1) & (actual == 1)).sum())
    fp = int(((pred == 1) & (actual == 0)).sum())
    fn = int(((pred == 0) & (actual == 1)).sum())
    tn = int(((pred == 0) & (actual == 0)).sum())
    prec = tp / max(tp + fp, 1)
    rec = tp / max(tp + fn, 1)
    f1 = 2 * prec * rec / max(prec + rec, 1e-9)

    # Mode-C backtest: if prob_stable > 0.65 → hold current rank1; else split rank1+rank2
    mom_cols = [f"returns_63d__{tk}" for tk in avail]
    fwd = []
    for i, (d, row) in enumerate(monthly.iterrows()):
        mom = df.loc[d, mom_cols].to_numpy(dtype=float)
        mom = np.where(np.isnan(mom), -np.inf, mom)
        order = np.argsort(-mom)
        tk1, tk2 = avail[order[0]], avail[order[1]]
        r1 = float(df.loc[d, f"TARGET_FWD21_{tk1}"])
        r2 = float(df.loc[d, f"TARGET_FWD21_{tk2}"])
        p = prob[i]
        if p > 0.65:
            r = r1
        elif p < 0.35:
            r = r2  # switch to #2
        else:
            r = 0.5 * r1 + 0.5 * r2
        fwd.append(r)
    fwd = np.array(fwd)
    stats = backtest_stats(fwd)
    annual = annual_returns_from_monthly(last.index, fwd)

    res = {
        "experiment": "EA2_leadership_persistence",
        "n_monthly": int(len(monthly)),
        "argmax_accuracy": acc,
        "precision": float(prec),
        "recall": float(rec),
        "f1": float(f1),
        "tp": tp, "fp": fp, "tn": tn, "fn": fn,
        "wf_cagr": stats["cagr"],
        "wf_sharpe": stats["sharpe"],
        "wf_max_dd": stats["max_dd"],
        "annual_returns": annual,
        "n_folds_used": len(fold_records),
        "fold_records": fold_records,
    }
    (OUT / "EA2.json").write_text(json.dumps(res, indent=2, default=str))
    print(f"  EA2: acc={acc:.3f} prec={prec:.3f} rec={rec:.3f} CAGR={stats['cagr']:.3f}")
    return res


# ---- Experiments E-A3 / E-A4: longer horizon regression -----------------

def compound_fwd(df, horizon_days):
    """Compound TARGET_FWD21 columns to longer horizons.

    horizon_days must be a multiple of 21. Returns dict ticker -> np.array."""
    assert horizon_days % 21 == 0
    k = horizon_days // 21
    out = {}
    for tk in ROT:
        fwd21 = df[f"TARGET_FWD21_{tk}"].to_numpy(dtype=float)
        cum = np.ones(len(df))
        for step in range(k):
            shifted = np.roll(fwd21, -21 * step)
            shifted[len(df) - 21 * step:] = np.nan
            cum = cum * (1.0 + shifted)
        out[tk] = cum - 1.0
    return out


def run_longer_horizon(df, feature_sets, horizon, exp_id):
    print(f"{exp_id} HistGB CORE T2 fwd{horizon}")
    fwd = compound_fwd(df, horizon)
    df2 = df.copy()
    for tk in ROT:
        df2[f"TARGET_FWDLH_{tk}"] = fwd[tk]
    feats = [c for c in feature_sets["core"] if c in df2.columns]

    # Cross-sectional expansion re-implemented with the new target
    shared, templates = split_features_by_ticker(feats, df2.columns)
    n_dates = len(df2)
    shared_arr = df2[shared].to_numpy(dtype=float) if shared else np.zeros((n_dates, 0))
    shared_rep = np.repeat(shared_arr, N_TK, axis=0)
    tmpl_arr = np.zeros((n_dates * N_TK, len(templates)), dtype=float)
    for j, p in enumerate(templates):
        cols = [f"{p}__{tk}" for tk in ROT]
        tmpl_arr[:, j] = df2[cols].to_numpy(dtype=float).reshape(-1)
    X_full = np.hstack([shared_rep, tmpl_arr])
    tgt_cols = [f"TARGET_FWDLH_{tk}" for tk in ROT]
    y_full = df2[tgt_cols].to_numpy(dtype=float).reshape(-1)
    feat_names = list(shared) + [f"TMPL__{p}" for p in templates]
    print(f"  expanded: {X_full.shape}, horizon={horizon}d")

    split_kw = dict(SPLIT_KW)
    split_kw["embargo_days"] = horizon
    split_kw["target_horizon"] = horizon
    splitter = ExpandingSplitter(**split_kw)
    folds = splitter.split(df2.index)
    date_to_pos = pd.Series(np.arange(len(df2)), index=df2.index)

    def sel(dt_idx):
        rp = date_to_pos.loc[dt_idx].to_numpy()
        return (rp[:, None] * N_TK + np.arange(N_TK)[None, :]).reshape(-1)

    sample_records = []
    fold_records = []
    for fold in folds:
        tr_d = fold["train_dates"]; te_d = fold["test_dates"]
        if len(tr_d) < 30 or len(te_d) < 1:
            continue
        sw_d = np.asarray(fold.get("train_sample_weights"))
        tr_rows = sel(tr_d); te_rows = sel(te_d)
        Xtr = X_full[tr_rows]; ytr = y_full[tr_rows]
        Xte = X_full[te_rows]; yte = y_full[te_rows]
        sw_tr = np.repeat(sw_d, N_TK)
        mtr = ~np.isnan(ytr); mte = ~np.isnan(yte)
        Xtr = Xtr[mtr]; ytr = ytr[mtr]; sw_tr = sw_tr[mtr]
        Xte_full = Xte.copy(); yte_full = yte.copy()
        if len(Xtr) < 50:
            continue
        pp = FeaturePreprocessor()
        Xtr_z = pp.fit_transform(pd.DataFrame(Xtr, columns=feat_names),
                                 sample_weights=sw_tr).to_numpy()
        Xte_z = pp.transform(pd.DataFrame(Xte_full, columns=feat_names)).to_numpy()
        mdl = HistGradientBoostingRegressor(
            max_iter=100, max_depth=3, learning_rate=0.1,
            min_samples_leaf=20, max_leaf_nodes=15, l2_regularization=1.0,
            random_state=0,
        )
        mdl.fit(Xtr_z, ytr, sample_weight=sw_tr)
        pred_full = mdl.predict(Xte_z)
        n_te = len(te_d)
        pred_mat = pred_full.reshape(n_te, N_TK)
        actual_mat = yte_full.reshape(n_te, N_TK)
        for i in range(n_te):
            sample_records.append({
                "date": pd.Timestamp(te_d[i]),
                "fold_id": fold["fold_id"],
                "pred": pred_mat[i].tolist(),
                "actual": actual_mat[i].tolist(),
            })
        fold_accs = []
        for i in range(n_te):
            a = actual_mat[i]; p = pred_mat[i]
            if np.isnan(a).any():
                continue
            fold_accs.append(int(np.nanargmax(p) == np.nanargmax(a)))
        if fold_accs:
            fold_records.append({
                "fold_id": fold["fold_id"],
                "argmax_acc": float(np.mean(fold_accs)),
                "n": len(fold_accs),
            })

    # Monthly aggregation — the existing aggregate_rotation expects `fwd_ret_pred_ticker`
    # built via FWD21. We need to override to use compounded returns.
    if not sample_records:
        return None
    rows = []
    for r in sample_records:
        pred = np.array(r["pred"])
        actual = np.array(r["actual"])
        valid = ~np.isnan(actual)
        if not valid.any():
            continue
        pred_idx = int(np.nanargmax(np.where(valid, pred, -np.inf)))
        actual_idx = int(np.nanargmax(np.where(valid, actual, -np.inf)))
        order = np.argsort(-np.where(valid, pred, -np.inf))
        top2 = set(order[:2].tolist())
        if valid.sum() >= 2 and np.std(pred[valid]) > 0 and np.std(actual[valid]) > 0:
            rp = pd.Series(pred[valid]).rank().to_numpy()
            ra = pd.Series(actual[valid]).rank().to_numpy()
            rho = float(np.corrcoef(rp, ra)[0, 1])
        else:
            rho = float("nan")
        rows.append({
            "date": r["date"], "fold_id": r["fold_id"],
            "pred_idx": pred_idx, "pred_ticker": ROT[pred_idx],
            "actual_idx": actual_idx,
            "argmax_correct": int(pred_idx == actual_idx),
            "top2_correct": int(actual_idx in top2),
            "spearman": rho,
            "fwd_ret_pred_ticker": float(actual[pred_idx]),
        })
    daily = pd.DataFrame(rows).set_index("date").sort_index()
    daily["__m"] = daily.index.to_period("M")
    monthly = daily.groupby("__m").tail(1).drop(columns="__m")
    monthly.index = monthly.index.to_period("M").to_timestamp("M")

    # Because returns are horizon-days long, we should NOT compound monthly (overlap).
    # Use non-overlapping stride = horizon/21 months for a clean annualized backtest.
    stride_m = horizon // 21
    stride_idx = monthly.iloc[::stride_m]
    fwd_ret = stride_idx["fwd_ret_pred_ticker"].to_numpy()
    n_periods = len(fwd_ret)
    # Annualize: CAGR computed from #periods per year = 12/stride_m
    r = fwd_ret[~np.isnan(fwd_ret)]
    if len(r) == 0:
        stats = dict(cagr=float("nan"), sharpe=float("nan"), max_dd=float("nan"),
                     mean_monthly=float("nan"), n=0)
    else:
        eq = np.cumprod(1.0 + r)
        years = len(r) * stride_m / 12.0
        cagr = float(eq[-1] ** (1.0 / years) - 1.0) if years > 0 else float("nan")
        sd = r.std(ddof=1) if len(r) > 1 else 0.0
        sharpe = float(r.mean() / sd * np.sqrt(12 / stride_m)) if sd > 0 else float("nan")
        peak = np.maximum.accumulate(eq)
        dd = eq / peak - 1.0
        stats = dict(cagr=cagr, sharpe=sharpe, max_dd=float(dd.min()),
                     mean_monthly=float(r.mean()), n=int(len(r)))
    acc = float(monthly["argmax_correct"].mean())
    top2 = float(monthly["top2_correct"].mean())
    rho = float(monthly["spearman"].mean(skipna=True))

    res = {
        "experiment": exp_id,
        "horizon_days": horizon,
        "n_monthly": int(len(monthly)),
        "n_backtest_periods": int(n_periods),
        "argmax_accuracy": acc,
        "top2_accuracy": top2,
        "mean_spearman": rho,
        "wf_cagr": stats["cagr"],
        "wf_sharpe": stats["sharpe"],
        "wf_max_dd": stats["max_dd"],
        "n_folds_used": len(fold_records),
        "fold_records": fold_records,
    }
    (OUT / f"{exp_id}.json").write_text(json.dumps(res, indent=2, default=str))
    print(f"  {exp_id}: acc={acc:.3f} CAGR={stats['cagr']:.3f} Sharpe={stats['sharpe']:.2f}")
    return res


def run_EA3(df, fs):
    return run_longer_horizon(df, fs, 42, "EA3_histgb_core_fwd42")


def run_EA4(df, fs):
    return run_longer_horizon(df, fs, 63, "EA4_histgb_core_fwd63")


# ---- Experiment E-A5: Weekly risk signal --------------------------------

def run_EA5(df, feature_sets):
    print("E-A5 Weekly risk (QQQ 5d < -3%) HistGB CORE")
    # Compute target: will QQQ return be less than -3% over next 5 trading days?
    r5 = df["returns_5d__QQQ"].to_numpy(dtype=float)
    fwd5 = np.roll(r5, -5)
    fwd5[-5:] = np.nan
    target = (fwd5 < -0.03).astype(float)
    target[np.isnan(fwd5)] = np.nan

    # Use a 5-day-horizon splitter
    split_kw = dict(SPLIT_KW)
    split_kw["sample_every_n_days"] = 5
    split_kw["embargo_days"] = 5
    split_kw["target_horizon"] = 5
    splitter = ExpandingSplitter(**split_kw)
    folds = splitter.split(df.index)
    feats = [c for c in feature_sets["core"] if c in df.columns]

    records = []
    fold_records = []
    for fold in folds:
        tr = fold["train_dates"]; te = fold["test_dates"]
        if len(tr) < 30 or len(te) < 1:
            continue
        sw = np.asarray(fold["train_sample_weights"])
        tr_mask = df.index.isin(tr); te_mask = df.index.isin(te)
        ytr_full = target[tr_mask]; yte_full = target[te_mask]
        Xtr = df.loc[tr, feats]; Xte = df.loc[te, feats]
        mtr = ~np.isnan(ytr_full); mte = ~np.isnan(yte_full)
        Xtr = Xtr.iloc[mtr]; Xte = Xte.iloc[mte]
        ytr = ytr_full[mtr].astype(int); yte = yte_full[mte].astype(int)
        sw_tr = sw[mtr]; te_used = te[mte]
        if len(Xtr) < 50 or len(Xte) < 1:
            continue
        # class-balance reweight
        n_pos = max(int(ytr.sum()), 1)
        n_neg = max(int((1 - ytr).sum()), 1)
        ratio = n_neg / n_pos
        sw_adj = sw_tr.copy()
        sw_adj[ytr == 1] *= ratio
        pp = FeaturePreprocessor()
        Xtr_z = pp.fit_transform(Xtr, sample_weights=sw_tr).to_numpy()
        Xte_z = pp.transform(Xte).to_numpy()
        clf = HistGradientBoostingClassifier(
            max_iter=200, max_depth=4, learning_rate=0.05,
            min_samples_leaf=20, l2_regularization=1.0, random_state=0,
        )
        clf.fit(Xtr_z, ytr, sample_weight=sw_adj)
        proba = clf.predict_proba(Xte_z)
        if 1 in clf.classes_:
            prob = proba[:, list(clf.classes_).index(1)]
        else:
            prob = np.zeros(len(Xte_z))
        pred = (prob >= 0.5).astype(int)
        for i in range(len(te_used)):
            records.append({
                "date": pd.Timestamp(te_used[i]),
                "fold_id": fold["fold_id"],
                "prob": float(prob[i]),
                "pred": int(pred[i]),
                "actual": int(yte[i]),
                "fwd5_ret": float(fwd5[df.index.get_loc(te_used[i])]),
            })
        fold_records.append({
            "fold_id": fold["fold_id"], "n": len(te_used),
            "pos_rate": float(ytr.mean()),
            "acc": float((pred == yte).mean()),
        })

    if not records:
        return None
    sr = pd.DataFrame(records).set_index("date").sort_index()
    prob_all = sr["prob"].to_numpy()
    actual_all = sr["actual"].to_numpy()
    pred_all = sr["pred"].to_numpy()
    tp = int(((pred_all == 1) & (actual_all == 1)).sum())
    fp = int(((pred_all == 1) & (actual_all == 0)).sum())
    fn = int(((pred_all == 0) & (actual_all == 1)).sum())
    tn = int(((pred_all == 0) & (actual_all == 0)).sum())
    prec = tp / max(tp + fp, 1)
    rec = tp / max(tp + fn, 1)
    f1 = 2 * prec * rec / max(prec + rec, 1e-9)
    # AUC (approx, no scipy)
    from sklearn.metrics import roc_auc_score
    try:
        auc = float(roc_auc_score(actual_all, prob_all))
    except Exception:
        auc = float("nan")

    # Overlay on systematic strategy: when prob>0.6 at weekly sample, reduce position
    # to 0.5 over the next 5 days (approximated: next daily samples get scaling applied)
    # Then aggregate to monthly for comparison.
    sys_picks = systematic_picks(df)
    # build daily fwd-5 returns for the systematic pick
    sys_fwd5 = np.full(len(df), np.nan)
    avail5 = [tk for tk in ROT if f"returns_5d__{tk}" in df.columns]
    ret5_dict = {tk: df[f"returns_5d__{tk}"].to_numpy(dtype=float) for tk in avail5}
    pick_arr = sys_picks["pick"].to_numpy()
    for i in range(len(df) - 5):
        tk = pick_arr[i]
        if tk in ret5_dict:
            sys_fwd5[i] = ret5_dict[tk][i + 5] if i + 5 < len(df) else np.nan

    # For each weekly sample in records: compare prob to threshold
    overlay_rets = []
    for _, row in sr.iterrows():
        d = row.name if hasattr(row, "name") else None
    # simpler: compute weekly sys return for each record
    sys_weekly = []
    for d, row in sr.iterrows():
        pos = df.index.get_loc(d)
        tk = pick_arr[pos]
        r = (ret5_dict[tk][pos + 5]
             if (tk in ret5_dict and pos + 5 < len(df)) else np.nan)
        sys_weekly.append(r)
        prob = float(row["prob"])
        if prob > 0.6:
            overlay_rets.append(0.0)  # flat for next 5 days
        elif prob > 0.4:
            overlay_rets.append(0.5 * r if not np.isnan(r) else np.nan)
        else:
            overlay_rets.append(r)
    sys_weekly = np.array(sys_weekly, dtype=float)
    overlay_rets = np.array(overlay_rets, dtype=float)

    def wk_stats(r):
        r = r[~np.isnan(r)]
        if len(r) == 0:
            return dict(cagr=float("nan"), sharpe=float("nan"), max_dd=float("nan"), n=0)
        eq = np.cumprod(1.0 + r)
        years = len(r) * 5 / 252.0
        cagr = float(eq[-1] ** (1.0 / years) - 1.0) if years > 0 else float("nan")
        sd = r.std(ddof=1) if len(r) > 1 else 0.0
        sharpe = float(r.mean() / sd * np.sqrt(52)) if sd > 0 else float("nan")
        peak = np.maximum.accumulate(eq)
        dd = eq / peak - 1.0
        return dict(cagr=cagr, sharpe=sharpe, max_dd=float(dd.min()), n=int(len(r)))

    overlay = wk_stats(overlay_rets)
    sys_only = wk_stats(sys_weekly)

    res = {
        "experiment": "EA5_weekly_risk_signal",
        "horizon_days": 5,
        "n_weekly_obs": int(len(sr)),
        "accuracy": float((pred_all == actual_all).mean()),
        "precision": float(prec),
        "recall": float(rec),
        "f1": float(f1),
        "auc": auc,
        "tp": tp, "fp": fp, "tn": tn, "fn": fn,
        "pos_rate": float(actual_all.mean()),
        "overlay_cagr": overlay["cagr"],
        "overlay_sharpe": overlay["sharpe"],
        "overlay_max_dd": overlay["max_dd"],
        "sys_weekly_cagr": sys_only["cagr"],
        "sys_weekly_sharpe": sys_only["sharpe"],
        "sys_weekly_max_dd": sys_only["max_dd"],
        "n_folds_used": len(fold_records),
        "fold_records": fold_records,
    }
    (OUT / "EA5.json").write_text(json.dumps(res, indent=2, default=str))
    print(f"  EA5: f1={f1:.3f} auc={auc:.3f} overlay_CAGR={overlay['cagr']:.3f} "
          f"sys_CAGR={sys_only['cagr']:.3f}")
    return res


def main():
    df = load_panel()
    fs = load_feature_sets()
    print(f"panel: {df.shape}")
    results = {}
    for name, fn in [("EA1", run_EA1), ("EA2", run_EA2), ("EA3", run_EA3),
                     ("EA4", run_EA4), ("EA5", run_EA5)]:
        try:
            results[name] = fn(df, fs)
        except Exception as e:
            import traceback
            print(f"{name} FAILED: {e}")
            traceback.print_exc()
            results[name] = {"error": str(e)}
    (OUT / "blockA_summary.json").write_text(json.dumps(
        {k: {kk: vv for kk, vv in v.items() if kk != "fold_records" and kk != "monthly_predictions"}
         if isinstance(v, dict) else v for k, v in results.items()},
        indent=2, default=str))
    print("Block A done.")


if __name__ == "__main__":
    main()
