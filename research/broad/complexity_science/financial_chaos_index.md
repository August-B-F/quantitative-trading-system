# Financial Chaos Index (FCIX)

**Citation:** Ataei, M., Chen, S., Yang, Z., and Peyghami, M.R. (2021). "Theory and Applications of Financial Chaos Index." *Physica A*, 583, 126356. arXiv:2101.02288. Updated 2025: arXiv:2504.18958.

**Core mechanism:** Constructs a 3rd-order tensor from rolling windows of cross-sectional price changes (not correlation matrices, but mutual price fluctuations). Computes the largest eigenvalue to produce the FCIX, which captures nonlinear multivariate co-movement that correlation matrices miss.

**Signal:** Compute FCIX daily from 500+ stock prices. Three regimes (low/intermediate/high chaos) via Modified Lognormal Power-Law distribution. Use elastic net regression on uncertainty indices (EPU, VIX, EMV) to forecast next-period FCIX.

**Data needed:** Daily prices for S&P 500 constituents. FRED uncertainty indices for forecasting.

**Performance:** Three distinct regimes 1990-2023. High-chaos regime coincides with all major crises. 33-year sample.

**Weaknesses:** Requires large cross-section daily -- computationally intensive. Tensor eigenvalue computation is non-standard. No direct portfolio backtest.

**Assessment:** Genuinely novel. Tensor approach captures higher-order dependencies that PCA/correlation miss. Adds information beyond VIX and Mahalanobis turbulence. **Real mechanism, high novelty, moderate-high implementation effort.**

**Application to 8-ETF rotation:** FCIX regime as third-party regime overlay. High-chaos triggers defensive positioning. More informative than VIX terciles because it captures cross-sectional structure.
