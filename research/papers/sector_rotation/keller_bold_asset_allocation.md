# Bold Asset Allocation (BAA)

- **Authors:** Wouter J. Keller
- **Year:** 2022
- **Source:** SSRN
- **Links:** [SSRN](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4166845)

## Core Signal / Method

Combines slow relative momentum (asset selection) with fast absolute momentum (crash protection). Uses a "canary universe" of separate assets to detect regime shifts — switches from offensive to defensive universe when any canary asset has negative absolute momentum.

## Reported Performance

- Returns >= 20% annualized
- Monthly max drawdown <= 15%
- Test period: December 1970 to June 2022

## Application to 8-ETF Rotation System

The "canary universe" concept is powerful: use 2-3 sentinel assets (e.g., EEM and AGG) as early warning indicators. When canary assets flash negative momentum, shift entire 8-ETF portfolio toward defensive positions.

## Known Failure Modes

- Overfitting risk on canary universe selection
- May generate false alarms
- Concentration in defensive assets during extended low-volatility periods
