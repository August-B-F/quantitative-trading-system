"""Tier 1 experiments E01-E05.

Runs five model experiments on the master feature panel using ExpandingSplitter
walk-forward, then aggregates predictions to one signal per month and produces
backtests vs B0/B1/B2 baselines.

Outputs:
    results/experiments/E01.json .. E05.json
    results/TIER1_REPORT.md
    results/TIER1_VERDICT.md
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from sklearn.ensemble import (
    HistGradientBoostingClassifier,
    HistGradientBoostingRegressor,
    RandomForestClassifier,
)
from sklearn.linear_model import LogisticRegression, Ridge

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from model.walk_forward import ExpandingSplitter  # noqa: E402
from model.preprocessing import FeaturePreprocessor  # noqa: E402

ROT = ["SOXX", "QQQ", "XLK", "VGT", "IGV", "XLE", "GLD", "SHY"]
N_TK = len(ROT)

SPLIT_KW = dict(
    min_train_months=60,
    val_months=6,
    test_months=3,
    step_months=3,
    sample_every_n_days=5,
    embargo_days=5,
    target_horizon=21,
    decay_halflife_months=36,
)


def load_panel():
    return pd.read_parquet(ROOT / "data/features/master_panel.parquet")


def load_feature_sets():
    return yaml.safe_load(open(ROOT / "configs/feature_sets.yaml"))


# Cross-sectional expansion

def split_features_by_ticker(feature_list, df_cols):
    """Return (shared_cols, template_prefixes) for cross-sectional expansion."""
    cols_set = set(df_cols)
    by_template = defaultdict(set)
    shared = []
    for f in feature_list:
        if f not in cols_set:
            continue
        if "__" in f:
            p, s = f.rsplit("__", 1)
            if s in ROT:
                by_template[p].add(s)
                continue
        shared.append(f)
    templates = []
    for p, ts in by_template.items():
        if all(f"{p}__{tk}" in cols_set for tk in ROT):
            templates.append(p)
        else:
            for tk in ts:
                shared.append(f"{p}__{tk}")
    # Always inject ETF discriminators if available
    for fb in [
        "cross_sectional_relative_mom_63d",
        "cross_sectional_mom_rank_63d",
        "relative_strength_126d",
    ]:
        if fb not in templates and all(f"{fb}__{tk}" in cols_set for tk in ROT):
            templates.append(fb)
    return shared, templates


def build_expanded_matrix(df, shared, templates):
    """Return (X (D*8, F), y (D*8), date_arr, ticker_arr, feat_names)."""
    n_dates = len(df)
    shared_arr = df[shared].to_numpy(dtype=float) if shared else np.zeros((n_dates, 0))
    shared_rep = np.repeat(shared_arr, N_TK, axis=0)
    tmpl_arr = np.zeros((n_dates * N_TK, len(templates)), dtype=float)
    for j, p in enumerate(templates):
        cols = [f"{p}__{tk}" for tk in ROT]
        tmpl_arr[:, j] = df[cols].to_numpy(dtype=float).reshape(-1)
    X = np.hstack([shared_rep, tmpl_arr])
    tgt_cols = [f"TARGET_FWD21_{tk}" for tk in ROT]
    y = df[tgt_cols].to_numpy(dtype=float).reshape(-1)
    dates = np.repeat(df.index.values, N_TK)
    tickers = np.tile(np.array(ROT), n_dates)
    feat_names = list(shared) + [f"TMPL__{p}" for p in templates]
    return X, y, dates, tickers, feat_names


# Backtest helpers

def annual_returns_from_monthly(monthly_dt: pd.DatetimeIndex, monthly_ret: np.ndarray):
    s = pd.Series(monthly_ret, index=pd.DatetimeIndex(monthly_dt))
    yr = (1.0 + s).groupby(s.index.year).prod() - 1.0
    return {int(k): float(v) for k, v in yr.items()}


def backtest_stats(monthly_ret: np.ndarray):
    r = np.asarray(monthly_ret, dtype=float)
    r = r[~np.isnan(r)]
    if len(r) == 0:
        return dict(cagr=float("nan"), sharpe=float("nan"), max_dd=float("nan"),
                    mean_monthly=float("nan"), n=0)
    mean = r.mean()
    sd = r.std(ddof=1) if len(r) > 1 else 0.0
    sharpe = float(mean / sd * np.sqrt(12)) if sd > 0 else float("nan")
    eq = np.cumprod(1.0 + r)
    years = len(r) / 12.0
    cagr = float(eq[-1] ** (1.0 / years) - 1.0) if years > 0 else float("nan")
    peak = np.maximum.accumulate(eq)
    dd = eq / peak - 1.0
    return dict(cagr=cagr, sharpe=sharpe, max_dd=float(dd.min()),
                mean_monthly=float(mean), n=int(len(r)))


def monthly_last_per_month(date_arr, payload_dict):
    """Collapse to one row per calendar month, taking last sample per month.

    payload_dict: dict of column_name -> array (same length as date_arr).
    """
    df = pd.DataFrame(payload_dict, index=pd.DatetimeIndex(date_arr))
    df = df.sort_index()
    df["__m"] = df.index.to_period("M")
    monthly = df.groupby("__m").tail(1).drop(columns="__m")
    monthly.index = monthly.index.to_period("M").to_timestamp("M")
    return monthly


def fwd_lookup_series(df_panel: pd.DataFrame, dates, tickers):
    """For each (date, ticker) lookup TARGET_FWD21_<ticker>."""
    out = np.full(len(dates), np.nan)
    cache = {tk: df_panel[f"TARGET_FWD21_{tk}"] for tk in ROT}
    for i, (d, tk) in enumerate(zip(dates, tickers)):
        try:
            out[i] = cache[tk].loc[d]
        except KeyError:
            pass
    return out


# Experiments

def run_regression_expanded(df, feature_list, model_factory, target_horizon=21):
    """E01/E02 style: cross-sectional expansion + regression on per-ETF fwd return."""
    shared, templates = split_features_by_ticker(feature_list, df.columns)
    X_full, y_full, dates_full, tk_full, feat_names = build_expanded_matrix(
        df, shared, templates
    )
    n_feat = X_full.shape[1]
    print(f"  expanded: {X_full.shape}, shared={len(shared)}, templates={len(templates)}")

    splitter = ExpandingSplitter(**SPLIT_KW)
    folds = splitter.split(df.index)

    # Reverse index: date -> row positions
    date_to_pos = pd.Series(np.arange(len(df)), index=df.index)

    def select_rows(date_idx):
        # date_idx: DatetimeIndex of sample dates
        row_idx = date_to_pos.loc[date_idx].to_numpy()
        # rows in expanded panel
        exp = (row_idx[:, None] * N_TK + np.arange(N_TK)[None, :]).reshape(-1)
        return exp

    sample_records = []  # one per test sample date (monthly aggregated later)
    fold_records = []

    for fold in folds:
        tr_d = fold["train_dates"]
        te_d = fold["test_dates"]
        if len(tr_d) < 30 or len(te_d) < 1:
            continue
        sw_dates = np.asarray(fold.get("train_sample_weights"))

        tr_rows = select_rows(tr_d)
        te_rows = select_rows(te_d)

        Xtr = X_full[tr_rows]
        ytr = y_full[tr_rows]
        Xte = X_full[te_rows]
        yte = y_full[te_rows]

        # replicate per-date sample weights across 8 ETFs
        sw_tr = np.repeat(sw_dates, N_TK)

        # drop NaN targets
        mtr = ~np.isnan(ytr)
        mte = ~np.isnan(yte)

        Xtr = Xtr[mtr]; ytr = ytr[mtr]; sw_tr = sw_tr[mtr]
        Xte_full = Xte.copy()
        yte_full = yte.copy()
        Xte = Xte[mte]; yte = yte[mte]
        if len(Xtr) < 50 or len(Xte) < 8:
            continue

        pp = FeaturePreprocessor()
        Xtr_z = pp.fit_transform(pd.DataFrame(Xtr, columns=feat_names),
                                 sample_weights=sw_tr).to_numpy()
        Xte_z = pp.transform(pd.DataFrame(Xte_full, columns=feat_names)).to_numpy()

        model = model_factory()
        try:
            model.fit(Xtr_z, ytr, sample_weight=sw_tr)
        except TypeError:
            model.fit(Xtr_z, ytr)
        pred_full = model.predict(Xte_z)  # length len(te_rows)

        # group by date
        # Reconstruct (date, ticker) for te_rows
        te_dates_arr = np.repeat(te_d.values, N_TK)
        te_tk_arr = np.tile(np.array(ROT), len(te_d))

        # group every 8 consecutive rows = one sample date
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

        # fold-level summary metrics
        fold_acc = []
        fold_rho = []
        for i in range(n_te):
            a = actual_mat[i]
            p = pred_mat[i]
            if np.isnan(a).any():
                continue
            fold_acc.append(int(np.nanargmax(p) == np.nanargmax(a)))
            # spearman
            if np.std(p) > 0 and np.std(a) > 0:
                rp = pd.Series(p).rank().to_numpy()
                ra = pd.Series(a).rank().to_numpy()
                rho = np.corrcoef(rp, ra)[0, 1]
                fold_rho.append(rho)
        if fold_acc:
            fold_records.append({
                "fold_id": fold["fold_id"],
                "n_samples": len(fold_acc),
                "argmax_acc": float(np.mean(fold_acc)),
                "spearman": float(np.mean(fold_rho)) if fold_rho else float("nan"),
            })

    return sample_records, fold_records


def aggregate_rotation(sample_records, df_panel):
    """Build monthly signal: last sample per calendar month → predicted argmax ticker."""
    if not sample_records:
        return None
    sr = sorted(sample_records, key=lambda r: r["date"])
    rows = []
    for r in sr:
        pred = np.array(r["pred"])
        actual = np.array(r["actual"])
        valid = ~np.isnan(actual)
        if not valid.any():
            continue
        pred_idx = int(np.nanargmax(np.where(valid, pred, -np.inf)))
        actual_idx = int(np.nanargmax(np.where(valid, actual, -np.inf)))
        # top-2
        order = np.argsort(-np.where(valid, pred, -np.inf))
        top2 = set(order[:2].tolist())
        # spearman
        if valid.sum() >= 2 and np.std(pred[valid]) > 0 and np.std(actual[valid]) > 0:
            rp = pd.Series(pred[valid]).rank().to_numpy()
            ra = pd.Series(actual[valid]).rank().to_numpy()
            rho = float(np.corrcoef(rp, ra)[0, 1])
        else:
            rho = float("nan")
        rows.append({
            "date": r["date"],
            "fold_id": r["fold_id"],
            "pred_idx": pred_idx,
            "pred_ticker": ROT[pred_idx],
            "actual_idx": actual_idx,
            "top2_correct": int(actual_idx in top2),
            "argmax_correct": int(pred_idx == actual_idx),
            "spearman": rho,
            "fwd_ret_pred_ticker": float(actual[pred_idx]),
        })
    daily_df = pd.DataFrame(rows).set_index("date").sort_index()
    daily_df["__m"] = daily_df.index.to_period("M")
    monthly = daily_df.groupby("__m").tail(1).drop(columns="__m")
    monthly.index = monthly.index.to_period("M").to_timestamp("M")
    return monthly


# Classification (E03)

def run_t1_classification(df, feature_list):
    feats = [c for c in feature_list if c in df.columns]
    print(f"  E03 features: {len(feats)}")
    splitter = ExpandingSplitter(**SPLIT_KW)
    folds = splitter.split(df.index)
    target = "TARGET_T1_winner_idx"
    sample_records = []
    fold_records = []
    train_class_dist_overall = []
    for fold in folds:
        tr = fold["train_dates"]; te = fold["test_dates"]
        if len(tr) < 30 or len(te) < 1:
            continue
        sw = np.asarray(fold["train_sample_weights"])
        Xtr = df.loc[tr, feats]; ytr = df.loc[tr, target]
        Xte = df.loc[te, feats]; yte = df.loc[te, target]
        mtr = ytr.notna(); mte = yte.notna()
        Xtr, ytr, sw = Xtr[mtr], ytr[mtr].astype(int), sw[mtr.to_numpy()]
        Xte, yte = Xte[mte], yte[mte].astype(int)
        te_used = te[mte.to_numpy()]
        if len(Xtr) < 50 or len(Xte) < 1:
            continue
        pp = FeaturePreprocessor()
        Xtr_z = pp.fit_transform(Xtr, sample_weights=sw)
        Xte_z = pp.transform(Xte)
        clf = RandomForestClassifier(
            n_estimators=200, max_depth=4, min_samples_leaf=5,
            max_features="sqrt", class_weight="balanced", random_state=0, n_jobs=-1,
        )
        clf.fit(Xtr_z.to_numpy(), ytr.to_numpy(), sample_weight=sw)
        proba = clf.predict_proba(Xte_z.to_numpy())
        # ensure full 8-class proba
        full_proba = np.zeros((len(Xte_z), N_TK))
        for j, c in enumerate(clf.classes_):
            full_proba[:, int(c)] = proba[:, j]
        pred = np.argmax(full_proba, axis=1)
        for i in range(len(te_used)):
            sample_records.append({
                "date": pd.Timestamp(te_used[i]),
                "fold_id": fold["fold_id"],
                "proba": full_proba[i].tolist(),
                "pred": int(pred[i]),
                "actual": int(yte.iloc[i]),
            })
        train_class_dist_overall.append(np.bincount(ytr.to_numpy(), minlength=N_TK))
        fold_records.append({
            "fold_id": fold["fold_id"],
            "n_samples": len(te_used),
            "acc": float((pred == yte.to_numpy()).mean()),
        })
    return sample_records, fold_records, train_class_dist_overall


def aggregate_classification(sample_records):
    if not sample_records:
        return None
    df_sr = pd.DataFrame(sample_records).sort_values("date").set_index("date")
    df_sr["__m"] = df_sr.index.to_period("M")
    monthly = df_sr.groupby("__m").tail(1).drop(columns="__m")
    monthly.index = monthly.index.to_period("M").to_timestamp("M")
    return monthly


# Drawdown (E04, E05)

def run_drawdown(df, feature_list, model_name):
    feats = [c for c in feature_list if c in df.columns]
    print(f"  {model_name} features: {len(feats)}")
    splitter = ExpandingSplitter(**SPLIT_KW)
    folds = splitter.split(df.index)
    target = "TARGET_T4_drawdown_gt_5pct"
    sample_records = []
    fold_records = []
    for fold in folds:
        tr = fold["train_dates"]; te = fold["test_dates"]
        if len(tr) < 30 or len(te) < 1:
            continue
        sw = np.asarray(fold["train_sample_weights"])
        Xtr = df.loc[tr, feats]; ytr = df.loc[tr, target]
        Xte = df.loc[te, feats]; yte = df.loc[te, target]
        mtr = ytr.notna(); mte = yte.notna()
        Xtr, ytr, sw = Xtr[mtr], ytr[mtr].astype(int), sw[mtr.to_numpy()]
        Xte, yte = Xte[mte], yte[mte].astype(int)
        te_used = te[mte.to_numpy()]
        if len(Xtr) < 50 or len(Xte) < 1:
            continue
        # class-balance reweight
        n_pos = max(int(ytr.sum()), 1)
        n_neg = max(int((1 - ytr).sum()), 1)
        ratio = n_neg / n_pos
        sw_adj = sw.copy()
        sw_adj[ytr.to_numpy() == 1] *= ratio
        pp = FeaturePreprocessor()
        Xtr_z = pp.fit_transform(Xtr, sample_weights=sw)
        Xte_z = pp.transform(Xte)
        if model_name == "histgb":
            mdl = HistGradientBoostingClassifier(
                max_iter=100, max_depth=3, learning_rate=0.1,
                min_samples_leaf=20, max_leaf_nodes=15, l2_regularization=1.0,
                random_state=0,
            )
            mdl.fit(Xtr_z.to_numpy(), ytr.to_numpy(), sample_weight=sw_adj)
        else:
            mdl = LogisticRegression(
                C=1.0, class_weight="balanced", max_iter=1000, solver="lbfgs"
            )
            mdl.fit(Xtr_z.to_numpy(), ytr.to_numpy(), sample_weight=sw)
        prob = mdl.predict_proba(Xte_z.to_numpy())[:, 1]
        for i in range(len(te_used)):
            sample_records.append({
                "date": pd.Timestamp(te_used[i]),
                "fold_id": fold["fold_id"],
                "prob": float(prob[i]),
                "actual": int(yte.iloc[i]),
            })
        fold_records.append({
            "fold_id": fold["fold_id"],
            "n_samples": len(te_used),
            "pos_rate": float(yte.mean()),
        })
    return sample_records, fold_records


def aggregate_drawdown(sample_records):
    df_sr = pd.DataFrame(sample_records).sort_values("date").set_index("date")
    df_sr["__m"] = df_sr.index.to_period("M")
    monthly = df_sr.groupby("__m").tail(1).drop(columns="__m")
    monthly.index = monthly.index.to_period("M").to_timestamp("M")
    return monthly


# Systematic 63d momentum signal (B2 in walk-forward space)

def systematic_picks(df):
    """Return per-date (rotation_ticker, fwd21_return)."""
    cols = []
    for tk in ROT:
        c = f"returns_63d__{tk}"
        if c in df.columns:
            cols.append(c)
    # Build a (D, len(cols)) matrix; pick argmax
    available_tk = [c.split("__")[1] for c in cols]
    mat = df[cols].to_numpy(dtype=float)
    mat_filled = np.where(np.isnan(mat), -np.inf, mat)
    pick_idx = np.argmax(mat_filled, axis=1)
    pick_tk = np.array([available_tk[i] for i in pick_idx])
    fwd_lookup = {tk: df[f"TARGET_FWD21_{tk}"].to_numpy() for tk in available_tk}
    fwd_ret = np.array([fwd_lookup[available_tk[pick_idx[i]]][i]
                        for i in range(len(df))])
    return pd.DataFrame({"pick": pick_tk, "fwd_ret": fwd_ret}, index=df.index)


def spy_monthly_rets(df):
    if "TARGET_FWD21_QQQ" not in df.columns:
        return None
    # SPY isn't in rotation but exists in panel
    if "TARGET_FWD21_SPY" in df.columns:
        return df["TARGET_FWD21_SPY"]
    # fallback to QQQ
    return df["TARGET_FWD21_QQQ"]


# Per-experiment driver

def metrics_for_rotation(monthly_df, df_panel, name, fold_records):
    fwd = monthly_df["fwd_ret_pred_ticker"].to_numpy()
    stats = backtest_stats(fwd)
    annual = annual_returns_from_monthly(monthly_df.index, fwd)
    acc = float(monthly_df["argmax_correct"].mean())
    top2 = float(monthly_df["top2_correct"].mean())
    rho = float(monthly_df["spearman"].mean(skipna=True))

    fold_accs = [f["argmax_acc"] for f in fold_records]
    fold_acc_std = float(np.std(fold_accs)) if fold_accs else float("nan")

    return {
        "experiment": name,
        "n_monthly": int(len(monthly_df)),
        "argmax_accuracy": acc,
        "top2_accuracy": top2,
        "mean_spearman": rho,
        "wf_cagr": stats["cagr"],
        "wf_sharpe": stats["sharpe"],
        "wf_max_dd": stats["max_dd"],
        "annual_returns": annual,
        "fold_acc_mean": float(np.mean(fold_accs)) if fold_accs else float("nan"),
        "fold_acc_std": fold_acc_std,
        "n_folds_used": len(fold_records),
    }


def run_E01(df, feature_sets):
    print("E01 Ridge MIN T2")
    feats = feature_sets["minimal"]
    sr, fr = run_regression_expanded(df, feats, lambda: Ridge(alpha=1.0))
    monthly = aggregate_rotation(sr, df)
    res = metrics_for_rotation(monthly, df, "E01_ridge_min_t2", fr)
    res["fold_records"] = fr
    res["monthly_predictions"] = [
        {"date": str(d.date()),
         "fold_id": int(row.fold_id),
         "pred_ticker": row.pred_ticker,
         "actual_idx": int(row.actual_idx),
         "argmax_correct": int(row.argmax_correct),
         "top2_correct": int(row.top2_correct),
         "spearman": float(row.spearman) if not np.isnan(row.spearman) else None,
         "fwd_ret": float(row.fwd_ret_pred_ticker)}
        for d, row in monthly.iterrows()
    ]
    return res, monthly


def run_E02(df, feature_sets):
    print("E02 HistGB CORE T2")
    feats = feature_sets["core"]
    sr, fr = run_regression_expanded(
        df, feats,
        lambda: HistGradientBoostingRegressor(
            max_iter=100, max_depth=3, learning_rate=0.1,
            min_samples_leaf=20, max_leaf_nodes=15, l2_regularization=1.0,
            random_state=0, early_stopping=True, n_iter_no_change=10,
            validation_fraction=0.15,
        ),
    )
    monthly = aggregate_rotation(sr, df)
    res = metrics_for_rotation(monthly, df, "E02_histgb_core_t2", fr)
    res["fold_records"] = fr
    res["monthly_predictions"] = [
        {"date": str(d.date()),
         "fold_id": int(row.fold_id),
         "pred_ticker": row.pred_ticker,
         "actual_idx": int(row.actual_idx),
         "argmax_correct": int(row.argmax_correct),
         "top2_correct": int(row.top2_correct),
         "spearman": float(row.spearman) if not np.isnan(row.spearman) else None,
         "fwd_ret": float(row.fwd_ret_pred_ticker)}
        for d, row in monthly.iterrows()
    ]
    return res, monthly


def run_E03(df, feature_sets):
    print("E03 RF CORE T1")
    feats = feature_sets["core"]
    sr, fr, train_dist = run_t1_classification(df, feats)
    monthly = aggregate_classification(sr)
    pred = monthly["pred"].to_numpy()
    actual = monthly["actual"].to_numpy()
    proba = np.array(monthly["proba"].tolist())
    # top2
    top2_correct = (np.argsort(-proba, axis=1)[:, :2] == actual[:, None]).any(axis=1).astype(int)
    # per-class accuracy
    per_class = {}
    for c in range(N_TK):
        mask = pred == c
        per_class[ROT[c]] = {
            "n_predicted": int(mask.sum()),
            "precision": float((actual[mask] == c).mean()) if mask.any() else None,
        }
    pred_dist = {ROT[c]: int((pred == c).sum()) for c in range(N_TK)}
    train_class_freq = np.sum(train_dist, axis=0) if train_dist else np.zeros(N_TK)
    train_freq_norm = (train_class_freq / max(train_class_freq.sum(), 1)).tolist()

    # macro F1
    from sklearn.metrics import f1_score
    macrof1 = float(f1_score(actual, pred, average="macro", labels=list(range(N_TK)),
                              zero_division=0))

    # ECE 10-bin (use top-class confidence)
    conf = proba.max(axis=1)
    correct = (pred == actual).astype(float)
    bins = np.linspace(0, 1, 11)
    ece = 0.0
    for i in range(10):
        m = (conf >= bins[i]) & (conf < bins[i + 1] if i < 9 else conf <= bins[i + 1])
        if m.sum() > 0:
            ece += (m.sum() / len(conf)) * abs(correct[m].mean() - conf[m].mean())

    # backtest: hold predicted ETF each month
    fwd_rets = np.zeros(len(monthly))
    for i, (d, row) in enumerate(monthly.iterrows()):
        tk = ROT[int(row["pred"])]
        try:
            fwd_rets[i] = df.loc[d, f"TARGET_FWD21_{tk}"]
        except KeyError:
            fwd_rets[i] = np.nan
    # use the test sample dates not month-end (the prediction date is sample date)
    # We use sample-date fwd ret already (TARGET_FWD21 is the 21-trading-day forward).
    # Actually monthly index is month-end timestamp. We need the fwd ret on the
    # actual sample date — re-derive from sample_records.
    rec_df = pd.DataFrame(sr).sort_values("date").set_index("date")
    rec_df["__m"] = rec_df.index.to_period("M")
    last = rec_df.groupby("__m").tail(1)
    fwd_rets2 = np.zeros(len(last))
    for i, (d, row) in enumerate(last.iterrows()):
        tk = ROT[int(row["pred"])]
        fwd_rets2[i] = df.loc[d, f"TARGET_FWD21_{tk}"]
    stats = backtest_stats(fwd_rets2)
    last.index = last.index.to_period("M").to_timestamp("M")
    annual = annual_returns_from_monthly(last.index, fwd_rets2)

    fold_accs = [f.get("acc") for f in fr]
    fold_acc_std = float(np.std(fold_accs)) if fold_accs else float("nan")

    res = {
        "experiment": "E03_rf_core_t1",
        "n_monthly": int(len(monthly)),
        "argmax_accuracy": float((pred == actual).mean()),
        "top2_accuracy": float(top2_correct.mean()),
        "macro_f1": macrof1,
        "ece_10bin": float(ece),
        "per_class": per_class,
        "pred_distribution": pred_dist,
        "train_class_freq_norm": train_freq_norm,
        "wf_cagr": stats["cagr"],
        "wf_sharpe": stats["sharpe"],
        "wf_max_dd": stats["max_dd"],
        "annual_returns": annual,
        "fold_acc_mean": float(np.mean(fold_accs)) if fold_accs else float("nan"),
        "fold_acc_std": fold_acc_std,
        "n_folds_used": len(fr),
        "fold_records": fr,
        "monthly_predictions": [
            {"date": str(d.date()),
             "fold_id": int(row.fold_id),
             "pred_ticker": ROT[int(row["pred"])],
             "actual_ticker": ROT[int(row["actual"])],
             "correct": int(int(row["pred"]) == int(row["actual"])),
             "fwd_ret": float(fwd_rets2[i])}
            for i, (d, row) in enumerate(last.iterrows())
        ],
    }
    return res, last, fwd_rets2


def run_drawdown_experiment(df, feature_sets, model_name, exp_id):
    print(f"{exp_id} {model_name} CORE T4 drawdown")
    feats = feature_sets["core"]
    sr, fr = run_drawdown(df, feats, model_name)
    rec_df = pd.DataFrame(sr).sort_values("date").set_index("date")
    rec_df["__m"] = rec_df.index.to_period("M")
    last = rec_df.groupby("__m").tail(1)
    # Drop the auxiliary column from the monthly snapshot.
    last = last.drop(columns="__m", errors="ignore")

    prob = last["prob"].to_numpy()
    actual = last["actual"].to_numpy()

    # binary classification metrics at threshold 0.5
    pred = (prob >= 0.5).astype(int)
    tp = int(((pred == 1) & (actual == 1)).sum())
    fp = int(((pred == 1) & (actual == 0)).sum())
    fn = int(((pred == 0) & (actual == 1)).sum())
    tn = int(((pred == 0) & (actual == 0)).sum())
    precision = tp / max(tp + fp, 1)
    recall = tp / max(tp + fn, 1)
    f1 = 2 * precision * recall / max(precision + recall, 1e-9)
    fpr = fp / max(fp + tn, 1)

    # Mode C backtest: blend with systematic momentum
    sys_picks = systematic_picks(df)
    fwd_rets = []
    sys_only = []
    for d in last.index:
        sys_row = sys_picks.loc[d]
        sys_fwd = float(sys_row["fwd_ret"])
        # Need also the fwd-21 return of SHY for drawdown shield
        shy_fwd = float(df.loc[d, "TARGET_FWD21_SHY"])
        p = float(last.loc[d, "prob"])
        if p < 0.50:
            r = sys_fwd
        elif p < 0.70:
            r = 0.6 * sys_fwd + 0.4 * shy_fwd
        else:
            r = shy_fwd
        fwd_rets.append(r)
        sys_only.append(sys_fwd)
    fwd_rets = np.array(fwd_rets)
    sys_only = np.array(sys_only)

    modec_stats = backtest_stats(fwd_rets)
    sys_stats = backtest_stats(sys_only)
    annual = annual_returns_from_monthly(last.index.to_period("M").to_timestamp("M"), fwd_rets)
    last_dt = last.copy()
    last_dt.index = last.index.to_period("M").to_timestamp("M")

    res = {
        "experiment": exp_id,
        "n_monthly": int(len(last)),
        "precision": float(precision),
        "recall": float(recall),
        "f1": float(f1),
        "fpr": float(fpr),
        "tp": tp, "fp": fp, "tn": tn, "fn": fn,
        "modec_cagr": modec_stats["cagr"],
        "modec_sharpe": modec_stats["sharpe"],
        "modec_max_dd": modec_stats["max_dd"],
        "sys_cagr": sys_stats["cagr"],
        "sys_max_dd": sys_stats["max_dd"],
        "annual_returns_modec": annual,
        "fold_records": fr,
        "monthly_predictions": [
            {"date": str(pd.Timestamp(d).date()),
             "fold_id": int(last.loc[d, "fold_id"]),
             "prob": float(last.loc[d, "prob"]),
             "actual": int(last.loc[d, "actual"]),
             "modec_ret": float(fwd_rets[i]),
             "sys_ret": float(sys_only[i])}
            for i, d in enumerate(last.index)
        ],
    }
    return res, last_dt, fwd_rets, sys_only


# Main

def main():
    out_dir = ROOT / "results/experiments"
    out_dir.mkdir(parents=True, exist_ok=True)

    df = load_panel()
    feature_sets = load_feature_sets()
    print(f"panel: {df.shape}")

    all_results = {}

    e01, e01_monthly = run_E01(df, feature_sets)
    (out_dir / "E01.json").write_text(json.dumps(e01, indent=2, default=str))
    all_results["E01"] = e01

    e02, e02_monthly = run_E02(df, feature_sets)
    (out_dir / "E02.json").write_text(json.dumps(e02, indent=2, default=str))
    all_results["E02"] = e02

    e03, e03_monthly, e03_fwd = run_E03(df, feature_sets)
    (out_dir / "E03.json").write_text(json.dumps(e03, indent=2, default=str))
    all_results["E03"] = e03

    e04, e04_monthly, e04_modec, e04_sys = run_drawdown_experiment(df, feature_sets, "histgb", "E04_histgb_core_t4")
    (out_dir / "E04.json").write_text(json.dumps(e04, indent=2, default=str))
    all_results["E04"] = e04

    e05, e05_monthly, e05_modec, e05_sys = run_drawdown_experiment(df, feature_sets, "logreg", "E05_logreg_core_t4")
    (out_dir / "E05.json").write_text(json.dumps(e05, indent=2, default=str))
    all_results["E05"] = e05

    # Build report tables ------------------------------------------------
    baselines = json.loads((ROOT / "results/baselines.json").read_text())
    B0 = baselines["B0_random"]
    B2 = baselines["B3_mom63d"]  # systematic 63d
    B1 = baselines["B1_QQQ"]

    rep = []
    rep.append("# TIER 1 REPORT")
    rep.append("")
    rep.append("Splitter: ExpandingSplitter (min_train=60mo, val=6mo, test=3mo, "
               "step=3mo, sample_every=5d, embargo=5d, halflife=36mo)")
    rep.append("")
    rep.append("## Rotation Models")
    rep.append("")
    rep.append("| Exp | Model | Features | Target | Acc | Top2 | RankCorr | "
               "WF CAGR | Sharpe | MaxDD | vs B0 | vs B2 |")
    rep.append("|---|---|---|---|---|---|---|---|---|---|---|---|")
    def fmt_pct(v): return f"{100*v:.1f}%" if v == v else "n/a"
    for ex, label in [(e01, "Ridge MIN(13) T2"), (e02, "HistGB CORE(50) T2"),
                       (e03, "RF CORE(50) T1")]:
        rep.append(f"| {ex['experiment']} | {label.split()[0]} | "
                   f"{label.split()[1]} | {label.split()[2]} | "
                   f"{fmt_pct(ex['argmax_accuracy'])} | {fmt_pct(ex['top2_accuracy'])} | "
                   f"{ex.get('mean_spearman', float('nan')):.3f} | "
                   f"{fmt_pct(ex['wf_cagr'])} | {ex['wf_sharpe']:.2f} | "
                   f"{fmt_pct(ex['wf_max_dd'])} | "
                   f"{fmt_pct(ex['argmax_accuracy'] - B0['monthly_accuracy'])} | "
                   f"{fmt_pct(ex['wf_cagr'] - B2['cagr'])} |")
    rep.append(f"| B0 | Random | n/a | n/a | {fmt_pct(B0['monthly_accuracy'])} | "
               f"~25% | 0.000 | {fmt_pct(B0['cagr'])} | {B0['sharpe_ann']:.2f} | "
               f"{fmt_pct(B0['max_dd'])} | — | — |")
    rep.append(f"| B2 | Systematic 63d | n/a | n/a | {fmt_pct(B2['monthly_accuracy'])} | "
               f"n/a | n/a | {fmt_pct(B2['cagr'])} | {B2['sharpe_ann']:.2f} | "
               f"{fmt_pct(B2['max_dd'])} | — | — |")
    rep.append(f"| B1 | QQQ buy&hold | n/a | n/a | n/a | n/a | n/a | "
               f"{fmt_pct(B1['cagr'])} | {B1['sharpe_ann']:.2f} | {fmt_pct(B1['max_dd'])} | — | — |")

    rep.append("")
    rep.append("## Drawdown Models (Mode C)")
    rep.append("")
    rep.append("| Exp | Model | Precision | Recall | F1 | FPR | "
               "ModeC CAGR | Sharpe | ModeC MaxDD | B2 MaxDD |")
    rep.append("|---|---|---|---|---|---|---|---|---|---|")
    for ex, label in [(e04, "HistGB CORE(50)"), (e05, "LogReg CORE(50)")]:
        rep.append(f"| {ex['experiment']} | {label} | "
                   f"{fmt_pct(ex['precision'])} | {fmt_pct(ex['recall'])} | "
                   f"{ex['f1']:.3f} | {fmt_pct(ex['fpr'])} | "
                   f"{fmt_pct(ex['modec_cagr'])} | {ex['modec_sharpe']:.2f} | "
                   f"{fmt_pct(ex['modec_max_dd'])} | {fmt_pct(B2['max_dd'])} |")
    rep.append(f"| B3 | Always-no-DD | n/a | 0% | 0 | 0% | "
               f"{fmt_pct(B2['cagr'])} | {B2['sharpe_ann']:.2f} | {fmt_pct(B2['max_dd'])} | "
               f"{fmt_pct(B2['max_dd'])} |")

    rep.append("")
    rep.append("## Annual Returns - Rotation")
    rep.append("")
    years = sorted(set(list(e01["annual_returns"].keys()) +
                       list(e02["annual_returns"].keys()) +
                       list(e03["annual_returns"].keys())))
    rep.append("| Year | E01 | E02 | E03 |")
    rep.append("|---|---|---|---|")
    for y in years:
        rep.append(f"| {y} | {fmt_pct(e01['annual_returns'].get(y, float('nan')))} | "
                   f"{fmt_pct(e02['annual_returns'].get(y, float('nan')))} | "
                   f"{fmt_pct(e03['annual_returns'].get(y, float('nan')))} |")

    rep.append("")
    rep.append("## Annual Returns - Drawdown Mode C")
    rep.append("")
    years_d = sorted(set(list(e04["annual_returns_modec"].keys()) +
                         list(e05["annual_returns_modec"].keys())))
    rep.append("| Year | E04 ModeC | E05 ModeC |")
    rep.append("|---|---|---|")
    for y in years_d:
        rep.append(f"| {y} | {fmt_pct(e04['annual_returns_modec'].get(y, float('nan')))} | "
                   f"{fmt_pct(e05['annual_returns_modec'].get(y, float('nan')))} |")

    # Q&A section ---------------------------------------------------------
    rep.append("")
    rep.append("## Q&A")
    rep.append("")
    best_rot = max([e01, e02, e03], key=lambda r: r["argmax_accuracy"])
    gap_b0 = best_rot["argmax_accuracy"] - B0["monthly_accuracy"]
    rep.append(f"**Q1 (beat B0 by >5%?):** Best rotation = {best_rot['experiment']} at "
               f"{fmt_pct(best_rot['argmax_accuracy'])} accuracy "
               f"vs B0 {fmt_pct(B0['monthly_accuracy'])}, gap = {fmt_pct(gap_b0)}. "
               f"{'YES' if gap_b0 > 0.05 else 'NO'}.")

    best_cagr = max([e01, e02, e03], key=lambda r: r["wf_cagr"])
    cagr_gap = best_cagr["wf_cagr"] - B2["cagr"]
    sharpe_gap = best_cagr["wf_sharpe"] - B2["sharpe_ann"]
    rep.append(f"**Q2 (beat B2 CAGR meaningfully?):** Best CAGR = {best_cagr['experiment']} "
               f"{fmt_pct(best_cagr['wf_cagr'])} vs B2 {fmt_pct(B2['cagr'])} "
               f"(gap {fmt_pct(cagr_gap)}, sharpe gap {sharpe_gap:+.2f}). "
               f"{'YES (meaningful)' if cagr_gap > 0.02 or sharpe_gap > 0.15 else 'NO (within noise)'}.")

    rep.append(f"**Q3 (drawdown signal?):** E04 recall={fmt_pct(e04['recall'])}, "
               f"precision={fmt_pct(e04['precision'])}, "
               f"E05 recall={fmt_pct(e05['recall'])}, precision={fmt_pct(e05['precision'])}.")
    # Check March 2020 and 2022 drawdowns
    def check_specific_months(monthly_df, prob_col="prob"):
        flagged = []
        for label, target in [("2020-03", "2020-03"),
                              ("2022-04", "2022-04"), ("2022-09", "2022-09")]:
            try:
                ts = pd.Timestamp(target)
                slice_ = monthly_df[(monthly_df.index.year == ts.year)
                                    & (monthly_df.index.month == ts.month)]
                if len(slice_):
                    flagged.append(f"{label}: prob={slice_[prob_col].iloc[0]:.2f} actual={int(slice_['actual'].iloc[0])}")
            except Exception:
                pass
        return flagged
    rep.append("E04 hits: " + "; ".join(check_specific_months(e04_monthly)))
    rep.append("E05 hits: " + "; ".join(check_specific_months(e05_monthly)))

    dd_red_e04 = (B2["max_dd"] - e04["modec_max_dd"])  # positive = improved
    rep.append(f"**Q4 (Mode C reduces MaxDD?):** "
               f"E04 ModeC MaxDD={fmt_pct(e04['modec_max_dd'])} vs B2 "
               f"{fmt_pct(B2['max_dd'])} (improvement {100*(e04['modec_max_dd']-B2['max_dd']):+.1f}pp), "
               f"CAGR {fmt_pct(e04['modec_cagr'])} vs B2 {fmt_pct(B2['cagr'])}. "
               f"E05 ModeC MaxDD={fmt_pct(e05['modec_max_dd'])} CAGR={fmt_pct(e05['modec_cagr'])}.")

    e04_e05_gap = e04["f1"] - e05["f1"]
    rep.append(f"**Q5 (linear vs nonlinear drawdown?):** E04 F1={e04['f1']:.3f} "
               f"vs E05 F1={e05['f1']:.3f}, gap={e04_e05_gap:+.3f}. "
               f"{'NONLINEAR (E04 >> E05)' if e04_e05_gap > 0.10 else 'LINEAR-LIKE (E05 ≈ E04)'}.")

    rep.append(f"**Q6 (E03 prediction distribution):** {e03['pred_distribution']}. "
               f"Train freq: {[round(f,3) for f in e03['train_class_freq_norm']]}.")

    rep.append(f"**Q7 (cross-sectional helps?):** "
               f"E01 spearman={e01['mean_spearman']:.3f}, "
               f"E02 spearman={e02['mean_spearman']:.3f}, "
               f"E03 (no expansion) accuracy={fmt_pct(e03['argmax_accuracy'])}.")

    rep.append(f"**Q8 (fold consistency):** Best model = {best_rot['experiment']}, "
               f"fold acc mean={fmt_pct(best_rot['fold_acc_mean'])} "
               f"std={best_rot['fold_acc_std']:.3f} across {best_rot['n_folds_used']} folds.")

    (ROOT / "results/TIER1_REPORT.md").write_text("\n".join(rep))
    print("wrote TIER1_REPORT.md")

    # Verdict -------------------------------------------------------------
    rotation_signal = gap_b0 > 0.05
    cagr_meaningful = cagr_gap > 0.02 or sharpe_gap > 0.15
    dd_value = (e04["modec_max_dd"] - B2["max_dd"] > 0.05) and (e04["modec_cagr"] > B2["cagr"] - 0.02)
    dd_value_e05 = (e05["modec_max_dd"] - B2["max_dd"] > 0.05) and (e05["modec_cagr"] > B2["cagr"] - 0.02)

    if rotation_signal and (cagr_meaningful or dd_value or dd_value_e05):
        verdict = "PROCEED_ALL"
        body = (f"Best rotation model {best_rot['experiment']} beats B0 by "
                f"{100*gap_b0:.1f}pp accuracy. Drawdown side also shows value "
                f"(E04 ModeC MaxDD {100*e04['modec_max_dd']:.1f}% vs B2 "
                f"{100*B2['max_dd']:.1f}%). Proceed to Tier 2 with both targets.")
    elif (dd_value or dd_value_e05):
        verdict = "PROCEED_DRAWDOWN_ONLY"
        body = (f"Rotation models show no meaningful edge over B0/B2 (best gap "
                f"{100*gap_b0:.1f}pp acc, {100*cagr_gap:+.1f}pp CAGR), but the "
                f"drawdown shield reduces MaxDD materially "
                f"(E04 {100*e04['modec_max_dd']:.1f}%, "
                f"E05 {100*e05['modec_max_dd']:.1f}% vs B2 {100*B2['max_dd']:.1f}%). "
                f"Proceed to Tier 2 focused on drawdown only.")
    else:
        verdict = "STOP"
        body = (f"No rotation model beats B0 by >5pp (best gap {100*gap_b0:.1f}pp). "
                f"No drawdown model materially reduces MaxDD with acceptable CAGR "
                f"(E04 ModeC: MaxDD {100*e04['modec_max_dd']:.1f}% / CAGR "
                f"{100*e04['modec_cagr']:.1f}%; E05: MaxDD {100*e05['modec_max_dd']:.1f}% / "
                f"CAGR {100*e05['modec_cagr']:.1f}%). The systematic 63d momentum "
                f"strategy operates without an AI layer at this frequency.")

    (ROOT / "results/TIER1_VERDICT.md").write_text(
        f"# TIER 1 VERDICT: {verdict}\n\n{body}\n"
    )
    print("VERDICT:", verdict)
    print("wrote TIER1_VERDICT.md")


if __name__ == "__main__":
    main()
