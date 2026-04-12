# Skulls, Financial Turbulence, and Risk Management

**HIGH PRIORITY**

- **Authors:** Mark Kritzman, Yuanzhen Li
- **Year:** 2010
- **Source:** Financial Analysts Journal, 66(5)

## Core Method

Mahalanobis distance as "turbulence index":

```
d(y_t) = (y_t - mu)^T * Sigma^{-1} * (y_t - mu)
```

Under multivariate normality, follows chi-squared distribution with n degrees of freedom. Threshold at 70th/80th/95th percentile partitions observations into turbulent/non-turbulent regimes.

## Key Finding

Returns-to-risk substantially lower during turbulent periods. Turbulence is persistent — arrives unexpectedly but does not immediately subside. Captures both extreme moves AND unusual correlation patterns.

## Application to 8-ETF Rotation System

Calculate daily Mahalanobis distance across the 8-ETF return vector. When turbulence exceeds threshold, reduce equity exposure and increase defensive positions. Captures correlation breakdowns that univariate volatility measures miss.

## Known Failure Modes

- Requires stable covariance estimation
- Threshold selection somewhat arbitrary
- Sensitive to sample period for mu and Sigma
- Assumes multivariate normality
