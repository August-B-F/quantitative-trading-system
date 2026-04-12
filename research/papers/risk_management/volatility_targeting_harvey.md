# The Impact of Volatility Targeting

**HIGH PRIORITY**

- **Authors:** Campbell R. Harvey, Edward Hoyle, Russell Korgaonkar
- **Year:** 2018
- **Source:** Man Group / Oxford Man Institute

## Core Method

Scale portfolio leverage inversely to realized volatility — leverage up in low-vol, scale down in high-vol. Maintain constant risk rather than constant notional exposure.

## Key Findings

1. Sharpe ratio substantially improved for equities and credit
2. Negligible effect on bonds, currencies, commodities
3. Reduces likelihood of extreme returns across ALL asset classes
4. Left-tail events are less severe (they occur during high vol when exposure is already reduced)

## Mechanism

Negative correlation between returns and volatility in risk assets creates an unintentional momentum overlay.

## Data

60+ assets, daily observations from 1926 forward.

## Application to 8-ETF Rotation System

Apply volatility targeting to the rotation system: scale position sizes by inverse of trailing realized volatility. Especially effective for equity ETFs in the universe.

## Related: Hood & Raughtigan (2024)

Volatility targeting's alpha comes from an implicit trend-following signal. NOT true for commodity, fixed income, or currency futures where leverage effect is absent.

## Known Failure Modes

- Leverage costs in low-vol
- Whipsaw if vol spikes and recovers quickly
- Ineffective for bond/commodity ETFs
