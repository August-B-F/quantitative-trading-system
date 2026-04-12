# Skewed Student-t Distribution Output Head

**Citation:** (2025). "Forecasting Probability Distributions of Financial Returns with Deep Neural Networks." arXiv:2508.18921.

**Core mechanism:** Trains LSTM/CNN to output parameters of skewed Student-t distribution (location, scale, shape, skewness) instead of point predictions. Custom NLL loss optimizes distribution parameters directly. Captures fat tails and asymmetry that Gaussian assumptions miss.

**Signal:** Replace model's final layer with 4 outputs: mu, sigma, nu (degrees of freedom), gamma (skewness). Train with NLL loss. Evaluate calibration via PIT histogram uniformity test. Skewed Student-t captures real return distribution properties.

**Data needed:** Same inputs as any return prediction model. Tested on 6 major equity indices.

**Performance:** LSTM + skewed Student-t achieves lowest LPS and CRPS across six markets. PIT test confirms substantially better calibration vs. Gaussian.

**Weaknesses:** PIT p-value of 0.031 is marginal. Daily frequency only tested; monthly needs revalidation. Still parametric.

**Assessment:** Solid methodological contribution. Easy to implement. Strictly dominates Gaussian outputs for financial returns. **Incremental but useful improvement.**

**Application to 8-ETF rotation:** Replace model output head with skewed Student-t parameterization. Gives calibrated uncertainty for: (1) Kelly-criterion sizing using full distribution; (2) risk budgeting using tail quantiles; (3) better confidence scores for ensemble.
