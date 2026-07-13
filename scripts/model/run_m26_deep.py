"""M26 deep dive: FOMC deferral on top of OPTIMIZED (E-R1 + M11 inv_vol).

Tests:
  1) M26 on OPTIMIZED (defer 5d around FOMC +/- 2)
  2) Window sensitivity (3/5/7/10 day deferrals)
  3) Multi-event stacking (FOMC/CPI/NFP/quad witching)
  4) Worst-drawdown mechanism check (March 2020, Q4 2018, 2022)
  5) False cost check (does deferral actually change picks?)

Outputs:
  results/experiments/M26_deep.json
  results/M26_ANALYSIS.md
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

OUT_DIR = ROOT / "results/experiments"

# Universe / spec from OPTIMIZED_STRATEGY.md
ETFS = ["SOXX", "QQQ", "XLK", "VGT", "IGV", "XLE", "GLD", "SHY"]
LB_STABLE = 63
LB_TRANS = 21
K = 3
W_TOP1 = 0.5
W_TOPK = 0.5

SPLIT_KW = dict(
    min_train_months=60, val_months=6, test_months=3, step_months=3,
    sample_every_n_days=5, embargo_days=5, target_horizon=21,
    decay_halflife_months=36,
)
REGIME_CLASSES = ["regime_hg_li", "regime_hg_hi", "regime_lg_li", "regime_lg_hi_stagflation"]
REGIME_FEATS = [f"regime_growth_inflation__{c}" for c in REGIME_CLASSES]

print("Loading master panel…")
df = pd.read_parquet(ROOT / "data/features/master_panel.parquet")
feature_sets = yaml.safe_load(open(ROOT / "configs/feature_sets.yaml"))
core_feats = [c for c in feature_sets["core"] if c in df.columns]
DATES = df.index
NDAYS = len(df)

def load_ret(days):
    return pd.read_parquet(ROOT / f"data/features/price/returns_{days}d.parquet").reindex(DATES)

R = {d: load_ret(d) for d in (21, 63)}
ALL = list(set(ETFS))

def fwd21(t):
    col = f"TARGET_FWD21_{t}"
    if col in df.columns:
        return df[col].values
    s = R[21][t].shift(-21)
    return s.reindex(DATES).values

FWD = {t: fwd21(t) for t in ALL}
shy_ret = FWD["SHY"]
spy_dist = df["quality_dist_sma200__SPY"].values

# WF regime classifier (same as run_optimization_block)
splitter = ExpandingSplitter(**SPLIT_KW)
folds = splitter.split(DATES)
test_dates = pd.DatetimeIndex(sorted(set(d for f in folds for d in f["test_dates"])))
te_pos = DATES.get_indexer(test_dates)
print(f"  folds={len(folds)} test_dates={len(test_dates)}")

target_col = "TARGET_TREG_growth_inflation_fwd21"
cls_to_idx = {c: i for i, c in enumerate(REGIME_CLASSES)}
current_reg = df[REGIME_FEATS].values.argmax(axis=1)
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
    proba = clf.predict_proba(Xte_z)
    full = np.zeros((len(Xte_z), 4))
    for j, c in enumerate(clf.classes_):
        full[:, int(c)] = proba[:, j]
    pr = np.argmax(full, axis=1)
    pred_reg[DATES.get_indexer(te)] = pr

# momentum arrays
def mom_arr(lookback):
    a = np.full((NDAYS, len(ETFS)), np.nan)
    rdf = R[lookback]
    for j, t in enumerate(ETFS):
        a[:, j] = rdf[t].reindex(DATES).values
    return a

M_STABLE = mom_arr(LB_STABLE)
M_TRANS = mom_arr(LB_TRANS)
use_trans = (pred_reg != -1) & (pred_reg != current_reg)
MOM = np.where(use_trans[:, None], M_TRANS, M_STABLE)
SF = np.where(np.isnan(MOM), -np.inf, MOM)

FWD_ARR = np.full((NDAYS, len(ETFS)), np.nan)
for j, t in enumerate(ETFS):
    FWD_ARR[:, j] = FWD[t]

# ATR for inv_vol
atr21 = pd.read_parquet(ROOT / "data/features/price/atr_21d.parquet").reindex(DATES)
ATR = np.full((NDAYS, len(ETFS)), np.nan)
for j, t in enumerate(ETFS):
    if t in atr21.columns:
        ATR[:, j] = atr21[t].values

# event windows
is_fomc_day = (df["timing__is_fomc_day"].values > 0)
is_cpi_wk = (df["timing__is_cpi_week"].values > 0)
is_nfp_wk = (df["timing__is_nfp_week"].values > 0)
is_quad_wk = (df["timing__is_quad_witching_week"].values > 0)

fomc_day_idx = np.where(is_fomc_day)[0]

def fomc_window_mask(pre_days=2, post_days=2):
    """True on trading-day positions within [-pre, +post] of any FOMC day."""
    m = np.zeros(NDAYS, bool)
    for i in fomc_day_idx:
        lo = max(0, i - pre_days)
        hi = min(NDAYS - 1, i + post_days)
        m[lo:hi + 1] = True
    return m

FOMC_WIN = fomc_window_mask(2, 2)  # ±2 trading days

# strategy core (inv_vol top-k, SMA200 gate on top-1, single date)
def pick_at(i):
    """Return (top1_idx, topk_idx_sorted) at daily position i."""
    sf_i = SF[i]
    top1 = int(np.argmax(sf_i))
    tk = np.argsort(-sf_i)[:K]
    return top1, tk

def ret_at(i, top1, tk):
    r1 = FWD_ARR[i, top1] if spy_dist[i] > -0.04 else shy_ret[i]
    # inv-vol weighted top-k
    sel_atr = ATR[i, tk]
    inv = 1.0 / np.where(sel_atr > 0, sel_atr, np.nan)
    if np.isnan(inv).all():
        rk = np.nanmean(FWD_ARR[i, tk])
    else:
        w = inv / np.nansum(inv)
        rk = np.nansum(FWD_ARR[i, tk] * w)
    return W_TOP1 * r1 + W_TOPK * rk

# monthly rebalance engine
def month_last_positions():
    """For each month in test_dates, return (period, daily_pos)."""
    s = pd.Series(te_pos, index=test_dates)
    last = s.groupby(test_dates.to_period("M")).tail(1)
    return last  # index=month-end date, values=daily pos

MONTH_POS = month_last_positions()

def run_variant(deferral_days=0, event_mask=None, label=""):
    """Return (series indexed by rebal date, picks log dataframe)."""
    out = {}
    picks = []
    for d, i in MONTH_POS.items():
        i = int(i)
        deferred = False
        if deferral_days > 0 and event_mask is not None and event_mask[i]:
            i_use = min(i + deferral_days, NDAYS - 1)
            deferred = True
        else:
            i_use = i
        top1, tk = pick_at(i_use)
        r = ret_at(i_use, top1, tk)
        out[d] = r
        picks.append({
            "rebal_date": d, "orig_i": i, "used_i": i_use,
            "deferred": deferred,
            "top1": ETFS[top1], "topk": [ETFS[j] for j in tk],
            "ret": float(r),
        })
    return pd.Series(out).sort_index(), pd.DataFrame(picks)

# stats helpers
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

def annual_returns(s):
    if len(s) == 0: return {}
    eq = (1 + s).cumprod()
    yr = s.index.to_series().dt.year
    out = {}
    for y, idx in s.groupby(yr).groups.items():
        r = s.loc[idx]
        out[int(y)] = float((1 + r).prod() - 1)
    return out

def drawdown_periods(s, top_n=5):
    """Return top-N non-overlapping drawdown episodes."""
    eq = (1 + s).cumprod()
    peak = eq.cummax()
    dd = eq / peak - 1
    # find episodes: start at each new peak, end at next peak
    episodes = []
    in_dd = False
    start = None
    trough = None
    trough_val = 0
    for t, v in dd.items():
        if v < 0 and not in_dd:
            in_dd = True
            start = t; trough = t; trough_val = v
        elif v < 0 and in_dd:
            if v < trough_val:
                trough = t; trough_val = v
        elif v >= 0 and in_dd:
            episodes.append({"start": start, "trough": trough, "end": t, "dd": trough_val})
            in_dd = False
    if in_dd:
        episodes.append({"start": start, "trough": trough, "end": dd.index[-1], "dd": trough_val})
    episodes.sort(key=lambda e: e["dd"])
    return episodes[:top_n]

if __name__ == "__main__":
    # TEST 1 — OPTIMIZED base vs OPTIMIZED + M26 (defer 5d)
    print("\n=== TEST 1: OPTIMIZED base vs +M26 (5d) ===")
    base_s, base_picks = run_variant(deferral_days=0, event_mask=None)
    m26_s, m26_picks = run_variant(deferral_days=5, event_mask=FOMC_WIN)
    base_st = stats(base_s.values)
    m26_st = stats(m26_s.values)
    print(f"  OPTIMIZED      : CAGR {base_st['cagr']*100:.2f}%  Sharpe {base_st['sharpe']:.2f}  MaxDD {base_st['max_dd']*100:.2f}%")
    print(f"  OPTIMIZED+M26  : CAGR {m26_st['cagr']*100:.2f}%  Sharpe {m26_st['sharpe']:.2f}  MaxDD {m26_st['max_dd']*100:.2f}%")
    print(f"  d               : dCAGR {(m26_st['cagr']-base_st['cagr'])*100:+.2f}pp  dSharpe {m26_st['sharpe']-base_st['sharpe']:+.2f}  dMaxDD {(m26_st['max_dd']-base_st['max_dd'])*100:+.2f}pp")

    n_deferred = int(m26_picks["deferred"].sum())
    print(f"  n_rebals={len(m26_picks)}  n_deferred={n_deferred}")

    # TEST 2 — Deferral window sensitivity
    print("\n=== TEST 2: Deferral window sensitivity ===")
    window_results = {}
    for days in (3, 5, 7, 10):
        s, _ = run_variant(deferral_days=days, event_mask=FOMC_WIN)
        st = stats(s.values)
        window_results[f"defer_{days}d"] = st
        print(f"  defer {days:2d}d : CAGR {st['cagr']*100:.2f}%  Sharpe {st['sharpe']:.2f}  MaxDD {st['max_dd']*100:.2f}%")

    # TEST 3 — Multi-event stacking (5d deferral, varying event sets)
    print("\n=== TEST 3: Multi-event stacking (5d defer) ===")
    def make_week_mask(flag_arr, pre=2, post=2):
        """For a 'week' flag, window it ±pre/post trading days."""
        idx = np.where(flag_arr)[0]
        m = np.zeros(NDAYS, bool)
        # flag_arr is already a whole week; just use it directly
        m[idx] = True
        return m

    masks = {
        "M26a_FOMC":          FOMC_WIN,
        "M26b_FOMC_CPI":      FOMC_WIN | is_cpi_wk,
        "M26c_FOMC_CPI_NFP":  FOMC_WIN | is_cpi_wk | is_nfp_wk,
        "M26d_all_events":    FOMC_WIN | is_cpi_wk | is_nfp_wk | is_quad_wk,
    }
    stack_results = {}
    for lbl, mk in masks.items():
        s, p = run_variant(deferral_days=5, event_mask=mk)
        st = stats(s.values)
        stack_results[lbl] = {**st, "n_deferred": int(p["deferred"].sum())}
        print(f"  {lbl:20s}: CAGR {st['cagr']*100:.2f}%  Sharpe {st['sharpe']:.2f}  MaxDD {st['max_dd']*100:.2f}%  deferred={int(p['deferred'].sum())}")

    # TEST 4 — Drawdown deep dive (OPTIMIZED vs OPTIMIZED+M26)
    print("\n=== TEST 4: Drawdown deep dive ===")
    base_dd = drawdown_periods(base_s, top_n=5)
    m26_dd = drawdown_periods(m26_s, top_n=5)

    def fomc_in_range(start, end):
        start = pd.Timestamp(start); end = pd.Timestamp(end)
        fds = [DATES[i].strftime("%Y-%m-%d") for i in fomc_day_idx
               if start <= DATES[i] <= end]
        return fds

    def summarize_dd(eps, label):
        rows = []
        for e in eps:
            fds = fomc_in_range(e["start"], e["end"])
            rows.append({
                "start": str(e["start"].date()),
                "trough": str(e["trough"].date()),
                "end": str(e["end"].date()),
                "dd": round(e["dd"] * 100, 2),
                "fomc_meetings": fds,
                "n_fomc": len(fds),
            })
            print(f"  {label:10s}: {e['start'].date()} -> {e['trough'].date()} -> {e['end'].date()}  dd={e['dd']*100:.2f}%  FOMC={len(fds)}")
        return rows

    base_dd_rows = summarize_dd(base_dd, "BASE")
    m26_dd_rows = summarize_dd(m26_dd, "M26")

    # Targeted check: March 2020, Q4 2018, 2022
    targets = [
        ("March 2020", "2020-02-01", "2020-06-01"),
        ("Q4 2018",    "2018-09-01", "2019-02-01"),
        ("2022",       "2022-01-01", "2023-01-01"),
    ]
    target_analysis = []
    for name, s0, s1 in targets:
        base_w = base_s[(base_s.index >= s0) & (base_s.index <= s1)]
        m26_w = m26_s[(m26_s.index >= s0) & (m26_s.index <= s1)]
        base_cum = float((1 + base_w).prod() - 1) if len(base_w) else 0
        m26_cum = float((1 + m26_w).prod() - 1) if len(m26_w) else 0
        fds = fomc_in_range(pd.Timestamp(s0), pd.Timestamp(s1))
        deferred_here = m26_picks[(m26_picks["rebal_date"] >= s0) & (m26_picks["rebal_date"] <= s1) & m26_picks["deferred"]]
        target_analysis.append({
            "name": name, "start": s0, "end": s1,
            "base_cum_ret": round(base_cum * 100, 2),
            "m26_cum_ret": round(m26_cum * 100, 2),
            "delta_pp": round((m26_cum - base_cum) * 100, 2),
            "n_fomc": len(fds),
            "fomc_meetings": fds,
            "n_deferred_rebals": int(len(deferred_here)),
            "deferred_dates": [str(d.date()) for d in deferred_here["rebal_date"]],
        })
        print(f"  {name:12s}: base {base_cum*100:+.2f}%  M26 {m26_cum*100:+.2f}%  d {(m26_cum-base_cum)*100:+.2f}pp  FOMC={len(fds)}  deferred={len(deferred_here)}")

    # TEST 5 — False cost check (pick diffs on deferred months)
    print("\n=== TEST 5: False cost check ===")
    merged = base_picks.merge(m26_picks, on="rebal_date", suffixes=("_base", "_m26"))
    deferred_rows = merged[merged["deferred_m26"]].copy()
    deferred_rows["top1_changed"] = deferred_rows["top1_base"] != deferred_rows["top1_m26"]
    deferred_rows["topk_changed"] = deferred_rows.apply(
        lambda r: tuple(r["topk_base"]) != tuple(r["topk_m26"]), axis=1
    )
    deferred_rows["ret_delta"] = deferred_rows["ret_m26"] - deferred_rows["ret_base"]

    n_def = len(deferred_rows)
    n_top1_diff = int(deferred_rows["top1_changed"].sum())
    n_topk_diff = int(deferred_rows["topk_changed"].sum())
    better = int((deferred_rows.loc[deferred_rows["top1_changed"], "ret_delta"] > 0).sum())
    worse = int((deferred_rows.loc[deferred_rows["top1_changed"], "ret_delta"] < 0).sum())
    avg_delta_changed = float(deferred_rows.loc[deferred_rows["top1_changed"], "ret_delta"].mean()) if n_top1_diff else 0.0

    print(f"  deferred rebalances: {n_def}")
    print(f"  top1 pick changed  : {n_top1_diff}  (better {better} / worse {worse})")
    print(f"  topk set changed   : {n_topk_diff}")
    print(f"  avg ret delta (when top1 changed): {avg_delta_changed*100:+.2f}pp")

    false_cost = {
        "n_deferred": n_def,
        "n_top1_changed": n_top1_diff,
        "n_topk_changed": n_topk_diff,
        "n_better_when_changed": better,
        "n_worse_when_changed": worse,
        "avg_ret_delta_when_changed_pp": round(avg_delta_changed * 100, 3),
        "changed_examples": deferred_rows[deferred_rows["top1_changed"]][
            ["rebal_date", "top1_base", "top1_m26", "ret_delta"]
        ].head(20).assign(
            rebal_date=lambda d: d["rebal_date"].astype(str),
            ret_delta=lambda d: d["ret_delta"].round(4),
        ).to_dict("records"),
    }

    # VERDICT
    dd_improvement_pp = (m26_st["max_dd"] - base_st["max_dd"]) * 100  # both negative; positive = better (less deep)
    cagr_drop_pp = (base_st["cagr"] - m26_st["cagr"]) * 100
    verdict_pass = (
        dd_improvement_pp > 4.0
        and cagr_drop_pp < 1.0
        and any(t["n_fomc"] > 0 for t in target_analysis)
    )
    print("\n=== VERDICT ===")
    print(f"  MaxDD improvement: {dd_improvement_pp:+.2f}pp (need >4pp)")
    print(f"  CAGR drop        : {cagr_drop_pp:+.2f}pp (need <1pp)")
    print(f"  FOMC in targets  : {any(t['n_fomc']>0 for t in target_analysis)}")
    print(f"  VERDICT          : {'INCLUDE' if verdict_pass else 'DROP'}")

    # save outputs
    payload = {
        "description": "M26 deep dive on OPTIMIZED (E-R1 + M11 inv_vol)",
        "optimized_base": {
            "stats": base_st,
            "annual_returns": annual_returns(base_s),
        },
        "test1_m26_5d": {
            "stats": m26_st,
            "annual_returns": annual_returns(m26_s),
            "n_rebals": int(len(m26_picks)),
            "n_deferred": n_deferred,
            "delta_vs_base": {
                "cagr_pp": round((m26_st["cagr"] - base_st["cagr"]) * 100, 3),
                "sharpe": round(m26_st["sharpe"] - base_st["sharpe"], 3),
                "maxdd_pp": round((m26_st["max_dd"] - base_st["max_dd"]) * 100, 3),
            },
        },
        "test2_window_sensitivity": window_results,
        "test3_event_stacking": stack_results,
        "test4_drawdown_deep_dive": {
            "base_top5_dds": base_dd_rows,
            "m26_top5_dds": m26_dd_rows,
            "targeted_windows": target_analysis,
        },
        "test5_false_cost": false_cost,
        "verdict": {
            "dd_improvement_pp": round(dd_improvement_pp, 3),
            "cagr_drop_pp": round(cagr_drop_pp, 3),
            "pass": bool(verdict_pass),
        },
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "M26_deep.json").write_text(json.dumps(payload, indent=2, default=str))
    print(f"\nWrote {OUT_DIR / 'M26_deep.json'}")

    # markdown report
    def fmt_pct(v): return f"{v*100:.2f}%" if v == v else "n/a"

    md = []
    md.append("# M26 DEEP DIVE — FOMC Deferral on OPTIMIZED Strategy\n")
    md.append("Tests whether FOMC rebalancing deferral (M26) improves the OPTIMIZED strategy (E-R1 + M11 inverse-vol) rather than just the E-R1 baseline.\n")
    md.append("## TL;DR\n")
    md.append(f"- OPTIMIZED base: CAGR **{fmt_pct(base_st['cagr'])}**, Sharpe {base_st['sharpe']:.2f}, MaxDD {fmt_pct(base_st['max_dd'])}")
    md.append(f"- OPTIMIZED + M26 (5d): CAGR **{fmt_pct(m26_st['cagr'])}**, Sharpe {m26_st['sharpe']:.2f}, MaxDD {fmt_pct(m26_st['max_dd'])}")
    md.append(f"- d: CAGR {(m26_st['cagr']-base_st['cagr'])*100:+.2f}pp, Sharpe {m26_st['sharpe']-base_st['sharpe']:+.2f}, MaxDD {(m26_st['max_dd']-base_st['max_dd'])*100:+.2f}pp")
    md.append(f"- **Verdict: {'INCLUDE M26' if verdict_pass else 'DROP M26'}**\n")

    md.append("## Test 1 — M26 on OPTIMIZED\n")
    md.append("Defer scheduled month-end rebalance by 5 trading days if date falls within ±2 trading days of an FOMC decision.\n")
    md.append("| Strategy | CAGR | Sharpe | MaxDD | d vs base |")
    md.append("|---|---|---|---|---|")
    md.append(f"| OPTIMIZED | {fmt_pct(base_st['cagr'])} | {base_st['sharpe']:.2f} | {fmt_pct(base_st['max_dd'])} | — |")
    md.append(f"| + M26 (5d) | {fmt_pct(m26_st['cagr'])} | {m26_st['sharpe']:.2f} | {fmt_pct(m26_st['max_dd'])} | "
              f"dCAGR {(m26_st['cagr']-base_st['cagr'])*100:+.2f}pp, dDD {(m26_st['max_dd']-base_st['max_dd'])*100:+.2f}pp |")
    md.append(f"\nDeferrals triggered: {n_deferred} / {len(m26_picks)} rebalances.\n")

    md.append("### Annual returns\n")
    ba = annual_returns(base_s); ma = annual_returns(m26_s)
    years = sorted(set(ba) | set(ma))
    md.append("| Year | OPTIMIZED | +M26 | d |")
    md.append("|---|---|---|---|")
    for y in years:
        b = ba.get(y); m = ma.get(y)
        db = f"{b*100:+.2f}%" if b is not None else "—"
        dm = f"{m*100:+.2f}%" if m is not None else "—"
        dd_ = f"{(m-b)*100:+.2f}pp" if (b is not None and m is not None) else "—"
        md.append(f"| {y} | {db} | {dm} | {dd_} |")

    md.append("\n## Test 2 — Deferral window sensitivity\n")
    md.append("| Window | CAGR | Sharpe | MaxDD |")
    md.append("|---|---|---|---|")
    for lbl, st in window_results.items():
        md.append(f"| {lbl} | {fmt_pct(st['cagr'])} | {st['sharpe']:.2f} | {fmt_pct(st['max_dd'])} |")

    md.append("\n## Test 3 — Multi-event stacking (5d defer)\n")
    md.append("| Variant | Events | CAGR | Sharpe | MaxDD | Deferred |")
    md.append("|---|---|---|---|---|---|")
    event_desc = {
        "M26a_FOMC": "FOMC ±2",
        "M26b_FOMC_CPI": "+ CPI week",
        "M26c_FOMC_CPI_NFP": "+ NFP week",
        "M26d_all_events": "+ quad witching",
    }
    for lbl, st in stack_results.items():
        md.append(f"| {lbl} | {event_desc[lbl]} | {fmt_pct(st['cagr'])} | {st['sharpe']:.2f} | {fmt_pct(st['max_dd'])} | {st['n_deferred']} |")

    md.append("\n## Test 4 — Drawdown deep dive\n")
    md.append("### Top-5 drawdowns (OPTIMIZED base)\n")
    md.append("| Start | Trough | End | DD | FOMC in range |")
    md.append("|---|---|---|---|---|")
    for r in base_dd_rows:
        md.append(f"| {r['start']} | {r['trough']} | {r['end']} | {r['dd']}% | {r['n_fomc']} |")

    md.append("\n### Top-5 drawdowns (OPTIMIZED + M26)\n")
    md.append("| Start | Trough | End | DD | FOMC in range |")
    md.append("|---|---|---|---|---|")
    for r in m26_dd_rows:
        md.append(f"| {r['start']} | {r['trough']} | {r['end']} | {r['dd']}% | {r['n_fomc']} |")

    md.append("\n### Targeted windows\n")
    md.append("| Period | Base cum | M26 cum | d | FOMC | Deferred |")
    md.append("|---|---|---|---|---|---|")
    for t in target_analysis:
        md.append(f"| {t['name']} | {t['base_cum_ret']:+.2f}% | {t['m26_cum_ret']:+.2f}% | {t['delta_pp']:+.2f}pp | {t['n_fomc']} | {t['n_deferred_rebals']} |")

    md.append("\n## Test 5 — False cost check\n")
    md.append(f"- Deferred rebalances: **{n_def}**")
    md.append(f"- Top-1 pick differed after 5d shift: **{n_top1_diff}** ({n_top1_diff/max(n_def,1)*100:.0f}%)")
    md.append(f"- Top-k set differed: **{n_topk_diff}**")
    md.append(f"- When top-1 changed: better={better}, worse={worse}, avg dret={avg_delta_changed*100:+.2f}pp\n")
    if n_top1_diff:
        md.append("Pick-change examples (first 20):\n")
        md.append("| Date | Base top1 | M26 top1 | dret |")
        md.append("|---|---|---|---|")
        for r in false_cost["changed_examples"]:
            md.append(f"| {r['rebal_date']} | {r['top1_base']} | {r['top1_m26']} | {r['ret_delta']*100:+.2f}% |")
    else:
        md.append("_No top-1 changes: the 5-day shift was free._\n")

    md.append("\n## Verdict\n")
    md.append(f"- MaxDD improvement: **{dd_improvement_pp:+.2f}pp** (threshold >4pp)")
    md.append(f"- CAGR drop       : **{cagr_drop_pp:+.2f}pp** (threshold <1pp)")
    md.append(f"- Mechanism (FOMC in target drawdowns): **{'yes' if any(t['n_fomc']>0 for t in target_analysis) else 'no'}**")
    md.append(f"- **Decision: {'INCLUDE M26 in OPTIMIZED' if verdict_pass else 'DROP M26'}**\n")

    (ROOT / "results/M26_ANALYSIS.md").write_text("\n".join(md), encoding="utf-8")
    print(f"Wrote results/M26_ANALYSIS.md")

    # optionally update OPTIMIZED_STRATEGY.md
    if verdict_pass:
        opt_path = ROOT / "results/OPTIMIZED_STRATEGY.md"
        lines = opt_path.read_text(encoding="utf-8").splitlines()
        updated = []
        for ln in lines:
            if ln.startswith("- Rebalancing variant:"):
                updated.append("- Rebalancing variant: monthly + M26 FOMC deferral (defer 5 trading days if rebalance falls within ±2 trading days of FOMC decision)")
            elif ln.startswith("- CAGR:"):
                updated.append(f"- CAGR: **{fmt_pct(m26_st['cagr'])}**")
            elif ln.startswith("- Sharpe:"):
                updated.append(f"- Sharpe: **{m26_st['sharpe']:.2f}**")
            elif ln.startswith("- MaxDD:"):
                updated.append(f"- MaxDD: **{fmt_pct(m26_st['max_dd'])}**")
            elif ln.startswith("- vs E-R1"):
                updated.append(ln + f"  \n- +M26 vs OPTIMIZED: dCAGR {(m26_st['cagr']-base_st['cagr'])*100:+.2f}pp, dSharpe {m26_st['sharpe']-base_st['sharpe']:+.2f}, dMaxDD {(m26_st['max_dd']-base_st['max_dd'])*100:+.2f}pp")
            else:
                updated.append(ln)
        opt_path.write_text("\n".join(updated), encoding="utf-8")
        print("Updated results/OPTIMIZED_STRATEGY.md with M26")

    print("\nDone.")
