# Regime-Switching DRO-CVaR

**Citation:** Pun, C.S., Wang, L., and Yan, H. (2023). "Data-Driven Distributionally Robust CVaR Portfolio Optimization Under Regime-Switching Ambiguity Set." SSRN 4378930.

**Core mechanism:** Combines distributionally robust optimization with regime-switching via HMM. Ambiguity set changes with detected regime: portfolio is robust to distributional uncertainty *within* each regime without being excessively conservative across regimes. Wasserstein ball radius adapts -- tighter in stable periods, wider in uncertain ones.

**Signal:** (1) Estimate HMM regimes. (2) Build regime-specific Wasserstein ambiguity sets around empirical distribution. (3) Solve DRO-CVaR within current regime's set. Automatic uncertainty handling.

**Data needed:** Daily returns for asset universe.

**Performance:** Out-of-sample superior CVaR and Sharpe vs. non-regime-switching DRO and classical mean-variance.

**Weaknesses:** Computationally heavier than mean-variance. HMM regime detection adds latency at transitions. Conservative by design -- underperforms in strong bull markets.

**Assessment:** Theoretically rigorous. Regime-switching ambiguity is genuine innovation over vanilla DRO. **Not data mining -- grounded in optimization theory.**

**Application to 8-ETF rotation:** Replace optimizer with regime-conditioned DRO-CVaR. When regime detector signals uncertainty, Wasserstein ball widens automatically, producing more defensive allocations. Principled uncertainty handling.
