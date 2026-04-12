# Conformal Predictive Portfolio Selection (CPPS)

**Citation:** Kato, M. (2024). "Conformal Predictive Portfolio Selection." arXiv:2410.16333.

**Core mechanism:** Uses conformal prediction to construct distribution-free prediction intervals for *portfolio-level* returns (not individual assets), then selects portfolios based on these intervals. Automatically captures correlation structure without modeling it explicitly.

**Signal:** For each candidate allocation, generate prediction interval using split conformal inference on residuals from any base model. Select portfolio whose lower bound is highest (maximin approach). Provides finite-sample coverage guarantees regardless of base model accuracy.

**Data needed:** Historical portfolio-level returns for each candidate allocation. Any base forecasting model.

**Performance:** Superior returns vs. naive strategies while maintaining valid coverage. Maximin approach improves worst-case performance.

**Weaknesses:** Conformal prediction assumes exchangeability, which time series violate. Coverage guarantees weaken under strong non-stationarity. Computational cost scales with candidate portfolio count.

**Assessment:** Clever and practical. Distribution-free safety net around any base model. **Not alpha-generating per se, but alpha-preserving through better risk management.**

**Application to 8-ETF rotation:** Generate discrete candidate allocations (top-1, top-3 equal weight, momentum-weighted, etc.). Apply conformal intervals. Use lower bound as selection criterion. Adds calibrated uncertainty layer and protects worst-case outcomes.
