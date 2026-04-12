# Momentum Crashes

**HIGH PRIORITY**

- **Authors:** Kent D. Daniel, Tobias J. Moskowitz
- **Year:** 2016
- **Source:** Journal of Financial Economics, Vol. 122(2), pp. 221-247; NBER WP #20439
- **Links:** [SSRN](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2371227), [NBER](https://www.nber.org/papers/w20439)

## Core Signal / Method

Crashes occur in "panic" states: following market declines + when market volatility is high + contemporaneous with market rebounds. Past losers embody a high-beta/option-like payoff during bear markets — when the market rebounds, losers surge, crushing long-winners/short-losers portfolios.

**Dynamic Momentum Strategy:** Scale position size so that conditional volatility is proportional to conditional Sharpe ratio. Forecast both mean and variance of momentum returns.

Formula: `w_t = (1/2) * (mu_t / sigma^2_t)` where mu_t and sigma^2_t are conditional forecasts.

## Reported Performance

- Static momentum Sharpe: ~0.30
- Dynamic momentum Sharpe: ~1.18 (4x improvement for US equities)
- Approximately doubles the Sharpe ratio of static momentum across all markets

## Application to 8-ETF Rotation System

Monitor market volatility (VIX) and recent drawdown. When VIX is elevated AND market has recently crashed, reduce momentum exposure or switch to contrarian/mean-reversion. Scale position sizes inversely with strategy variance. Most critical for equity-heavy rotation (SPY, QQQ, IWM, EFA, EEM).

## Known Failure Modes

- Forecasting variance is imperfect
- May reduce exposure prematurely in sustained trends
