# Time Series Momentum

**HIGH PRIORITY**

- **Authors:** Tobias J. Moskowitz, Yao Hua Ooi, Lasse Heje Pedersen
- **Year:** 2012
- **Source:** Journal of Financial Economics, Vol. 104(2), pp. 228-250
- **Links:** [JFE](https://www.sciencedirect.com/science/article/pii/S0304405X11002613), [SSRN](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2089463)

## Core Signal / Method

Past 12-month excess return of each instrument is a positive predictor of its future return. Goes long instruments with positive 12-month returns; short those with negative returns. 1-month holding period.

## Data Used

58 diverse futures and forward contracts across country equity indices, currencies, commodities, and sovereign bonds. 25+ years of data.

## Reported Performance

- Substantial abnormal returns with little exposure to standard asset pricing factors
- Diversified portfolio across all asset classes performs best during extreme markets
- Momentum persists 1-12 months, partially reverses beyond 12 months

## Application to 8-ETF Rotation System

Use 12-month return as the primary ranking signal for rotation. Rank ETFs by trailing 12-month return; overweight top performers. Add absolute momentum filter (only hold if 12-month return > 0).

## Known Failure Modes

- Momentum crashes: sharp reversals after extended trends
- Partial reversal effect at 12+ months suggests holding periods should not extend beyond 12 months
- Crowding risk as strategy becomes widely adopted
