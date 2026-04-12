# ARCHIVED: tier1b block C — superseded by run_tier2
"""Tier 1B Block C — SPECIALIST TEAM.

E-C1: Build 5 specialists + combine with rules.
E-C2: Stacked meta-learner on top of 5 specialists' OOF outputs.

Specialists:
  M1 Regime classifier  (4-class GI quadrant, 21d fwd)
  M2 Vol forecaster     (predicts 21d realized vol)
  M3 Momentum persist.  (binary: rank1 stays rank1?)
  M4 Sector rotation    (cross-sectional predicted relative return)
  M5 Tail risk          (binary: TARGET_T4_drawdown_gt_5pct)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import (HistGradientBoostingClassifier,
                              HistGradientBoostingRegressor)
from sklearn.linear_model import LogisticRegression, Ridge

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts" / "model"))

from model.walk_forward import ExpandingSplitter  # noqa: E402
from model.preprocessing import FeaturePreprocessor  # noqa: E402
from run_tier1 import (  # noqa: E402
    ROT, N_TK, SPLIT_KW, load_panel, load_feature_sets,
    split_features_by_ticker, build_expanded_matrix,
    backtest_stats, annual_returns_from_monthly, systematic_picks,
)
from run_tier1b_blockA import REGIME_CLASSES, REGIME_TO_ETF, build_leadership_target  # noqa: E402

OUT = ROOT / "results/experiments"


# -------------------- Shared WF loop (per-date classifier/regressor) --------

def wf_loop(df, feats, target_col, model_factory, is_classifier, sw_reweight=False):
    """Standard walk-forward loop for a single-column (date-indexed) target.

    Returns dict: {date -> {prob or value, actual}}.
    """
    splitter = ExpandingSplitter(**SPLIT_KW)
    folds = splitter.split(df.index)
    out = {}
    fold_accs = []
    for fold in folds:
        tr = fold["train_dates"]; te = fold["test_dates"]
        sw = np.asarray(fold["train_sample_weights"])
        Xtr = df.loc[tr, feats]; ytr = df.loc[tr, target_col]
        Xte = df.loc[te, feats]; yte = df.loc[te, target_col]
        mtr = ytr.notna(); mte = yte.notna()
        Xtr, ytr, sw = Xtr[mtr], ytr[mtr], sw[mtr.to_numpy()]
        Xte, yte = Xte[mte], yte[mte]
        te_used = te[mte.to_numpy()]
        if len(Xtr) < 50 or len(Xte) < 1:
            continue
        if is_classifier:
            ytr_v = ytr.astype(int).to_numpy()
            yte_v = yte.astype(int).to_numpy()
        else:
            ytr_v = ytr.astype(float).to_numpy()
            yte_v = yte.astype(float).to_numpy()
        pp = FeaturePreprocessor()
        Xtr_z = pp.fit_transform(Xtr, sample_weights=sw).to_numpy()
        Xte_z = pp.transform(Xte).to_numpy()
        sw_fit = sw.copy()
        if is_classifier and sw_reweight:
            n_pos = max(int(ytr_v.sum()), 1)
            n_neg = max(int((1 - ytr_v).sum()), 1)
            ratio = n_neg / n_pos
            sw_fit = sw.copy()
            sw_fit[ytr_v == 1] *= ratio
        mdl = model_factory()
        try:
            mdl.fit(Xtr_z, ytr_v, sample_weight=sw_fit)
        except TypeError:
            mdl.fit(Xtr_z, ytr_v)
        if is_classifier:
            proba = mdl.predict_proba(Xte_z)
            # Pick P(class=1) for binary, full vector for multi-class
            if proba.shape[1] == 2:
                vals = proba[:, list(mdl.classes_).index(1)] if 1 in mdl.classes_ else proba[:, 1]
            else:
                vals = proba  # full matrix for multiclass
        else:
            vals = mdl.predict(Xte_z)
        for i, d in enumerate(te_used):
            out[pd.Timestamp(d)] = {
                "value": vals[i].tolist() if isinstance(vals[i], np.ndarray) else float(vals[i]),
                "actual": yte_v[i].tolist() if isinstance(yte_v[i], np.ndarray) else (int(yte_v[i]) if is_classifier else float(yte_v[i])),
                "fold_id": fold["fold_id"],
            }
        if is_classifier:
            pred_cls = np.argmax(proba, axis=1) if proba.shape[1] > 2 else (proba[:, 1] > 0.5).astype(int)
            fold_accs.append(float((pred_cls == yte_v).mean()))
    return out, fold_accs


# -------------------- Specialist builders -----------------------------------

def sp_m1_regime(df, fs):
    """Multi-class regime classifier, core macro features."""
    feats = [c for c in fs["core"] if c in df.columns
             and not any(tk in c for tk in ROT)]  # exclude price features
    cls_to_idx = {c: i for i, c in enumerate(REGIME_CLASSES)}
    df2 = df.copy()
    df2["_regime_idx"] = df2["TARGET_TREG_growth_inflation_fwd21"].map(cls_to_idx)
    def fac():
        return HistGradientBoostingClassifier(
            max_iter=200, max_depth=4, learning_rate=0.05,
            min_samples_leaf=20, l2_regularization=1.0, random_state=0,
        )
    out, acc = wf_loop(df2, feats, "_regime_idx", fac, is_classifier=True)
    return out, acc


def sp_m2_vol(df, fs):
    """Predict realized 21d volatility of QQQ returns, macro + vol features."""
    # Build target: rolling std of daily-returns proxy = sqrt(252) * |returns_5d|/sqrt(5)
    r5 = df["returns_5d__QQQ"].to_numpy(dtype=float)
    # 21d realized vol forward: stdev of next 4 non-overlapping 5d returns
    fwd_vol = np.full(len(df), np.nan)
    for i in range(len(df) - 20):
        chunk = []
        for k in range(4):
            idx = i + 1 + k * 5
            if idx < len(df) and not np.isnan(r5[idx]):
                chunk.append(r5[idx])
        if len(chunk) >= 3:
            fwd_vol[i] = float(np.std(chunk) * np.sqrt(252 / 5))
    df2 = df.copy()
    df2["_fwd_vol"] = fwd_vol
    # vol/macro feature subset
    feats = [c for c in fs["core"] if c in df2.columns
             and (c.startswith("vol_") or "vix" in c or "credit" in c
                  or c.startswith("regime_") or c.startswith("yield"))]
    if len(feats) < 5:
        feats = [c for c in fs["core"] if c in df2.columns]
    def fac():
        return HistGradientBoostingRegressor(
            max_iter=200, max_depth=4, learning_rate=0.05,
            min_samples_leaf=20, random_state=0,
        )
    out, _ = wf_loop(df2, feats, "_fwd_vol", fac, is_classifier=False)
    return out


def sp_m3_momentum(df, fs):
    """Binary momentum persistence."""
    target, rank1, gap, stab = build_leadership_target(df)
    df2 = df.copy()
    df2["_persist"] = target
    df2["_gap"] = gap
    df2["_stab"] = stab
    feats = [c for c in fs["core"] if c in df2.columns and any(tk in c for tk in ROT)]
    feats += ["_gap", "_stab"]
    feats = list(dict.fromkeys(feats))
    def fac():
        return LogisticRegression(C=1.0, class_weight="balanced", max_iter=1000)
    out, acc = wf_loop(df2, feats, "_persist", fac, is_classifier=True)
    return out, rank1, acc


def sp_m4_sector(df, fs):
    """Cross-sectional: predict relative return vs median."""
    feats = fs["extended"]
    shared, templates = split_features_by_ticker(feats, df.columns)
    X_full, y_full, _, _, feat_names = build_expanded_matrix(df, shared, templates)
    # Compute per-date relative return: y_full is flat (D*8); reshape and subtract median
    n_dates = len(df)
    y_mat = y_full.reshape(n_dates, N_TK)
    med = np.nanmedian(y_mat, axis=1, keepdims=True)
    y_rel_mat = y_mat - med
    y_full_rel = y_rel_mat.reshape(-1)

    splitter = ExpandingSplitter(**SPLIT_KW)
    folds = splitter.split(df.index)
    date_to_pos = pd.Series(np.arange(len(df)), index=df.index)

    def sel(dt_idx):
        rp = date_to_pos.loc[dt_idx].to_numpy()
        return (rp[:, None] * N_TK + np.arange(N_TK)[None, :]).reshape(-1)

    out = {}
    for fold in folds:
        tr = fold["train_dates"]; te = fold["test_dates"]
        sw = np.asarray(fold["train_sample_weights"])
        tr_rows = sel(tr); te_rows = sel(te)
        Xtr = X_full[tr_rows]; ytr = y_full_rel[tr_rows]
        Xte = X_full[te_rows]
        sw_tr = np.repeat(sw, N_TK)
        mtr = ~np.isnan(ytr)
        if mtr.sum() < 50:
            continue
        pp = FeaturePreprocessor()
        Xtr_z = pp.fit_transform(pd.DataFrame(Xtr[mtr], columns=feat_names),
                                 sample_weights=sw_tr[mtr]).to_numpy()
        Xte_z = pp.transform(pd.DataFrame(Xte, columns=feat_names)).to_numpy()
        mdl = HistGradientBoostingRegressor(
            max_iter=200, max_depth=4, learning_rate=0.05,
            min_samples_leaf=20, random_state=0,
        )
        mdl.fit(Xtr_z, ytr[mtr], sample_weight=sw_tr[mtr])
        pred = mdl.predict(Xte_z)  # length len(te_rows)
        pred_mat = pred.reshape(len(te), N_TK)
        for i, d in enumerate(te):
            out[pd.Timestamp(d)] = {
                "scores": pred_mat[i].tolist(),
                "fold_id": fold["fold_id"],
            }
    return out


def sp_m5_tail(df, fs):
    """Binary tail risk (TARGET_T4_drawdown_gt_5pct)."""
    feats = [c for c in fs["core"] if c in df.columns]
    def fac():
        return HistGradientBoostingClassifier(
            max_iter=150, max_depth=3, learning_rate=0.1,
            min_samples_leaf=20, max_leaf_nodes=15, l2_regularization=1.0,
            random_state=0,
        )
    out, _ = wf_loop(df, feats, "TARGET_T4_drawdown_gt_5pct", fac,
                     is_classifier=True, sw_reweight=True)
    return out


# ----------------- Combine specialists ------------------------------------

def run_EC1(df, fs):
    print("E-C1 Specialist team (5 models)")
    print("  training M1 regime…")
    m1, m1_acc = sp_m1_regime(df, fs)
    print(f"    M1 fold acc mean: {np.mean(m1_acc):.3f}")
    print("  training M2 vol forecaster…")
    m2 = sp_m2_vol(df, fs)
    print("  training M3 momentum persistence…")
    m3, rank1_arr, m3_acc = sp_m3_momentum(df, fs)
    print(f"    M3 fold acc mean: {np.mean(m3_acc):.3f}")
    print("  training M4 sector rotation…")
    m4 = sp_m4_sector(df, fs)
    print("  training M5 tail risk…")
    m5 = sp_m5_tail(df, fs)

    # Combine: iterate over dates present in all specialist outputs
    common_dates = sorted(set(m1) & set(m2) & set(m3) & set(m4) & set(m5))
    print(f"  common test dates: {len(common_dates)}")

    sys_pick = systematic_picks(df)
    avail_mom = [tk for tk in ROT if f"returns_63d__{tk}" in df.columns]

    rows = []
    for d in common_dates:
        # M1 regime prediction
        m1_vec = np.array(m1[d]["value"])
        m1_idx = int(np.argmax(m1_vec))
        m1_conf = float(m1_vec[m1_idx])
        pred_regime = REGIME_CLASSES[m1_idx]
        regime_etf = REGIME_TO_ETF[pred_regime]
        # M2 vol
        pred_vol = float(m2[d]["value"])
        # M3 momentum persist prob
        m3_prob = float(m3[d]["value"])
        # M4 sector scores
        scores = np.array(m4[d]["scores"])
        m4_best_idx = int(np.nanargmax(scores))
        m4_best_etf = ROT[m4_best_idx]
        # M5 tail prob
        tail_prob = float(m5[d]["value"])

        # Current systematic pick
        sys_tk = sys_pick.loc[d, "pick"]

        # Step 1: tail override
        pick = sys_tk
        note = "systematic"
        if tail_prob > 0.6:
            pick = "SHY"; note = "tail_override"
        else:
            # Step 2: vol reduction (keep pick but size 0.6) — we'll apply later
            # Step 3: regime prediction differs → prefer regime-favored
            # Step 4: momentum persistence
            if m3_prob > 0.65:
                pick = sys_tk; note = "momentum_stable"
            elif m3_prob < 0.35:
                pick = m4_best_etf; note = "momentum_switch"
            elif m1_conf > 0.7 and regime_etf in ROT:
                pick = regime_etf; note = "regime_pref"

        # Look up fwd return for chosen pick
        try:
            r = float(df.loc[d, f"TARGET_FWD21_{pick}"])
        except KeyError:
            r = float(df.loc[d, f"TARGET_FWD21_{sys_tk}"])
            pick = sys_tk
        # Step 2 sizing
        if pred_vol > 0.25 and note != "tail_override":
            r = 0.6 * r + 0.4 * 0.0
        rows.append({
            "date": d, "pick": pick, "note": note,
            "fwd_ret": r, "tail_prob": tail_prob, "pred_vol": pred_vol,
            "m1_conf": m1_conf, "m3_prob": m3_prob,
        })

    daily = pd.DataFrame(rows).set_index("date").sort_index()
    daily["__m"] = daily.index.to_period("M")
    monthly = daily.groupby("__m").tail(1).drop(columns="__m")
    monthly.index = monthly.index.to_period("M").to_timestamp("M")

    fwd = monthly["fwd_ret"].to_numpy()
    stats = backtest_stats(fwd)
    annual = annual_returns_from_monthly(monthly.index, fwd)

    # Note-level breakdown
    note_counts = monthly["note"].value_counts().to_dict()

    res = {
        "experiment": "EC1_specialist_team",
        "n_monthly": int(len(monthly)),
        "n_common_dates": len(common_dates),
        "wf_cagr": stats["cagr"],
        "wf_sharpe": stats["sharpe"],
        "wf_max_dd": stats["max_dd"],
        "annual_returns": annual,
        "note_counts": note_counts,
        "specialist_perf": {
            "M1_regime_fold_acc": float(np.mean(m1_acc)) if m1_acc else None,
            "M3_momentum_fold_acc": float(np.mean(m3_acc)) if m3_acc else None,
        },
    }
    (OUT / "EC1.json").write_text(json.dumps(res, indent=2, default=str))
    print(f"  EC1: CAGR={stats['cagr']:.3f} Sharpe={stats['sharpe']:.2f} "
          f"MaxDD={stats['max_dd']:.3f} notes={note_counts}")

    # Stash for EC2
    return res, (m1, m2, m3, m4, m5, common_dates)


def run_EC2(df, fs, bundle):
    print("E-C2 Stacked meta-learner")
    m1, m2, m3, m4, m5, common_dates = bundle
    rows = []
    sys_pick = systematic_picks(df)
    for d in common_dates:
        m1_vec = np.array(m1[d]["value"])
        m1_conf = float(m1_vec.max())
        m1_idx = int(m1_vec.argmax())
        m2_val = float(m2[d]["value"])
        m3_prob = float(m3[d]["value"])
        m4_scores = np.array(m4[d]["scores"])
        m4_best = int(np.nanargmax(m4_scores))
        m4_top2 = int(np.argsort(-m4_scores)[1])
        m4_range = float(np.nanmax(m4_scores) - np.nanmin(m4_scores))
        m5_prob = float(m5[d]["value"])
        # Actual T1 winner
        try:
            y = int(df.loc[d, "TARGET_T1_winner_idx"])
        except Exception:
            continue
        rows.append({
            "date": d,
            "m1_idx": m1_idx, "m1_conf": m1_conf,
            "m2_vol": m2_val, "m3_persist": m3_prob,
            "m4_best": m4_best, "m4_top2": m4_top2, "m4_range": m4_range,
            "m5_tail": m5_prob,
            "y_winner": y,
            "fold_id": m1[d]["fold_id"],
        })
    meta = pd.DataFrame(rows).set_index("date").sort_index()
    if len(meta) == 0:
        return None

    # Walk-forward: for each fold, use all earlier folds' OOF preds as meta training set
    fold_ids = sorted(meta["fold_id"].unique())
    preds_rows = []
    feats_cols = ["m1_idx", "m1_conf", "m2_vol", "m3_persist",
                  "m4_best", "m4_top2", "m4_range", "m5_tail"]
    for fid in fold_ids:
        train = meta[meta["fold_id"] < fid]
        test = meta[meta["fold_id"] == fid]
        if len(train) < 30 or len(test) < 1:
            continue
        Xtr = train[feats_cols].to_numpy()
        ytr = train["y_winner"].astype(int).to_numpy()
        Xte = test[feats_cols].to_numpy()
        yte = test["y_winner"].astype(int).to_numpy()
        mdl = HistGradientBoostingClassifier(
            max_iter=100, max_depth=3, learning_rate=0.1,
            min_samples_leaf=5, random_state=0,
        )
        mdl.fit(Xtr, ytr)
        proba = mdl.predict_proba(Xte)
        full = np.zeros((len(Xte), N_TK))
        for j, c in enumerate(mdl.classes_):
            full[:, int(c)] = proba[:, j]
        pred = np.argmax(full, axis=1)
        for i, d in enumerate(test.index):
            preds_rows.append({
                "date": d, "pred": int(pred[i]),
                "actual": int(yte[i]),
            })

    if not preds_rows:
        return None
    pdf = pd.DataFrame(preds_rows).set_index("date").sort_index()
    pdf["__m"] = pdf.index.to_period("M")
    monthly = pdf.groupby("__m").tail(1).drop(columns="__m")
    monthly.index = monthly.index.to_period("M").to_timestamp("M")
    acc = float((monthly["pred"] == monthly["actual"]).mean())
    fwd = []
    for d, row in monthly.iterrows():
        tk = ROT[int(row["pred"])]
        try:
            fwd.append(float(df.loc[d, f"TARGET_FWD21_{tk}"]))
        except KeyError:
            fwd.append(np.nan)
    fwd = np.array(fwd)
    stats = backtest_stats(fwd)
    annual = annual_returns_from_monthly(monthly.index, fwd)
    res = {
        "experiment": "EC2_stacked_meta",
        "n_monthly": int(len(monthly)),
        "argmax_accuracy": acc,
        "wf_cagr": stats["cagr"],
        "wf_sharpe": stats["sharpe"],
        "wf_max_dd": stats["max_dd"],
        "annual_returns": annual,
    }
    (OUT / "EC2.json").write_text(json.dumps(res, indent=2, default=str))
    print(f"  EC2: acc={acc:.3f} CAGR={stats['cagr']:.3f} Sharpe={stats['sharpe']:.2f}")
    return res


def main():
    df = load_panel()
    fs = load_feature_sets()
    print(f"panel: {df.shape}")
    res1, bundle = run_EC1(df, fs)
    res2 = run_EC2(df, fs, bundle)
    print("Block C done.")


if __name__ == "__main__":
    main()
