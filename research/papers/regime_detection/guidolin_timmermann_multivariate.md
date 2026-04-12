# Asset Allocation Under Multivariate Regime Switching

**HIGH PRIORITY**

- **Authors:** Massimo Guidolin, Allan Timmermann
- **Year:** 2007
- **Source:** Journal of Economic Dynamics and Control, 31(11), 3503-3544
- **Links:** [SSRN](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=940652)

## Core Method

Multivariate regime-switching model for joint distribution of stocks (large-cap, small-cap) and bonds. Model selection tested k=1,2,3,4,5,6 states and lag orders p=0,1,2,3 using information criteria. Four-state model selected.

## 4 Regimes Identified

| Regime | Stock-Bond Corr | Large-Small Corr |
|--------|-----------------|------------------|
| Crash | -0.40 | 0.82 |
| Slow Growth | moderate | moderate |
| Bull | positive | moderate |
| Recovery | 0.37 | 0.50 |

Correlations vary dramatically across regimes.

## Application to 8-ETF Rotation System

HIGHLY RELEVANT. The four-regime framework maps naturally to different ETF allocations. In "crash" regime, bonds decorrelate from stocks (negative correlation) making them effective hedges. In "bull" regime, maximize equity exposure.

## Known Failure Modes

- Estimation requires long historical samples
- Four regimes may overfit shorter datasets
- Real-time regime identification is uncertain
