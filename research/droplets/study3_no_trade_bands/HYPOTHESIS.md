# STUDY 3 — No-trade bands / turnover reduction

Date: 2026-07-02. Author: study3 droplet (Claude research subagent).
Engine: `src/backtest/ledger.py::run_ledger_backtest` (daily_ledger_v1), cash sleeve SHV.
Costs: every config reported at BOTH 10 bps/side and 20 bps/side (cost levels are
not separate configs).

## Hypothesis

Most of the live strategies' ~12x/yr turnover is rank-churn noise (asset #3/#4
swapping, small inverse-vol weight updates, vol-target wiggles) that pays spread
without capturing signal. No-trade bands (rank hysteresis, per-position drift
bands) should cut turnover 30-60% while losing little gross signal, so NET Sharpe
should improve at both cost levels. Expected saving: two-sleeve baseline cost drag
is ~48 bps/yr at 10 bps/side; a 40-60% turnover cut ≈ 20-30 bps/yr saved at
10 bps/side (double at 20). Kill scenario: if the skipped trades WERE signal
(momentum decays fast at 63d horizon), gross CAGR drops more than costs saved and
net Sharpe falls — then the answer is "do not band" and we report the null.

## Rules under study (fixed ex-ante)

- **Rule A — 63d top-3 inverse-vol rotation.** Universe fixed ex-ante:
  [SOXX, QQQ, XLK, VGT, IGV, XLE, GLD, SHY]. At each month-end (last trading day
  of month on the union calendar of the universe): rank by trailing 63-trading-day
  total return (adj_close, data <= as_of); take top 3 (assets with < 64 bars of
  history are ineligible); weight the 3 by inverse 63d realized vol
  (daily std * sqrt(252)), normalized to sum 1. Trade at next day's open
  (ledger convention). No SPY gate — the rotation rule itself is the object.
- **Rule B — two-sleeve.** `src/strategy/sleeves.py::two_sleeve_weights`
  verbatim (0.6 TSMOM + 0.4 GEM, 10% vol target), month-end schedule via
  `build_schedule`.

Drift accounting for band decisions: at decision date d, "current" weights are the
last emitted target drifted by each ticker's adj_close return from the previous
decision date's close to d's close (one-overnight approximation of the ledger's
open-fill drift; error is negligible vs 2-10 point bands). Emitting the drifted
weight for an unbanded leg produces ~zero traded notional in the engine, so
"hold at drift" is free by construction.

## Pre-registered configs (EXACTLY these 10, incl. the 2 no-band baselines)

| id | rule | design |
|----|------|--------|
| A0 | A | baseline: full rebalance to target every month-end |
| A1 | A | rank hysteresis m=1: a held asset stays while its momentum rank <= 4; ejected only below; vacated slots filled by best-ranked non-held; inverse-vol weights recomputed monthly over the resulting 3 |
| A2 | A | rank hysteresis m=2: eject only when rank > 5 |
| A3 | A | per-position drift band X=5 wt-pts: trade only legs with abs(target - drifted) > 0.05, others held at drift; month skipped entirely if no leg breaches |
| A4 | A | A2 hysteresis (m=2) + A3 band (X=0.05) combined |
| B0 | B | baseline: two_sleeve_weights, full rebalance every month-end |
| B1 | B | per-position drift band X=2 wt-pts |
| B2 | B | per-position drift band X=5 wt-pts |
| B3 | B | per-position drift band X=10 wt-pts |
| B4 | B | portfolio min-trade: skip the month unless half-turnover 0.5*sum(abs(target-drifted)) > 0.10 |

Per-position band mixing: w_emit[t] = target[t] if abs(dev)>X else drifted[t];
if sum(w_emit) > 1 scale all legs by 1/sum; residual < 1 goes to SHV via the
engine. Hysteresis state = the 3 held tickers; band state = last emitted weights.

## Windows

- Dev (design/tune): Rule A 2005-01-01..2017-12-31; Rule B 2007-01-01..2017-12-31
  (SHV/DBC listing — matches the BASELINES.md two_sleeve start).
- Validation (ONE look): 2018-01-01..latest, run ONLY on the single winning
  config per rule (plus its no-band baseline as reference), reported verbatim.

## Decision rule (pre-registered, no post-hoc edits)

For each rule, a band config QUALIFIES iff on the dev window:
1. net Sharpe(config) >= net Sharpe(that rule's baseline) at 10 bps/side, AND
2. net Sharpe(config) >= net Sharpe(baseline) at 20 bps/side, AND
3. annual turnover is reduced by >= 20% vs baseline.

Winner per rule = qualifying config with the highest mean of (net Sharpe@10,
net Sharpe@20); tie broken by larger turnover reduction. If NO config qualifies
for a rule, the result is "do not band this rule" (null) and no validation look
is spent on it. The recommendation ships the winner's exact parameters, the
measured cost-drag saving (bps/yr) at both cost levels, and the drop-in function
signature for the signal->execution path.

## Metrics reported per config (dev)

net Sharpe, CAGR, MaxDD, ann_turnover (x/yr), ann_cost_drag (bps/yr) — at 10 and
20 bps/side. All from run_ledger_backtest. Every config logged to trials.csv.
