# Splitter Comparison — E00 Label-Shuffle Diagnostic

Daily-sampled walk-forward splits evaluated on MINIMAL features (11 columns that
intersect the panel) with `HistGradientBoostingClassifier` (max_depth=4, 120
iters, lr=0.05). Each fold trains once on real labels and once on labels
permuted within the training set. Test predictions are aggregated to monthly
(last sample per calendar month) before scoring. The signal metric is
`gap = real_monthly_acc − shuf_monthly_acc`; larger positive = more real
signal extracted. 63 folds, 189 evaluated test months (185 for monthly-only).

| Variant | Splitter | sample_every_n | T1 real | T1 shuffled | **T1 gap** | T4 real | T4 shuffled | **T4 gap** |
|---|---|---|---:|---:|---:|---:|---:|---:|
| E00a | Overlapping rolling | 5 | 0.1852 | 0.2169 | **−0.0317** | 0.8730 | 0.8783 | **−0.0053** |
| E00b | Expanding + decay   | 5 | 0.2275 | 0.1746 | **+0.0529** | 0.8730 | 0.8783 | **−0.0053** |
| E00c | Overlapping monthly | 21 | 0.2216 | 0.2324 | **−0.0108** | 0.8594 | 0.8757 | **−0.0162** |

For reference, naive baselines on the same test months (see `baselines.json`):
random pick = 11.6% monthly accuracy, 12-1 momentum = 18.5%, 63-day momentum =
22.8%.

## Observations

1. **T1 (winner classification).** Only the expanding+decay splitter shows a
   positive real-vs-shuffled gap (+5.3pp). Rolling-overlap and monthly-only
   both come in slightly negative, meaning a tiny model on 11 features can't
   tell real labels from noise within a short window. The long-memory training
   set in the expanding splitter is what lets signal show up.
2. **T4 (drawdown > 5%).** T4 is ~87% class-imbalanced (drawdowns are frequent
   in this sample), so all variants sit near the majority-class rate and the
   gap is noise. The minimal feature set lacks drawdown-predictive features
   (VIX-regime interactions, credit spreads scaled per-regime, etc.); E00 is
   under-powered for T4 until a richer set is tried.
3. **Overlapping daily samples do NOT automatically help.** With 11 features
   and a shallow booster, the extra ~4× samples are mostly autocorrelated
   noise and actively hurt the rolling variant. The expanding splitter benefits
   not from the daily cadence per se but from the larger effective history and
   the recency-weighted fit.

## Recommendation

**Use `ExpandingSplitter` as the primary Tier-1 splitter for T1 experiments.**
It is the only variant where real labels beat shuffled labels on E00 (+5.3pp
on T1, matching B3's ~22.8% monthly accuracy with a simple model). Keep
`OverlappingSplitter` available as a secondary for diagnostic/ablation runs
and for models that explicitly model sample correlation (e.g. grouped CV
with block bootstrap).

For T4, do not gate splitter choice on the current E00 because the feature
set cannot move the metric. Re-run E00 for T4 after Tier-1 adds VIX/credit
interaction features; until then, default to `ExpandingSplitter` for
consistency with T1.

## Caveats

- 11 features is a deliberately tiny smoke test; absolute accuracy numbers
  are not meant to reflect production performance.
- Shuffling is within-fold, so it preserves fold-level class frequencies.
- Results are deterministic under the seeds in `run_e00.py`; rerun with
  different seeds to estimate variance before locking the choice in.
