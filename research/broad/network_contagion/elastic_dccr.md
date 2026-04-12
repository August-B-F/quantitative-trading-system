# Elastic Detrended Cross-Correlation Ratio (DCCR)

**Citation:** Daethey, D. et al. (2025). "Detecting Network Instability via Multiscale Detrended Cross-Correlations and MST Topology." arXiv:2602.10174.

**Core mechanism:** Combines Detrended Cross-Correlation Analysis (DCCA) with Minimum Spanning Tree filtering across multiple time scales. When short-term correlations spike relative to long-term (network synchronizes at short horizons), this signals stress.

**Signal:** (1) Compute DCCA coefficients between all asset pairs at multiple scales (10-day, 50-day, 200-day). (2) Build MSTs at each scale. (3) Elastic DCCR = d(log MST_length)/d(log scale). Sharp drop below baseline signals crisis regime.

**Data needed:** Daily returns for set of equity indices. GARCH(1,1) residuals as inputs.

**Performance:** Elastic DCCR rises sharply during all major disruptions 2013-2023, capturing episodes invisible to single-scale analysis.

**Weaknesses:** New paper (Feb 2025), not yet cited. No portfolio backtest. Computation heavy. 10-year sample.

**Assessment:** The multi-scale angle is genuinely novel -- captures correlation structure compression at short horizons during stress that single-scale measures miss. **Novel mechanism, needs portfolio validation.**

**Application to 8-ETF rotation:** Compute from 8 ETF daily returns. When short-term MST contracts relative to long-term, shift defensive. Different facet of correlation breakdown than static measures.
