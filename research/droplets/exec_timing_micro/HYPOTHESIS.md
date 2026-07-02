# HYPOTHESIS — Study 1: Execution timing & microstructure (engineering)

Date: 2026-07-02
Droplet: exec_timing_micro
Type: ENGINEERING MEASUREMENT (no signal parameter is tuned; full window
2005-01-01..2026-06-30 allowed for gap/liquidity statistics). The one
signal-adjacent piece (twin-substitution ledger check) runs on the DEV
window only (2005-01-01..2017-12-31) so no validation look is consumed.

## Q1 — OPEN vs CLOSE fill convention

Hypothesis: momentum buys gap UP overnight after the decision close (we pay
the gap at the next open), and sold legs gap up less; the systematic
open-fill drag is positive but small (expected 5-30 bps/yr at monthly
cadence). Filling at next-day CLOSE instead adds one day of intraday drift
on the OLD portfolio; since momentum continues intraday on average, I
expect open fill to be equal or CHEAPER than close fill (i.e. no change
recommended). I do not have a strong prior on sign; that is why I measure.

Method (exact):
- Representative rotations, month-end decision, fixed ex-ante:
  R1 = GEM (sleeves.gem_weights, verbatim defaults) on SPY/EFA/AGG/SHV.
  R2 = equal-weight top-3 by 63-trading-day total adj_close return on the
       8-ETF universe [SOXX,QQQ,XLK,VGT,IGV,XLE,GLD,SHY], 1/3 each.
  R3 = top-1 by same 63d rule, 100% (mimics live 82-88% top-1 concentration).
  No SMA gate, no other variants. These are turnover-profile probes, not
  candidate strategies.
- Run each through run_ledger_backtest at cost_bps=0, full window, cash SHV.
  From the trades table (exact bought/sold legs and notional fractions):
  * overnight-gap stat: for each leg on fill day f, gap = adj_open_f /
    adj_close_{f-1} - 1; report notional-weighted mean gap on BUY legs vs
    SELL legs, and the net drift cost of open fill vs the (untradeable)
    decision-close paper price, in bps/yr.
  * open-vs-close fill delta (exact, per rebalance): NAV growth difference
    on the fill day = sum_i (w_new_i - w_drifted_old_i) * intraday_ret_i,
    where intraday_ret = adj_close_f/adj_open_f - 1. Positive => open fill
    is better. Annualize (x12). This leg-level arithmetic is exact because
    both conventions hold identical portfolios outside fill-day intraday
    hours; I use it INSTEAD of a shifted-schedule ledger run because a +1
    day shift changes the fill to open of t+2, which is a different
    (delay) question. I additionally report the 1-day-delay NAV delta
    (schedule shifted +1 trading day, 0 bps) as a bracket/robustness check.

Decision rule (pre-committed): if |open-close delta| < 10 bps/yr on R2 and
R3 (the live-like profiles), the fill convention is immaterial -> recommend
keeping next-open fills (matches engine + live). If close fill is cheaper
by >= 10 bps/yr on BOTH R2 and R3, recommend evaluating MOC execution. If
open fill is cheaper by >= 10 bps/yr, recommend keeping open fills and
record the number. Kills the idea: delta inside +/-10 bps/yr.

## Q2 — Twin substitution (SOXX->SMH, VGT->XLK)

Hypothesis: SMH/SOXX and XLK/VGT are >0.97-correlated twins with 2-4% ann
tracking error; swapping to the tighter-spread twin (SMH over SOXX, XLK
over VGT) saves ~1 bp/side on the affected legs, i.e. single-digit bps/yr
at 12x turnover, without materially changing the strategy.

Method (exact):
- Full-window daily adj_close return correlation, ann. tracking error
  (std of return diff * sqrt(252)), and liquidity proxy = median
  (volume * close) over 2023-07-01..2026-06-30, for pairs (SOXX,SMH),
  (XLK,VGT), (QQQ,XLK), (QQQ,VGT).
- Ledger check on DEV window only (2005-01-01..2017-12-31), R2 rule
  (EW top-3 63d), at 10 AND 20 bps/side, cash SHV. EXACTLY 4 universes:
  U0 base [SOXX,QQQ,XLK,VGT,IGV,XLE,GLD,SHY];
  U1 = U0 with SMH replacing SOXX;
  U2 = U0 with XLK replacing VGT (universe becomes 7 tickers: XLK stays once);
  U3 = both substitutions (7 tickers).
- Spread saving estimate: per-ticker share of traded notional from the U0
  trades table x public spread differential (SOXX~2.5bp vs SMH~1.5bp;
  VGT~2.5bp vs XLK~1.5bp) x annual turnover.

Decision rule (pre-committed): recommend a twin swap only if (a) corr >=
0.95 and TE <= 6% ann, (b) dev-window Sharpe delta vs U0 >= -0.05 at 10
bps, and (c) estimated spread saving >= 1 bp/yr. Kills the idea: Sharpe
drop > 0.05 or corr < 0.95. No further universe variants will be run
regardless of results.

## Q3 — Market vs marketable-limit orders (ESTIMATE, no intraday data)

Hypothesis: for these ETFs (1-5 bp spreads) at monthly cadence, market-on-
open-ish market orders lose only ~half-spread + impact (~1-3 bps/side);
a marketable limit pegged to last close +/- 20 bps would miss fills
whenever the overnight gap exceeds 20 bps, which for these ETFs is FREQUENT
(vol ~1-1.5%/day => |gap|>20bp probably >40% of days), so a close-pegged
limit is a bad design; a limit pegged near the opening quote is the only
sensible variant and its edge over market orders is < 2 bps/side.

Method:
- Extract slippage_bps from logs/rebalance_log.json (live paper fills) —
  report distribution (noisy equity-drift proxy, stated as such).
- From daily data: frequency and magnitude of |open_t+1/close_t - 1| >
  20 bps on the 8-ETF universe (miss-rate of a close-pegged limit), and
  conditional overshoot (cost of chasing after a miss).
- Combine with public spread figures for a bounded estimate.

Decision rule: recommend changing src/execution order type ONLY if the
bounded estimate of savings exceeds the bounded estimate of miss cost by
> 2 bps/yr at portfolio level; otherwise recommend keeping market orders
(possibly with a wide protective limit for fat-finger protection only).

## Config budget

Engineering measurements (gap stats, correlations, liquidity, gap-miss
frequencies) are exempt. Ledger runs planned: R1/R2/R3 full-window 0 bps
(3, measurement), R2 dev-window U0/U1/U2/U3 at 10 & 20 bps (4 configs, 8
runs), 1-day-delay variants of R2/R3 at 0 bps (2, measurement). Total
distinct configs logged: 9. No additional configs will be evaluated.

## What kills each idea
- Q1: |delta| < 10 bps/yr -> "immaterial, keep open fill".
- Q2: Sharpe drop > 0.05 dev or corr < 0.95 -> no swap.
- Q3: savings-minus-miss-cost <= 2 bps/yr -> keep market orders.
