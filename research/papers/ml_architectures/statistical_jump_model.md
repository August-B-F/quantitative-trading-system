# Regime-Aware Asset Allocation: A Statistical Jump Model Approach

**HIGH PRIORITY**

- **Year:** 2024
- **Source:** arXiv:2402.05272

## Architecture

- **Statistical Jump Model (JM)** with jump penalty lambda
- 2 regimes (low-vol vs high-vol)
- **Features:** 3 EWM downside deviations (half-lives 20, 60, 120 days) + 1 EWM return (120-day)
- Binary allocation: 100% equity or 100% risk-free

## Performance (1990-2023, S&P 500)

| Metric | JM (lambda=100) | HMM | Buy-Hold |
|--------|-----------------|-----|----------|
| Return | 12.55% | 7.51% | ~10% |
| Sharpe | 0.78 | 0.51 | ~0.45 |
| Turnover | 0.16%/day | 1.35%/day | 0% |
| Regime Shifts | 14 total | 115 total | N/A |

## Key Advantage over HMM

JM produces only 14 regime shifts vs 115 for HMM over 33 years. The jump penalty enforces persistence, avoiding noise-driven whipsaws. HMM requires post-hoc median filtering to achieve similar stability.

## Walk-Forward Protocol

Refit every 6 months with 2000-day lookback. Lambda selected on 1968-1990 validation period, applied without change through 2023 test period.

## Application to 8-ETF Rotation System

Use JM to identify macro regime, then allocate across ETFs based on regime-conditional expected returns. The persistence property is critical — avoids costly over-trading in ETF rotation.

## Known Failure Modes

- Binary state limitation
- Delayed regime detection (by construction, nowcasting only)
- Fixed lambda may not be optimal across all market environments
- Pure price-based features miss fundamental regime shifts
