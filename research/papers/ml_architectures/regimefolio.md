# RegimeFolio: Regime Aware ML System for Sectoral Portfolio Optimization

**HIGH PRIORITY**

- **Year:** 2025
- **Source:** arXiv:2510.14986

## Architecture Details

- **VIX-based regime classifier:** rolling 252-day terciles (thresholds ~17.8 and ~23.1)
- **3 regimes:** Low, Medium, High volatility
- Per-regime Random Forest (100 estimators, max_depth=10, min_samples_split=5)
- Per-regime Gradient Boosting (100 estimators, lr=0.1, max_depth=6)
- Ledoit-Wolf shrinkage covariance estimation per regime
- Dynamic mean-variance optimizer with turnover constraints

## Features

- **Technical:** RSI, MACD, Bollinger Bands, rolling volatility
- **Momentum:** 5, 10, 20-day price momentum
- **Macro:** VIX levels, ICE BofA High Yield OAS spread
- All features standardized separately within each regime

## SHAP Importance by Regime

| Regime | Momentum | Mean-Rev | Volatility |
|--------|----------|----------|------------|
| Low Vol | **0.342** | 0.198 | 0.167 |
| Medium Vol | 0.198 | **0.267** | 0.234 |
| High Vol | 0.087 | 0.156 | **0.456** |

## Performance (2020-2024)

| Metric | RegimeFolio | S&P 500 |
|--------|-------------|---------|
| Total Return | 137.0% | 73.8% |
| Sharpe Ratio | 1.17 | 0.66 |
| Max Drawdown | -29.3% | -41.2% |
| Annualized Return | 18.9% | 11.7% |

## Application to 8-ETF Rotation System

Directly applicable. Replace 34 stocks with 8 ETFs, maintain VIX-tercile regime classification, train separate ensemble models per regime-ETF pair. SHAP analysis reveals which features to prioritize per regime — momentum dominates in low-vol, volatility signals dominate in high-vol.

## Known Failure Modes

- Overfitting risk with short high-volatility training windows
- VIX-only regime definition may miss credit/rates regimes
- 2020-2024 period favorable to regime strategies
