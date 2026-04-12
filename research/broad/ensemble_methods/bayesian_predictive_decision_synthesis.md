# Bayesian Predictive Decision Synthesis (BPDS)

**Citation:** Tallman, E. and West, M. (2024). "Predictive Decision Synthesis for Portfolios: Betting on Better Models." arXiv:2405.01598. Foundational: Tallman & West (2022), arXiv:2206.03815.

**Core mechanism:** Extends BPS by incorporating the decision context (portfolio allocation) into model combination. Jointly learns combination weights that are optimal for the downstream decision, not just the most accurate forecaster. Weights tilted toward whichever model is most useful for the actual portfolio objective.

**Signal:** Maintain K candidate models producing forecast densities. BPDS uses a synthesis function (DLM) that maps model outputs to combined predictions, with parameters estimated by optimizing decision-relevant loss (Sharpe ratio, mean-variance utility). Sequential MCMC updates weights over time.

**Data needed:** Same inputs your candidate models use. Meta-layer on top of existing model outputs.

**Performance:** Applied to FX portfolio rebalancing. Outperforms BMA, equal-weight, and individual models on realized portfolio metrics.

**Weaknesses:** Computationally heavier (requires MCMC). Advantage is largest when candidate models have heterogeneous strengths. Modest improvement if all models are similar.

**Assessment:** Principled framework from top Bayesian statistics group (Mike West, Duke). Not data-mined. Alpha comes from better *combination*, not new signals. **Likely modest but consistent improvement.**

**Application to 8-ETF rotation:** Layer BPDS on top of existing ensemble (deep ensembles, TFT, HMM-LSTM, XGBoost). Instead of simple averaging, let BPDS learn time-varying combination weights optimized for your portfolio objective.
