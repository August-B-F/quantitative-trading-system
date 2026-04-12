# Score-Driven Bayesian Online Changepoint Detection

**Citation:** Tsaknaki, Lillo, Mazzarisi (2023). "Online Learning of Order Flow and Market Impact with Bayesian Change-Point Detection Methods." arXiv:2307.02375 / SSRN 4500960.

**Core mechanism:** Extends Adams-MacKay BOCPD with a score-driven observation model handling temporal correlations and time-varying parameters *within* each regime. Detects regime shifts in real-time, provides regime-specific forecasts. Run-length posterior tells you probability of being N periods since last changepoint.

**Signal:** (1) Run BOCPD on returns/volatility/order flow. (2) Within each regime, parameters evolve via score-driven update (GAS model) rather than being static. (3) Bimodal run-length distribution signals likely regime change. (4) Use regime-specific parameters for downstream forecasting.

**Data needed:** Daily returns or volume data.

**Performance:** Out-of-sample forecasting outperforms autocorrelated time series models without regimes. Regime dynamics consistent with microstructure theory.

**Weaknesses:** Tested on order flow, not directly on portfolio returns. Score-driven extension adds complexity. O(T) memory for exact inference.

**Assessment:** **Genuine advance over vanilla BOCPD.** Score-driven intra-regime dynamics address real weakness (i.i.d. within-regime assumption). Online, non-parametric in regime count, handles intra-regime dynamics.

**Application to 8-ETF rotation:** Replace or augment current regime detector. Run-length posterior provides probability of regime change as a gating mechanism. Intra-regime dynamics prevent "false stability" where HMMs stay in regime too long.
