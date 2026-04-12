# Demystifying Time-Series Momentum Strategies

**HIGH PRIORITY**

- **Authors:** Nick Baltas, Robert Kosowski
- **Year:** 2013
- **Source:** Journal of Derivatives & Hedge Funds, Vol 19(4), pp 289-310

## Core Method

Replace standard close-to-close volatility with Yang-Zhang (2000) range-based estimator (uses OHLC). Replace discrete +1/-1 signal with continuous TREND signal reflecting price trend strength.

## Data

58 futures contracts, January 1985 to December 2009.

## Key Findings

1. Yang-Zhang estimator reduces turnover by ~35% without performance degradation
2. Continuous TREND signal avoids extreme positions of binary signal
3. High pairwise correlations explain post-2008 momentum underperformance

## Application to 8-ETF Rotation System

- Use OHLC-based Yang-Zhang vol estimator instead of close-only
- Implement continuous momentum scoring (not binary in/out)
- Monitor inter-ETF correlations as strategy health indicator

## Known Failure Modes

- Post-GFC high-correlation regimes degrade strategy
- OHLC data may not be available for all assets
- Range estimator assumes no gaps
