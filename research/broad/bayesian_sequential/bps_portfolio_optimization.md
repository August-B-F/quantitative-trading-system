# Bayesian Portfolio Optimization by Predictive Synthesis

**Citation:** Kato, M. (2025). "Bayesian Portfolio Optimization by Predictive Synthesis." arXiv:2510.07180.

**Core mechanism:** BPS with dynamic linear models combines multiple asset return prediction models, using combined Bayesian predictive posterior for portfolio optimization. DLM synthesis learns time-varying combination weights. Tests mean-variance, quantile-based, and risk parity on BPS output.

**Signal:** Maintain K prediction models. BPS combines via DLM synthesis function with Kalman filter updates providing natural sequential learning. Extract posterior predictive distribution for each asset. Quantile-based allocation provides better downside protection than mean-variance.

**Data needed:** Multiple model forecasts for each asset. Standard market data for base models.

**Performance:** BPS outperforms individual models and BMA across portfolio metrics. Quantile-based allocation superior for downside protection.

**Weaknesses:** DLM assumes approximately linear combination function. Sequential MCMC is computationally demanding. Improvement over simple averaging may be modest when base models are similar.

**Assessment:** Principled Bayesian framework. Sequential DLM updating is natural for time series. Quantile-based allocation is a practical innovation. **Solid but incremental.**

**Application to 8-ETF rotation:** Feed existing ensemble outputs into BPS-DLM synthesis. Kalman filter learns time-varying weights. Extract posterior predictive for each ETF, use quantile-based allocation (median prediction constrained by 10th percentile). Principled sequential updating for your ensemble.
