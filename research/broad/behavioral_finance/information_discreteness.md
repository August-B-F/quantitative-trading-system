# Information Discreteness (Frog-in-the-Pan)

**Citation:** Da, Z., Gurun, U.G., and Warachka, M. (2014). "Frog in the Pan: Continuous Information and Momentum." *Review of Financial Studies*, 27(7), 2171-2218.

**Core mechanism:** Investors are inattentive to information arriving in small, frequent increments. Assets whose cumulative return was achieved via many small same-sign daily moves (continuous information) exhibit much stronger momentum than those whose return came from a few large jumps (discrete information).

**Signal:** ID = sgn(PRET) x [%neg - %pos], where %pos/%neg = fraction of positive/negative daily return days in formation period. ID ranges from -1 (perfectly continuous) to +1 (perfectly discrete). More negative ID = stronger, more trustworthy momentum signal.

**Data needed:** Daily returns over the formation period. Trivially computable for any ETF.

**Performance:** Momentum spread goes from 5.94% annualized for most-continuous to -2.07% for most-discrete stocks. Does NOT reverse at long horizons. Robust across size quintiles, subperiods 1927-2011, survives transaction costs.

**Weaknesses:** Designed for individual stock cross-sections. With only 8 ETFs, limited cross-sectional variation. Most powerful with many assets to sort.

**Assessment:** Real alpha. One of the cleanest tests of the limited-attention hypothesis. **Novel, mechanistically grounded, does not reverse.**

**Application to 8-ETF rotation:** Before entering a momentum-driven position, check the ETF's ID. If the uptrend was driven by a few large up-days (discrete), the momentum is less trustworthy -- downweight or skip. If achieved via many small positive days (continuous), momentum is more reliable. Acts as a *momentum quality* filter.
