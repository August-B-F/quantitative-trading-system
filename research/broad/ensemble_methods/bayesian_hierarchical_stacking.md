# Bayesian Hierarchical Stacking

**Citation:** Yao, Y., Pirs, G., Vehtari, A., and Gelman, A. (2022). "Bayesian Hierarchical Stacking: Some Models Are (Somewhere) Useful." *Bayesian Analysis*, 17(4). arXiv:2101.08954.

**Core mechanism:** Generalizes Bayesian stacking so model combination weights vary as a function of covariates (regime indicators, volatility, macro variables). Weights are partially pooled via hierarchical prior, preventing overfitting while allowing genuine regime-dependent model selection.

**Signal:** Define stacking weights w_k(x) where x includes regime indicators (VIX, yield curve, momentum breadth). Fit hierarchical regression on unconstrained log-weights with partial pooling. Optimize via cross-validated log predictive density. Implementable with Stan or PyMC.

**Data needed:** Covariates predicting which model performs best (regime indicators you already compute). Plus out-of-fold predictions from each candidate model.

**Performance:** When model performance is heterogeneous across regimes, hierarchical stacking substantially outperforms fixed stacking. Demonstrated across multiple domains.

**Weaknesses:** Requires enough data per "regime" for weight function to learn. If candidate models all perform similarly across regimes, reduces to standard stacking.

**Assessment:** **High confidence this is real and implementable.** Yao/Vehtari/Gelman is among the most rigorous teams in Bayesian statistics. The hierarchical prior prevents overfitting the weight function. Exactly the kind of principled improvement that survives out-of-sample.

**Application to 8-ETF rotation:** Use HMM regime labels, VIX, yield curve, credit spreads as covariates. Let hierarchical stacking learn that (e.g.) HMM-LSTM dominates in transitions while XGBoost dominates in stable trends. Replaces ad-hoc regime-conditional ensemble logic with a principled framework.
