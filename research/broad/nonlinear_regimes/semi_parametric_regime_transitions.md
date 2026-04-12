# Semi-Parametric Regime Transition Models

**Citation:** Chen, R. et al. (2025). "Learning Nonlinear Regime Transitions via Semi-Parametric State-Space Models." arXiv:2604.04963.

**Core mechanism:** Replaces standard logistic/probit transition probability in Markov-switching models with a nonparametric function learned via kernel methods (RKHS). Allows transition probability between regimes to depend on covariates (VIX, sentiment) in arbitrarily complex, nonlinear ways.

**Signal:** Monthly state-space model with observable covariates (VIX, AAII bull-bear spread) driving regime transitions. Learned function captures joint extremes of uncertainty and sentiment that trigger shifts. Output: filtered probability of being in each regime.

**Data needed:** Monthly VIX, AAII sentiment index, plus return series.

**Performance:** Superior regime classification accuracy and earlier detection vs. parametric Markov-switching. Tested 2005-2023.

**Weaknesses:** Very new (April 2025) -- no citations yet. Kernel method requires careful bandwidth selection. 228 monthly observations is modest for nonparametric method. No direct portfolio backtest.

**Assessment:** Theoretically elegant. Addresses real limitation of standard Markov-switching. Economically sensible that regime transitions depend nonlinearly on VIX x sentiment interaction. **Promising but needs more validation.**

**Application to 8-ETF rotation:** Improved regime filter capturing scenarios like "high VIX + bearish sentiment = high probability of staying in crisis" that linear models miss.
