# Walk-Forward Validation Framework for Financial ML

**HIGH PRIORITY**

- **Year:** 2024
- **Source:** arXiv:2512.12924

## Methodology

- **Training window:** 252 days (1 year)
- **Testing window:** 63 days (1 quarter)
- **Step size:** 63 days (non-overlapping)
- **Total folds:** 34 over 10 years
- Transaction costs: $1 fixed + 5bps slippage
- Position limits: max 5 concurrent, 20% per position

## Key Findings

- **"Over 90% of academic strategies fail when implemented with real capital"**
- Strong regime dependence: +0.60% quarterly in high-vol (2020-2024), -0.16% in stable markets (2015-2019)
- Only 12% statistical power with 34 folds; need ~540 tests for 80% power
- P-value of 0.34 for aggregate returns (not significant) — honest reporting

## Best Practices

1. Never use K-fold or random splits for time series
2. Test across multiple market regimes
3. Include realistic transaction costs
4. Report non-significant results honestly
5. Assess statistical power of your test design
6. Use expanding or rolling windows (252-day train optimal)
7. Retrain quarterly minimum

## Application to 8-ETF Rotation System

Use 252-day rolling train window, 63-day test window, quarterly refit. Ensure training folds contain examples of all regimes (regime-stratified). Always include transaction costs in backtest.
