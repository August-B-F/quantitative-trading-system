# HYPOTHESIS — Study 15: CLS auction execution — signal-flip viability

Date: 2026-07-02 (written BEFORE any experiment in this folder)
Droplet: study15_cls_flip
Workstream: H (CLS/OPG auction execution mode)
Budget note: this batch runs under an explicit OWNER-AUTHORIZED expansion of
the quarterly spec budget.
Type: ENGINEERING MEASUREMENT — no signal parameter is tuned and no config
will be selected from results; the full window 2005-01-01..2026-06-30 is
used for flip statistics and the stale-signal ledger bracket, mirroring the
exemption precedent in research/droplets/exec_timing_micro/HYPOTHESIS.md.
The frozen blend_126_252 spec (src/strategy/rotation.py) is used verbatim.

## Background — the lead being tested

DROPLET_LEDGER lead: decide pre-close (~15:45 ET) and fill AT the
decision-day closing auction via Alpaca `cls` orders, capturing the
overnight gap the strategy currently pays at next-open (~+46-50 bps/yr
estimated; top-1 leg t=0.98 — weak). Verified Alpaca constraints: `cls`
TIF cutoff 15:50 ET, market/limit only, WHOLE-SHARE qty only
(notional/fractional orders are `day` TIF only); `opg` cutoff 09:28 ET.
The risk: a signal computed at ~15:45 uses prices that are NOT the closing
prices — the top-3 selection or the SPY/SMA200 gate could flip between
15:45 and 16:00, making the auction fill act on a wrong pick.

## Hypothesis

The blend_126_252 ranks are built from 126d/252d trailing returns, so one
day of price movement rarely reorders the cross-section: I expect the
top-3 set computed at close[t-1] to match close[t] on >~90% of month-ends
and the gate to flip on only a small minority (it flips only when SPY sits
essentially ON its 200d SMA at a month-end). If the bars below hold, cls
execution is viable pending a live 15:45 shadow test; if they fail, the
overnight-gap lead is dead as designed.

## Method (exact, pre-committed)

- Calendar: intersection of adj_close indexes of the 8-ETF universe
  [SOXX,QQQ,XLK,VGT,IGV,XLE,GLD,SHY] + SPY, clipped to
  2005-01-01..2026-06-30. Decision dates: month-end trading days
  (offset 0), i.e. every month-end 2005..2026 with a prior trading day.
- At each decision date t with previous trading day t-1 on that calendar:
  * top3_true = top-3 tickers by blend score at t (sort_values descending,
    head(3), exactly as blend_rotation_weights does); top3_stale = same at
    t-1. Compared as SETS.
  * gate_true = gate_risk_off(prices, t); gate_stale = same at t-1.
  * w_true = blend_rotation_weights(prices, t); w_stale = same at t-1.
  * composition flip := (gate_true != gate_stale) OR (both risk-on AND
    top3_true != top3_stale). Inverse-vol weight micro-differences with the
    SAME composition are NOT flips.
- Report: % of month-ends where the top-3 set differs; % where the gate
  differs; % composition flips; and on composition-flip months the cost of
  acting on the stale pick = fwd 1-month (t -> next month-end, adj_close)
  return of w_true minus w_stale — mean, median, t-stat, and annualized
  drag = mean delta x flip frequency x 12. Last month-end (no fwd month)
  is excluded from the cost calc only.
- Secondary robustness (measurement, not a bar): the same flip statistics
  at tranche offsets +5/+10/+15, because the deployed candidate is the
  4-tranche book and each tranche decides on its own date.
- Ledger bracket (daily_ledger_v1, run_ledger_backtest, full window, cash
  SHV, costs 10 AND 20 bps/side): schedule_true = month-end decisions with
  weights from close[t] (the frozen spec) vs schedule_stale = SAME decision
  dates with weights computed at close[t-1]. The Sharpe/CAGR delta is the
  FULL cost of acting on one-day-stale signals at every month-end, an
  upper bound on 15-minute staleness. Fills stay next-open in BOTH runs
  (engine convention) so the bracket isolates signal staleness from fill
  timing. 4 ledger runs total; all logged to trials.csv.
- OVERSTATEMENT NOTE (pre-committed interpretation): the real information
  gap for cls execution is 15:45 -> 16:00 — the intraday drift over those
  15 minutes is a small fraction of a full close-to-close move (this study
  substitutes the full t-1 -> t move because we only have daily data). The
  t-1-vs-t flip rates therefore OVERSTATE the real flip risk and are read
  as an UPPER BOUND. This framing is fixed now, before results.

## Viability bar (pre-registered, verbatim from the workstream brief)

CLS execution is VIABLE iff, at month-end offset 0 over the full sample:
- the top-3 set is identical on >= 90% of month-ends, AND
- the gate decision flips on <= 2% of month-ends.

Kills the idea: either bar fails (even though the bars are computed on an
overstating proxy — failing an upper bound is not exoneration, but passing
it is strong evidence). If viable, the dormant AuctionExecutor may be
enabled by a future operator config ONLY AFTER a live shadow test
comparing the 15:45 signal to the actual close signal; nothing in this
study wires anything live.

## Config budget

Flip statistics = engineering measurement (exempt). Ledger runs: 2
schedules (true, stale) x 2 cost levels (10, 20 bps/side) = 4 runs, 2
distinct configs; all appended to trials.csv. No additional configs will
be evaluated regardless of results.
