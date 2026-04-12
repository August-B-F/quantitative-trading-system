# Generalized Protective Momentum / Defensive Asset Allocation (DAA)

**HIGH PRIORITY**

- **Authors:** Wouter J. Keller, Jan Willem Keuning
- **Year:** 2016-2018
- **Source:** SSRN

## Core Method — GPM

Two-step process:
1. Score assets by momentum AND correlation to overall universe
2. When >50% of assets show negative scores, shift 100% to crash protection asset (short/intermediate treasuries based on relative momentum)

## Core Method — DAA

Separate "canary" universe (VWO + BND / EEM + AGG) for crash signaling via breadth momentum. Cash fraction governed by number of canary assets with bad momentum. Risky allocation to top 6 assets ranked by momentum.

## Performance

- CAGR >10%, max drawdown <15% (out-of-sample across 4 universes)
- Cash fraction half that of VAA with similar risk-adjusted returns

## Application to 8-ETF Rotation System

Use 2 "canary" ETFs (EM equities + aggregate bonds) as early warning. When either shows negative momentum, increase cash allocation proportionally. Score ETFs by momentum + correlation, select top 3.

## Known Failure Modes

- Canary signals can lag in fast-moving markets
- March 2020 whipsaw scenario
- Monthly rebalancing misses intra-month crashes
