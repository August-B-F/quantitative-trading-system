# Combining Mean Reversion and Momentum Trading Strategies in Foreign Exchange Markets

- **Authors:** Various
- **Year:** 2010
- **Source:** Journal of Banking & Finance

## Core Signal / Method

Dynamically switches between momentum and mean-reversion signals depending on market conditions. When both signals align (same direction), assigns highest risk allocation. Produces higher Sharpe ratios than pure momentum or pure mean-reversion alone.

## Application to 8-ETF Rotation System

Add a mean-reversion layer: when an ETF has fallen sharply but momentum is still positive (or when relative valuation is extreme), consider contrarian re-entry. Tier the signal: strongest allocation when both momentum AND mean-reversion agree.

## Known Failure Modes

- Signal conflict periods where momentum and mean-reversion disagree
- Requires careful calibration of switching thresholds
