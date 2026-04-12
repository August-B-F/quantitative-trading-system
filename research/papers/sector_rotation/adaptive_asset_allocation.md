# Adaptive Asset Allocation: A Primer

**HIGH PRIORITY**

- **Authors:** Adam Butler, Michael Philbrick, Rodrigo Gordillo, David Varadi (ReSolve Asset Management)
- **Year:** 2012
- **Source:** SSRN
- **Links:** [SSRN](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2328254)

## Core Signal / Method

Combines momentum ranking with minimum-variance optimization. Uses return, variance, and correlation estimates that adapt over time. Selects top-momentum assets, then optimizes weights using inverse-variance or minimum-variance approach.

## Data Used

Global multi-asset universe including equities, bonds, REITs, commodities.

## Reported Performance

Higher risk-adjusted returns than equal-weight momentum or buy-and-hold. Specifically designed to handle volatility differences across diverse ETF groups.

## Application to 8-ETF Rotation System

HIGHLY applicable. After ranking 8 ETFs by momentum, use inverse-volatility weighting instead of equal-weight to compensate for variance differences. This addresses a core challenge: ETFs with different volatilities (e.g., commodities vs. bonds) create unbalanced risk contributions.

## Known Failure Modes

- Estimation error in covariance matrices
- Sensitivity to lookback window for volatility estimation
- Concentration in low-volatility assets during calm markets, missing upside
