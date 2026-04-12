"""Final search for the best ensemble: hybrid two-leg + soft trend gate +
ML drawdown overlay (optional). Tests the most promising configurations.
"""
import sys
import numpy as np
import pandas as pd
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from model.walk_forward import ExpandingSplitter

df = pd.read_parquet(ROOT / "data/features/master_panel.parquet")
r63 = pd.read_parquet(ROOT / "data/features/price/returns_63d.parquet")
r126 = pd.read_parquet(ROOT / "data/features/price/returns_126d.parquet")
r42 = pd.read_parquet(ROOT / "data/features/price/returns_42d.parquet")

ETFS = ["SOXX", "QQQ", "XLK", "VGT", "IGV", "XLE", "GLD", "SHY"]
mom = r63[ETFS].reindex(df.index).values
mom126 = r126[ETFS].reindex(df.index).values
mom42 = r42[ETFS].reindex(df.index).values
fwd = df[[f"TARGET_FWD21_{tk}" for tk in ETFS]].copy()
fwd.columns = ETFS
fwd_arr = fwd.values
shy_ret = fwd["SHY"].values

splitter = ExpandingSplitter(min_train_months=60, val_months=6, test_months=3,
                             step_months=3, sample_every_n_days=5, embargo_days=5,
                             target_horizon=21, decay_halflife_months=36)
folds = splitter.split(df.index)
test_dates = pd.DatetimeIndex(sorted(set(d for f in folds for d in f["test_dates"])))
te_pos = df.index.get_indexer(test_dates)


def stats(r):
    r = np.asarray(r); r = r[~np.isnan(r)]
    eq = np.cumprod(1 + r); years = len(r) / 12
    cagr = eq[-1] ** (1 / years) - 1
    sd = r.std(ddof=1)
    sh = r.mean() / sd * np.sqrt(12) if sd > 0 else float("nan")
    peak = np.maximum.accumulate(eq)
    dd = (eq / peak - 1).min()
    return cagr, sh, dd


def to_monthly(daily):
    s = pd.Series(daily, index=test_dates).dropna()
    return s.groupby(s.index.to_period("M")).tail(1)


def evaluate(name, daily):
    sm = to_monthly(daily)
    s = stats(sm.values)
    print(f"{name:60s} CAGR={s[0]*100:5.1f}%  Sharpe={s[1]:4.2f}  MaxDD={s[2]*100:6.1f}%")
    return s, sm


def topk(sig, k):
    sig_filled = np.where(np.isnan(sig), -np.inf, sig)
    sig_te = sig_filled[te_pos]
    fwd_te = fwd_arr[te_pos]
    if k == 1:
        return fwd_te[np.arange(len(te_pos)), np.argmax(sig_te, axis=1)]
    idx = np.argsort(-sig_te, axis=1)[:, :k]
    return fwd_te[np.arange(len(te_pos))[:, None], idx].mean(axis=1)


def rank_avg_topk(sigs, k):
    rk_sum = np.zeros((len(df), len(ETFS)))
    for s in sigs:
        sf = np.where(np.isnan(s), -np.inf, s)
        order = np.argsort(-sf, axis=1)
        rk = np.empty_like(order)
        for i in range(len(df)):
            rk[i, order[i]] = np.arange(len(ETFS))
        rk_sum += rk
    rk_te = rk_sum[te_pos]
    fwd_te = fwd_arr[te_pos]
    if k == 1:
        return fwd_te[np.arange(len(te_pos)), np.argmin(rk_te, axis=1)]
    idx = np.argsort(rk_te, axis=1)[:, :k]
    return fwd_te[np.arange(len(te_pos))[:, None], idx].mean(axis=1)


top1_63 = topk(mom, 1)
top3_63 = topk(mom, 3)
ra2_top1 = rank_avg_topk([mom, mom126], 1)
ra2_top3 = rank_avg_topk([mom, mom126], 3)
ra3_top3 = rank_avg_topk([mom, mom126, mom42], 3)
shy_te = shy_ret[te_pos]

# Trend gate features
spy_dist = df["quality_dist_sma200__SPY"].values[te_pos]
spy_dist50 = df["quality_dist_sma50__SPY"].values[te_pos]
vix = df["vol_features__vix"].values[te_pos]
hyig = df["credit_features__hy_ig_spread"].values[te_pos]
nfci = df["credit_features__nfci"].values[te_pos]

print("=== Reference baselines ===")
evaluate("B3 top1 63d", top1_63)
evaluate("top-3 63d", top3_63)
evaluate("rank-avg(63,126,42) top3 (lowest MaxDD)", ra3_top3)

# Hybrid: top-1 with trend gate + top-3 always
def trend_gate(base, threshold=-0.04):
    return np.where(spy_dist > threshold, base, shy_te)

print("\n=== Two-leg hybrid ensembles ===")
evaluate("0.5*[top1 + SMA-4% gate] + 0.5*top3",
         0.5 * trend_gate(top1_63, -0.04) + 0.5 * top3_63)
evaluate("0.5*[top1 + SMA-2% gate] + 0.5*top3",
         0.5 * trend_gate(top1_63, -0.02) + 0.5 * top3_63)
evaluate("0.6*[top1 + SMA-4%] + 0.4*top3",
         0.6 * trend_gate(top1_63, -0.04) + 0.4 * top3_63)
evaluate("0.4*[top1 + SMA-4%] + 0.6*top3",
         0.4 * trend_gate(top1_63, -0.04) + 0.6 * top3_63)

# Try: top1 + SMA gate ALONE -- this had 20.3/1.08/-22.3
# Add a small SHY allocation:
print("\n=== SMA-gated top-1 with overlay ===")
evaluate("[top1+SMA-4%] only", trend_gate(top1_63, -0.04))
evaluate("0.85*[top1+SMA-4%] + 0.15*SHY", 0.85*trend_gate(top1_63,-0.04)+0.15*shy_te)
evaluate("0.8*[top1+SMA-4%] + 0.2*SHY", 0.8*trend_gate(top1_63,-0.04)+0.2*shy_te)
evaluate("0.9*[top1+SMA-4%] + 0.1*SHY", 0.9*trend_gate(top1_63,-0.04)+0.1*shy_te)

print("\n=== Three-leg ensembles ===")
evaluate("(top1+top3+ra3_top3)/3", (top1_63+top3_63+ra3_top3)/3)
evaluate("(top1_gated+top3+ra3_top3)/3",
         (trend_gate(top1_63,-0.04)+top3_63+ra3_top3)/3)
evaluate("(top1+top3+ra2_top1)/3", (top1_63+top3_63+ra2_top1)/3)
evaluate("(top1+top3+ra2_top1+ra2_top3)/4", (top1_63+top3_63+ra2_top1+ra2_top3)/4)
evaluate("(top1_gated+top3+ra2_top1_gated)/3",
         (trend_gate(top1_63,-0.04)+top3_63+trend_gate(ra2_top1,-0.04))/3)

# Quintet
print("\n=== Big ensembles ===")
strats = {"top1": top1_63, "top3": top3_63, "ra2_top1": ra2_top1,
          "ra2_top3": ra2_top3, "ra3_top3": ra3_top3}
def avg(*names):
    return np.mean([strats[n] for n in names], axis=0)
evaluate("ensemble all 5", avg("top1","top3","ra2_top1","ra2_top3","ra3_top3"))
evaluate("3 high-CAGR (top1, ra2_top1, top3)", avg("top1","ra2_top1","top3"))
evaluate("3 high-Sharpe (top3, ra2_top3, ra3_top3)", avg("top3","ra2_top3","ra3_top3"))
evaluate("4 (top1, top3, ra2_top1, ra3_top3)", avg("top1","top3","ra2_top1","ra3_top3"))
evaluate("0.5*top1 + 0.5*ra2_top1", 0.5*top1_63+0.5*ra2_top1)

# Best so far: try variations of the ensemble + SHY drag
print("\n=== Adding SHY drag to ensembles ===")
ens = (top1_63+top3_63+ra3_top3)/3
for w in [0.10, 0.15, 0.20, 0.25]:
    evaluate(f"ensemble + {int(w*100)}% SHY", (1-w)*ens + w*shy_te)

# Add gate
ens_gated = (trend_gate(top1_63,-0.04)+top3_63+ra3_top3)/3
for w in [0.0, 0.10, 0.15, 0.20]:
    evaluate(f"ensemble_gated + {int(w*100)}% SHY", (1-w)*ens_gated + w*shy_te)

# CAGR-focused: 50/50 of two best CAGR strategies + small SMA gate
print("\n=== CAGR-focused ===")
best_cagr = 0.5*top1_63 + 0.5*ra2_top1
evaluate("0.5*top1 + 0.5*ra2_top1", best_cagr)
for thresh in [-0.04, -0.06]:
    g = np.where(spy_dist > thresh, best_cagr, shy_te)
    evaluate(f"best_cagr + SMA{thresh}", g)

# Even more CAGR: 3 high-CAGR strategies
ens_cagr = (top1_63 + ra2_top1 + 0.5*(top3_63+ra3_top3))/2.5  # weights
evaluate("weighted CAGR ensemble", ens_cagr)
PY
