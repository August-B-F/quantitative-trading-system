# Overnight vs. Intraday Expected Returns

**Citation:** Lou, D., Polk, C., and Skouras, S. (2019). "A Tug of War: Overnight Versus Intraday Expected Returns." *Journal of Financial Economics*, 134, 192-213.

**Core mechanism:** Momentum profits are earned *entirely* overnight. Value/profitability premia are earned *entirely* intraday. The two components offset each other cross-period. This decomposition is driven by institutional "tug of war" between different trader types operating at different times.

**Signal:** Decompose close-to-close returns into overnight (close-to-open) and intraday (open-to-close). Sort on overnight momentum separately. Smoothed spread between overnight and intraday return components forecasts time variation in strategy performance.

**Data needed:** Daily open and close prices for ETFs.

**Performance:** Momentum sorted on overnight returns produces significantly higher Sharpe than close-to-close momentum. The overnight/intraday spread is a timing signal for strategy allocation.

**Weaknesses:** ETF-level overnight returns are noisier than single stocks. Effect weakens in very liquid large-cap ETFs. Monthly rebalancing may not capture full effect.

**Assessment:** Real mechanism grounded in institutional behavior. Not data mining. **Survives at monthly frequency as a signal modifier, not high-frequency strategy.**

**Application to 8-ETF rotation:** Use ratio of overnight-to-intraday momentum as auxiliary feature. When overnight momentum is strong relative to intraday, momentum is more likely to persist. When intraday dominates, expect mean reversion.
