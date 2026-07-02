"""Droplets 1 & 3: idle-cash fraction and dust drift from logs/rebalance_log.json."""
import json
from collections import defaultdict

import numpy as np

with open("logs/rebalance_log.json") as f:
    data = json.load(f)

# Keep the LAST entry per (date) that has executed strategies with
# post_rebalance_weights (retries overwrite earlier failures).
runs = []  # (date, strategy, dict result)
seen = set()
for e in reversed(data):
    d = e.get("date")
    for name, s in (e.get("strategies") or {}).items():
        key = (d, name)
        if key in seen:
            continue
        if s.get("post_rebalance_weights") is None:
            continue
        seen.add(key)
        runs.append((d, name, s))
runs.sort()

print(f"{len(runs)} strategy-executions with post_rebalance_weights")
cash_fracs = []
drift_all = []          # per-ticker |post - target| where ticker held or targeted
drift_sub_noise = []    # deviations < 0.01 (never corrected)
band_5_10 = []          # deltas in [0.005, 0.01) — what NOISE=0.005 would add
per_run_summary = []

for d, name, s in runs:
    tw = s["target_weights"]
    pw = s["post_rebalance_weights"]
    cash = 1.0 - sum(pw.values())
    cash_fracs.append(cash)
    devs = {}
    for t in set(tw) | set(pw):
        dev = abs(tw.get(t, 0.0) - pw.get(t, 0.0))
        devs[t] = dev
        drift_all.append(dev)
        if dev < 0.01:
            drift_sub_noise.append(dev)
        if 0.005 <= dev < 0.01:
            band_5_10.append(dev)
    per_run_summary.append((d, name, cash, max(devs.values()), s.get("success")))

cash_fracs = np.array(cash_fracs)
print("\n--- D1: uninvested cash fraction per successful execution ---")
print(f"mean={cash_fracs.mean()*100:.3f}%  median={np.median(cash_fracs)*100:.3f}%  "
      f"min={cash_fracs.min()*100:.3f}%  max={cash_fracs.max()*100:.3f}%  n={len(cash_fracs)}")

print("\nper run (date, strategy, cash%, max_dev%, success):")
for d, name, c, mdev, ok in per_run_summary:
    print(f"  {d}  {name:32s}  cash={c*100:6.3f}%  max_dev={mdev*100:6.3f}%  success={ok}")

drift_all = np.array(drift_all)
nz = drift_all[drift_all > 1e-6]
print("\n--- D3: per-ticker |post - target| deviation ---")
print(f"all tickers: n={len(drift_all)}, nonzero n={len(nz)}, "
      f"mean(nonzero)={nz.mean()*100:.3f}%  p90={np.percentile(nz,90)*100:.3f}%  max={nz.max()*100:.3f}%")
sub = np.array(drift_sub_noise)
subnz = sub[sub > 1e-6]
print(f"sub-noise (<1%) nonzero deviations: n={len(subnz)}, sum per run avg="
      f"{subnz.sum()/max(len(runs),1)*100:.3f}% of equity, mean={subnz.mean()*100:.3f}%")
b = np.array(band_5_10)
print(f"deltas in [0.5%,1.0%) (extra trades under NOISE=0.005): n={len(b)}, "
      f"total={b.sum()*100:.3f}% of equity across {len(runs)} runs, "
      f"per-rebalance avg={b.sum()/max(len(runs),1)*100:.3f}% of equity")
