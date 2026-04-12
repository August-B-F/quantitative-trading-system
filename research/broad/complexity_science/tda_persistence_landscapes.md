# Topological Data Analysis -- Persistence Landscapes

**Citation:** Gidea, M. and Katz, Y. (2018). "Topological Data Analysis of Financial Time Series: Landscapes of Crashes." *Physica A*, 491, 820-834. arXiv:1703.04385.

**Core mechanism:** Embeds multivariate return time series into a point cloud, computes persistent homology (H1 loops), and converts barcodes into persistence landscapes. The Lp-norms of these landscapes quantify how "loopy" the return structure is -- rising norms reflect increasing coherent co-movement that precedes crashes.

**Signal:** Compute L1/L2 norm of persistence landscape from rolling 50-day window of daily returns across 4+ equity indices. Monitor spectral density of Lp-norm time series. Sustained rising trend over ~250 trading days signals approaching regime break. Threshold: spectral density >2 std above rolling mean.

**Data needed:** Daily returns of 4+ equity indices (S&P 500, DJIA, Nasdaq, Russell 2000).

**Performance:** Strong rising trend detected 250 days before both 2000 dot-com crash and 2008 Lehman bankruptcy. Validated across Black Monday, dot-com, 2008, COVID. Topology is coordinate-invariant.

**Weaknesses:** Very slow signal (250-day lead). No clear re-entry signal. Limited out-of-sample portfolio backtest. Persistent homology computation is O(n^3).

**Assessment:** Real mechanism grounded in algebraic topology, not data mining. Genuinely novel vs. existing stack. **Likely real signal, moderate implementation difficulty.**

**Application to 8-ETF rotation:** Use Lp-norm trend as "crash proximity" overlay. When 6-month spectral density crosses threshold, shift toward defensive ETFs. Complementary to VIX/turbulence because it detects structural topology changes, not just volatility.
