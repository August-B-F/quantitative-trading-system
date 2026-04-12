# Baseline Report — T1 Monthly Winner Selection

Evaluated on the 189 monthly test observations produced by
`OverlappingSplitter(train=60m, val=6m, test=3m, step=3m, every=5d, embargo=5)`
run over the full master panel (2005-01-03 → 2026-04-10, 63 folds).

Predictions are aggregated to one decision per month (last test sample in
each calendar month). Strategy metrics come from the forward-21d return of
the ETF selected by each baseline, compounded as monthly returns.

| Baseline | Logic | Monthly acc. | Mean mo. | Sharpe (ann) | CAGR | Max DD |
|---|---|---:|---:|---:|---:|---:|
| B0 random | Uniform pick over 8 ETFs | 11.6% | 1.10% | 0.69 | 12.0% | −25.8% |
| B1 QQQ    | Static QQQ buy-and-hold  |  2.6% | 1.50% | 1.01 | 17.7% | −22.2% |
| B2 12-1   | Argmax of 12-1 momentum  | 18.5% | 1.58% | 0.85 | 17.8% | −37.2% |
| B3 63d    | Argmax of 63-day return  | **22.8%** | **1.64%** | 1.00 | **19.2%** | −21.7% |

Notes:
- B1 uses QQQ as the static core; SPY is not in the 8-ETF universe.
- B1's low monthly accuracy is expected — it matches the true winner only
  when QQQ actually wins, but still compounds to a strong Sharpe because QQQ
  is a high-ergodicity asset over this sample.
- B3 is the target to beat for any Tier-1 model: 22.8% monthly accuracy,
  19.2% CAGR, −21.7% drawdown. Random accuracy for 8 classes is 12.5%; B3
  nearly doubles it with one feature.
- The raw per-baseline numbers are persisted to `results/baselines.json`.

## Interpretation for Tier-1 modeling

Any model that cannot clear B3 (22.8% monthly accuracy AND 1.0 Sharpe) is
not adding value over a one-line momentum rule. Tier-1 experiments should
report the same monthly metrics alongside model-native ones, and should
include `B3 − model` deltas in every results table.
