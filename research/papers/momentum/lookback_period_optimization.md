# Lookback Period Optimization for Momentum Signals

**HIGH PRIORITY**

- **Sources:** Multiple (Moskowitz et al., ReSolve Asset Management, Quantpedia, CME Group)

## Key Research Findings

- **Academic consensus:** Momentum is a phenomenon at 6-12 month horizons. Beyond 12 months, momentum wanes and reversal begins.
- **Moskowitz recommendation:** 12-month lookback is the standard.
- **Empirical findings (1988-2008):** 12-month lookback performed best for equity/bond portfolio.
- **Post-2008:** 3-month lookback has worked better in recent years (faster-moving markets, algorithmic trading).
- **S&P 500 stocks (2015-2025 backtest):** 6-month lookback, 1-month holding, skip most recent month, top 10% — delivered 702% total return over a decade.
- **Dynamic lookback:** The optimal lookback period changes over time. ReSolve Asset Management research shows the "half-life" of optimal lookback is not stable.
- **Multiple lookback blend:** Averaging signals from 1, 3, 6, and 12-month lookbacks provides more robust signals than any single period.
- **Skip month:** Most academic papers skip the most recent month (short-term reversal effect).

## Application to 8-ETF Rotation System

- **Primary signal:** 12-month return (skip last month) — most robust, most academic support
- **Enhancement:** Blend with 3-month and 6-month signals (e.g., 50% weight to 12M, 25% to 6M, 25% to 3M)
- **Further enhancement:** Use vol-adjusted returns for ranking
- **Dynamic approach:** Shorten lookback when market vol is elevated (faster adaptation needed in crisis)

## VAA Weighted Momentum Formula (Keller)

`Score = (12 × 1M return) + (4 × 3M return) + (2 × 6M return) + (1 × 12M return)`

This weights recent momentum more heavily (~40% on most recent month) while still incorporating longer-term trends.
