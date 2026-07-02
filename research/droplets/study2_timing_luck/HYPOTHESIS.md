# STUDY 2 — Rebalance timing luck & tranching (engineering measurement)

Date: 2026-07-02. Author droplet: study2_timing_luck.
Type: ENGINEERING MEASUREMENT — nothing is tuned, no offset will be "selected"
for deployment based on its performance. Full window allowed. Config budget
exempt (measurement grid declared below); every run still logged to trials.csv.

## Question

The old stress report claimed month-end is "load-bearing" (mid-month drops
Sharpe 1.50 -> 1.17). That is the classic rebalance-timing-luck signature
(Hoffstein/Newfound): the choice of rebalance day is a lottery and pinning the
lucky day is hidden selection bias. Measure the size of the lottery on two
UNTUNED reference rules, and measure how much of it tranching removes and what
it costs.

## Reference rules (fixed ex-ante, zero tuning)

R1. GEM — `src/strategy/sleeves.gem_weights` verbatim (SPY vs EFA, 12-1 mom,
    SHV hurdle, AGG fallback). Universe fixed by that file.
R2. ROT63 — 63-trading-day total-return momentum on the 8-ETF live universe
    [SOXX, QQQ, XLK, VGT, IGV, XLE, GLD, SHY]: take top-3 by 63d adj_close
    return, weight by inverse 63d realized vol (daily std * sqrt(252)),
    normalized. Tickers with < 64 bars of history at the decision date are
    excluded from ranking. No SMA gate, no hurdle — deliberately plain, to
    mirror the live strategies' rotation mechanics without their tuned parts.

Both rebalance monthly. Decision date for offset k = the k-th trading day
AFTER the last trading day of the month (k=0 = month-end itself), on the
intersection calendar of the rule's tickers. Signal is computed at the
decision date (the whole rebalance shifts — same rule, only the day moves).
Fill = next trading day's open (ledger engine convention).

## What will be measured (the exact grid)

1. TIMING-LUCK LOTTERY: for each rule, ledger backtest at offsets
   k = 0, 2, 4, 6, 8, 10, 12, 14, 16, 18 (10 offsets). Report per-offset
   CAGR / Sharpe / MaxDD and the distribution min / median / max / std.
   The spread IS the timing-luck magnitude.
2. TRANCHING: same rules split into
   - 2 tranches at offsets +0 / +10 (each 50% of capital), and
   - 4 tranches at offsets +0 / +5 / +10 / +15 (each 25%).
   Each tranche is an independent ledger run (own sub-account, no
   cross-tranche rebalancing); combined NAV = equal-weighted sum of tranche
   NAVs (exact for separate sub-accounts). This requires two extra offset
   runs per rule (k = 5, 15) which are measurement support, not candidates.
   Measure: (a) does the tranched Sharpe land near the median of the
   single-date distribution, (b) dispersion removed, (c) "expected regret
   avoided" = median minus 5th percentile of single-date CAGR (and Sharpe).
3. TRANCHING COST: combined annualized turnover and cost drag of the 4-tranche
   book vs the median single-date book, at 10 and 20 bps/side. Trade-count
   inflation stated separately (fixed costs ~zero at Alpaca; spread costs
   scale with notional, not trade count).

Engine: `src/backtest/ledger.py::run_ledger_backtest`, cash sleeve SHV,
costs reported at BOTH 10 and 20 bps/side.
Window: decisions from 2005-01-01 (first month-end each rule has history for)
through latest data (~2026-06-30). NAV window identical across offsets within
a rule so distributions are comparable.

## Expectations (stated before running)

- ROT63 (concentrated top-3 monthly rotation, ~high turnover) shows a
  material offset spread — order 0.1-0.3 Sharpe between best and worst
  offset, consistent with Hoffstein's published magnitudes for concentrated
  monthly rotation. GEM (rare switches) shows a smaller but nonzero spread.
- The 4-tranche portfolio lands near the single-date median Sharpe and cuts
  outcome dispersion by roughly the sqrt(N) ~ half or better.
- Tranching adds little total turnover (each tranche trades the same rule at
  1/N size), so the cost of tranching is near zero; the benefit is variance
  reduction around the true expected return, NOT added return.

## Decision rule (fixed now, no post-hoc edits)

- If for the live-like rule (ROT63) the single-date spread is material —
  (max - min) Sharpe >= 0.10 OR (median - p5) CAGR >= 0.75%/yr — AND the
  4-tranche book's extra cost drag is < 5 bps/yr at 10 bps/side, recommend
  4-tranche staggered rebalancing (+0/+5/+10/+15) for the relaunch
  candidates.
- If the spread is below both thresholds, or tranching costs >= 5 bps/yr
  extra, recommend "not worth it" with the numbers.
- KILL condition for the idea: ROT63 offset spread (max-min Sharpe) < 0.05
  => timing luck is immaterial here and tranching is pure complexity.

## What is and is not claimed

Tranching is claimed ONLY as variance reduction around the rule's true
expected return (diversification across the rebalance-date lottery). No
return improvement is claimed or expected. The month-end-vs-mid-month Sharpe
gap in the old stress report is treated as a draw from this lottery, not as
evidence month-end is special.

validation_look: N/A (engineering study; nothing tuned; no 2018+ single look
consumed).
