# ETF Flow Contrarian Signal

**Citation:** Brown, D.C., Davies, S., and Ringgenberg, M.C. (2021). "ETF Arbitrage, Non-Fundamental Demand, and Return Predictability." *Review of Finance*, 25(4), 937-972.

**Core mechanism:** When non-fundamental demand pushes ETF prices away from NAV, authorized participants create/redeem shares to arbitrage the gap. These flows are observable and signal temporary price dislocations that subsequently reverse over 1-6 months.

**Signal:** Measure net ETF creation/redemption activity (shares outstanding changes) normalized by AUM. ETFs with extreme recent inflows tend to underperform over 1-6 months (non-fundamental demand inflates prices temporarily).

**Data needed:** ETF shares outstanding (daily, from exchanges/Bloomberg), ETF AUM, ETF returns. All publicly available.

**Performance:** Long-short portfolio earns 1.1-2.0% per month in excess returns. Published in Review of Finance.

**Weaknesses:** Long-short strategy; for long-only rotation, use as filter. The 1-2% monthly alpha seems high and likely includes small/illiquid ETFs. Capacity constraints may apply for liquid ETFs.

**Assessment:** Mechanism is real and grounded in limits-to-arbitrage. Magnitude likely overstated for liquid sector ETFs. **Usable as a contrarian filter, not standalone signal.**

**Application to 8-ETF rotation:** Use trailing 1-month ETF flow data as a negative screen -- penalize ETFs experiencing abnormally high creation activity (crowded flows). Adds a microstructure dimension genuinely different from all existing signals.
