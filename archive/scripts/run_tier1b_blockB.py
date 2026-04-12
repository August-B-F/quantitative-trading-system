# ARCHIVED: tier1b block B — superseded by run_tier2
"""Tier 1B Block B — BIGGER MODELS.

E-B1: Large HistGB, EXTENDED (120), T2, cross-sectional
E-B2: MLP 2-layer (128, 64), CORE, T2, cross-sectional
E-B3: MLP 3-layer (256, 128, 64), EXTENDED, T2, cross-sectional
E-B4: Deep HistGB, ALL (~886), T2, cross-sectional
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts" / "model"))

from model.walk_forward import ExpandingSplitter  # noqa: E402
from model.preprocessing import FeaturePreprocessor  # noqa: E402
from run_tier1 import (  # noqa: E402
    ROT, N_TK, SPLIT_KW, load_panel, load_feature_sets,
    split_features_by_ticker, build_expanded_matrix,
    backtest_stats, annual_returns_from_monthly,
    aggregate_rotation, metrics_for_rotation,
)

import torch
import torch.nn as nn

OUT = ROOT / "results/experiments"
OUT.mkdir(parents=True, exist_ok=True)

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"


# ------------------------- shared regression loop -------------------------

def expanded_regression_loop(df, feature_list, model_factory, exp_id,
                             fit_is_torch=False, verbose=True):
    shared, templates = split_features_by_ticker(feature_list, df.columns)
    X_full, y_full, dates_full, tk_full, feat_names = build_expanded_matrix(df, shared, templates)
    if verbose:
        print(f"  {exp_id}: expanded {X_full.shape} shared={len(shared)} templates={len(templates)}")
    splitter = ExpandingSplitter(**SPLIT_KW)
    folds = splitter.split(df.index)
    date_to_pos = pd.Series(np.arange(len(df)), index=df.index)

    def sel(dt_idx):
        rp = date_to_pos.loc[dt_idx].to_numpy()
        return (rp[:, None] * N_TK + np.arange(N_TK)[None, :]).reshape(-1)

    sample_records = []
    fold_records = []
    for fi, fold in enumerate(folds):
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

        if fit_is_torch:
            pred_full = model_factory(Xtr_z, ytr, sw_tr, Xte_z)
        else:
            mdl = model_factory()
            try:
                mdl.fit(Xtr_z, ytr, sample_weight=sw_tr)
            except TypeError:
                mdl.fit(Xtr_z, ytr)
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
            if np.isnan(a).any() or np.isnan(p).all():
                continue
            try:
                fold_accs.append(int(np.nanargmax(p) == np.nanargmax(a)))
            except ValueError:
                continue
        if fold_accs:
            fold_records.append({"fold_id": fold["fold_id"],
                                 "argmax_acc": float(np.mean(fold_accs)),
                                 "n": len(fold_accs)})
    return sample_records, fold_records


def finalize_rotation(sample_records, fold_records, exp_id):
    monthly = aggregate_rotation(sample_records, None)
    res = metrics_for_rotation(monthly, None, exp_id, fold_records)
    res["fold_records"] = fold_records[:20]  # truncate
    (OUT / f"{exp_id}.json").write_text(json.dumps(res, indent=2, default=str))
    print(f"  {exp_id}: acc={res['argmax_accuracy']:.3f} CAGR={res['wf_cagr']:.3f} "
          f"Sharpe={res['wf_sharpe']:.2f} MaxDD={res['wf_max_dd']:.3f}")
    return res


# ------------------------- E-B1: Large HistGB EXT -------------------------

def run_EB1(df, fs):
    print("E-B1 Large HistGB EXTENDED T2")
    feats = fs["extended"]
    def factory():
        return HistGradientBoostingRegressor(
            max_iter=500, max_depth=5, learning_rate=0.05,
            min_samples_leaf=10, l2_regularization=0.5, random_state=0,
            early_stopping=True, n_iter_no_change=15, validation_fraction=0.15,
        )
    sr, fr = expanded_regression_loop(df, feats, factory, "EB1")
    return finalize_rotation(sr, fr, "EB1_large_histgb_ext_t2")


# ------------------------- MLP trainer -----------------------------------

class MLP(nn.Module):
    def __init__(self, in_dim, hidden, dropout):
        super().__init__()
        layers = []
        prev = in_dim
        for h in hidden:
            layers += [nn.Linear(prev, h), nn.ReLU(), nn.Dropout(dropout)]
            prev = h
        layers.append(nn.Linear(prev, 1))
        self.net = nn.Sequential(*layers)

    def forward(self, x):
        return self.net(x).squeeze(-1)


def train_mlp(Xtr, ytr, sw, Xte, hidden, dropout, lr=1e-3, epochs=60, batch=64,
              val_frac=0.15, patience=10, seed=0):
    torch.manual_seed(seed)
    np.random.seed(seed)
    n = len(Xtr)
    perm = np.random.permutation(n)
    n_val = max(int(n * val_frac), 1)
    val_idx = perm[:n_val]; tr_idx = perm[n_val:]
    Xtr_t = torch.tensor(Xtr[tr_idx], dtype=torch.float32, device=DEVICE)
    ytr_t = torch.tensor(ytr[tr_idx], dtype=torch.float32, device=DEVICE)
    sw_t = torch.tensor(sw[tr_idx], dtype=torch.float32, device=DEVICE)
    Xv_t = torch.tensor(Xtr[val_idx], dtype=torch.float32, device=DEVICE)
    yv_t = torch.tensor(ytr[val_idx], dtype=torch.float32, device=DEVICE)
    Xte_t = torch.tensor(Xte, dtype=torch.float32, device=DEVICE)

    model = MLP(Xtr.shape[1], hidden, dropout).to(DEVICE)
    opt = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=1e-5)
    best_val = float("inf")
    best_state = None
    bad = 0
    ntr = len(tr_idx)
    for ep in range(epochs):
        model.train()
        order = np.random.permutation(ntr)
        for i in range(0, ntr, batch):
            b = order[i:i + batch]
            xb = Xtr_t[b]; yb = ytr_t[b]; wb = sw_t[b]
            pred = model(xb)
            loss = (wb * (pred - yb) ** 2).mean()
            if torch.isnan(loss) or torch.isinf(loss):
                continue
            opt.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
        model.eval()
        with torch.no_grad():
            vp = model(Xv_t)
            vloss = ((vp - yv_t) ** 2).mean().item()
        if vloss < best_val - 1e-6:
            best_val = vloss
            best_state = {k: v.detach().clone() for k, v in model.state_dict().items()}
            bad = 0
        else:
            bad += 1
            if bad >= patience:
                break
    if best_state is not None:
        model.load_state_dict(best_state)
    model.eval()
    with torch.no_grad():
        pred = model(Xte_t).cpu().numpy()
    return pred


def run_EB2(df, fs):
    print("E-B2 MLP 2-layer CORE T2")
    feats = fs["core"]
    def factory(Xtr, ytr, sw, Xte):
        return train_mlp(Xtr, ytr, sw, Xte, hidden=[128, 64], dropout=0.3)
    sr, fr = expanded_regression_loop(df, feats, factory, "EB2", fit_is_torch=True)
    return finalize_rotation(sr, fr, "EB2_mlp_small_core_t2")


def run_EB3(df, fs):
    print("E-B3 MLP 3-layer EXTENDED T2")
    feats = fs["extended"]
    def factory(Xtr, ytr, sw, Xte):
        return train_mlp(Xtr, ytr, sw, Xte, hidden=[256, 128, 64], dropout=0.4)
    sr, fr = expanded_regression_loop(df, feats, factory, "EB3", fit_is_torch=True)
    return finalize_rotation(sr, fr, "EB3_mlp_big_ext_t2")


# ------------------------- E-B4: Deep HistGB ALL -------------------------

def build_all_features(df):
    """Return all non-target, numeric feature columns from the master panel."""
    drop_prefixes = ("TARGET_",)
    cols = [c for c in df.columns if not c.startswith(drop_prefixes)]
    # drop non-numeric
    num = df[cols].select_dtypes(include=[np.number]).columns.tolist()
    return num


def run_EB4(df, fs):
    print("E-B4 Deep HistGB ALL T2")
    feats = build_all_features(df)
    print(f"  all features: {len(feats)}")
    def factory():
        return HistGradientBoostingRegressor(
            max_iter=1000, max_depth=6, learning_rate=0.01,
            min_samples_leaf=5, l2_regularization=0.1, random_state=0,
            early_stopping=True, n_iter_no_change=20, validation_fraction=0.15,
        )
    t0 = time.time()
    sr, fr = expanded_regression_loop(df, feats, factory, "EB4")
    print(f"  EB4 training time: {time.time() - t0:.0f}s")
    return finalize_rotation(sr, fr, "EB4_deep_histgb_all_t2")


def main():
    df = load_panel()
    fs = load_feature_sets()
    print(f"panel: {df.shape}")
    results = {}
    for name, fn in [("EB1", run_EB1), ("EB2", run_EB2),
                     ("EB3", run_EB3), ("EB4", run_EB4)]:
        try:
            results[name] = fn(df, fs)
        except Exception as e:
            import traceback
            print(f"{name} FAILED: {e}")
            traceback.print_exc()
            results[name] = {"error": str(e)}
    print("Block B done.")


if __name__ == "__main__":
    main()
