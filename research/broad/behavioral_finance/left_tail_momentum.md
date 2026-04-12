# Left-Tail Momentum

**Citation:** Atilgan, Y., Bali, T.G., Demirtas, K.O., and Gunaydin, A.D. (2020). "Left-Tail Momentum: Underreaction to Bad News, Costly Arbitrage and Equity Returns." *Journal of Financial Economics*, 135(3), 725-753.

**Core mechanism:** Investors underestimate the persistence of left-tail risk. Assets that recently experienced extreme negative returns continue to underperform because investors are slow to update their assessment of downside risk.

**Signal:** Compute left-tail risk using VaR or Expected Shortfall at the 5% level from daily returns over the past month or quarter. Avoid/underweight ETFs with high recent left-tail risk (VaR persistence).

**Data needed:** Daily returns to compute VaR/ES. Trivially available for ETFs.

**Performance:** Tested across US equities 1962-2015, with international validation across 23 developed markets. Stronger for retail-investor-heavy and low-attention assets.

**Weaknesses:** Strongest as a long-short stock strategy. For long-only 8-ETF rotation, this is essentially a crash avoidance filter. ETFs have lower idiosyncratic tail risk than individual stocks.

**Assessment:** Real alpha with credible mechanism. Published in JFE with international robustness. **Most naturally serves as a risk filter at ETF level.**

**Application to 8-ETF rotation:** Add a VaR/ES filter: before entering a momentum position, check whether the ETF has had extreme left-tail events (e.g., >2 daily returns below -3% in past month). If yes, avoid even if momentum score is positive. Complementary to volatility targeting and turbulence filters.
