# Regime-Conditional Kalman Filtering

**Citation:** Kang (2025/2026). "When the Rules Change: Adaptive Signal Extraction via Kalman Filtering and Markov-Switching Regimes." arXiv:2601.05716.

**Core mechanism:** Three-pillar framework: (1) Adaptive Kalman filter extracts signal from noisy order flow, (2) 3-state Markov-switching model (Bull/Normal/Crisis) where Kalman parameters *change with regime*, (3) asymmetric response functions for positive vs. negative shocks.

**Signal:** Classify regime using 3-state Markov model. Run Kalman filter with regime-specific parameters (signal-to-noise ratio, observation noise, state transition). Regime-conditional coefficients: e.g., predictive power rises 8.9x from Bull to Crisis.

**Data needed:** Daily price and volume per ETF. Ideally investor-type flows (can be approximated from volume patterns).

**Performance:** Strategy Sharpe: 1.08 in 2020 (high vol), 0.65 in 2024, but poor in 2021-2023 (low vol). 2,439 stocks, 2.79M observations.

**Weaknesses:** Korean market only. Requires investor-type flow data. Collapses in low-vol grinding bear markets.

**Assessment:** The *framework* is excellent -- regime-conditional Kalman where filter adapts to regime is powerful and novel. The 2021-2023 failure is honest and informative. **Framework transfers, methodology is sound.**

**Application to 8-ETF rotation:** Regime-conditional Kalman on momentum signals. In high-vol: increase Kalman gain (respond faster). In low-vol: decrease gain (trust prior, trade less). Addresses whipsawing in choppy markets.
