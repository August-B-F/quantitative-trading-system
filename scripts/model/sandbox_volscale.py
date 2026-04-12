"""Volatility-targeted exposure scaling on top of momentum.

Idea: don't try to predict drawdowns. Just scale exposure inversely to realized
volatility. When realized vol is high, hold less of the risky position and more
in SHY/cash. This is a classical risk-targeting overlay.
"""
import sys
import numpy as np
import pandas as pd
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from model.walk_forward import ExpandingSplitter

df = pd.read_parquet(ROOT / "data/features/master_panel.parquet")
ETFS = ["SOXX", "QQQ", "IGV", "XLE", "GLD", "SHY"]

mom = df[[f"returns_63d__{tk}" for tk in ETFS]].copy()
mom.columns = ETFS
mom_arr = mom.values
mom_filled = np.where(np.isnan(mom_arr), -np.inf, mom_arr)
top1_idx = np.argmax(mom_filled, axis=1)
fwd = df[[f"TARGET_FWD21_{tk}" for tk in ETFS]].copy()
fwd.columns = ETFS
fwd_arr = fwd.values
top1_ret = fwd_arr[np.arange(len(df)), top1_idx]
top3_idx = np.argsort(-mom_filled, axis=1)[:, :3]
top3_ret = np.array([fwd_arr[i, top3_idx[i]].mean() for i in range(len(df))])
shy_ret = fwd["SHY"].values

# Realized vol of the picked ETF (vol_42d__<pick>)
def build_pick_vol(template):
    cols = {tk: f"{template}__{tk}" for tk in ETFS}
    avail = {tk: c for tk, c in cols.items() if c in df.columns}
    if len(avail) < len(ETFS): return None
    arr = np.full(len(df), np.nan)
    for i, tk in enumerate(ETFS):
        m = top1_idx == i
        arr[m] = df[avail[tk]].values[m]
    return arr

vol_pick = build_pick_vol("vol_42d")
if vol_pick is None:
    # SHY may lack vol_42d; use vol_21d fallback per ETF
    vol_pick = np.full(len(df), np.nan)
    for i, tk in enumerate(ETFS):
        for v in ["vol_42d", "vol_21d", "vol_63d", "atr_14d"]:
            c = f"{v}__{tk}"
            if c in df.columns:
                m = top1_idx == i
                vol_pick[m] = df[c].values[m]
                break
print("vol_pick non-null:", (~np.isnan(vol_pick)).sum(), "of", len(vol_pick))

# Compute top-3 realized vol = mean of top3 vols (rough approx)
top3_vol = np.full(len(df), np.nan)
vol_cols = {tk: df[f"vol_42d__{tk}"] if f"vol_42d__{tk}" in df.columns else None for tk in ETFS}
vol_mat = np.full((len(df), len(ETFS)), np.nan)
for i, tk in enumerate(ETFS):
    if vol_cols[tk] is not None:
        vol_mat[:, i] = vol_cols[tk].values
for i in range(len(df)):
    top3_vol[i] = np.nanmean(vol_mat[i, top3_idx[i]])

# Walk-forward sample dates
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


def to_monthly(daily, dts):
    s = pd.Series(daily, index=dts).dropna()
    return s.groupby(s.index.to_period("M")).tail(1)


def evaluate(name, daily):
    sm = to_monthly(daily, test_dates)
    s = stats(sm.values)
    print(f"{name:50s} CAGR={s[0]*100:5.1f}%  Sharpe={s[1]:4.2f}  MaxDD={s[2]*100:6.1f}%")
    return s


# Vol target scaling
def vol_target_scale(base_ret, base_vol, target_vol, max_w=1.0):
    # base_vol is already annualized? vol_42d in this panel — let me assume daily vol annualized.
    # Use max_w cap. When base_vol=target, w=1. When base_vol=2*target, w=0.5.
    base = base_ret[te_pos]
    bv = base_vol[te_pos]
    bv = np.where((bv <= 0) | np.isnan(bv), target_vol, bv)
    w = np.minimum(max_w, target_vol / bv)
    shy = shy_ret[te_pos]
    out = w * base + (1 - w) * shy
    return out


print("Baselines:")
top1_base = top1_ret[te_pos]
top3_base = top3_ret[te_pos]
evaluate("top-1 raw", top1_base)
evaluate("top-3 raw", top3_base)

print("\nVol-target on top-1 (target_vol annualized):")
for tv in [0.10, 0.12, 0.15, 0.18, 0.20]:
    out = vol_target_scale(top1_ret, vol_pick, tv)
    evaluate(f"top-1 vol_target={tv:.2f}", out)

print("\nVol-target on top-3:")
for tv in [0.10, 0.12, 0.15, 0.18]:
    out = vol_target_scale(top3_ret, top3_vol, tv)
    evaluate(f"top-3 vol_target={tv:.2f}", out)

# Hybrid: leverage cap, no SHY blend; just scale w
print("\nVol scaling no cash (just scale exposure, no SHY):")
def vol_scale_only(base_ret, base_vol, target_vol):
    base = base_ret[te_pos]
    bv = base_vol[te_pos]
    bv = np.where((bv <= 0) | np.isnan(bv), target_vol, bv)
    w = np.minimum(1.0, target_vol / bv)
    return w * base  # remainder is 0% (cash with 0 yield)

for tv in [0.12, 0.15, 0.18]:
    out = vol_scale_only(top1_ret, vol_pick, tv)
    evaluate(f"top-1 scale_only tv={tv}", out)

# Realized-vol from past returns of the actual base (rolling 63d vol of daily picks)
# more honest: compute trailing 63d vol of base portfolio's *realized daily returns*
# But we only have monthly samples; use vol_42d__SPY as proxy
spy_vol = df["vol_42d__SPY"].values if "vol_42d__SPY" in df.columns else None
if spy_vol is not None:
    print("\nVol-target using SPY vol (regime proxy):")
    for tv in [0.10, 0.12, 0.15]:
        out = vol_target_scale(top1_ret, spy_vol, tv)
        evaluate(f"top-1 SPY-vol tv={tv}", out)
        out = vol_target_scale(top3_ret, spy_vol, tv)
        evaluate(f"top-3 SPY-vol tv={tv}", out)
