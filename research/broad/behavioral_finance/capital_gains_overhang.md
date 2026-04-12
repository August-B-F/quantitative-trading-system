# Capital Gains Overhang (CGO)

**Citation:** Grinblatt, M. and Han, B. (2005). "Prospect Theory, Mental Accounting, and Momentum." *Journal of Financial Economics*, 78(2), 311-339.

**Core mechanism:** The disposition effect (selling winners too early, holding losers too long) creates a wedge between fundamental value and market price. This wedge is proxied by the aggregate unrealized capital gains overhang. As this gap closes, prices exhibit predictable continuation -- what we observe as momentum.

**Signal:** Compute CGO_t = (P_t - RP_t) / P_t, where RP_t is the reference price (cost basis) estimated as a weighted average of past prices using turnover to approximate holding periods. When controlling for CGO, standard past-return momentum loses all predictive power. CGO subsumes momentum.

**Data needed:** Daily prices and volume/turnover for ETFs.

**Performance:** CGO subsumes standard momentum in cross-sectional regressions. Robust across subperiods 1967-2002. Does not reverse at long horizons (unlike standard momentum).

**Weaknesses:** At ETF level, estimating aggregate cost basis is imprecise -- ETF turnover includes creation/redemption activity. Works best in individual equities.

**Assessment:** Real alpha grounded in prospect theory. Strongest evidence that disposition effect *is* the momentum mechanism. Challenge is translating CGO to 8-ETF universe. **Likely real, moderate implementation difficulty.**

**Application to 8-ETF rotation:** Use ETF-level CGO as a refinement overlay on momentum rankings. When two ETFs have similar past returns, prefer the one with higher CGO. CGO divergence from price momentum can also serve as a crash warning.
