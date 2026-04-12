# Model Predictive Control (MPC) for Portfolio Optimization

**Citation:** Nystrup et al. (2021) / Boyd et al. (2017). "Multi-Period Portfolio Optimization using Model Predictive Control." arXiv:2103.10813.

**Core mechanism:** MPC plans a sequence of future trades over a lookahead horizon but only executes the first, then re-plans. Naturally handles transaction costs, turnover constraints, and path-dependent risk by incorporating them into the multi-period objective.

**Signal:** At each rebalance: (1) Forecast returns and covariances over T-period horizon. (2) Solve convex optimization minimizing risk minus return plus transaction cost penalty over full horizon. (3) Execute only first period's trades. (4) Repeat.

**Data needed:** Return and covariance forecasts (existing model provides these), transaction cost estimates per ETF.

**Performance:** OOS Sharpe 0.64 (mean-variance) to 0.97 (risk-parity MPC), 2006-2020. Turnover reduced 30-50% vs. single-period optimization. 30x speedup from successive convex programming.

**Weaknesses:** Requires calibrated return forecasts over lookahead -- garbage in, garbage out. Benefit over single-period most pronounced when transaction costs are high relative to alpha.

**Assessment:** Solid operations research, widely used in practice. **Not a new alpha source but a better implementation of existing signals.** Genuine improvement over myopic rebalancing.

**Application to 8-ETF rotation:** Set MPC lookahead to 3-6 months. Optimizer automatically delays trades when alpha is marginal relative to costs, front-loads when signals are strong. Smooths turnover, reduces whipsawing at regime transitions.
