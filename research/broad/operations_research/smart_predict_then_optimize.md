# Smart Predict-then-Optimize (SPO) for Portfolios

**Citation:** (2026). "Smart Predict-then-Optimize for Portfolio Optimization in Real Markets." arXiv:2601.04062.

**Core mechanism:** Instead of training return predictor to minimize MSE then feeding into optimizer, train predictor to directly minimize downstream portfolio loss. SPO+ surrogate loss backpropagates through the optimization layer. Key insight: "improvements in return forecast accuracy do not always lead to proportional improvements in portfolio decision quality."

**Signal:** (1) Define portfolio optimization problem (mean-variance with costs/turnover). (2) Replace MSE loss with SPO+ loss measuring how much worse portfolio decision is with predicted vs. true returns. (3) Train linear predictors on return/technical features. (4) Monthly rolling-window rebalancing.

**Data needed:** Same features you already use, plus optimization problem specification.

**Performance:** Tested on US ETF data (2015-2025) with monthly rebalancing. Decision-focused training consistently improves risk-adjusted performance vs. predict-then-optimize across crisis and bull markets.

**Weaknesses:** Requires differentiable optimization layer (convex problems work; integer constraints do not). Linear predictors may miss nonlinear relationships. Improvement is moderate, not dramatic.

**Assessment:** Methodologically rigorous from OR community. The forecast-accuracy != decision-quality insight is well-established but underappreciated in quant finance. **Directly tested on ETFs with monthly rebalancing -- rare and valuable.** Likely 50-100 bps improvement.

**Application to 8-ETF rotation:** Retrain existing models using SPO+ loss instead of MSE/cross-entropy. Wrap your allocator as differentiable layer (cvxpylayers). Model learns predictions that lead to *better portfolios*, not just better forecasts.
