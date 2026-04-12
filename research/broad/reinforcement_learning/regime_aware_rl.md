# Adaptive and Regime-Aware RL for Portfolio Optimization

**Citation:** Nixon Raj, G. (2025). "Adaptive and Regime-Aware RL for Portfolio Optimization." arXiv:2509.14385. NYU.

**Core mechanism:** RL environments where agents receive hybrid observations (price features + latent regime indicators) and train with constrained reward functions: returns - volatility penalty - turnover cost. Capital resets at regime transitions force agent to learn regime-adaptive behavior.

**Signal:** RL environment provides: asset returns/vol, regime indicators from HMM, macro features. Transformer-PPO achieves highest risk-adjusted returns; LSTM-PPO offers better interpretability/cost tradeoff.

**Data needed:** Standard price data, volatility indicators, macro features, regime labels.

**Performance:** Both variants outperform equal-weight and Sharpe-optimized portfolios. Robust under simulated financial stress.

**Weaknesses:** RL agents overfit on repeated trajectories. Monthly rebalancing = very few decision steps per year (challenging for RL). "Robust under stress" based on simulated stress, not actual crises.

**Assessment:** Regime-aware reward design and capital reset mechanism are thoughtful. However, **RL for monthly portfolio rebalancing is fundamentally data-starved** (~12 decisions/year). Architecture ideas worth borrowing for existing framework; full RL control at monthly frequency is risky.

**Application to 8-ETF rotation:** Borrow the reward function design (return - vol penalty - turnover cost) for training any model. If using RL, use only for allocation weighting step (given predictions, how to size) rather than full predict-and-allocate. LSTM-PPO with regime conditioning is most practical.
