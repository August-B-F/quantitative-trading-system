# Dynamic Factor Allocation via SJM

**Citation:** Shu, Y. and Mulvey, J.M. (2024). "Dynamic Factor Allocation Leveraging Regime-Switching Signals." *Journal of Portfolio Management*, 51(3). arXiv:2410.14841.

**Core mechanism:** Same SJM framework applied to factor indices (value, size, momentum, quality, low vol, growth). Identifies bull/bear regimes for each factor's active return relative to market. Integrates signals into Black-Litterman for dynamic factor tilt.

**Signal:** For each factor ETF: compute active return features, run SJM to label bull/bear, forecast regime probability, tilt weights toward factors in predicted bull regimes.

**Data needed:** Monthly returns for factor ETFs or factor-mimicking portfolios.

**Performance:** Information ratio 0.05 -> 0.4-0.5. Calendar year hit rate 78.6%. Turnover ~3x annually. Published in JPM (top practitioner journal).

**Weaknesses:** Factor timing has mixed academic track record. 78.6% hit rate still means ~1 in 5 years underperformance. US-centric.

**Assessment:** Published in JPM, explicitly considers transaction costs and turnover, uses ETF-level data. 3x annual turnover is compatible with monthly rebalancing. **Strong practical paper.**

**Application to 8-ETF rotation:** If ETFs include factor tilts (small-cap value vs. large-cap growth), apply per-factor SJM signals to determine which factor ETFs to overweight each month.
