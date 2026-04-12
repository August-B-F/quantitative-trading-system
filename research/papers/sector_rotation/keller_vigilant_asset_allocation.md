# Breadth Momentum and Vigilant Asset Allocation (VAA)

**HIGH PRIORITY**

- **Authors:** Wouter J. Keller, Jan Willem Keuning
- **Year:** 2017
- **Source:** SSRN
- **Links:** [SSRN](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3002624), [Allocate Smartly](https://allocatesmartly.com/vigilant-asset-allocation-dr-wouter-keller-jw-keuning/)

## Core Signal / Method

Weighted momentum formula: `(12 × 1-month return) + (4 × 3-month return) + (2 × 6-month return) + (1 × 12-month return)`

Emphasizes recent momentum (40% weight on most recent month). Binary switch: if ANY offensive asset has negative momentum, switch entire portfolio to best defensive asset.

**Assets:**
- Offensive: SPY, EFA, EEM, AGG
- Defensive: LQD, IEF, SHY

## Reported Performance (1971-present)

- Sharpe Ratio: 1.10
- Max Drawdown: -16.1%
- Holds single asset at a time (100% allocation)

## Application to 8-ETF Rotation System

The weighted momentum formula is directly usable for ranking 8 ETFs. The "breadth momentum" concept (checking if ANY asset has negative momentum as a crash indicator) is a powerful risk-off signal. Modify for 8-ETF system: hold top 3-4 instead of single asset.

## Known Failure Modes

- Extreme concentration risk (single asset)
- Sensitive to trading day selection ("timing luck")
- Potential overfitting of AGG inclusion
- Whipsaw in transition regimes
