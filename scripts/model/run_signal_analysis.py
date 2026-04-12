"""Parts B + C — Strategy attribution and correlation analysis.

Reconstructs the OPTIMIZED strategy (E-R1 + M11 + M26_post_3d) at monthly rebalance
cadence and decomposes month-by-month returns into:

  V0 = base 63d top-1 (no gate, no top3, no regime switch, no defer)
  V1 = V0 + regime switch  (use 21d when transitioning)
  V2 = V1 + top-3 inverse-vol (50/50 with top-1)
  V3 = V2 + SMA200 -4% gate on top-1 leg
  V4 = V3 + M26_post_3d (defer 3 trading days when within 0..2d AFTER an FOMC day)

Component contribution = V_i − V_{i-1}.

Then computes (Part C):
  C1 — strategy vs SPY upside/downside capture asymmetry
  C2 — factor correlations (MTUM, VLUE, QUAL, GLD, TLT)
  C3 — regime-conditional CAGR vs SPY

Outputs: results/SIGNAL_ANALYSIS_REPORT.md
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

OUT = ROOT / "results"

ETFS = ["SOXX", "QQQ", "XLK", "VGT", "IGV", "XLE", "GLD", "SHY"]
LB_STABLE = 63
LB_TRANS = 21
K = 3
W1 = 0.5
WK = 0.5

SPLIT_KW = dict(
    min_train_months=60, val_months=6, test_months=3, step_months=3,
    sample_every_n_days=5, embargo_days=5, target_horizon=21,
    decay_halflife_months=36,
)
REGIME_CLASSES = ["regime_hg_li", "regime_hg_hi", "regime_lg_li", "regime_lg_hi_stagflation"]
REGIME_LABELS = {"regime_hg_li": "HG/LI", "regime_hg_hi": "HG/HI",
                 "regime_lg_li": "LG/LI", "regime_lg_hi_stagflation": "LG/HI"}
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


# ---------------------------------------------------------------------------
# Load
# ---------------------------------------------------------------------------
print("Loading panel…")
df = pd.read_parquet(ROOT / "data/features/master_panel.parquet")
feature_sets = yaml.safe_load(open(ROOT / "configs/feature_sets.yaml"))
core_feats = [c for c in feature_sets["core"] if c in df.columns]
DATES = df.index
NDAYS = len(df)


def load_ret(d):
    return pd.read_parquet(ROOT / f"data/features/price/returns_{d}d.parquet").reindex(DATES)


R21 = load_ret(21); R63 = load_ret(63)


def fwd21(t):
    col = f"TARGET_FWD21_{t}"
    if col in df.columns:
        return df[col].values
    return R21[t].shift(-21).reindex(DATES).values


FWD = {t: fwd21(t) for t in ETFS}
FWD_ARR = np.column_stack([FWD[t] for t in ETFS])
shy_ret = FWD["SHY"]
spy_dist = df["quality_dist_sma200__SPY"].values

atr21 = pd.read_parquet(ROOT / "data/features/price/atr_21d.parquet").reindex(DATES)
ATR = np.full((NDAYS, len(ETFS)), np.nan)
for j, t in enumerate(ETFS):
    if t in atr21.columns:
        ATR[:, j] = atr21[t].values

# Walk-forward splits + regime classifier
splitter = ExpandingSplitter(**SPLIT_KW)
folds = splitter.split(DATES)
test_dates = pd.DatetimeIndex(sorted(set(d for f in folds for d in f["test_dates"])))
te_pos = DATES.get_indexer(test_dates)

target_col = "TARGET_TREG_growth_inflation_fwd21"
cls_to_idx = {c: i for i, c in enumerate(REGIME_CLASSES)}
current_reg_full = df[REGIME_FEATS].values.argmax(axis=1)
pred_reg = np.full(NDAYS, -1, dtype=int)
print("Training walk-forward regime classifier…")
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
    pr = np.argmax(clf.predict_proba(Xte_z), axis=1)
    # Map clf classes to global
    full = np.zeros((len(Xte_z), 4))
    for j, c in enumerate(clf.classes_):
        full[:, int(c)] = clf.predict_proba(Xte_z)[:, j]
    pr = np.argmax(full, axis=1)
    pred_reg[DATES.get_indexer(te)] = pr

# Momentum arrays
def mom_arr(lookback):
    rdf = R63 if lookback == 63 else R21
    return np.column_stack([rdf[t].reindex(DATES).values for t in ETFS])


M63 = mom_arr(63)
M21 = mom_arr(21)
use_trans = (pred_reg != -1) & (pred_reg != current_reg_full)

# FOMC post-event window
is_fomc_day = (df["timing__is_fomc_day"].values > 0)
fomc_day_idx = np.where(is_fomc_day)[0]


def fomc_post_mask(post_days=2):
    m = np.zeros(NDAYS, bool)
    for i in fomc_day_idx:
        hi = min(NDAYS - 1, i + post_days)
        m[i:hi + 1] = True
    return m


POST_MASK = fomc_post_mask(2)

# Monthly rebalance positions on test_dates
mp = pd.Series(te_pos, index=test_dates)
MONTH_POS = mp.groupby(test_dates.to_period("M")).tail(1)


def top1_idx_at(mom_row):
    sf = np.where(np.isnan(mom_row), -np.inf, mom_row)
    return int(np.argmax(sf))


def topk_idx_at(mom_row, k=K):
    sf = np.where(np.isnan(mom_row), -np.inf, mom_row)
    return np.argsort(-sf)[:k]


def top1_ret_at(i, mom):
    j = top1_idx_at(mom[i])
    return FWD_ARR[i, j], j


def topk_iv_ret_at(i, mom, k=K):
    idx = topk_idx_at(mom[i], k)
    sel_atr = ATR[i, idx]
    inv = 1.0 / np.where(sel_atr > 0, sel_atr, np.nan)
    if np.isnan(inv).all():
        return float(np.nanmean(FWD_ARR[i, idx])), idx
    w = inv / np.nansum(inv)
    return float(np.nansum(FWD_ARR[i, idx] * w)), idx


def gated_top1(i, raw_ret):
    return raw_ret if spy_dist[i] > -0.04 else shy_ret[i]


# ---------------------------------------------------------------------------
# Build per-month variant returns
# ---------------------------------------------------------------------------
records = []
for d, i in MONTH_POS.items():
    i = int(i)
    # Decide deferral position for V4
    deferred = bool(POST_MASK[i])
    i_def = min(i + 3, NDAYS - 1) if deferred else i

    # V0: 63d top-1 only
    r_v0_top1, v0_pick = top1_ret_at(i, M63)
    v0 = r_v0_top1
    # V1: switch to 21d when transitioning
    mom_cond = M21 if use_trans[i] else M63
    r_v1_top1, v1_pick = top1_ret_at(i, mom_cond)
    v1 = r_v1_top1
    # V2: 0.5*top1_cond + 0.5*top3_iv (no gate)
    r_v2_topk, v2_topk_idx = topk_iv_ret_at(i, mom_cond)
    v2 = W1 * r_v1_top1 + WK * r_v2_topk
    # V3: gate top1 leg
    v3_top1_gated = gated_top1(i, r_v1_top1)
    v3 = W1 * v3_top1_gated + WK * r_v2_topk
    # V4: M26 post-3d deferral
    mom_cond_def = M21 if use_trans[i_def] else M63
    r_v4_top1, _ = top1_ret_at(i_def, mom_cond_def)
    r_v4_topk, _ = topk_iv_ret_at(i_def, mom_cond_def)
    v4_top1_gated = r_v4_top1 if spy_dist[i_def] > -0.04 else shy_ret[i_def]
    v4 = W1 * v4_top1_gated + WK * r_v4_topk

    records.append({
        "date": d, "i": i, "i_def": i_def,
        "switch_active": bool(use_trans[i]),
        "gate_active": bool(spy_dist[i] <= -0.04),
        "defer_active": deferred,
        "pred_regime": int(pred_reg[i]) if pred_reg[i] != -1 else -1,
        "current_regime": int(current_reg_full[i]),
        "v0": v0, "v1": v1, "v2": v2, "v3": v3, "v4": v4,
        "v0_top1_pick": ETFS[v0_pick],
        "v1_top1_pick": ETFS[v1_pick],
        "v2_topk_picks": [ETFS[j] for j in v2_topk_idx],
        "v3_top1_gated": float(v3_top1_gated),
        # For B2: 21d-vs-63d on switch months
        "r_top1_63d": float(top1_ret_at(i, M63)[0]),
        "r_top1_21d": float(top1_ret_at(i, M21)[0]),
        "top1_63d_pick": ETFS[top1_idx_at(M63[i])],
        "top1_21d_pick": ETFS[top1_idx_at(M21[i])],
    })

mdf = pd.DataFrame(records).set_index("date").sort_index()
mdf = mdf.dropna(subset=["v0", "v1", "v2", "v3", "v4"])
print(f"  monthly rebalance rows: {len(mdf)}")

# Component contribution series
mdf["c_base"] = mdf["v0"]
mdf["c_switch"] = mdf["v1"] - mdf["v0"]
mdf["c_top3"] = mdf["v2"] - mdf["v1"]
mdf["c_gate"] = mdf["v3"] - mdf["v2"]
mdf["c_defer"] = mdf["v4"] - mdf["v3"]
mdf["final"] = mdf["v4"]

# ---------------------------------------------------------------------------
# B1 — Component attribution table
# ---------------------------------------------------------------------------
def active_mask(name):
    if name == "base": return np.ones(len(mdf), bool)
    if name == "switch": return mdf["switch_active"].values
    if name == "top3": return np.ones(len(mdf), bool)
    if name == "gate": return mdf["gate_active"].values
    if name == "defer": return mdf["defer_active"].values
    raise KeyError(name)


comp_meta = [
    ("Base 63d top1", "c_base", "base"),
    ("Regime switch (21d trans)", "c_switch", "switch"),
    ("Top-3 inv-vol blend", "c_top3", "top3"),
    ("SMA200 gate", "c_gate", "gate"),
    ("M26 post-3d defer", "c_defer", "defer"),
]
b1_rows = []
for label, col, akey in comp_meta:
    mask = active_mask(akey)
    series = mdf[col]
    active = series[mask]
    if akey == "base":
        avg_active = float(active.mean())
        # Total compounded contribution: log of geometric ratio (only meaningful for base)
        total_log = float(np.log1p(series).sum())
        best_idx = active.idxmax(); worst_idx = active.idxmin()
    else:
        # For incremental components, contribution is additive delta
        avg_active = float(active.mean()) if len(active) else 0.0
        total_log = float(active.sum())  # additive delta cumulative
        best_idx = active.idxmax() if len(active) else None
        worst_idx = active.idxmin() if len(active) else None
    b1_rows.append({
        "label": label,
        "active_months": int(mask.sum()),
        "avg_when_active": avg_active,
        "total_contribution": total_log,
        "best_month": (str(best_idx.date()), float(active.loc[best_idx])) if best_idx is not None else None,
        "worst_month": (str(worst_idx.date()), float(active.loc[worst_idx])) if worst_idx is not None else None,
    })

# ---------------------------------------------------------------------------
# B2 — Regime switch detailed analysis
# ---------------------------------------------------------------------------
sw_rows = mdf[mdf["switch_active"]].copy()
# Was prediction correct? compare predicted regime to actual regime ~21d later (use current_reg_full)
def actual_future_regime(i, lag=21):
    j = min(i + lag, NDAYS - 1)
    return int(current_reg_full[j])


sw_rows["actual_fwd"] = sw_rows["i"].map(actual_future_regime)
sw_rows["pred_correct"] = sw_rows["pred_regime"] == sw_rows["actual_fwd"]
sw_rows["pick_diff"] = sw_rows["top1_21d_pick"] != sw_rows["top1_63d_pick"]
sw_rows["delta_21_vs_63"] = sw_rows["r_top1_21d"] - sw_rows["r_top1_63d"]


def categorize(row):
    if row["pred_correct"] and row["pick_diff"] and row["delta_21_vs_63"] > 0:
        return "HELPFUL"
    if row["pred_correct"] and not row["pick_diff"]:
        return "NEUTRAL_CORRECT"
    if (not row["pred_correct"]) and not row["pick_diff"]:
        return "NEUTRAL_WRONG"
    return "HARMFUL"


sw_rows["category"] = sw_rows.apply(categorize, axis=1)
sw_dist = sw_rows["category"].value_counts().to_dict()
sw_total = max(int(len(sw_rows)), 1)
sw_pct = {k: 100 * v / sw_total for k, v in sw_dist.items()}
helpful_or_neutral = sum(sw_dist.get(k, 0) for k in ("HELPFUL", "NEUTRAL_CORRECT", "NEUTRAL_WRONG"))

# ---------------------------------------------------------------------------
# B3 — Annual attribution
# ---------------------------------------------------------------------------
mdf["year"] = mdf.index.year
b3_rows = []
for y, g in mdf.groupby("year"):
    b3_rows.append({
        "year": int(y),
        "v0": float((1 + g["v0"]).prod() - 1),
        "delta_switch_sum": float(g["c_switch"].sum()),
        "delta_top3_sum": float(g["c_top3"].sum()),
        "delta_gate_sum": float(g["c_gate"].sum()),
        "delta_defer_sum": float(g["c_defer"].sum()),
        "v4_total": float((1 + g["final"]).prod() - 1),
    })

# ---------------------------------------------------------------------------
# C1/C2/C3 — Correlation & factor analysis
# ---------------------------------------------------------------------------
# Key alignment: strategy return at rebal date d represents performance over the
# following ~21 trading days. So we must compute factor returns over THE SAME
# forward 21d window starting at the same rebal date, not trailing month returns.
print("Loading factor proxies…")


def load_close(t):
    p = ROOT / f"data/raw/yahoo/{t}.parquet"
    if not p.exists():
        return None
    d = pd.read_parquet(p)
    s = d["adj_close"] if "adj_close" in d.columns else d["close"]
    s.index = pd.to_datetime(d.index)
    return s.sort_index()


def fwd21_at_rebal(close, rebal_dates):
    """For each rebal date, compute the next-21-trading-day return using daily close."""
    if close is None: return None
    out = pd.Series(index=rebal_dates, dtype=float)
    cidx = close.index
    for d in rebal_dates:
        try:
            i = cidx.get_indexer([d], method="nearest")[0]
        except Exception:
            continue
        j = min(i + 21, len(close) - 1)
        if i == j:
            out.loc[d] = float("nan")
            continue
        out.loc[d] = float(close.iloc[j] / close.iloc[i] - 1)
    return out


# Use the rebal dates from mdf (these are the actual trading days at which
# the strategy compounds)
rebal_dates = pd.DatetimeIndex(mdf.index)
factors = {}
for tk in ["SPY", "MTUM", "VLUE", "QUAL", "GLD", "TLT"]:
    factors[tk] = fwd21_at_rebal(load_close(tk), rebal_dates)

# Strategy series stays on its native rebal-date index — perfectly aligned now.
strat = mdf["final"].copy()


def align(a, b):
    j = pd.concat([a.rename("s"), b.rename("f")], axis=1).dropna()
    return j["s"], j["f"]


# C1: SPY asymmetry
spy_m = factors["SPY"]
s_a, f_a = align(strat, spy_m)
up = f_a > 0; dn = f_a <= 0
c1 = {
    "corr_all": float(s_a.corr(f_a)),
    "corr_up": float(s_a[up].corr(f_a[up])) if up.sum() > 1 else float("nan"),
    "corr_dn": float(s_a[dn].corr(f_a[dn])) if dn.sum() > 1 else float("nan"),
    "strat_avg_up": float(s_a[up].mean()),
    "strat_avg_dn": float(s_a[dn].mean()),
    "spy_avg_up": float(f_a[up].mean()),
    "spy_avg_dn": float(f_a[dn].mean()),
    "upside_capture": float(s_a[up].mean() / f_a[up].mean()) if f_a[up].mean() != 0 else float("nan"),
    "downside_capture": float(s_a[dn].mean() / f_a[dn].mean()) if f_a[dn].mean() != 0 else float("nan"),
    "n_up": int(up.sum()), "n_dn": int(dn.sum()),
}

# C2: factor correlations
c2 = {}
mtum_corr_switch_on = mtum_corr_switch_off = float("nan")
for tk, ser in factors.items():
    if ser is None:
        c2[tk] = float("nan"); continue
    s_x, f_x = align(strat, ser)
    c2[tk] = float(s_x.corr(f_x)) if len(s_x) > 1 else float("nan")
if factors["MTUM"] is not None:
    swkey = mdf["switch_active"]
    j = pd.concat([strat.rename("s"), factors["MTUM"].rename("m"),
                   swkey.rename("sw")], axis=1).dropna()
    if j["sw"].sum() > 2:
        mtum_corr_switch_on = float(j[j["sw"]]["s"].corr(j[j["sw"]]["m"]))
    if (~j["sw"]).sum() > 2:
        mtum_corr_switch_off = float(j[~j["sw"]]["s"].corr(j[~j["sw"]]["m"]))

# C3: regime-conditional performance (actual regime, not predicted)
# Use current_reg_full at each month-end
mdf["actual_regime_code"] = mdf["current_regime"]
c3_rows = []
for code, label in enumerate(REGIME_CLASSES):
    g = mdf[mdf["actual_regime_code"] == code]
    if g.empty:
        c3_rows.append({"regime": REGIME_LABELS[label], "n": 0, "strat_cagr": float("nan"),
                        "spy_cagr": float("nan"), "excess": float("nan")})
        continue
    s_st = stats(g["final"].values)
    spy_part = spy_m.reindex(g.index).dropna()
    spy_st = stats(spy_part.values) if len(spy_part) else dict(cagr=float("nan"))
    c3_rows.append({
        "regime": REGIME_LABELS[label],
        "n": int(len(g)),
        "strat_cagr": s_st["cagr"],
        "spy_cagr": spy_st["cagr"],
        "excess": s_st["cagr"] - spy_st["cagr"] if spy_st["cagr"] == spy_st["cagr"] else float("nan"),
    })

# ---------------------------------------------------------------------------
# Stats summary
# ---------------------------------------------------------------------------
final_st = stats(mdf["final"].values)
v0_st = stats(mdf["v0"].values)
print(f"\nFINAL: CAGR {final_st['cagr']*100:.2f}%  Sharpe {final_st['sharpe']:.2f}  MaxDD {final_st['max_dd']*100:.2f}%")
print(f"V0   : CAGR {v0_st['cagr']*100:.2f}%  Sharpe {v0_st['sharpe']:.2f}")

# ---------------------------------------------------------------------------
# Write report
# ---------------------------------------------------------------------------
def fmt_pct(v): return "n/a" if v is None or v != v else f"{v*100:.2f}%"
def fmt_pp(v):  return "n/a" if v is None or v != v else f"{v*100:+.2f}pp"


lines = []
lines.append("# SIGNAL ANALYSIS REPORT — Strategy Attribution & Correlation\n")
lines.append("OPTIMIZED strategy: E-R1 (regime-conditional 63d/21d momentum) + M11 (top-3 inverse-vol) "
             "+ M26_post_3d (defer 3 trading days when within 0–2d after an FOMC decision).\n")
lines.append(f"Walk-forward monthly rebalances analyzed: **{len(mdf)}**")
lines.append(f"- V0 (base 63d top-1): CAGR {fmt_pct(v0_st['cagr'])}, Sharpe {v0_st['sharpe']:.2f}")
lines.append(f"- V4 (final): CAGR {fmt_pct(final_st['cagr'])}, Sharpe {final_st['sharpe']:.2f}, MaxDD {fmt_pct(final_st['max_dd'])}\n")

# B1
lines.append("## B1 — Component attribution\n")
lines.append("Contribution of each layer = ΔV between successive variants on the same monthly schedule.")
lines.append("Base row reports geometric (compounded) properties; incremental rows report additive monthly Δ.\n")
lines.append("| Component | Active months | Avg Δ when active | Total contribution | Best month | Worst month |")
lines.append("|---|---|---|---|---|---|")
for r in b1_rows:
    bm = f"{r['best_month'][0]} ({r['best_month'][1]*100:+.2f}%)" if r["best_month"] else "—"
    wm = f"{r['worst_month'][0]} ({r['worst_month'][1]*100:+.2f}%)" if r["worst_month"] else "—"
    lines.append(f"| {r['label']} | {r['active_months']} | {r['avg_when_active']*100:+.3f}% | "
                 f"{r['total_contribution']*100:+.2f}pp | {bm} | {wm} |")

# B2
lines.append("\n## B2 — Regime switch detailed analysis\n")
lines.append(f"Total switch-active months: **{sw_total}**\n")
lines.append("| Category | Count | % |")
lines.append("|---|---|---|")
for k in ("HELPFUL", "NEUTRAL_CORRECT", "NEUTRAL_WRONG", "HARMFUL"):
    n = sw_dist.get(k, 0)
    lines.append(f"| {k} | {n} | {sw_pct.get(k, 0):.1f}% |")
ratio_ok = (helpful_or_neutral / sw_total) >= 0.7 if sw_total else False
lines.append(f"\n**HELPFUL + NEUTRAL** = {helpful_or_neutral}/{sw_total} = "
             f"{100*helpful_or_neutral/max(sw_total,1):.1f}%  → "
             + ("✅ switch earns its place (≥70%)." if ratio_ok else "⚠️  below 70% bar."))

# Detail table (head)
lines.append("\n<details><summary>Switch month detail (first 25 rows)</summary>\n")
lines.append("\n| Date | Cur reg | Pred reg | Correct? | 63d pick | 21d pick | Δ (21−63) | Category |")
lines.append("|---|---|---|---|---|---|---|---|")
for d, row in sw_rows.head(25).iterrows():
    lines.append(f"| {d.date()} | {REGIME_CLASSES[row['current_regime']][7:]} | "
                 f"{REGIME_CLASSES[row['pred_regime']][7:] if row['pred_regime'] != -1 else 'n/a'} | "
                 f"{'Y' if row['pred_correct'] else 'N'} | {row['top1_63d_pick']} | {row['top1_21d_pick']} | "
                 f"{row['delta_21_vs_63']*100:+.2f}% | {row['category']} |")
lines.append("\n</details>\n")

# B3
lines.append("\n## B3 — Annual attribution\n")
lines.append("| Year | V0 base | + Switch | + Top-3 IV | + SMA gate | + M26 defer | = TOTAL |")
lines.append("|---|---|---|---|---|---|---|")
for r in b3_rows:
    lines.append(f"| {r['year']} | {fmt_pct(r['v0'])} | {fmt_pp(r['delta_switch_sum'])} | "
                 f"{fmt_pp(r['delta_top3_sum'])} | {fmt_pp(r['delta_gate_sum'])} | "
                 f"{fmt_pp(r['delta_defer_sum'])} | {fmt_pct(r['v4_total'])} |")

# C1
lines.append("\n## C1 — SPY market correlation asymmetry\n")
lines.append("| Regime | Corr w/ SPY | Strategy avg | SPY avg | n |")
lines.append("|---|---|---|---|---|")
lines.append(f"| SPY up months | {c1['corr_up']:.3f} | {c1['strat_avg_up']*100:+.2f}% | {c1['spy_avg_up']*100:+.2f}% | {c1['n_up']} |")
lines.append(f"| SPY down months | {c1['corr_dn']:.3f} | {c1['strat_avg_dn']*100:+.2f}% | {c1['spy_avg_dn']*100:+.2f}% | {c1['n_dn']} |")
lines.append(f"| All months | {c1['corr_all']:.3f} | — | — | {c1['n_up']+c1['n_dn']} |")
lines.append(f"\n- **Upside capture:** {c1['upside_capture']*100:.1f}%")
lines.append(f"- **Downside capture:** {c1['downside_capture']*100:.1f}%")

# C2
lines.append("\n## C2 — Factor correlations\n")
lines.append("| Factor | Correlation |")
lines.append("|---|---|")
for tk in ["SPY", "MTUM", "VLUE", "QUAL", "GLD", "TLT"]:
    v = c2.get(tk, float("nan"))
    lines.append(f"| {tk} | {'n/a' if v != v else f'{v:.3f}'} |")
lines.append(f"\nMTUM correlation **on switch months**: {mtum_corr_switch_on:.3f}  vs  "
             f"**off switch months**: {mtum_corr_switch_off:.3f}")
if c2.get("MTUM", 0) > 0.85:
    lines.append("\n> ⚠️  MTUM correlation > 0.85 — strategy is largely momentum with extra steps.")
if mtum_corr_switch_on < mtum_corr_switch_off:
    lines.append("> ✅ Regime switch reduces MTUM correlation during transitions (as designed).")
else:
    lines.append("> ⚠️  Regime switch does NOT reduce MTUM correlation during transitions.")

# C3
lines.append("\n## C3 — Performance by ACTUAL growth-inflation regime\n")
lines.append("| Actual regime | Months | Strategy CAGR | SPY CAGR | Excess |")
lines.append("|---|---|---|---|---|")
for r in c3_rows:
    lines.append(f"| {r['regime']} | {r['n']} | {fmt_pct(r['strat_cagr'])} | "
                 f"{fmt_pct(r['spy_cagr'])} | {fmt_pp(r['excess'])} |")

(OUT / "SIGNAL_ANALYSIS_REPORT.md").write_text("\n".join(lines), encoding="utf-8")
print(f"\nWrote {OUT / 'SIGNAL_ANALYSIS_REPORT.md'}")

# Dump JSON
(OUT / "signal_analysis.json").write_text(json.dumps({
    "v0_stats": v0_st, "v4_stats": final_st,
    "b1": b1_rows, "b2_dist": sw_dist, "b2_n": sw_total,
    "b3": b3_rows, "c1": c1, "c2": c2,
    "c2_mtum_switch_on": mtum_corr_switch_on, "c2_mtum_switch_off": mtum_corr_switch_off,
    "c3": c3_rows,
}, indent=2, default=str))
print("Done.")
