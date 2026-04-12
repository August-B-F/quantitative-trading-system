# Absorption Ratio

**Citation:** Kritzman, M., Li, Y., Page, S., and Rigobon, R. (2011). "Principal Components as a Measure of Systemic Risk." *Journal of Portfolio Management*, 37(4), 112-126. SSRN:1633027.

**Core mechanism:** The Absorption Ratio (AR) = fraction of total variance explained by a fixed number of eigenvectors (typically 1/5 of assets). When AR is high, markets are tightly coupled and fragile. Spikes in AR (delta-AR) precede major drawdowns.

**Signal:** Rolling 500-day AR from cross-section of asset returns. Signal: standardized change in AR over 2 weeks (delta-AR / rolling std). When delta-AR > 1 std, shift defensive. When < -1 std, shift risk-on. It's the *change* in AR that predicts, not the level.

**Data needed:** Daily returns for 50+ assets (sector ETFs, individual stocks, or mix).

**Performance:** Most significant US drawdowns preceded by AR spikes. Stock prices depreciate following spikes, appreciate following declines. Leading indicator of US housing bubble. 700+ citations. Published in JPM.

**Weaknesses:** Related to existing PCA-based clustering. Relies on somewhat arbitrary eigenvector count. Does not distinguish between types of coupling.

**Assessment:** Extremely well-cited and simple to implement. The delta-AR timing mechanism is distinct from existing PCA methods. **Real signal, highly cited.**

**Application to 8-ETF rotation:** Compute AR from daily returns of 8 ETFs plus additional sector ETFs. Use delta-AR as crash proximity indicator complementing turbulence measure.
