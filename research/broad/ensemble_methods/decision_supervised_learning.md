# Decision by Supervised Learning with Deep Ensembles (DSL)

**Citation:** (2025). "Decision by Supervised Learning with Deep Ensembles: A Practical Framework for Robust Portfolio Optimization." arXiv:2503.13544.

**Core mechanism:** Reframes portfolio construction as supervised learning: train models to directly predict optimal portfolio weights (not returns), using cross-entropy loss against target portfolios from rolling Sharpe optimization. Deep Ensembles (100 runs averaged) reduce variance.

**Signal:** Target label = optimal portfolio weights from rolling optimization. Train neural network to map features to weights directly. Average 100 independent training runs. Bypasses predict-then-optimize pipeline.

**Data needed:** Standard features. Labels constructed from your own historical optimization.

**Performance:** Outperforms traditional and competing ML methods across diverse universes.

**Weaknesses:** Target labels from historical optimization create circular dependency risk. 100-ensemble averaging adds significant compute. Monthly frequency may not generate enough training samples.

**Assessment:** Predict-weights-directly approach is sound, avoids error propagation. Question is whether learned mapping generalizes better than just running the optimizer. **Moderate improvement, more from robustness than alpha.**

**Application to 8-ETF rotation:** Train network to predict 8-ETF weight vector using macro/regime features as inputs and walk-forward Sharpe-optimal weights as labels. Average 50-100 runs. Could replace or supplement predict-then-allocate pipeline.
