# ARCHIVED: lookback trigger sweep — results in LOOKBACK_TRIGGER_REPORT.md
"""Test alternative lookback triggers for OPTIMIZED strategy.

Replaces the ML regime classifier with rule-based triggers (T01-T09) and a
random baseline (T10) at the same ~28% firing frequency.

Strategy unchanged elsewhere: top-3 inverse-vol, 0.5/0.5 top1/top3, SMA200 -4%
gate on top-1 leg, M26_post_3d deferral, monthly rebalance.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from sklearn.ensemble import HistGradientBoostingClassifier

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from model.walk_forward import ExpandingSplitter  # noqa: E402
from model.preprocessing import FeaturePreprocessor  # noqa: E402

ETFS = ["SOXX", "QQQ", "XLK", "VGT", "IGV", "XLE", "GLD", "SHY"]
LB_STABLE = 63; LB_TRANS = 21; K = 3; W1 = 0.5; WK = 0.5
SPLIT_KW = dict(min_train_months=60, val_months=6, test_months=3, step_months=3,
                sample_every_n_days=5, embargo_days=5, target_horizon=21,
                decay_halflife_months=36)
REGIME_CLASSES = ["regime_hg_li", "regime_hg_hi", "regime_lg_li", "regime_lg_hi_stagflation"]
REGIME_FEATS = [f"regime_growth_inflation__{c}" for c in REGIME_CLASSES]


def stats(r):
    r = np.asarray(r, float); r = r[~np.isnan(r)]
    if len(r) == 0:
        return dict(cagr=float("nan"), sharpe=float("nan"), max_dd=float("nan"), n=0)
    eq = np.cumprod(1 + r)
    yrs = len(r) / 12.0
    cagr = float(eq[-1] ** (1 / yrs) - 1)
    sd = r.std(ddof=1) if len(r) > 1 else 0.0
    sh = float(r.mean() / sd * np.sqrt(12)) if sd > 0 else float("nan")
    peak = np.maximum.accumulate(eq)
    dd = float((eq / peak - 1).min())
    return dict(cagr=cagr, sharpe=sh, max_dd=dd, n=int(len(r)))


print("Loading panel...")
df = pd.read_parquet(ROOT / "data/features/master_panel.parquet")
feature_sets = yaml.safe_load(open(ROOT / "configs/feature_sets.yaml"))
core_feats = [c for c in feature_sets["core"] if c in df.columns]
DATES = df.index; NDAYS = len(df)

R21 = pd.read_parquet(ROOT / "data/features/price/returns_21d.parquet").reindex(DATES)
R63 = pd.read_parquet(ROOT / "data/features/price/returns_63d.parquet").reindex(DATES)


def fwd21(t):
    col = f"TARGET_FWD21_{t}"
    if col in df.columns: return df[col].values
    return R21[t].shift(-21).reindex(DATES).values


FWD = {t: fwd21(t) for t in ETFS}
FWD_ARR = np.column_stack([FWD[t] for t in ETFS])
shy_ret = FWD["SHY"]
spy_dist = df["quality_dist_sma200__SPY"].values

atr21 = pd.read_parquet(ROOT / "data/features/price/atr_21d.parquet").reindex(DATES)
ATR = np.full((NDAYS, len(ETFS)), np.nan)
for j, t in enumerate(ETFS):
    if t in atr21.columns: ATR[:, j] = atr21[t].values

splitter = ExpandingSplitter(**SPLIT_KW)
folds = splitter.split(DATES)
test_dates = pd.DatetimeIndex(sorted(set(d for f in folds for d in f["test_dates"])))
te_pos = DATES.get_indexer(test_dates)

# ---- Regime classifier (control) ----
target_col = "TARGET_TREG_growth_inflation_fwd21"
cls_to_idx = {c: i for i, c in enumerate(REGIME_CLASSES)}
current_reg = df[REGIME_FEATS].values.argmax(axis=1)
pred_reg = np.full(NDAYS, -1, dtype=int)
print("Training WF regime classifier (control)...")
for fold in folds:
    tr = fold["train_dates"]; te = fold["test_dates"]
    if len(tr) < 30 or len(te) < 1: continue
    sw = np.asarray(fold["train_sample_weights"])
    Xtr = df.loc[tr, core_feats]; ytr_raw = df.loc[tr, target_col]
    Xte = df.loc[te, core_feats]
    mtr = ytr_raw.notna()
    Xtr, ytr_raw, sw = Xtr[mtr], ytr_raw[mtr], sw[mtr.to_numpy()]
    if len(Xtr) < 50: continue
    ytr = ytr_raw.map(cls_to_idx).astype(int).to_numpy()
    pp = FeaturePreprocessor()
    Xtr_z = pp.fit_transform(Xtr, sample_weights=sw).to_numpy()
    Xte_z = pp.transform(Xte).to_numpy()
    clf = HistGradientBoostingClassifier(max_iter=200, max_depth=4, learning_rate=0.05,
                                          min_samples_leaf=20, l2_regularization=1.0, random_state=0)
    clf.fit(Xtr_z, ytr, sample_weight=sw)
    proba = clf.predict_proba(Xte_z)
    full = np.zeros((len(Xte_z), 4))
    for j, c in enumerate(clf.classes_):
        full[:, int(c)] = proba[:, j]
    pred_reg[DATES.get_indexer(te)] = np.argmax(full, axis=1)

regime_trigger = (pred_reg != -1) & (pred_reg != current_reg)

# ---- Momentum arrays ----
def mom_arr(lb):
    rdf = R63 if lb == 63 else R21
    return np.column_stack([rdf[t].reindex(DATES).values for t in ETFS])


M63 = mom_arr(63); M21 = mom_arr(21)

# ---- Signal features for triggers ----
vix = df["vol_features__vix"].values
hy_z = df["credit_features__hy_ig_spread_z252"].values if "credit_features__hy_ig_spread_z252" in df.columns else np.full(NDAYS, np.nan)

# SPY daily returns for realized vol
spy_close = pd.read_parquet(ROOT / "data/raw/yahoo/SPY.parquet")["adj_close"]
spy_close.index = pd.to_datetime(spy_close.index)
spy_daily = spy_close.pct_change().reindex(DATES)
rvol_21 = spy_daily.rolling(21).std().values * np.sqrt(252)
rvol_63_med = pd.Series(rvol_21, index=DATES).rolling(63).median().values

# VIX change over 21 days
vix_s = pd.Series(vix, index=DATES)
vix_chg_21 = (vix_s - vix_s.shift(21)).values

# Cross-sectional dispersion of 63d returns across the 8 ETFs
disp_63 = np.nanstd(M63, axis=1)

# Top1 - Top2 gap on 63d
def top_gap(arr):
    sf = np.where(np.isnan(arr), -np.inf, arr)
    srt = -np.sort(-sf, axis=1)
    return srt[:, 0] - srt[:, 1]
mom_gap_63 = top_gap(M63)

# ---- FOMC post-3d mask ----
is_fomc_day = (df["timing__is_fomc_day"].values > 0)
fomc_day_idx = np.where(is_fomc_day)[0]


def fomc_post_mask(post_days=2):
    m = np.zeros(NDAYS, bool)
    for i in fomc_day_idx:
        hi = min(NDAYS - 1, i + post_days)
        m[i:hi + 1] = True
    return m


POST_MASK = fomc_post_mask(2)
mp = pd.Series(te_pos, index=test_dates)
MONTH_POS = mp.groupby(test_dates.to_period("M")).tail(1)


# ---- Strategy engine ----
def top1_idx_at(row):
    sf = np.where(np.isnan(row), -np.inf, row)
    return int(np.argmax(sf))


def topk_idx_at(row, k=K):
    sf = np.where(np.isnan(row), -np.inf, row)
    return np.argsort(-sf)[:k]


def topk_iv(i, idx):
    sel = ATR[i, idx]
    inv = 1.0 / np.where(sel > 0, sel, np.nan)
    if np.isnan(inv).all():
        return float(np.nanmean(FWD_ARR[i, idx]))
    w = inv / np.nansum(inv)
    return float(np.nansum(FWD_ARR[i, idx] * w))


def run_strategy(use_trans_arr):
    """Run full strategy (incl. M26_post_3d) with a given NDAYS boolean
    use_trans array. Returns (monthly Series, fire_count, per-month records)."""
    rows = []
    for d, i in MONTH_POS.items():
        i = int(i)
        deferred = bool(POST_MASK[i])
        i_use = min(i + 3, NDAYS - 1) if deferred else i
        mom = M21 if use_trans_arr[i_use] else M63
        top1 = top1_idx_at(mom[i_use])
        tk = topk_idx_at(mom[i_use])
        r1 = FWD_ARR[i_use, top1] if spy_dist[i_use] > -0.04 else shy_ret[i_use]
        rk = topk_iv(i_use, tk)
        rows.append({
            "date": d, "i": i, "i_use": i_use,
            "switch_active": bool(use_trans_arr[i]),
            "r_final": W1 * r1 + WK * rk,
            "r_top1_63d": float(FWD_ARR[i, top1_idx_at(M63[i])]),
            "r_top1_21d": float(FWD_ARR[i, top1_idx_at(M21[i])]),
            "top1_63d_pick": ETFS[top1_idx_at(M63[i])],
            "top1_21d_pick": ETFS[top1_idx_at(M21[i])],
        })
    d = pd.DataFrame(rows).set_index("date").sort_index().dropna(subset=["r_final"])
    n_fires = int(d["switch_active"].sum())
    return d, n_fires


# Convert test-date-relative firing rate to a full NDAYS mask:
# All triggers defined at daily cadence; rates reported at rebal months.

TRIGGERS = {
    "Regime (ML)": ("66.5% acc classifier", regime_trigger),
    "T01 VIX>25": ("VIX level > 25", vix > 25),
    "T02 VIX>20": ("VIX level > 20", vix > 20),
    "T03 VIX>30": ("VIX level > 30", vix > 30),
    "T04 rvol>63d med": ("SPY 21d rvol > 63d rolling median", rvol_21 > rvol_63_med),
    "T05 VIX chg>5": ("VIX up >5pts over 21d", vix_chg_21 > 5),
    "T06 HY-IG z>1": ("HY-IG credit z-score > 1.0", hy_z > 1.0),
    "T07 VIX>25 | HY-IG z>1": ("Either VIX>25 or HY-IG z>1", (vix > 25) | (hy_z > 1.0)),
    "T08 disp<5%": ("Cross-sec 63d return stdev < 5%", disp_63 < 0.05),
    "T09 top gap<2pp": ("Top1-Top2 gap on 63d mom < 2pp", mom_gap_63 < 0.02),
}

results = {}
picks_store = {}
print("\nRunning deterministic triggers...")
for name, (desc, mask) in TRIGGERS.items():
    mask_clean = np.where(np.isnan(mask.astype(float)), False, mask).astype(bool)
    mdf, nfires = run_strategy(mask_clean)
    st = stats(mdf["r_final"].values)
    results[name] = {"description": desc, "n_fires": nfires, **st}
    picks_store[name] = mdf
    print(f"  {name:25s}  fires={nfires:3d}  CAGR {st['cagr']*100:5.2f}%  Sharpe {st['sharpe']:.2f}  DD {st['max_dd']*100:6.2f}%")

# ---- T10 random baseline ----
print("\nT10 random 28% baseline (500 runs)...")
target_rate = 0.28
sharpes = []; cagrs = []; dds = []; fires_list = []
rng = np.random.default_rng(42)
for seed in range(500):
    rng_ = np.random.default_rng(seed)
    mask = rng_.random(NDAYS) < target_rate
    mdf, nf = run_strategy(mask)
    st = stats(mdf["r_final"].values)
    sharpes.append(st["sharpe"]); cagrs.append(st["cagr"]); dds.append(st["max_dd"])
    fires_list.append(nf)

t10 = {
    "description": f"Random daily fire at {target_rate*100:.0f}% (500 runs)",
    "median_cagr": float(np.median(cagrs)),
    "median_sharpe": float(np.median(sharpes)),
    "median_dd": float(np.median(dds)),
    "p05_sharpe": float(np.quantile(sharpes, 0.05)),
    "p95_sharpe": float(np.quantile(sharpes, 0.95)),
    "p05_cagr": float(np.quantile(cagrs, 0.05)),
    "p95_cagr": float(np.quantile(cagrs, 0.95)),
    "mean_fires": float(np.mean(fires_list)),
    "regime_sharpe_percentile": float((np.array(sharpes) < results["Regime (ML)"]["sharpe"]).mean() * 100),
    "regime_cagr_percentile": float((np.array(cagrs) < results["Regime (ML)"]["cagr"]).mean() * 100),
}
results["T10 random 28%"] = {
    "description": t10["description"],
    "n_fires": int(t10["mean_fires"]),
    "cagr": t10["median_cagr"],
    "sharpe": t10["median_sharpe"],
    "max_dd": t10["median_dd"],
    **{f"rand_{k}": v for k, v in t10.items()},
}
print(f"  median Sharpe {t10['median_sharpe']:.2f}  (p05 {t10['p05_sharpe']:.2f}, p95 {t10['p95_sharpe']:.2f})")
print(f"  median CAGR   {t10['median_cagr']*100:.2f}%")
print(f"  regime classifier percentile: Sharpe {t10['regime_sharpe_percentile']:.1f} / CAGR {t10['regime_cagr_percentile']:.1f}")

# ---- B2 hit ratio for top 3 triggers by Sharpe ----
rank = sorted(
    [(k, v) for k, v in results.items() if not k.startswith("T10")],
    key=lambda x: -x[1]["sharpe"],
)
top3_names = [r[0] for r in rank[:3]]
print(f"\nTop-3 triggers by Sharpe: {top3_names}")


def b2(mdf_t):
    sw = mdf_t[mdf_t["switch_active"]].copy()
    # Determine actual fwd regime from panel labels ~21d later
    def afwd(i):
        j = min(int(i) + 21, NDAYS - 1)
        return int(current_reg[j])
    # Predicted regime unavailable for rule-based triggers → use
    # 21d-pick vs 63d-pick as the directly testable hypothesis:
    # HELPFUL if picks differ AND 21d beats 63d.
    sw["pick_diff"] = sw["top1_21d_pick"] != sw["top1_63d_pick"]
    sw["delta"] = sw["r_top1_21d"] - sw["r_top1_63d"]
    def cat(row):
        if row["pick_diff"] and row["delta"] > 0: return "HELPFUL"
        if not row["pick_diff"]: return "NEUTRAL"
        return "HARMFUL"
    sw["cat"] = sw.apply(cat, axis=1)
    return sw["cat"].value_counts().to_dict(), int(len(sw))


b2_out = {}
for name in top3_names:
    dist, n = b2(picks_store[name])
    b2_out[name] = {"n": n, "dist": dist,
                    "helpful_pct": 100 * dist.get("HELPFUL", 0) / max(n, 1),
                    "harmful_pct": 100 * dist.get("HARMFUL", 0) / max(n, 1)}
    print(f"  {name:25s}  n={n:3d}  H={dist.get('HELPFUL',0)}  N={dist.get('NEUTRAL',0)}  X={dist.get('HARMFUL',0)}")

# ---- Save JSON ----
(ROOT / "results/experiments/LOOKBACK_TRIGGERS.json").write_text(json.dumps({
    "control": {"name": "Regime (ML)", **results["Regime (ML)"]},
    "triggers": results,
    "random": t10,
    "b2_top3": b2_out,
}, indent=2, default=str))
print("\nWrote results/experiments/LOOKBACK_TRIGGERS.json")

# ---- Report markdown ----
def fmt_pct(v): return "n/a" if v != v else f"{v*100:.2f}%"
lines = []
lines.append("# LOOKBACK TRIGGER REPORT\n")
lines.append("Replacing the ML regime classifier with rule-based triggers for the 63d↔21d "
             "lookback switch. All other components (top-3 inv-vol, SMA200 -4% gate, M26 post-3d "
             "defer, monthly rebalance) identical.\n")
lines.append("## Results\n")
lines.append("| Trigger | Description | Fires (test days) | CAGR | Sharpe | MaxDD |")
lines.append("|---|---|---|---|---|---|")
for name, r in results.items():
    if name.startswith("T10"):
        lines.append(f"| {name} | {r['description']} | ~{r['n_fires']} | "
                     f"{fmt_pct(r['cagr'])} (median) | {r['sharpe']:.2f} (median) | {fmt_pct(r['max_dd'])} (median) |")
    else:
        lines.append(f"| {name} | {r['description']} | {r['n_fires']} | "
                     f"{fmt_pct(r['cagr'])} | {r['sharpe']:.2f} | {fmt_pct(r['max_dd'])} |")

lines.append("\n## T10 random baseline distribution (500 runs at 28% fire rate)\n")
lines.append(f"- Median Sharpe: **{t10['median_sharpe']:.2f}**  (p05 {t10['p05_sharpe']:.2f}, p95 {t10['p95_sharpe']:.2f})")
lines.append(f"- Median CAGR: **{fmt_pct(t10['median_cagr'])}**  (p05 {fmt_pct(t10['p05_cagr'])}, p95 {fmt_pct(t10['p95_cagr'])})")
lines.append(f"- Average fires per run: {t10['mean_fires']:.0f}")
lines.append(f"- Regime classifier Sharpe percentile in random distribution: **{t10['regime_sharpe_percentile']:.1f}**")
lines.append(f"- Regime classifier CAGR percentile in random distribution: **{t10['regime_cagr_percentile']:.1f}**")

lines.append("\n## B2 hit-ratio for top-3 triggers\n")
lines.append("For rule-based triggers, HELPFUL = picks differ AND 21d beats 63d (no prediction to "
             "score, so correctness uses the direct pick-outcome test only).\n")
lines.append("| Trigger | n switches | HELPFUL | NEUTRAL | HARMFUL | Helpful % |")
lines.append("|---|---|---|---|---|---|")
for name, b in b2_out.items():
    d = b["dist"]
    lines.append(f"| {name} | {b['n']} | {d.get('HELPFUL', 0)} | {d.get('NEUTRAL', 0)} | "
                 f"{d.get('HARMFUL', 0)} | {b['helpful_pct']:.1f}% |")

# ---- Verdict ----
regime_sh = results["Regime (ML)"]["sharpe"]
rand_sh = t10["median_sharpe"]
best_rule = max(
    [(k, v) for k, v in results.items() if k.startswith("T") and not k.startswith("T10")],
    key=lambda x: x[1]["sharpe"],
)

lines.append("\n## Verdict\n")
gap_random = regime_sh - rand_sh
if abs(gap_random) < 0.1:
    lines.append(f"**Random baseline (Sharpe {rand_sh:.2f}) is within 0.1 of the regime classifier "
                 f"(Sharpe {regime_sh:.2f}).**  The specific trigger does not matter — the edge is "
                 f"purely *'use 21d lookback ~28% of the time.'* The ML classifier adds no directional "
                 f"value over a coin flip at the right frequency. **Recommendation:** replace the "
                 f"classifier with the simplest interpretable trigger; VIX-based rules are the "
                 f"obvious choice.")
else:
    lines.append(f"**Random baseline median Sharpe {rand_sh:.2f} vs regime classifier {regime_sh:.2f} "
                 f"(gap {gap_random:+.2f}).** The regime classifier sits at the "
                 f"{t10['regime_sharpe_percentile']:.0f}th percentile of random — "
                 + ("so random noise rarely matches it, meaning the timing of switches does carry signal."
                    if t10['regime_sharpe_percentile'] >= 70 else
                    "which is comparable to noise, so the classifier is not demonstrably better than random."))

if best_rule[1]["sharpe"] > regime_sh + 0.05:
    lines.append(f"\n**Best rule-based trigger:** `{best_rule[0]}` — Sharpe {best_rule[1]['sharpe']:.2f} "
                 f"beats the classifier by {best_rule[1]['sharpe'] - regime_sh:+.2f}. Swap the classifier "
                 f"for this simpler rule.")
    update_opt = True
    new_trigger = best_rule[0]
else:
    lines.append(f"\nBest rule-based trigger: `{best_rule[0]}` (Sharpe {best_rule[1]['sharpe']:.2f}). "
                 f"Not materially better than the classifier.")
    update_opt = False
    new_trigger = None

(ROOT / "results/LOOKBACK_TRIGGER_REPORT.md").write_text("\n".join(lines), encoding="utf-8")
print("Wrote results/LOOKBACK_TRIGGER_REPORT.md")

if update_opt:
    OPT = ROOT / "results/OPTIMIZED_STRATEGY.md"
    txt = OPT.read_text(encoding="utf-8")
    if "Lookback trigger upgrade" not in txt:
        add = [
            "\n\n---\n",
            "## Lookback trigger upgrade\n",
            f"Rule-based trigger `{new_trigger}` replaces the ML regime classifier. Performance:\n",
            f"- CAGR: **{fmt_pct(best_rule[1]['cagr'])}**",
            f"- Sharpe: **{best_rule[1]['sharpe']:.2f}**",
            f"- MaxDD: **{fmt_pct(best_rule[1]['max_dd'])}**",
            f"- Fires: {best_rule[1]['n_fires']} test days",
            "\nSimpler, no ML training required, mechanistically transparent.",
        ]
        OPT.write_text(txt + "\n".join(add), encoding="utf-8")
        print(f"Updated {OPT}")

print("\nDone.")
