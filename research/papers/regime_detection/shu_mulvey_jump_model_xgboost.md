# Dynamic Asset Allocation with Asset-Specific Regime Forecasts

**HIGH PRIORITY**

- **Authors:** Yizhan Shu, Chenyu Yu, John M. Mulvey (Princeton University)
- **Year:** 2024
- **Source:** arXiv:2406.09578 / Annals of Operations Research

## Architecture

Two-stage hybrid:
1. **Statistical Jump Model** classifies historical periods into bullish/bearish per asset
2. **XGBoost** gradient-boosted classifier predicts future regimes using return + macro features

## Features/Inputs

- **Return features:** EWMA downside deviation, average return, Sortino ratio at 5/10/21-day half-lives (8 features)
- **Macro features:** US Treasury 2-year yield, yield curve slope (10Y-2Y), VIX, stock-bond correlation

## Data

1991-2023 (test: 2007-2023). 12 risky assets: US equity (LargeCap, MidCap, SmallCap), International (EAFE, EM), Bonds (Agg, Treasury, HY, Corp), REIT, Commodities, Gold.

## Application to 8-ETF Rotation System

PERFECT MATCH. The 12-asset universe is very similar to an 8-ETF rotation system. Apply asset-specific regime forecasts to each ETF, then allocate based on which are in bullish regimes. XGBoost forecaster adds predictive power beyond simple regime persistence.

## Known Failure Modes

- Forecast delay (especially 2015-2016 selloff detection lag)
- Bearish return forecasts capped at -10bps
- Imperfect during complex multi-factor events
