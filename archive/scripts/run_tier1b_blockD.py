# ARCHIVED: tier1b block D — superseded by run_tier2
"""Tier 1B Block D — UNCONVENTIONAL / EXPERIMENTAL.

E-D1 Similarity-based prediction (k-NN on CORE features)
E-D2 Contrarian inversion of tier1 E03
E-D3 Signal disagreement heuristic (no ML)
E-D4 Temporal patterns (LSTM on 6-month × minimal features sequences)
E-D5 Dispersion prediction (regressor + overlay)
E-D6 Ensemble of Block A/B models
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.neighbors import NearestNeighbors

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts" / "model"))

from model.walk_forward import ExpandingSplitter  # noqa: E402
from model.preprocessing import FeaturePreprocessor  # noqa: E402
from run_tier1 import (  # noqa: E402
    ROT, N_TK, SPLIT_KW, load_panel, load_feature_sets,
    backtest_stats, annual_returns_from_monthly, systematic_picks,
)

import torch
import torch.nn as nn

OUT = ROOT / "results/experiments"
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"


# ------------------- E-D1: Similarity / k-NN prediction ------------------

def run_ED1(df, fs):
    print("E-D1 k-NN similarity prediction")
    feats = [c for c in fs["core"] if c in df.columns]
    target_cols = [f"TARGET_FWD21_{tk}" for tk in ROT]
    splitter = ExpandingSplitter(**SPLIT_KW)
    folds = splitter.split(df.index)
    records = []
    fold_records = []
    for fold in folds:
        tr = fold["train_dates"]; te = fold["test_dates"]
        if len(tr) < 30 or len(te) < 1:
            continue
        Xtr = df.loc[tr, feats]; Xte = df.loc[te, feats]
        ytr = df.loc[tr, target_cols]
        mtr = ytr.notna().all(axis=1)
        Xtr = Xtr[mtr]; ytr = ytr[mtr]
        pp = FeaturePreprocessor()
        Xtr_z = pp.fit_transform(Xtr).to_numpy()
        Xte_z = pp.transform(Xte).to_numpy()
        # L2-normalize for cosine
        def norm(x):
            n = np.linalg.norm(x, axis=1, keepdims=True)
            n[n == 0] = 1
            return x / n
        knn = NearestNeighbors(n_neighbors=5, metric="cosine", n_jobs=-1)
        knn.fit(Xtr_z)
        dist, idx = knn.kneighbors(Xte_z)
        ytr_arr = ytr.to_numpy(dtype=float)
        for i, d in enumerate(te):
            nbr = idx[i]
            winners = np.argmax(ytr_arr[nbr], axis=1)
            vote = np.bincount(winners, minlength=N_TK)
            pred = int(np.argmax(vote))
            records.append({
                "date": pd.Timestamp(d),
                "fold_id": fold["fold_id"],
                "pred": pred,
            })
        fold_records.append({"fold_id": fold["fold_id"], "n": len(te)})

    if not records:
        return None
    sr = pd.DataFrame(records).set_index("date").sort_index()
    sr["__m"] = sr.index.to_period("M")
    monthly = sr.groupby("__m").tail(1).drop(columns="__m")
    # Keep actual trading-day index; don't re-map to month-end.
    fwd = []
    correct = []
    for d, row in monthly.iterrows():
        tk = ROT[int(row["pred"])]
        try:
            fwd.append(float(df.loc[d, f"TARGET_FWD21_{tk}"]))
            actual_raw = df.loc[d, "TARGET_T1_winner_idx"]
            if pd.isna(actual_raw):
                correct.append(0)
            else:
                correct.append(int(int(row["pred"]) == int(actual_raw)))
        except KeyError:
            fwd.append(np.nan); correct.append(0)
    fwd = np.array(fwd)
    stats = backtest_stats(fwd)
    annual = annual_returns_from_monthly(monthly.index, fwd)
    acc = float(np.mean(correct))
    res = {
        "experiment": "ED1_knn_similarity",
        "n_monthly": int(len(monthly)),
        "argmax_accuracy": acc,
        "wf_cagr": stats["cagr"],
        "wf_sharpe": stats["sharpe"],
        "wf_max_dd": stats["max_dd"],
        "annual_returns": annual,
    }
    (OUT / "ED1.json").write_text(json.dumps(res, indent=2, default=str))
    print(f"  ED1: acc={acc:.3f} CAGR={stats['cagr']:.3f} Sharpe={stats['sharpe']:.2f}")
    return res


# ------------------- E-D2: Contrarian E03 inversion ----------------------

def run_ED2(df, fs):
    print("E-D2 Contrarian E03 inversion")
    e03 = json.loads((ROOT / "results/experiments/E03.json").read_text())
    mp = e03["monthly_predictions"]
    rows = []
    for m in mp:
        d = pd.Timestamp(m["date"])
        actual_tk = m["actual_ticker"]
        pred_tk = m["pred_ticker"]
        # Invert: pick worst of the 8 (heuristic — opposite of argmax)
        # We need prob vector to invert. Since E03 uses full proba, but here we only
        # have the top class, invert by picking SHY when pred is a risky ETF and vice versa.
        # Simpler: use argmin of a rank estimate — fall back to SHY when non-SHY predicted.
        inverted = "SHY" if pred_tk != "SHY" else "SOXX"
        try:
            r = float(df.loc[d, f"TARGET_FWD21_{inverted}"])
        except KeyError:
            r = np.nan
        rows.append({
            "date": d, "pred_ticker": inverted,
            "actual_ticker": actual_tk,
            "correct": int(inverted == actual_tk),
            "fwd_ret": r,
        })
    monthly = pd.DataFrame(rows).set_index("date").sort_index()
    fwd = monthly["fwd_ret"].to_numpy()
    stats = backtest_stats(fwd)
    annual = annual_returns_from_monthly(monthly.index, fwd)
    acc = float(monthly["correct"].mean())
    res = {
        "experiment": "ED2_contrarian_e03",
        "n_monthly": int(len(monthly)),
        "inverted_accuracy": acc,
        "original_e03_accuracy": e03["argmax_accuracy"],
        "wf_cagr": stats["cagr"],
        "wf_sharpe": stats["sharpe"],
        "wf_max_dd": stats["max_dd"],
        "annual_returns": annual,
    }
    (OUT / "ED2.json").write_text(json.dumps(res, indent=2, default=str))
    print(f"  ED2: inv_acc={acc:.3f} (orig E03={e03['argmax_accuracy']:.3f}) "
          f"CAGR={stats['cagr']:.3f}")
    return res


# ------------------- E-D3: Signal disagreement heuristic -----------------

def run_ED3(df, fs):
    print("E-D3 Signal disagreement heuristic")
    avail = [tk for tk in ROT if f"returns_63d__{tk}" in df.columns]
    # Signal 1: 63d momentum
    mom63 = df[[f"returns_63d__{tk}" for tk in avail]].to_numpy(dtype=float)
    # Signal 2: 126d momentum (where available)
    avail126 = [tk for tk in avail if f"returns_126d__{tk}" in df.columns]
    mom126 = df[[f"returns_126d__{tk}" for tk in avail126]].to_numpy(dtype=float)
    # Signal 3: vol-adjusted momentum
    # use quality_voladj_mom_126d__{tk}
    va_cols = [f"quality_voladj_mom_126d__{tk}" for tk in avail
               if f"quality_voladj_mom_126d__{tk}" in df.columns]
    va_tks = [c.split("__")[-1] for c in va_cols]
    va_mom = df[va_cols].to_numpy(dtype=float)
    # Signal 4: regime-implied ETF
    reg_col = "TARGET_TREG_growth_inflation_fwd21"  # not available at inference time — use CURRENT regime features
    reg_cur = df[["regime_growth_inflation__regime_hg_li",
                  "regime_growth_inflation__regime_hg_hi",
                  "regime_growth_inflation__regime_lg_li",
                  "regime_growth_inflation__regime_lg_hi_stagflation"]].to_numpy(dtype=float)
    reg_to_tk = {0: "SOXX", 1: "XLE", 2: "SHY", 3: "GLD"}

    rows = []
    for i, d in enumerate(df.index):
        mom63_pick = avail[int(np.nanargmax(np.where(np.isnan(mom63[i]), -np.inf, mom63[i])))]
        try:
            mom126_pick = avail126[int(np.nanargmax(np.where(np.isnan(mom126[i]), -np.inf, mom126[i])))]
        except (ValueError, IndexError):
            mom126_pick = mom63_pick
        try:
            va_pick = va_tks[int(np.nanargmax(np.where(np.isnan(va_mom[i]), -np.inf, va_mom[i])))]
        except (ValueError, IndexError):
            va_pick = mom63_pick
        if not np.isnan(reg_cur[i]).all():
            rg_pick = reg_to_tk[int(np.nanargmax(reg_cur[i]))]
        else:
            rg_pick = mom63_pick
        picks = [mom63_pick, mom126_pick, va_pick, rg_pick]
        # Agreement
        from collections import Counter
        top, count = Counter(picks).most_common(1)[0]
        score = count / 4.0
        # Mode: follow mom63 (systematic) but if agreement<0.5 go to SHY
        chosen = mom63_pick
        if score < 0.5:
            chosen = "SHY"
        try:
            r = float(df.loc[d, f"TARGET_FWD21_{chosen}"])
        except KeyError:
            r = np.nan
        rows.append({"date": d, "score": score, "pick": chosen, "fwd_ret": r})

    daily = pd.DataFrame(rows).set_index("date")
    daily["__m"] = daily.index.to_period("M")
    monthly = daily.groupby("__m").tail(1).drop(columns="__m")
    monthly.index = monthly.index.to_period("M").to_timestamp("M")
    # Restrict to walk-forward test window (from 2010+) to match B2
    monthly = monthly[monthly.index >= pd.Timestamp("2010-01-01")]
    fwd = monthly["fwd_ret"].to_numpy()
    stats = backtest_stats(fwd)
    annual = annual_returns_from_monthly(monthly.index, fwd)
    res = {
        "experiment": "ED3_signal_disagreement",
        "n_monthly": int(len(monthly)),
        "mean_agreement": float(monthly["score"].mean()),
        "wf_cagr": stats["cagr"],
        "wf_sharpe": stats["sharpe"],
        "wf_max_dd": stats["max_dd"],
        "annual_returns": annual,
        "pick_distribution": monthly["pick"].value_counts().to_dict(),
    }
    (OUT / "ED3.json").write_text(json.dumps(res, indent=2, default=str))
    print(f"  ED3: CAGR={stats['cagr']:.3f} Sharpe={stats['sharpe']:.2f} "
          f"mean_agree={res['mean_agreement']:.2f}")
    return res


# ------------------- E-D4: Temporal LSTM ---------------------------------

class TinyLSTM(nn.Module):
    def __init__(self, in_dim, hidden=16, dropout=0.3):
        super().__init__()
        self.lstm = nn.LSTM(in_dim, hidden, batch_first=True)
        self.drop = nn.Dropout(dropout)
        self.out = nn.Linear(hidden, 1)

    def forward(self, x):
        h, _ = self.lstm(x)
        h = h[:, -1, :]
        return self.out(self.drop(h)).squeeze(-1)


def run_ED4(df, fs):
    print("E-D4 LSTM on 6-month minimal sequences")
    feats_min = [c for c in fs["minimal"] if c in df.columns]
    # Build sequences: for each date, take last 126 trading days at monthly stride
    # (126 days = ~6 months, 21 per month → 6 steps per sample)
    seq_len = 6
    stride = 21
    lookback = seq_len * stride
    n_feat = len(feats_min)
    print(f"  features: {n_feat}, seq_len: {seq_len}, lookback: {lookback}d")

    # Get feature matrix
    X_mat = df[feats_min].to_numpy(dtype=float)
    # Build (n_dates - lookback, seq_len, n_feat)
    n_dates = len(df)
    # Targets per ETF fwd21
    y_mat = df[[f"TARGET_FWD21_{tk}" for tk in ROT]].to_numpy(dtype=float)

    splitter = ExpandingSplitter(**SPLIT_KW)
    folds = splitter.split(df.index)
    date_to_pos = pd.Series(np.arange(n_dates), index=df.index)

    def build_seq(pos):
        # last seq_len timesteps, stride 21
        idxs = [pos - stride * (seq_len - 1 - k) for k in range(seq_len)]
        if min(idxs) < 0:
            return None
        return X_mat[idxs]

    sample_records = []
    fold_records = []
    for fold in folds:
        tr = fold["train_dates"]; te = fold["test_dates"]
        if len(tr) < 30 or len(te) < 1:
            continue
        sw_d = np.asarray(fold["train_sample_weights"])
        tr_pos = date_to_pos.loc[tr].to_numpy()
        te_pos = date_to_pos.loc[te].to_numpy()

        # Build train sequences & targets (per ETF cross-sectional)
        Xtr_seq = []
        ytr_val = []
        sw_tr = []
        for idx, p in enumerate(tr_pos):
            s = build_seq(p)
            if s is None or np.isnan(s).any():
                continue
            for j in range(N_TK):
                if np.isnan(y_mat[p, j]):
                    continue
                Xtr_seq.append(s)
                ytr_val.append(y_mat[p, j])
                sw_tr.append(sw_d[idx])
        if len(Xtr_seq) < 100:
            continue
        Xtr_arr = np.stack(Xtr_seq)  # (N, seq_len, n_feat)
        ytr_arr = np.array(ytr_val, dtype=np.float32)
        sw_arr = np.array(sw_tr, dtype=np.float32)

        # Standardize per-feature across training
        mu = Xtr_arr.reshape(-1, n_feat).mean(axis=0)
        sd = Xtr_arr.reshape(-1, n_feat).std(axis=0) + 1e-6
        Xtr_arr = (Xtr_arr - mu) / sd

        torch.manual_seed(0)
        model = TinyLSTM(n_feat, hidden=16, dropout=0.3).to(DEVICE)
        opt = torch.optim.Adam(model.parameters(), lr=1e-3, weight_decay=1e-5)
        Xtr_t = torch.tensor(Xtr_arr, dtype=torch.float32, device=DEVICE)
        ytr_t = torch.tensor(ytr_arr, dtype=torch.float32, device=DEVICE)
        sw_t = torch.tensor(sw_arr, dtype=torch.float32, device=DEVICE)
        n = len(Xtr_t)
        epochs = 20
        batch = 64
        for ep in range(epochs):
            order = np.random.permutation(n)
            model.train()
            for i in range(0, n, batch):
                b = order[i:i + batch]
                pred = model(Xtr_t[b])
                loss = (sw_t[b] * (pred - ytr_t[b]) ** 2).mean()
                opt.zero_grad(); loss.backward(); opt.step()

        # Predict on test
        model.eval()
        for p in te_pos:
            s = build_seq(p)
            if s is None or np.isnan(s).any():
                continue
            s_n = (s - mu) / sd
            # 8 copies for 8 ETFs — since target is per-ETF,
            # but features are shared → model predicts single value.
            # Instead, we predict once per date and use that as pred for ALL ETFs,
            # then pick the actual argmax winner based on prediction ranking.
            # But with shared features the model can't differentiate → we need
            # to concat a one-hot ETF indicator. For now, rank by actual:
            # this wouldn't predict winners, just predict avg fwd return.
            # Instead: predict next-month avg return and threshold → pick top momentum.
            with torch.no_grad():
                pred_avg = float(model(torch.tensor(s_n[None], dtype=torch.float32, device=DEVICE)))
            # Fallback: use systematic mom63 pick as rotation, scaled by pred_avg sign
            # (just record pred_avg; evaluate via sign correlation)
            sample_records.append({
                "date": pd.Timestamp(df.index[p]),
                "fold_id": fold["fold_id"],
                "pred_avg": pred_avg,
                "actual_mean": float(np.nanmean(y_mat[p])),
            })
        fold_records.append({"fold_id": fold["fold_id"], "n": len(te)})

    if not sample_records:
        return None
    sr = pd.DataFrame(sample_records).set_index("date").sort_index()
    sr["__m"] = sr.index.to_period("M")
    monthly = sr.groupby("__m").tail(1).drop(columns="__m")
    # Sign correlation — how well does pred_avg predict actual_mean?
    valid = monthly.dropna()
    if len(valid) < 5:
        return None
    corr = float(np.corrcoef(valid["pred_avg"], valid["actual_mean"])[0, 1])
    sign_acc = float((np.sign(valid["pred_avg"]) == np.sign(valid["actual_mean"])).mean())
    # Overlay on systematic: if pred_avg < 0, hold SHY. Use trading-day index.
    sys_pick = systematic_picks(df)
    fwd = []
    for d, row in monthly.iterrows():
        pred = float(row["pred_avg"])
        try:
            tk = sys_pick.loc[d, "pick"] if pred > 0 else "SHY"
            fwd.append(float(df.loc[d, f"TARGET_FWD21_{tk}"]))
        except KeyError:
            fwd.append(np.nan)
    fwd = np.array(fwd)
    stats = backtest_stats(fwd)
    annual = annual_returns_from_monthly(monthly.index, fwd)
    res = {
        "experiment": "ED4_lstm_temporal",
        "n_monthly": int(len(monthly)),
        "pred_vs_actual_corr": corr,
        "sign_accuracy": sign_acc,
        "wf_cagr": stats["cagr"],
        "wf_sharpe": stats["sharpe"],
        "wf_max_dd": stats["max_dd"],
        "annual_returns": annual,
    }
    (OUT / "ED4.json").write_text(json.dumps(res, indent=2, default=str))
    print(f"  ED4: corr={corr:.3f} sign_acc={sign_acc:.3f} CAGR={stats['cagr']:.3f}")
    return res


# ------------------- E-D5: Dispersion prediction -------------------------

def run_ED5(df, fs):
    print("E-D5 Dispersion prediction + overlay")
    # Target: cross-sectional std of 21d forward returns
    yall = df[[f"TARGET_FWD21_{tk}" for tk in ROT]].to_numpy(dtype=float)
    disp = np.nanstd(yall, axis=1)
    df2 = df.copy()
    df2["_disp"] = disp
    feats = [c for c in fs["core"] if c in df2.columns]

    splitter = ExpandingSplitter(**SPLIT_KW)
    folds = splitter.split(df2.index)
    records = []
    for fold in folds:
        tr = fold["train_dates"]; te = fold["test_dates"]
        sw = np.asarray(fold["train_sample_weights"])
        Xtr = df2.loc[tr, feats]; ytr = df2.loc[tr, "_disp"]
        Xte = df2.loc[te, feats]; yte = df2.loc[te, "_disp"]
        mtr = ytr.notna(); mte = yte.notna()
        Xtr, ytr, sw = Xtr[mtr], ytr[mtr], sw[mtr.to_numpy()]
        Xte, yte = Xte[mte], yte[mte]
        te_used = te[mte.to_numpy()]
        if len(Xtr) < 50 or len(Xte) < 1:
            continue
        pp = FeaturePreprocessor()
        Xtr_z = pp.fit_transform(Xtr, sample_weights=sw).to_numpy()
        Xte_z = pp.transform(Xte).to_numpy()
        mdl = HistGradientBoostingRegressor(
            max_iter=200, max_depth=4, learning_rate=0.05,
            min_samples_leaf=20, random_state=0,
        )
        mdl.fit(Xtr_z, ytr.to_numpy(), sample_weight=sw)
        pred = mdl.predict(Xte_z)
        for i, d in enumerate(te_used):
            records.append({
                "date": pd.Timestamp(d),
                "fold_id": fold["fold_id"],
                "pred_disp": float(pred[i]),
                "actual_disp": float(yte.iloc[i]),
            })
    if not records:
        return None
    sr = pd.DataFrame(records).set_index("date").sort_index()
    sr["__m"] = sr.index.to_period("M")
    monthly = sr.groupby("__m").tail(1).drop(columns="__m")
    # Keep trading-day index.

    # Metrics
    corr = float(np.corrcoef(monthly["pred_disp"], monthly["actual_disp"])[0, 1])
    # Overlay: if predicted dispersion < median, hold QQQ; else follow systematic
    sys_pick = systematic_picks(df)
    median_pred = float(monthly["pred_disp"].median())
    fwd = []
    for d, row in monthly.iterrows():
        try:
            if float(row["pred_disp"]) < median_pred:
                tk = "QQQ"
            else:
                tk = sys_pick.loc[d, "pick"]
            fwd.append(float(df.loc[d, f"TARGET_FWD21_{tk}"]))
        except KeyError:
            fwd.append(np.nan)
    fwd = np.array(fwd)
    stats = backtest_stats(fwd)
    annual = annual_returns_from_monthly(monthly.index, fwd)
    res = {
        "experiment": "ED5_dispersion",
        "n_monthly": int(len(monthly)),
        "pred_vs_actual_corr": corr,
        "median_threshold": median_pred,
        "wf_cagr": stats["cagr"],
        "wf_sharpe": stats["sharpe"],
        "wf_max_dd": stats["max_dd"],
        "annual_returns": annual,
    }
    (OUT / "ED5.json").write_text(json.dumps(res, indent=2, default=str))
    print(f"  ED5: corr={corr:.3f} CAGR={stats['cagr']:.3f} Sharpe={stats['sharpe']:.2f}")
    return res


# ------------------- E-D6: Ensemble of everything ------------------------

def run_ED6(df, fs):
    print("E-D6 Ensemble of all rotation models (avg monthly pick returns)")
    import glob
    files = sorted(glob.glob(str(OUT / "*.json")))
    picks_by_date = {}
    contributors = []
    for f in files:
        try:
            r = json.loads(open(f).read())
        except Exception:
            continue
        mps = r.get("monthly_predictions")
        if not isinstance(mps, list):
            continue
        # Only use ones with argmax_accuracy available OR clearly rotation-producing
        if r.get("argmax_accuracy") is None and "rotation" not in r.get("experiment", "").lower():
            continue
        contributors.append(r["experiment"])
        for m in mps:
            d = m.get("date"); tk = m.get("pred_ticker")
            if d is None or tk is None:
                continue
            picks_by_date.setdefault(d, []).append(tk)
    if not picks_by_date:
        return None
    rows = []
    for d, picks in picks_by_date.items():
        from collections import Counter
        top_tk = Counter(picks).most_common(1)[0][0]
        try:
            r = float(df.loc[pd.Timestamp(d), f"TARGET_FWD21_{top_tk}"])
        except KeyError:
            r = np.nan
        rows.append({"date": pd.Timestamp(d), "pick": top_tk, "n_votes": len(picks), "fwd_ret": r})
    monthly = pd.DataFrame(rows).set_index("date").sort_index()
    monthly = monthly[monthly.index >= pd.Timestamp("2010-01-01")]
    fwd = monthly["fwd_ret"].to_numpy()
    stats = backtest_stats(fwd)
    annual = annual_returns_from_monthly(monthly.index, fwd)
    res = {
        "experiment": "ED6_ensemble",
        "contributors": contributors,
        "n_monthly": int(len(monthly)),
        "wf_cagr": stats["cagr"],
        "wf_sharpe": stats["sharpe"],
        "wf_max_dd": stats["max_dd"],
        "annual_returns": annual,
        "pick_distribution": monthly["pick"].value_counts().to_dict(),
    }
    (OUT / "ED6.json").write_text(json.dumps(res, indent=2, default=str))
    print(f"  ED6: CAGR={stats['cagr']:.3f} Sharpe={stats['sharpe']:.2f} "
          f"contributors={len(contributors)}")
    return res


def main():
    df = load_panel()
    fs = load_feature_sets()
    print(f"panel: {df.shape}")
    results = {}
    for name, fn in [("ED1", run_ED1), ("ED2", run_ED2), ("ED3", run_ED3),
                     ("ED4", run_ED4), ("ED5", run_ED5)]:
        try:
            results[name] = fn(df, fs)
        except Exception as e:
            import traceback
            print(f"{name} FAILED: {e}")
            traceback.print_exc()
            results[name] = {"error": str(e)}
    # ED6 last — reads all JSON files
    try:
        results["ED6"] = run_ED6(df, fs)
    except Exception as e:
        import traceback
        print(f"ED6 FAILED: {e}")
        traceback.print_exc()
    print("Block D done.")


if __name__ == "__main__":
    main()
