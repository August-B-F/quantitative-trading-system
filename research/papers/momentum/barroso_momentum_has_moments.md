# Momentum Has Its Moments

**HIGH PRIORITY**

- **Authors:** Pedro Barroso, Pedro Santa-Clara
- **Year:** 2015
- **Source:** Journal of Financial Economics, Vol. 116(1), pp. 111-120
- **Links:** [SSRN](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2041429)

## Core Signal / Method

Scale momentum portfolio by realized volatility from prior 6 months of daily momentum returns. Target constant volatility:

`w_t = sigma_target / sigma_{t-1}`

where sigma is realized vol of momentum returns over trailing 126 days. Simple, implementable rule that virtually eliminates momentum crashes.

## Reported Performance

- Unmanaged momentum Sharpe: 0.53
- Volatility-managed momentum Sharpe: 0.97 (nearly doubled)
- Excess kurtosis: reduced from 18.24 to 2.68
- Skewness: improved from -2.47 to -0.42
- Crash risk virtually eliminated

## Application to 8-ETF Rotation System

Calculate trailing 6-month realized volatility of your rotation strategy's returns. When strategy vol is high, reduce position sizes proportionally. Target a constant strategy volatility (e.g., 10% annualized). This is the simplest, most robust crash protection available.

## Known Failure Modes

- Slight drag on returns in calm trending markets (may under-allocate when vol is normal)
