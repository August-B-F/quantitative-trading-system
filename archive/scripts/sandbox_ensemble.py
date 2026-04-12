# ARCHIVED: ensemble sandbox — superseded by run_m26_deep
"""Strategy ensembles + ML overlay on top of full 8-ETF portfolios."""
import sys
import numpy as np
import pandas as pd
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from model.walk_forward import ExpandingSplitter
from model.preprocessing import FeaturePreprocessor
from sklearn.ensemble import HistGradientBoostingRegressor, HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression

df = pd.read_parquet(ROOT / "data/features/master_panel.parquet")
r63 = pd.read_parquet(ROOT / "data/features/price/returns_63d.parquet")
r126 = pd.read_parquet(ROOT / "data/features/price/returns_126d.parquet")
r42 = pd.read_parquet(ROOT / "data/features/price/returns_42d.parquet")
r12_1 = pd.read_parquet(ROOT / "data/features/price/returns_12_1_mom.parquet")

ETFS = ["SOXX", "QQQ", "XLK", "VGT", "IGV", "XLE", "GLD", "SHY"]
mom = r63[ETFS].reindex(df.index).values
mom126 = r126[ETFS].reindex(df.index).values
mom42 = r42[ETFS].reindex(df.index).values
mom121 = r12_1[ETFS].reindex(df.index).values

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
    r = np.asarray(r)
    r = r[~np.isnan(r)]
    eq = np.cumprod(1 + r)
    years = len(r) / 12
    cagr = eq[-1] ** (1 / years) - 1
    sd = r.std(ddof=1)
    sh = r.mean() / sd * np.sqrt(12) if sd > 0 else float("nan")
    peak = np.maximum.accumulate(eq)
    dd = (eq / peak - 1).min()
    return cagr, sh, dd


def to_monthly(daily, dts=None):
    if dts is None: dts = test_dates
    s = pd.Series(daily, index=dts).dropna()
    return s.groupby(s.index.to_period("M")).tail(1)


def evaluate(name, daily):
    sm = to_monthly(daily)
    s = stats(sm.values)
    print(f"{name:55s} CAGR={s[0]*100:5.1f}%  Sharpe={s[1]:4.2f}  MaxDD={s[2]*100:6.1f}%")
    return s


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


# Compute base strategies
top1_63 = topk(mom, 1)
top3_63 = topk(mom, 3)
ra_63_126_top1 = rank_avg_topk([mom, mom126], 1)
ra_63_126_top3 = rank_avg_topk([mom, mom126], 3)
ra_3_top3 = rank_avg_topk([mom, mom126, mom42], 3)
ra_3_top1 = rank_avg_topk([mom, mom126, mom42], 1)
ra_4_top3 = rank_avg_topk([mom, mom126, mom42, mom121], 3)
shy_te = shy_ret[te_pos]

print("=== Base strategies ===")
evaluate("top-1 63d", top1_63)
evaluate("top-3 63d", top3_63)
evaluate("rank-avg(63,126) top-1", ra_63_126_top1)
evaluate("rank-avg(63,126) top-3", ra_63_126_top3)
evaluate("rank-avg(63,126,42) top-3", ra_3_top3)
evaluate("rank-avg(63,126,42) top-1", ra_3_top1)
evaluate("rank-avg(63,126,42,12-1) top-3", ra_4_top3)

print("\n=== Strategy blends ===")
evaluate("0.5*top1_63 + 0.5*top3_63", 0.5 * top1_63 + 0.5 * top3_63)
evaluate("0.5*ra_top1 + 0.5*top3_63", 0.5 * ra_63_126_top1 + 0.5 * top3_63)
evaluate("0.5*ra_top1 + 0.5*ra_63_126_top3", 0.5 * ra_63_126_top1 + 0.5 * ra_63_126_top3)
evaluate("0.4*top1 + 0.4*top3 + 0.2*shy", 0.4*top1_63 + 0.4*top3_63 + 0.2*shy_te)
evaluate("0.5*top1 + 0.3*top3 + 0.2*shy", 0.5*top1_63 + 0.3*top3_63 + 0.2*shy_te)
evaluate("0.7*top3 + 0.3*shy", 0.7*top3_63 + 0.3*shy_te)
evaluate("0.7*ra_3_top3 + 0.3*shy", 0.7*ra_3_top3 + 0.3*shy_te)
evaluate("0.5*top1 + 0.5*top3 (8etf)", 0.5*top1_63 + 0.5*top3_63)
evaluate("(top1+top3+ra_top3)/3", (top1_63 + top3_63 + ra_63_126_top3) / 3)
evaluate("(top1+top3+ra_3_top3)/3", (top1_63 + top3_63 + ra_3_top3) / 3)

# Vol scaling on top-3
def get_vol_pick():
    arr = np.full(len(df), np.nan)
    sig_idx = np.argmax(np.where(np.isnan(mom), -np.inf, mom), axis=1)
    for i, tk in enumerate(ETFS):
        for v in ["vol_42d", "vol_21d", "vol_63d"]:
            c = f"{v}__{tk}"
            if c in df.columns:
                m = sig_idx == i
                arr[m] = df[c].values[m]
                break
    return arr

vol_pick = get_vol_pick()

def vol_target_blend(base, target_vol=0.15, max_w=1.0):
    bv = vol_pick[te_pos]
    bv = np.where((bv <= 0) | np.isnan(bv), target_vol, bv)
    w = np.minimum(max_w, target_vol / bv)
    return w * base + (1 - w) * shy_te

print("\n=== Vol-targeted top-3 ===")
for tv in [0.12, 0.15, 0.18]:
    evaluate(f"top-3 + vol-target {tv}", vol_target_blend(top3_63, tv))
    evaluate(f"ra_3_top3 + vol-target {tv}", vol_target_blend(ra_3_top3, tv))

# Trend filter: only hold base if SPY > SMA200, else SHY
spy_dist = df["quality_dist_sma200__SPY"].values[te_pos]
print("\n=== SPY trend gate ===")
for thresh in [0.0, -0.02, -0.04]:
    gate = spy_dist > thresh
    out = np.where(gate, top3_63, shy_te)
    evaluate(f"top3 if SPY-SMA200>{thresh}", out)
    out = np.where(gate, ra_3_top3, shy_te)
    evaluate(f"ra_3_top3 if SPY-SMA200>{thresh}", out)
    out = np.where(gate, top1_63, shy_te)
    evaluate(f"top1 if SPY-SMA200>{thresh}", out)

print("\n=== Combined: SPY trend filter + top-3 ensemble ===")
gate = spy_dist > -0.02
ensemble = (top1_63 + top3_63 + ra_3_top3) / 3
evaluate("ensemble + SPY-2% gate", np.where(gate, ensemble, shy_te))
evaluate("top3 + ra_3_top3 + SPY-2% gate", np.where(gate, 0.5*top3_63 + 0.5*ra_3_top3, shy_te))

# Soft trend gate: scale linearly with sma_dist
print("\n=== Soft SPY trend gate ===")
for low, high in [(-0.04, 0.02), (-0.06, 0.0), (-0.04, 0.0)]:
    w = np.clip((spy_dist - low) / (high - low), 0, 1)
    evaluate(f"top3 soft SPY [{low},{high}]", w * top3_63 + (1 - w) * shy_te)
    evaluate(f"ra_3_top3 soft SPY [{low},{high}]", w * ra_3_top3 + (1 - w) * shy_te)
