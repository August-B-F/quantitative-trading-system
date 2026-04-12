# A Machine Learning Approach to Regime Modeling (Two Sigma)

**HIGH PRIORITY**

- **Authors:** Two Sigma Research
- **Year:** 2020+
- **Source:** Two Sigma Insights

## Methodology

- **Gaussian Mixture Model (GMM)** — unsupervised
- 17 factors from Two Sigma Factor Lens (U.S. version)
- Data back to early 1970s
- Factors include: Equity, Credit, Interest Rates, Inflation, Value, Momentum, Quality, Currency, Volatility

## 4 Regimes Identified

| Regime | Characteristics |
|--------|----------------|
| **Crisis** | Negative equity/credit returns, positive bonds, elevated correlations |
| **Steady State** | Consistent positive performance across factors |
| **Inflation** | Inflation hedges outperform, weak equity/bonds |
| **Walking on Ice (WOI)** | High volatility, fragile, reversal behavior, often surrounds crises |

## Asset Performance by Regime

- **Crisis:** Large-cap outperforms, small-cap underperforms, bonds rally
- **Inflation:** Foreign currency and inflation-hedged assets excel
- **WOI:** Elevated factor volatility with mixed returns
- **Steady State:** Broad positive performance

## Application to 8-ETF Rotation System

Map 8 ETFs to factor exposures. Use GMM on multi-factor returns to identify current regime. Allocate to ETFs with historically strong regime-conditional performance:
- Crisis → TLT, GLD
- Steady State → SPY, QQQ
- Inflation → GLD, EEM
- WOI → Reduce exposure, diversify

## Known Failure Modes

- Regime labels are interpretive (unsupervised model)
- Requires factor return data as inputs
- Regime transitions may be detected with lag
