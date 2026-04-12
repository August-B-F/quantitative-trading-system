# ARCHIVED: feature-importance exploration — results in FEATURE_IMPORTANCE_REPORT.md
"""Part A — Regime classifier internals.

A1: SHAP values across walk-forward folds (top features, mean |SHAP|, direction)
A2: Per-regime feature drivers (top 5 features pushing toward each quadrant)
A3: Feature stability across early/middle/late periods (rank correlations)
A4: Feature reduction — retrain with top-N features, report WF accuracy
A5: Ablation — remove top-1, top-2, top-3 features, retrain

Output: results/FEATURE_IMPORTANCE_REPORT.md
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from scipy.stats import spearmanr
from sklearn.ensemble import HistGradientBoostingClassifier

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from model.walk_forward import ExpandingSplitter  # noqa: E402
from model.preprocessing import FeaturePreprocessor  # noqa: E402

OUT = ROOT / "results"
OUT.mkdir(exist_ok=True)

REGIME_CLASSES = ["regime_hg_li", "regime_hg_hi", "regime_lg_li", "regime_lg_hi_stagflation"]
REGIME_LABELS = ["HG/LI (tech)", "HG/HI (energy)", "LG/LI (defensive)", "LG/HI (stagflation)"]
SPLIT_KW = dict(
    min_train_months=60, val_months=6, test_months=3, step_months=3,
    sample_every_n_days=5, embargo_days=5, target_horizon=21,
    decay_halflife_months=36,
)
TARGET_COL = "TARGET_TREG_growth_inflation_fwd21"


def make_clf():
    return HistGradientBoostingClassifier(
        max_iter=200, max_depth=4, learning_rate=0.05,
        min_samples_leaf=20, l2_regularization=1.0, random_state=0,
    )


def fit_predict_fold(df, feats, fold):
    tr = fold["train_dates"]; te = fold["test_dates"]
    if len(tr) < 30 or len(te) < 1:
        return None
    sw = np.asarray(fold["train_sample_weights"])
    Xtr = df.loc[tr, feats]; ytr_raw = df.loc[tr, TARGET_COL]
    Xte = df.loc[te, feats]; yte_raw = df.loc[te, TARGET_COL]
    mtr = ytr_raw.notna(); mte = yte_raw.notna()
    if mtr.sum() < 50 or mte.sum() < 1:
        return None
    Xtr = Xtr[mtr]; sw = sw[mtr.to_numpy()]
    cls_to_idx = {c: i for i, c in enumerate(REGIME_CLASSES)}
    ytr = ytr_raw[mtr].map(cls_to_idx).astype(int).to_numpy()
    yte = yte_raw[mte].map(cls_to_idx).astype(int).to_numpy()
    Xte_used = Xte[mte]
    pp = FeaturePreprocessor()
    Xtr_z = pp.fit_transform(Xtr, sample_weights=sw)
    Xte_z = pp.transform(Xte_used)
    clf = make_clf()
    clf.fit(Xtr_z.to_numpy(), ytr, sample_weight=sw)
    pred = clf.predict(Xte_z.to_numpy())
    acc = float((pred == yte).mean())
    return dict(clf=clf, Xtr_z=Xtr_z, Xte_z=Xte_z, ytr=ytr, yte=yte, pred=pred, acc=acc, te_dates=Xte_used.index)


def walkforward_accuracy(df, feats, folds):
    accs = []
    for f in folds:
        r = fit_predict_fold(df, feats, f)
        if r is not None:
            accs.append(r["acc"])
    return float(np.mean(accs)) if accs else float("nan")


def main():
    print("Loading panel & features…")
    df = pd.read_parquet(ROOT / "data/features/master_panel.parquet")
    feature_sets = yaml.safe_load(open(ROOT / "configs/feature_sets.yaml"))
    feats_full = [c for c in feature_sets["core"] if c in df.columns]
    print(f"  panel {df.shape}  CORE feats {len(feats_full)}")

    splitter = ExpandingSplitter(**SPLIT_KW)
    folds = splitter.split(df.index)
    print(f"  folds: {len(folds)}")

    # ----- A1: SHAP per fold -----
    print("\n[A1] SHAP across folds…")
    import shap

    full_acc_per_fold = []
    shap_sums = np.zeros((len(REGIME_CLASSES), len(feats_full)), dtype=float)
    shap_signed_sums = np.zeros((len(REGIME_CLASSES), len(feats_full)), dtype=float)
    shap_counts = np.zeros(len(feats_full), dtype=float)
    fold_period_imp = {"early": [], "mid": [], "late": []}

    for fi, fold in enumerate(folds):
        r = fit_predict_fold(df, feats_full, fold)
        if r is None:
            continue
        full_acc_per_fold.append(r["acc"])
        try:
            expl = shap.TreeExplainer(r["clf"])
            sv = expl.shap_values(r["Xte_z"].to_numpy())
        except Exception as e:
            print(f"    fold {fi}: TreeExplainer failed ({e}); skipping SHAP")
            continue
        # sv shape: (n, F, C) for newer SHAP, or list of (n, F) per class for older
        if isinstance(sv, list):
            arrs = sv  # list of len C
        else:
            arrs = [sv[:, :, c] for c in range(sv.shape[-1])]
        # Map class index in clf.classes_ to global regime idx
        for ci_local, c_glob in enumerate(r["clf"].classes_):
            a = arrs[ci_local]
            shap_sums[int(c_glob)] += np.abs(a).mean(axis=0)
            shap_signed_sums[int(c_glob)] += a.mean(axis=0)
        shap_counts += 1
        # Period bucket by median test date
        med = pd.Timestamp(np.array(r["te_dates"])[len(r["te_dates"]) // 2])
        bucket = "early" if med.year <= 2015 else ("mid" if med.year <= 2020 else "late")
        # Per-fold importance: mean across classes of mean|SHAP|
        per_feat = np.mean(np.stack([np.abs(a).mean(axis=0) for a in arrs]), axis=0)
        fold_period_imp[bucket].append(per_feat)

    n_used = max(int(shap_counts.max()), 1)
    mean_abs_shap_per_class = shap_sums / n_used  # (C, F)
    mean_signed_per_class = shap_signed_sums / n_used  # (C, F)
    mean_abs_overall = mean_abs_shap_per_class.mean(axis=0)  # (F,)
    full_wf_acc = float(np.mean(full_acc_per_fold)) if full_acc_per_fold else float("nan")
    print(f"  full WF accuracy: {full_wf_acc:.4f}")

    # Top 15
    order_overall = np.argsort(-mean_abs_overall)
    top15 = order_overall[:15]
    direction_label = {0: "→HG/LI", 1: "→HG/HI", 2: "→LG/LI", 3: "→LG/HI"}
    a1_rows = []
    for j in top15:
        # Direction = which regime has the largest positive mean signed SHAP?
        signed_per = mean_signed_per_class[:, j]
        pushed_to = int(np.argmax(signed_per))
        # Sign of correlation between feature and that class push (rough): use signed value
        direction_sign = "higher value pushes" if signed_per[pushed_to] > 0 else "lower value pushes"
        a1_rows.append({
            "feature": feats_full[j],
            "mean_abs_shap": float(mean_abs_overall[j]),
            "primary_regime": REGIME_LABELS[pushed_to],
            "direction": direction_sign,
            "per_class_signed": [float(x) for x in signed_per],
        })

    # ----- A2: Per-regime top 5 -----
    print("\n[A2] Per-regime feature drivers…")
    a2 = {}
    for ci in range(len(REGIME_CLASSES)):
        # Rank by mean signed SHAP for THAT class (most positive = pushes toward it)
        signed = mean_signed_per_class[ci]
        order = np.argsort(-signed)[:5]
        a2[REGIME_LABELS[ci]] = [
            {"feature": feats_full[j], "signed_shap": float(signed[j]),
             "abs_shap": float(mean_abs_shap_per_class[ci, j])}
            for j in order
        ]

    # ----- A3: Feature stability across periods -----
    print("\n[A3] Feature stability…")
    period_imp = {}
    for k, lst in fold_period_imp.items():
        period_imp[k] = np.mean(np.stack(lst), axis=0) if lst else np.full(len(feats_full), np.nan)
    a3_corr = {}
    for k1, k2 in [("early", "mid"), ("mid", "late"), ("early", "late")]:
        v1 = period_imp[k1]; v2 = period_imp[k2]
        if np.all(np.isnan(v1)) or np.all(np.isnan(v2)):
            a3_corr[f"{k1}_{k2}"] = float("nan")
        else:
            rho, _ = spearmanr(v1, v2)
            a3_corr[f"{k1}_{k2}"] = float(rho)

    # ----- A4: Feature reduction -----
    print("\n[A4] Feature reduction…")
    a4_rows = [{"n": len(feats_full), "label": f"All ({len(feats_full)})", "acc": full_wf_acc}]
    for n in [15, 10, 7, 5, 3]:
        sub = [feats_full[j] for j in order_overall[:n]]
        acc = walkforward_accuracy(df, sub, folds)
        a4_rows.append({"n": n, "label": f"Top {n}", "acc": acc, "features": sub})
        print(f"  top {n:2d}: acc={acc:.4f}")

    # Find min set above 63%
    min_set = None
    for row in a4_rows[::-1]:
        if row["acc"] >= 0.63:
            min_set = row
            break

    # ----- A5: Ablation -----
    print("\n[A5] Ablation…")
    a5_rows = [{"removed": "(none)", "acc": full_wf_acc, "delta_pp": 0.0}]
    for k in [1, 2, 3]:
        remove = [feats_full[j] for j in order_overall[:k]]
        sub = [f for f in feats_full if f not in remove]
        acc = walkforward_accuracy(df, sub, folds)
        delta = (acc - full_wf_acc) * 100
        a5_rows.append({"removed": ", ".join(remove), "n_remaining": len(sub),
                        "acc": acc, "delta_pp": float(delta)})
        print(f"  remove top {k}: acc={acc:.4f}  d={delta:+.2f}pp")

    # ----- Write report -----
    def fmt(v): return "n/a" if v is None or v != v else f"{v:.4f}"
    lines = []
    lines.append("# FEATURE IMPORTANCE REPORT — Regime Classifier Internals\n")
    lines.append(f"Walk-forward HistGB regime classifier on CORE feature set ({len(feats_full)} features).")
    lines.append(f"Full WF accuracy: **{full_wf_acc:.4f}** across {len(full_acc_per_fold)} folds.\n")

    lines.append("## A1 — Top 15 features by mean |SHAP|\n")
    lines.append("| Rank | Feature | Mean abs SHAP | Primary regime push | Direction |")
    lines.append("|---|---|---|---|---|")
    for r, row in enumerate(a1_rows, 1):
        lines.append(f"| {r} | `{row['feature']}` | {row['mean_abs_shap']:.4f} | {row['primary_regime']} | {row['direction']} |")

    lines.append("\n**Sanity check vs economic theory:** expected drivers include CPI/PCE trends "
                 "(inflation axis), PMI / OECD CLI / industrial production (growth axis), and credit "
                 "spreads / VIX (cross-cutting risk).")
    suspicious = []
    for r, row in enumerate(a1_rows[:5], 1):
        f = row["feature"].lower()
        ok = any(t in f for t in ["cpi", "pce", "pmi", "cli", "ind", "credit", "spread", "vix",
                                  "nfci", "yield", "inflat", "activity", "yc_", "claims", "m2"])
        if not ok:
            suspicious.append(f"#{r}: `{row['feature']}`")
    if suspicious:
        lines.append("\n> ⚠️  Suspicious top-5 features (don't match growth/inflation/risk theme): " + ", ".join(suspicious))
    else:
        lines.append("\n> ✅ Top-5 features align with macro theory (inflation / growth / risk signals).")

    lines.append("\n## A2 — Per-regime top 5 drivers (most positive signed SHAP)\n")
    for label, rows in a2.items():
        lines.append(f"### {label}\n")
        lines.append("| Feature | Signed SHAP (push toward) | Abs SHAP |")
        lines.append("|---|---|---|")
        for row in rows:
            lines.append(f"| `{row['feature']}` | {row['signed_shap']:+.4f} | {row['abs_shap']:.4f} |")
        lines.append("")

    lines.append("## A3 — Feature stability across time periods\n")
    lines.append("Rank-correlation of per-feature mean |SHAP| between period buckets:\n")
    lines.append("| Comparison | Spearman ρ | Verdict |")
    lines.append("|---|---|---|")
    def verdict(r):
        if r != r: return "n/a"
        if r > 0.7: return "stable — consistent signals"
        if r > 0.4: return "moderate drift"
        return "unstable — different patterns by period"
    for k, v in a3_corr.items():
        lines.append(f"| {k.replace('_', ' → ')} | {fmt(v)} | {verdict(v)} |")

    lines.append("\n## A4 — Feature reduction\n")
    lines.append("| Features | Accuracy | Δ vs full |")
    lines.append("|---|---|---|")
    for row in a4_rows:
        d = (row['acc'] - full_wf_acc) * 100
        dstr = "—" if row['n'] == len(feats_full) else f"{d:+.2f}pp"
        lines.append(f"| {row['label']} | {row['acc']:.4f} | {dstr} |")
    if min_set:
        lines.append(f"\n**Minimum set above 63% accuracy:** {min_set['label']} → {min_set['acc']:.4f}")
        if "features" in min_set:
            lines.append("\nFeatures: " + ", ".join(f"`{f}`" for f in min_set["features"]))

    lines.append("\n## A5 — Ablation (remove top-N features)\n")
    lines.append("| Removed | n remaining | Accuracy | Δ vs full |")
    lines.append("|---|---|---|---|")
    for row in a5_rows:
        n_rem = row.get("n_remaining", len(feats_full))
        lines.append(f"| {row['removed']} | {n_rem} | {row['acc']:.4f} | {row['delta_pp']:+.2f}pp |")

    fragile = abs(a5_rows[1]["delta_pp"]) > 5.0
    if fragile:
        lines.append("\n> ⚠️  **Fragility flag:** removing the #1 feature drops accuracy by more than 5pp. "
                     "The classifier depends heavily on this single signal — log this for the risk section.")
    else:
        lines.append("\n> ✅ No single feature is load-bearing (removing top-1 drops accuracy by "
                     f"{a5_rows[1]['delta_pp']:+.2f}pp).")

    out_path = OUT / "FEATURE_IMPORTANCE_REPORT.md"
    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nWrote {out_path}")

    # Also dump raw JSON for downstream use
    (OUT / "feature_importance.json").write_text(json.dumps({
        "full_wf_acc": full_wf_acc,
        "n_folds_with_shap": int(n_used),
        "feats_full": feats_full,
        "mean_abs_shap_overall": mean_abs_overall.tolist(),
        "mean_abs_shap_per_class": mean_abs_shap_per_class.tolist(),
        "mean_signed_per_class": mean_signed_per_class.tolist(),
        "a1_top15": a1_rows,
        "a2_per_regime": a2,
        "a3_corrs": a3_corr,
        "a4": a4_rows,
        "a5": a5_rows,
        "order_overall": order_overall.tolist(),
    }, indent=2, default=str))


if __name__ == "__main__":
    main()
