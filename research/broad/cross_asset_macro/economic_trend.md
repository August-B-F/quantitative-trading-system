# Economic Trend (AQR)

**Citation:** Brooks, J., Feilbogen, N., Ooi, Y.H., and Akant, A. (2024). "Economic Trend." AQR White Paper / SSRN 4710868.

**Core mechanism:** Asset prices systematically under-react to changes in macroeconomic fundamentals. Positioning based on trends in macro data (not price trends) captures this slow incorporation of fundamental information. Extends and refines the earlier "macro momentum" concept.

**Signal:** Track trends in macro fundamentals per asset class: GDP growth, inflation, unemployment, PMI, trade balance, central bank rate changes, risk sentiment. Go long assets where fundamentals are improving. Each theme scaled to 10% target volatility. The specific innovation: decomposition into business cycle, monetary policy, international trade, and risk sentiment themes.

**Data needed:** Standard macro time series: GDP, CPI, PMI, unemployment, trade balance, policy rates. All available from FRED/Bloomberg with 50+ year history.

**Performance:** Sharpe ratio 1.0+ over 50+ years. Positive in every simulated decade. Low/negative correlation to equities and bonds.

**Weaknesses:** "Macro momentum" is already in the known signal list, though this 2024 paper adds significant refinement. Full strategy is long-short across global assets. Macro data has publication lags.

**Assessment:** **Borderline on novelty** vs. existing macro momentum, but the specific signal construction (theme decomposition, vol-targeting each theme, complementarity with price trends) adds implementable detail. Real and robust.

**Application to 8-ETF rotation:** Use business cycle theme (GDP growth trend + inflation trend) to identify current macro regime. The specific innovation: use the *trend* in macro data (12M change in 3M moving average of PMI) rather than the level. Combine with price momentum for dual-signal system.
