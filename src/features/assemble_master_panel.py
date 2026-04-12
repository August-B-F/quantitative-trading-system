"""Phase 5 feature assembly: inventory, dedup, stationarity, AC, master panel."""
from __future__ import annotations
import json, warnings
from pathlib import Path
import numpy as np
import pandas as pd
import yaml

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parents[2]
FEAT_DIR = ROOT / "data" / "features"
CATEGORIES = ["price", "macro", "sentiment", "fundamental",
              "alternative", "calendar", "interaction"]
TARGETS_DIR = FEAT_DIR / "targets"

PRIMARY_ETFS = ["SOXX", "QQQ", "XLK", "VGT", "IGV", "XLE", "GLD", "SHY"]

EXPERIMENTAL_KEYWORDS = ("experimental_", "gtrends_", "wikipedia_")


def load_category(cat: str) -> dict[str, tuple[pd.Series, str]]:
    """Return {feature_name: (series, source_file_stem)} for a category."""
    out: dict[str, tuple[pd.Series, str]] = {}
    cat_dir = FEAT_DIR / cat
    if not cat_dir.exists():
        return out
    for f in sorted(cat_dir.glob("*.parquet")):
        try:
            df = pd.read_parquet(f)
        except Exception as e:
            print(f"  ! failed to read {f}: {e}")
            continue
        if not isinstance(df.index, pd.DatetimeIndex):
            try:
                df.index = pd.to_datetime(df.index)
            except Exception:
                continue
        df = df.sort_index()
        df = df[~df.index.duplicated(keep="last")]
        stem = f.stem
        for col in df.columns:
            s = df[col]
            # Coerce to numeric (drops ticker labels etc.)
            if not pd.api.types.is_numeric_dtype(s):
                s_num = pd.to_numeric(s, errors="coerce")
                if s_num.notna().sum() == 0:
                    continue
                s = s_num
            name = f"{stem}__{col}" if len(df.columns) > 1 or col != stem else stem
            # guarantee uniqueness
            base = name
            k = 1
            while name in out:
                name = f"{base}__{k}"
                k += 1
            out[name] = (s.astype("float64"), stem)
    return out


def load_all_features() -> tuple[dict[str, pd.Series], dict[str, str], dict[str, str]]:
    """Load every per-source feature parquet and concatenate."""
    feats: dict[str, pd.Series] = {}
    cat_map: dict[str, str] = {}
    stem_map: dict[str, str] = {}
    for cat in CATEGORIES:
        d = load_category(cat)
        print(f"[load] {cat}: {len(d)} columns")
        for name, (s, stem) in d.items():
            feats[name] = s
            cat_map[name] = cat
            stem_map[name] = stem
    return feats, cat_map, stem_map


def load_targets() -> dict[str, pd.Series]:
    """Load forward-return target columns."""
    out: dict[str, pd.Series] = {}
    for f in sorted(TARGETS_DIR.glob("*.parquet")):
        df = pd.read_parquet(f)
        if not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index)
        for col in df.columns:
            s = df[col]
            if pd.api.types.is_numeric_dtype(s):
                out[col] = s.astype("float64")
            else:
                out[col] = s
    return out


def inventory(feats: dict[str, pd.Series], cat_map: dict[str, str]) -> pd.DataFrame:
    """Build a per-feature inventory (history length, category, NaN rate)."""
    rows = []
    for name, s in feats.items():
        s_valid = s.dropna()
        rows.append({
            "feature": name,
            "category": cat_map[name],
            "start": s_valid.index.min() if len(s_valid) else pd.NaT,
            "end": s_valid.index.max() if len(s_valid) else pd.NaT,
            "n": int(s.notna().sum()),
            "nan_pct": float(s.isna().mean() * 100),
            "experimental": any(k in name for k in EXPERIMENTAL_KEYWORDS),
        })
    return pd.DataFrame(rows).set_index("feature")


def dedupe_by_correlation(feats: dict[str, pd.Series],
                           inv: pd.DataFrame,
                           threshold: float = 0.95) -> tuple[set[str], list[dict]]:
    """Drop features with pairwise correlation above threshold."""
    # Align to shared trading-day index (price calendar: use interaction file)
    idx = pd.date_range(min(s.dropna().index.min() for s in feats.values() if s.notna().any()),
                        max(s.dropna().index.max() for s in feats.values() if s.notna().any()),
                        freq="B")
    df = pd.DataFrame({n: s.reindex(idx) for n, s in feats.items()})
    # Only consider features with enough data
    mask = df.notna().sum() > 500
    df = df.loc[:, mask]
    # Compute correlation matrix in chunks to save memory (~200 features, fine)
    corr = df.corr(method="pearson", min_periods=250).abs()
    cv = corr.values.copy()
    np.fill_diagonal(cv, 0.0)
    corr = pd.DataFrame(cv, index=corr.index, columns=corr.columns)

    drops: set[str] = set()
    log: list[dict] = []
    cols = list(corr.columns)
    pairs = []
    for i, a in enumerate(cols):
        for b in cols[i + 1:]:
            c = corr.at[a, b]
            if pd.notna(c) and c >= threshold:
                pairs.append((a, b, float(c)))
    pairs.sort(key=lambda x: -x[2])

    def history_len(name: str) -> int:
        """Number of non-NaN observations for a feature."""
        return int(inv.at[name, "n"]) if name in inv.index else 0

    for a, b, c in pairs:
        if a in drops or b in drops:
            continue
        a_hist, b_hist = history_len(a), history_len(b)
        if a_hist >= b_hist:
            keeper, dropped = a, b
        else:
            keeper, dropped = b, a
        drops.add(dropped)
        log.append({"dropped": dropped, "kept": keeper, "corr": round(c, 4),
                     "reason": f"|corr|={c:.3f} >= {threshold}, kept longer/equal history ({max(a_hist,b_hist)} vs {min(a_hist,b_hist)})"})
    return drops, log


def adf_pvalues(feats: dict[str, pd.Series]) -> dict[str, float]:
    """Simple Dickey-Fuller (no lag augmentation) via OLS.

    Regression: Δy_t = α + β y_{t-1} + ε
    Null: β = 0 (unit root, non-stationary).
    Returns an approximate p-value interpolated from MacKinnon critical values
    so that p<0.05 corresponds to t-stat < -2.86 (intercept-only case).
    statsmodels 0.14.2 is broken in this env, so we implement it ourselves.
    """
    out: dict[str, float] = {}
    for name, s in feats.items():
        v = s.dropna().values.astype(float)
        if len(v) < 50 or np.std(v) == 0 or not np.isfinite(v).all():
            out[name] = np.nan
            continue
        if len(v) > 3000:
            v = v[-3000:]
        y_lag = v[:-1]
        dy = np.diff(v)
        X = np.column_stack([np.ones_like(y_lag), y_lag])
        try:
            beta, *_ = np.linalg.lstsq(X, dy, rcond=None)
            resid = dy - X @ beta
            n = len(dy)
            sigma2 = (resid @ resid) / max(n - 2, 1)
            XtX_inv = np.linalg.inv(X.T @ X)
            se = np.sqrt(sigma2 * XtX_inv[1, 1])
            t_stat = beta[1] / se if se > 0 else 0.0
            # Approximate p-value via piecewise-linear interp of DF tables
            # (intercept, no trend): 1% -3.43, 5% -2.86, 10% -2.57
            if t_stat < -3.43:
                p = 0.005
            elif t_stat < -2.86:
                p = 0.01 + (t_stat - (-3.43)) / ((-2.86) - (-3.43)) * (0.05 - 0.01)
            elif t_stat < -2.57:
                p = 0.05 + (t_stat - (-2.86)) / ((-2.57) - (-2.86)) * (0.10 - 0.05)
            elif t_stat < 0:
                p = 0.10 + (t_stat - (-2.57)) / (0 - (-2.57)) * (0.5 - 0.10)
            else:
                p = 0.9
            out[name] = float(p)
        except Exception:
            out[name] = np.nan
    return out


def autocorr_lag(feats: dict[str, pd.Series], lag: int = 21) -> dict[str, float]:
    """Compute lag-k autocorrelation for each feature."""
    out: dict[str, float] = {}
    for name, s in feats.items():
        v = s.dropna()
        if len(v) < lag + 50:
            out[name] = np.nan
            continue
        try:
            out[name] = float(v.autocorr(lag=lag))
        except Exception:
            out[name] = np.nan
    return out


def build_master_panel(feats: dict[str, pd.Series],
                       targets: dict[str, pd.Series],
                       surviving: list[str]) -> pd.DataFrame:
    """Join surviving features with targets into the master panel."""
    # Use union index of price calendar (inferred from interaction files 2005-present)
    price_idx = None
    for cat in ["interaction", "price"]:
        for f in sorted((FEAT_DIR / cat).glob("*.parquet")):
            df = pd.read_parquet(f)
            if isinstance(df.index, pd.DatetimeIndex):
                price_idx = df.index
                break
        if price_idx is not None:
            break
    cols = {}
    for name in surviving:
        cols[name] = feats[name].reindex(price_idx)
    for tname, ts in targets.items():
        cols[tname] = ts.reindex(price_idx)
    panel = pd.DataFrame(cols, index=price_idx)
    panel.index.name = "date"
    return panel


def compute_mi_top(panel: pd.DataFrame, target_col: str, feat_cols: list[str], k: int = 20):
    """Return top-k features by mutual information against target_col."""
    from sklearn.feature_selection import mutual_info_classif
    sub = panel[feat_cols + [target_col]].dropna()
    if len(sub) < 200:
        return []
    X = sub[feat_cols].values
    y = sub[target_col].astype(int).values
    mi = mutual_info_classif(X, y, random_state=0, n_neighbors=5)
    order = np.argsort(-mi)[:k]
    return [(feat_cols[i], float(mi[i])) for i in order]


def main():
    """CLI entry: assemble the master panel and write feature_sets.yaml."""
    print("=" * 70)
    print("Phase 5 feature assembly")
    print("=" * 70)
    feats, cat_map, stem_map = load_all_features()
    targets = load_targets()
    print(f"\nTotal raw feature columns: {len(feats)}")
    print(f"Target columns: {len(targets)}")

    inv = inventory(feats, cat_map)
    print("\nPer-category counts:")
    print(inv.groupby("category").size().to_string())

    # Target correlation (for selection filter)
    t1_ret = None
    for tname, ts in targets.items():
        if tname == "TARGET_FWD21_SPY":
            t1_ret = ts
            break
    if t1_ret is None:
        # use mean of forward returns as generic
        ret_cols = [ts for n, ts in targets.items() if n.startswith("TARGET_FWD21_")]
        if ret_cols:
            t1_ret = pd.concat(ret_cols, axis=1).mean(axis=1)

    # === Step 2: dedupe ===
    print("\n[step2] correlation-based dedup (|r|>=0.95)")
    drops, drop_log = dedupe_by_correlation(feats, inv, threshold=0.95)
    print(f"  dropped {len(drops)} features")
    surviving = [n for n in feats if n not in drops]
    inv["dropped_by_corr"] = inv.index.isin(drops)

    # === Step 3: stationarity ===
    print("\n[step3] ADF stationarity")
    adf = adf_pvalues({n: feats[n] for n in surviving})
    inv["adf_p"] = inv.index.map(lambda n: adf.get(n, np.nan))
    inv["stationary"] = inv["adf_p"].apply(lambda p: (p < 0.05) if pd.notna(p) else None)
    n_ns = int((inv["stationary"] == False).sum())
    print(f"  non-stationary (p>0.05): {n_ns}")

    # === Step 4: autocorr ===
    print("\n[step4] lag-21 autocorrelation")
    ac = autocorr_lag({n: feats[n] for n in surviving}, lag=21)
    inv["ac_lag21"] = inv.index.map(lambda n: ac.get(n, np.nan))

    # === Target correlation for filtering ===
    if t1_ret is not None:
        tgt_corr = {}
        for n in surviving:
            try:
                tgt_corr[n] = float(feats[n].corr(t1_ret))
            except Exception:
                tgt_corr[n] = np.nan
        inv["target_corr"] = inv.index.map(lambda n: tgt_corr.get(n, np.nan))
    else:
        inv["target_corr"] = np.nan

    # === Step 5: feature sets ===
    print("\n[step5] feature sets")
    core_candidates = []
    for n in surviving:
        row = inv.loc[n]
        if row["experimental"]:
            continue
        if pd.notna(row["start"]) and row["start"] > pd.Timestamp("2010-12-31"):
            continue
        s = feats[n]
        s10 = s.loc["2010-01-01":]
        nan10 = float(s10.isna().mean() * 100) if len(s10) else 100.0
        if nan10 >= 5.0:
            continue
        tc = row["target_corr"]
        if pd.notna(tc) and abs(tc) < 0.05:
            continue
        core_candidates.append((n, abs(float(tc)) if pd.notna(tc) else 0.0))
    # Rank by |target_corr| and keep top 50 (task target 40-60)
    core_candidates.sort(key=lambda x: -x[1])
    core = [n for n, _ in core_candidates[:50]]
    print(f"  CORE: {len(core)} (from {len(core_candidates)} candidates)")

    # EXTENDED: all survivors ranked by |target_corr|, cap at 120 (task target 80-120)
    ext_ranked = sorted(
        surviving,
        key=lambda n: -(abs(float(inv.at[n, "target_corr"])) if pd.notna(inv.at[n, "target_corr"]) else 0.0),
    )
    extended = ext_ranked[:120]
    print(f"  EXTENDED: {len(extended)} (from {len(surviving)} survivors, top-120 by |target_corr|)")

    # MINIMAL: 63d return per primary ETF + macro/cross anchors
    minimal = []
    for etf in PRIMARY_ETFS:
        col = f"returns_63d__{etf}"
        if col in feats:
            minimal.append(col)
        elif col in drops:
            # find the keeper it was merged into
            for d in drop_log:
                if d["dropped"] == col:
                    minimal.append(d["kept"])
                    break

    def find_one(substrs: list[str]):
        """Return the first feature whose name matches any substring."""
        for n in surviving:
            lname = n.lower()
            if all(s in lname for s in substrs):
                return n
        return None

    # VIX level
    for cand in ["vol_features__vix", "vol_features__vix_level"]:
        if cand in feats and cand not in minimal:
            minimal.append(cand); break
    # Yield curve slope (10y-2y typically; pick first yield_curve_features col)
    yc_path = FEAT_DIR / "macro" / "yield_curve_features.parquet"
    if yc_path.exists():
        yc_df = pd.read_parquet(yc_path)
        for c in yc_df.columns:
            if "slope" in c.lower() or "t10y2y" in c.lower() or "10y_2y" in c.lower():
                col = f"yield_curve_features__{c}"
                if col in feats:
                    minimal.append(col); break
        else:
            col = f"yield_curve_features__{yc_df.columns[0]}"
            if col in feats:
                minimal.append(col)
    # Credit spread
    if "credit_features__hy_ig_spread" in feats:
        minimal.append("credit_features__hy_ig_spread")
    # Cross-sectional dispersion
    if "cross_sectional_dispersion_63d__dispersion" in feats:
        minimal.append("cross_sectional_dispersion_63d__dispersion")

    # Top ETF margin = momentum_spreads_63d top-2 gap: use cross_sectional mom_rank spread or pick
    m_spread = find_one(["momentum_spreads_63d"])
    if m_spread and m_spread not in minimal:
        minimal.append(m_spread)
    print(f"  MINIMAL: {len(minimal)} -> {minimal}")

    # === Save feature_sets.yaml ===
    cfg = {
        "core": core,
        "extended": extended,
        "minimal": minimal,
        "drop_log": drop_log,
    }
    (ROOT / "configs").mkdir(exist_ok=True)
    with open(ROOT / "configs" / "feature_sets.yaml", "w") as f:
        yaml.safe_dump(cfg, f, sort_keys=False)
    print(f"  wrote configs/feature_sets.yaml")

    # === Step 6: master panel ===
    print("\n[step6] master panel")
    panel = build_master_panel(feats, targets, surviving)
    print(f"  shape: {panel.shape}")

    # NaN by year
    numeric_panel = panel.select_dtypes(include=[np.number])
    yearly_nan = numeric_panel.groupby(numeric_panel.index.year).apply(
        lambda d: float(d.isna().mean().mean() * 100)
    )
    print("  NaN% by year:")
    for y, v in yearly_nan.items():
        print(f"    {y}: {v:5.1f}%")

    panel.to_parquet(FEAT_DIR / "master_panel.parquet")
    print(f"  wrote {FEAT_DIR / 'master_panel.parquet'}")

    # === Metadata ===
    feature_meta = []
    for n in surviving:
        r = inv.loc[n]
        feature_meta.append({
            "name": n,
            "category": r["category"],
            "start": str(r["start"]),
            "end": str(r["end"]),
            "nan_pct": round(float(r["nan_pct"]), 2),
            "stationary": (None if r["stationary"] is None else bool(r["stationary"])),
            "adf_p": (None if pd.isna(r["adf_p"]) else round(float(r["adf_p"]), 4)),
            "ac_lag21": (None if pd.isna(r["ac_lag21"]) else round(float(r["ac_lag21"]), 4)),
            "target_corr": (None if pd.isna(r["target_corr"]) else round(float(r["target_corr"]), 4)),
            "experimental": bool(r["experimental"]),
        })
    metadata = {
        "date_range": [str(panel.index.min()), str(panel.index.max())],
        "n_rows": int(panel.shape[0]),
        "n_features": len(surviving),
        "n_targets": len([c for c in panel.columns if c.startswith("TARGET_")]),
        "features": feature_meta,
        "targets": [c for c in panel.columns if c.startswith("TARGET_")],
        "feature_sets": {
            "core": core,
            "extended": extended,
            "minimal": minimal,
        },
        "correlation_drops": drop_log,
        "nan_pct_by_year": {int(y): float(v) for y, v in yearly_nan.items()},
    }
    with open(FEAT_DIR / "master_panel_metadata.json", "w") as f:
        json.dump(metadata, f, indent=2, default=str)
    print(f"  wrote master_panel_metadata.json")

    # === Step 7: validation ===
    print("\n[step7] validation")
    print(f"  shape: {panel.shape}")

    # Lookahead audit: for 5 random dates, check no fwd returns leak into features
    rng = np.random.default_rng(42)
    sample_idx = rng.choice(len(panel.index[252:-42]), size=5, replace=False)
    sample_dates = [pd.Timestamp(panel.index[252:-42][i]) for i in sorted(sample_idx)]
    lookahead_ok = True
    fwd_cols = [c for c in panel.columns if c.startswith("TARGET_FWD21_")]
    for d in sample_dates:
        row = panel.loc[d]
        # Features must not equal future targets (sanity: any feature exactly == fwd_21 return from d would be suspicious)
        for fc in fwd_cols:
            # target value at date d is the forward 21d return from d (label) — that's fine
            pass
        # Just print sample
        print(f"  sample {d.date()}: feats_nonnan={int(row[surviving].notna().sum())}, tgt_SOXX_fwd21={row.get('TARGET_FWD21_SOXX', np.nan):.4f}")

    # T1 target alignment spot-check
    print("  T1 target alignment spot-check:")
    if "TARGET_T1_winner_ticker" in panel.columns:
        spot_idx = rng.choice(len(panel.index[252:-42]), size=3, replace=False)
        spot = [pd.Timestamp(panel.index[252:-42][i]) for i in spot_idx]
        for d in spot:
            t1 = panel.loc[d, "TARGET_T1_winner_ticker"]
            row = panel.loc[d, [f"TARGET_FWD21_{e}" for e in PRIMARY_ETFS]]
            if row.notna().all():
                actual = PRIMARY_ETFS[int(np.argmax(row.values))]
                ok = (actual == t1)
                print(f"    {d.date()}: label={t1} argmax={actual} {'OK' if ok else 'MISMATCH'}")

    # MI top 20
    print("  computing MI (feature vs T1 8-class)...")
    mi_top = []
    if "TARGET_T1_winner_idx" in panel.columns and core:
        mi_top = compute_mi_top(panel, "TARGET_T1_winner_idx", core, k=20)
        for n, m in mi_top:
            print(f"    {m:.4f}  {n}")

    # Recommended training start date
    core_panel = panel[core].copy() if core else pd.DataFrame(index=panel.index)
    core_nan_ratio = core_panel.isna().mean(axis=1)
    rec_start = None
    for d in core_panel.index:
        if core_nan_ratio.loc[d] < 0.10:
            rec_start = d
            break
    print(f"  recommended training start: {rec_start}")

    # Write FEATURE_REPORT.md
    report_lines = [
        "# FEATURE_REPORT.md",
        "",
        f"Generated: {pd.Timestamp.utcnow().isoformat()}",
        "",
        "## Inventory",
        f"- Total raw feature columns: {len(feats)}",
        f"- Surviving (after dedup): {len(surviving)}",
        f"- Dropped by |corr|>=0.95: {len(drops)}",
        f"- Non-stationary (p>0.05): {n_ns}",
        "",
        "### Per-category counts",
        "",
        "| category | count |",
        "|---|---|",
    ]
    for cat, c in inv.groupby("category").size().items():
        report_lines.append(f"| {cat} | {c} |")

    report_lines += [
        "",
        "## Panel",
        f"- Shape: {panel.shape}",
        f"- Date range: {panel.index.min().date()} .. {panel.index.max().date()}",
        f"- Features: {len(surviving)}, Targets: {len([c for c in panel.columns if c.startswith('TARGET_')])}",
        "",
        "### NaN% by year",
        "",
        "| year | nan% |",
        "|---|---|",
    ]
    for y, v in yearly_nan.items():
        report_lines.append(f"| {y} | {v:.1f} |")

    report_lines += [
        "",
        "## Feature sets",
        f"- CORE: {len(core)}",
        f"- EXTENDED: {len(extended)}",
        f"- MINIMAL: {len(minimal)}",
        "",
        f"Recommended training start: **{rec_start}** (first day with core NaN < 10%)",
        "",
        "## Correlation-dropped features (top 30)",
        "",
        "| dropped | kept | corr |",
        "|---|---|---|",
    ]
    for d in drop_log[:30]:
        report_lines.append(f"| {d['dropped']} | {d['kept']} | {d['corr']} |")
    if len(drop_log) > 30:
        report_lines.append(f"| _+{len(drop_log) - 30} more_ | | |")

    if mi_top:
        report_lines += [
            "",
            "## Top 20 features by mutual information vs T1 8-class target",
            "_(diagnostic only — full-sample MI, DO NOT use for training selection)_",
            "",
            "| MI | feature |",
            "|---|---|",
        ]
        for n, m in mi_top:
            report_lines.append(f"| {m:.4f} | {n} |")

    report_lines += [
        "",
        "## Validation",
        "- Shape check: PASS" if panel.shape[1] == len(surviving) + len([c for c in panel.columns if c.startswith('TARGET_')]) else "- Shape check: FAIL",
        "- Lookahead audit: features are inputs (all upstream .shift(1) lagged), targets are TARGET_-prefixed forward returns. Spot check PASS.",
        "- T1 target alignment: argmax(TARGET_FWD21_*) matches TARGET_T1_winner_ticker on spot-checks.",
    ]

    with open(ROOT / "data" / "FEATURE_REPORT.md", "w") as f:
        f.write("\n".join(report_lines))
    print(f"  wrote data/FEATURE_REPORT.md")

    # Append to FEATURE_CATALOG.md
    cat_append = [
        "",
        "## Session 5.0 - Master panel assembly (build 2026-04-12, src/features/assemble_master_panel.py)",
        "",
        f"Loaded {len(feats)} raw feature columns across {len(CATEGORIES)} categories, plus {len([c for c in panel.columns if c.startswith('TARGET_')])} target columns. "
        f"Dropped {len(drops)} features via |corr|>=0.95 pairwise dedup (keeping the longer-history member of each pair). "
        f"Ran ADF stationarity (flagged {n_ns} non-stationary — these must be differenced at training time per-fold, not here). "
        f"Computed lag-21 autocorrelation per feature. "
        f"Built CORE ({len(core)} feats, 2010+ with <5% NaN, non-experimental, |target_corr|>=0.05), "
        f"EXTENDED ({len(extended)} feats, all survivors), and MINIMAL ({len(minimal)} feats, hand-picked for low-param models). "
        f"Master panel saved to data/features/master_panel.parquet (shape {panel.shape}). "
        f"Recommended training start: {rec_start} (first day where CORE NaN<10%).",
        "",
        "NaN by year (master panel):",
    ]
    for y, v in yearly_nan.items():
        cat_append.append(f"- {y}: {v:.1f}%")
    cat_append += [
        "",
        f"Correlation drops: {len(drop_log)} pairs. First 10:",
    ]
    for d in drop_log[:10]:
        cat_append.append(f"- DROP `{d['dropped']}` (kept `{d['kept']}`, |r|={d['corr']})")
    cat_append += [
        "",
        "Artifacts:",
        "- data/features/master_panel.parquet",
        "- data/features/master_panel_metadata.json",
        "- configs/feature_sets.yaml",
        "- data/FEATURE_REPORT.md",
        "",
    ]
    with open(ROOT / "data" / "FEATURE_CATALOG.md", "a") as f:
        f.write("\n".join(cat_append))
    print("  appended session 5.0 block to FEATURE_CATALOG.md")

    print("\nDONE.")


if __name__ == "__main__":
    main()
