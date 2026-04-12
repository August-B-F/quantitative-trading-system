# Tactical Asset Allocation with Macroeconomic Regime Detection

**HIGH PRIORITY**

- **Authors:** Daniel Cunha Oliveira, Dylan Sandfelder, Andre Fujita, Xiaowen Dong, Mihai Cucuringu
- **Year:** 2025
- **Source:** arXiv:2503.11499

## Core Method

Modified k-means with two sequential distance metrics:
1. L2 clustering to identify outlier months
2. Cosine clustering on remaining data

Converts deterministic assignments to probabilistic via fuzzy c-means. PCA reduces 127 FRED-MD variables to 61 principal components (95% variance explained).

## 6 Regimes Identified

1. Economic Difficulty/Crisis
2. Economic Recovery
3. Expansionary Growth
4. Stagflationary Pressure
5. Pre-Recession Transition
6. Reflationary Boom

## Assets

10 sector ETFs: SPY, XLB, XLE, XLF, XLI, XLK, XLP, XLU, XLV, XLY

## Data

Feb 2000 - Jan 2023 (746 monthly observations), 48-month rolling estimation window.

## Application to 8-ETF Rotation System

DIRECTLY APPLICABLE. Use FRED-MD macro data to identify current economic regime, then apply historically optimal ETF weights for that regime. Very close to a practical rotation system.

## Known Failure Modes

- K-means is deterministic
- Limited to sector ETFs (no bonds/commodities in original)
- 4-year estimation window may miss longer cycles
- Excludes transaction costs
