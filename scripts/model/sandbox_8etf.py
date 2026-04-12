"""Use raw returns_63d.parquet (which has ALL 8 ETFs) instead of master_panel
which is missing XLK/VGT. Test if full 8-ETF rotation is materially better.
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
r12_1 = pd.read_parquet(ROOT / "data/features/price/returns_12_1_mom.parquet")
print("returns_63d cols:", list(r63.columns))

ETFS = ["SOXX", "QQQ", "XLK", "VGT", "IGV", "XLE", "GLD", "SHY"]
mom = r63[ETFS].reindex(df.index).values
mom126 = r126[ETFS].reindex(df.index).values
mom42 = r42[ETFS].reindex(df.index).values
mom12_1 = r12_1[ETFS].reindex(df.index).values

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


def to_monthly(daily):
    s = pd.Series(daily, index=test_dates).dropna()
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
        idx = np.argmax(sig_te, axis=1)
        return fwd_te[np.arange(len(te_pos)), idx]
    idx = np.argsort(-sig_te, axis=1)[:, :k]
    return fwd_te[np.arange(len(te_pos))[:, None], idx].mean(axis=1)


def topk_dual(sig, k, cash_idx=ETFS.index("SHY")):
    """Dual momentum: keep position only if mom > SHY mom; else partial cash."""
    sig_filled = np.where(np.isnan(sig), -np.inf, sig)
    sig_te = sig_filled[te_pos]
    fwd_te = fwd_arr[te_pos]
    out = np.zeros(len(te_pos))
    for i in range(len(te_pos)):
        order = np.argsort(-sig_te[i])[:k]
        keep = [o for o in order if sig_te[i, o] > sig_te[i, cash_idx]]
        if not keep:
            out[i] = fwd_te[i, cash_idx]
        else:
            r = sum(fwd_te[i, o] for o in keep) / k
            r += (k - len(keep)) / k * fwd_te[i, cash_idx]
            out[i] = r
    return out


print("=== 8-ETF ranking ===")
print("--- single signal ---")
for name, sig in [("63d", mom), ("126d", mom126), ("42d", mom42), ("12-1mom", mom12_1)]:
    evaluate(f"top-1 {name}", topk(sig, 1))
    evaluate(f"top-2 {name}", topk(sig, 2))
    evaluate(f"top-3 {name}", topk(sig, 3))
    evaluate(f"dual top-3 {name}", topk_dual(sig, 3))


def rank_avg(sigs, k):
    """Average ranks across multiple signals, take top-k."""
    rk_sum = np.zeros((len(df), len(ETFS)))
    for s in sigs:
        s_f = np.where(np.isnan(s), -np.inf, s)
        order = np.argsort(-s_f, axis=1)
        rk = np.empty_like(order)
        for i in range(len(df)):
            rk[i, order[i]] = np.arange(len(ETFS))
        rk_sum += rk
    rk_te = rk_sum[te_pos]
    fwd_te = fwd_arr[te_pos]
    if k == 1:
        idx = np.argmin(rk_te, axis=1)
        return fwd_te[np.arange(len(te_pos)), idx]
    idx = np.argsort(rk_te, axis=1)[:, :k]
    return fwd_te[np.arange(len(te_pos))[:, None], idx].mean(axis=1)


print("\n--- rank-average ensembles ---")
for k in [1, 2, 3]:
    evaluate(f"rank-avg(63,126) top-{k}", rank_avg([mom, mom126], k))
    evaluate(f"rank-avg(63,126,42) top-{k}", rank_avg([mom, mom126, mom42], k))
    evaluate(f"rank-avg(63,126,12_1) top-{k}", rank_avg([mom, mom126, mom12_1], k))


def topk_dual_rankavg(sigs, k):
    """Rank average + dual momentum: only hold if rank-avg-pick beats SHY by raw mom."""
    out = np.zeros(len(te_pos))
    rk_sum = np.zeros((len(df), len(ETFS)))
    for s in sigs:
        s_f = np.where(np.isnan(s), -np.inf, s)
        order = np.argsort(-s_f, axis=1)
        rk = np.empty_like(order)
        for i in range(len(df)):
            rk[i, order[i]] = np.arange(len(ETFS))
        rk_sum += rk
    rk_te = rk_sum[te_pos]
    fwd_te = fwd_arr[te_pos]
    mom_te = mom[te_pos]
    shy_idx = ETFS.index("SHY")
    for i in range(len(te_pos)):
        order = np.argsort(rk_te[i])[:k]
        keep = [o for o in order if mom_te[i, o] > mom_te[i, shy_idx]]
        if not keep:
            out[i] = fwd_te[i, shy_idx]
        else:
            r = sum(fwd_te[i, o] for o in keep) / k
            r += (k - len(keep)) / k * fwd_te[i, shy_idx]
            out[i] = r
    return out


print("\n--- dual rank-avg ---")
for k in [2, 3]:
    evaluate(f"dual rank-avg(63,126,42) top-{k}", topk_dual_rankavg([mom, mom126, mom42], k))
    evaluate(f"dual rank-avg(63,126) top-{k}", topk_dual_rankavg([mom, mom126], k))
