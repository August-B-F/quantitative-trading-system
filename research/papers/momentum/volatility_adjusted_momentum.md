# Volatility-Adjusted Momentum

**HIGH PRIORITY**

- **Authors:** Jeroen van Zundert
- **Year:** 2018
- **Source:** Journal of Banking & Finance; SSRN #2880097
- **Links:** [SSRN](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2880097)

## Core Signal / Method

Instead of ranking by raw 12-month return, rank by return DIVIDED BY volatility (Sharpe-like momentum signal):

`Momentum_adj_i = r_{i,t-12,t} / sigma_i`

This underweights high-volatility losers (which tend to rebound, causing crashes) and overweights low-volatility winners.

## Data Used

US equities, 1927-2015; out-of-sample: USD corporate bonds.

## Reported Performance

- Traditional momentum Sharpe: 0.34
- Volatility-adjusted momentum Sharpe: 1.14 (3.4x improvement)
- Strongly reduced crash risk
- Effect driven by underweighting high-vol losers

## Application to 8-ETF Rotation System

Instead of ranking ETFs purely by 12-month return, rank by 12-month return / realized volatility. This is essentially a Sharpe ratio ranking. ETFs with strong but volatile returns (e.g., EEM) will be penalized relative to strong, stable returns (e.g., SPY in a steady uptrend).

## Known Failure Modes

- May miss explosive momentum in high-vol assets
- Requires accurate volatility estimation
