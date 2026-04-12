# LOOKBACK TRIGGER REPORT

Replacing the ML regime classifier with rule-based triggers for the 63d↔21d lookback switch. All other components (top-3 inv-vol, SMA200 -4% gate, M26 post-3d defer, monthly rebalance) identical.

## Results

| Trigger | Description | Fires (test days) | CAGR | Sharpe | MaxDD |
|---|---|---|---|---|---|
| Regime (ML) | 66.5% acc classifier | 53 | 23.61% | 1.50 | -12.94% |
| T01 VIX>25 | VIX level > 25 | 25 | 21.57% | 1.39 | -14.53% |
| T02 VIX>20 | VIX level > 20 | 50 | 17.85% | 1.15 | -17.82% |
| T03 VIX>30 | VIX level > 30 | 11 | 21.48% | 1.38 | -13.81% |
| T04 rvol>63d med | SPY 21d rvol > 63d rolling median | 86 | 17.54% | 1.15 | -18.17% |
| T05 VIX chg>5 | VIX up >5pts over 21d | 23 | 21.13% | 1.38 | -14.53% |
| T06 HY-IG z>1 | HY-IG credit z-score > 1.0 | 34 | 20.35% | 1.32 | -20.08% |
| T07 VIX>25 | HY-IG z>1 | Either VIX>25 or HY-IG z>1 | 44 | 20.18% | 1.31 | -20.08% |
| T08 disp<5% | Cross-sec 63d return stdev < 5% | 75 | 15.05% | 0.98 | -26.21% |
| T09 top gap<2pp | Top1-Top2 gap on 63d mom < 2pp | 68 | 19.94% | 1.30 | -23.62% |
| T10 random 28% | Random daily fire at 28% (500 runs) | ~52 | 19.14% (median) | 1.24 (median) | -17.85% (median) |

## T10 random baseline distribution (500 runs at 28% fire rate)

- Median Sharpe: **1.24**  (p05 1.06, p95 1.42)
- Median CAGR: **19.14%**  (p05 16.02%, p95 22.06%)
- Average fires per run: 53
- Regime classifier Sharpe percentile in random distribution: **99.8**
- Regime classifier CAGR percentile in random distribution: **99.6**

## B2 hit-ratio for top-3 triggers

For rule-based triggers, HELPFUL = picks differ AND 21d beats 63d (no prediction to score, so correctness uses the direct pick-outcome test only).

| Trigger | n switches | HELPFUL | NEUTRAL | HARMFUL | Helpful % |
|---|---|---|---|---|---|
| Regime (ML) | 53 | 13 | 26 | 14 | 24.5% |
| T01 VIX>25 | 25 | 7 | 13 | 5 | 28.0% |
| T05 VIX chg>5 | 23 | 8 | 10 | 5 | 34.8% |

## Verdict

**Random baseline median Sharpe 1.24 vs regime classifier 1.50 (gap +0.26).** The regime classifier sits at the 100th percentile of random — so random noise rarely matches it, meaning the timing of switches does carry signal.

Best rule-based trigger: `T01 VIX>25` (Sharpe 1.39). Not materially better than the classifier.