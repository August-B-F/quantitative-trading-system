# Factor Momentum

**Citation:** Ehsani, S. and Linnainmaa, J.T. (2022). "Factor Momentum and the Momentum Factor." *Journal of Finance*, 77(3), 1877-1919.

**Core mechanism:** Individual stock momentum is an aggregation of autocorrelations in underlying factors. Factors themselves exhibit positive autocorrelation (6bp/month after a losing year vs. 51bp/month after a winning year). Momentum in stocks is transmitted from momentum in factors.

**Signal:** Go long factors with positive trailing 12-month returns, short those with negative returns. Factor momentum subsumes individual stock momentum. For ETFs: rotating among factor-tilted ETFs based on trailing factor returns IS factor momentum. High-eigenvalue factors carry strongest momentum autocorrelation.

**Data needed:** Factor returns (Ken French Data Library or AQR). Or use factor-proxy ETFs directly.

**Performance:** Explains most of individual stock momentum profits. Concentrated in high-eigenvalue factors. Robust 1963-2019.

**Weaknesses:** More theoretical insight than new tradeable signal. If already doing ETF rotation among asset-class ETFs, you are implicitly running factor momentum.

**Assessment:** Landmark paper reframing momentum. Not directly actionable as a new signal, but the eigenvalue-weighting insight is new and useful.

**Application to 8-ETF rotation:** Weight momentum signals more heavily for ETFs loading on high-eigenvalue factors (market, value, momentum). A factor-momentum overlay (tracking which macro factors are trending) can improve rotation timing.
