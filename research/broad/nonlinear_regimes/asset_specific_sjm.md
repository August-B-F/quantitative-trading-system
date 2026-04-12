# Asset-Specific SJM Regime Forecasts

**Citation:** Shu, Y., Yu, C., and Mulvey, J.M. (2024). "Dynamic Asset Allocation with Asset-Specific Regime Forecasts." *Annals of Operations Research*. arXiv:2406.09578.

**Core mechanism:** Statistical Jump Model applied per-asset (not single market state). Each asset gets its own bull/bear regime label via jump-penalty optimization. A supervised Random Forest then forecasts next-period regime probabilities, feeding into Black-Litterman framework.

**Signal:** For each ETF: (1) Extract rolling features (mean, volatility, skewness, max drawdown). (2) Run SJM to label bull/bear. (3) Train Random Forest to predict next-month regime probability. (4) Integrate via Black-Litterman. Only ~10 regime transitions over 22 years.

**Data needed:** Monthly returns for each ETF, rolling feature windows (~12 months).

**Performance:** Substantially improves Sharpe, Sortino, cumulative return, and information ratio vs. equal-weight and buy-and-hold. Published in peer-reviewed journal.

**Weaknesses:** Per-asset approach requires training separate models per ETF. RF adds ML dependency. BL requires specifying prior views.

**Assessment:** **Most directly actionable paper for this system.** SJM is strict improvement over HMM (adds jump penalty). Per-asset regime is novel vs. single-state macro regime. 10-transitions-in-22-years addresses transaction cost concern.

**Application to 8-ETF rotation:** Replace or augment current HMM/jump model with per-ETF SJM regime forecasts. Asset-specific signals naturally translate to rotation weights.
