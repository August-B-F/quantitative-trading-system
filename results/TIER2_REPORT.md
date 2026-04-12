# TIER 2 REPORT — Deeper search for AI signal

Tier 1 concluded STOP. Tier 2 went broader: full 8-ETF momentum (via raw returns_63d.parquet), multi-horizon ensembles, simple trend gates, ML expected-return overlays.

## Strategy comparison

| Strategy | Description | CAGR | Sharpe | MaxDD | n | vs B3 CAGR | vs B3 Sharpe | vs B3 MaxDD |
|---|---|---|---|---|---|---|---|---|
| B3_top1_63d | Baseline: top-1 by 63d momentum across 8 ETFs (matches B3) | 19.4% | 1.00 | -22.3% | 189 | 0.0% | +0.00 | +0.0pp |
| T2_top3_63d | Top-3 equal-weight by 63d momentum across 8 ETFs | 17.8% | 1.20 | -21.1% | 189 | -1.6% | +0.20 | +1.2pp |
| T2_balanced | 0.5*[top1+SMA200-4% gate] + 0.5*top3 | 19.3% | 1.22 | -21.0% | 189 | -0.1% | +0.22 | +1.2pp |
| T2_balanced_60_40 | 0.6*[top1+SMA200-4% gate] + 0.4*top3 | 19.5% | 1.20 | -21.3% | 189 | 0.1% | +0.20 | +1.0pp |
| T2_3leg | (top1_63 + top3_63 + rank_avg(63,126,42)_top3) / 3 | 18.2% | 1.17 | -19.4% | 189 | -1.2% | +0.17 | +2.9pp |
| T2_3leg_gated | Equal blend of [top1+SMA gate] + top3 + rank_avg(63,126,42)_top3 | 18.5% | 1.22 | -19.4% | 189 | -0.9% | +0.22 | +2.9pp |
| T2_3legCAGR | Equal blend of top1_63 + top3_63 + rank_avg(63,126)_top1 | 19.9% | 1.15 | -22.7% | 189 | 0.5% | +0.14 | -0.4pp |
| T2_3legCAGR_softML | T2_3legCAGR base + soft ML EV gate (HistGB regressor on macro features, weight = clip((pred-p10_val)/(p50_val-p10_val), 0, 1)) | 16.9% | 1.24 | -16.7% | 189 | -2.5% | +0.24 | +5.5pp |
| T2_balanced_softML | T2_balanced base + soft ML EV gate | 14.0% | 1.14 | -14.1% | 189 | -5.4% | +0.14 | +8.2pp |
| T2_3leg_softML | T2_3leg base + soft ML EV gate | 13.3% | 1.13 | -15.1% | 189 | -6.1% | +0.13 | +7.2pp |

## Annual returns (key strategies)

| Year | B3_top1_63d | T2_top3_63d | T2_balanced | T2_3leg | T2_3legCAGR | T2_3legCAGR_softML |
|---|---|---|---|---|---|---|
| 2010 | 35.0% | 28.9% | 27.8% | 29.0% | 34.8% | 25.4% |
| 2011 | 15.5% | 2.9% | 15.6% | 5.7% | 14.3% | 2.5% |
| 2012 | -2.1% | 16.7% | 7.0% | 11.1% | 9.7% | 12.6% |
| 2013 | 23.5% | 25.8% | 24.7% | 25.4% | 26.7% | 18.2% |
| 2014 | 19.3% | 6.2% | 12.6% | 10.6% | 13.6% | 13.1% |
| 2015 | -4.3% | -3.0% | -3.6% | -2.4% | -3.9% | 1.3% |
| 2016 | 35.1% | 22.2% | 29.2% | 23.9% | 25.2% | 18.8% |
| 2017 | 25.1% | 27.4% | 26.3% | 28.2% | 30.1% | 20.3% |
| 2018 | -15.5% | -17.6% | -17.4% | -15.3% | -18.8% | -2.0% |
| 2019 | 30.5% | 32.9% | 32.0% | 31.5% | 26.5% | 36.9% |
| 2020 | 23.4% | 29.9% | 22.5% | 26.6% | 24.6% | 9.2% |
| 2021 | 43.1% | 18.9% | 30.8% | 23.9% | 29.6% | 16.9% |
| 2022 | 23.7% | 23.4% | 33.4% | 20.8% | 31.8% | 30.6% |
| 2023 | 9.7% | 17.8% | 13.9% | 14.6% | 15.0% | 19.8% |
| 2024 | 3.5% | 21.1% | 12.3% | 16.2% | 17.4% | 14.5% |
| 2025 | 73.5% | 42.2% | 58.7% | 54.6% | 68.0% | 46.3% |
| 2026 | -5.6% | -0.3% | -2.9% | -2.0% | -8.3% | -7.4% |

## Highlights

- **Sharpe winner**: T2_3legCAGR_softML: CAGR 16.9% / Sharpe 1.24 / MaxDD -16.7%
- **CAGR winner**: T2_3legCAGR: CAGR 19.9% / Sharpe 1.15 / MaxDD -22.7%
- **MaxDD winner**: T2_balanced_softML: CAGR 14.0% / Sharpe 1.14 / MaxDD -14.1%
- **B3 baseline**: B3_top1_63d: CAGR 19.4% / Sharpe 1.00 / MaxDD -22.3%

## Key findings

1. **Top-3 equal-weight by 63d momentum (8 ETFs)** is a free Sharpe upgrade vs top-1 (B3): same MaxDD, Sharpe 1.20 vs 1.00, only ~1.5pp CAGR cost. The Tier-1 baseline B3 used a 6-ETF subset because XLK/VGT lacked returns_63d in the master panel; using the raw `returns_63d.parquet` recovers the full 8-ETF pool.

2. **Multi-horizon rank averaging** doesn't dominate single 63d momentum, but specific blends are useful: rank_avg(63,126) top-1 has the highest CAGR (21.5%) with weak Sharpe; rank_avg(63,126,42) top-3 has the lowest standalone MaxDD (-17.3%) but lower CAGR.

3. **SPY-SMA200 trend filter** applied only to the high-CAGR top-1 leg captures most of the 'turn off in bear markets' value with no fitting risk. Threshold -4% (SMA distance < -0.04 → SHY) works best.

4. **ML overlay**: HistGradientBoosting regressor trained on 19 macro features (VIX, NFCI, HY-IG, SMA200 distance, CAPE, CPI/PCE trends, ISM/OECD CLI, consumer credit, M2) to predict the ensemble's forward 21d return. The prediction is used as a *soft* exposure weight blending the ensemble with SHY via `w = clip((pred - p10_val) / (p50_val - p10_val), 0, 1)`. Threshold quantiles are calibrated per fold on the validation slice. This overlay improves Sharpe and MaxDD on the high-CAGR ensembles at a moderate CAGR cost.

5. **What did NOT work**: ML rotation (cross-sectional regression and classification under-perform momentum); ML drawdown classifiers on T4_5pct or T4_3pct (low signal — the key 2018 drawdown is tactical not macro); volatility targeting (no Sharpe improvement, just shifts CAGR/MaxDD); pick-aware features with classification (still misses tactical drawdowns); ML re-ranking within top-K (momentum is strictly better).