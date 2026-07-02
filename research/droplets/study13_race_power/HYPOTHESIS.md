# HYPOTHESIS — Study 13: Race decisiveness (power of the promotion rule) + SPA test

Date: 2026-07-02. Droplet: `research/droplets/study13_race_power/`.
Engine: `src/backtest/ledger.py::run_ledger_backtest` (daily_ledger_v1). Written BEFORE any run.
This batch runs under the OWNER-AUTHORIZED expansion of the quarterly spec budget
(noted in every trials.csv row). This study evaluates NO new strategy configs —
it measures the statistical power of the EVALUATION.md §4 decision rule and runs
the pre-existing frozen arms through the engine as inputs.

## Object under study

EVALUATION.md §4 promotes a candidate only on a "clear" edge: **>= 0.20 net Sharpe
over BOTH controls after 12 months**. Question: can 12 months of daily returns
distinguish a 0.20 Sharpe edge from zero at all? We estimate the promotion rule's
false-positive and false-negative rates by block bootstrap of the actual arm
returns, the minimum window for 80% power, and whether a PAIRED daily-difference
test (which differences away the shared beta) rescues decisiveness. Separately we
run Hansen's SPA test of the adopted candidate vs the two controls on the full
common history.

## Fixed inputs (ex-ante, never varied)

- Arms (frozen specs, zero degrees of freedom here):
  1. `blend_126_252` single-tranche month-end (src/strategy/rotation.py
     `blend_rotation_weights`, universe SOXX QQQ XLK VGT IGV XLE GLD SHY,
     SPY/SMA200 gate to SHY) — the candidate as raced per arm definition
     ("blend single-tranche" per the workstream brief).
  2. GEM dual momentum (src/strategy/sleeves.py `gem_weights`, 12-1, SPY/EFA
     vs SHV hurdle, fallback AGG) — permanent control.
  3. SPY/SMA200 trend (SPY when close > 200d SMA else SHY, month-end checks,
     identical to scripts/run_baselines.py `_sma_trend_weights`) — permanent control.
- Engine: run_ledger_backtest, cash sleeve SHV, next-open fills, monthly
  month-end decisions via `build_schedule` / rotation conventions.
- Costs: 10 bps/side PRIMARY, 20 bps/side CONFIRMATORY (both reported).
- Power window: 2018-01-01..latest (the validation era). SPA window: full
  common window (inner join of the three arms' daily NAV returns, expected
  ~2007-02..2026-07) per the brief.
- Daily returns: nav.pct_change().dropna(), inner-joined across arms on dates.

## Bootstrap design (frozen)

- Circular block bootstrap, block length 21 trading days, joint across arms
  (same block indices for all arms — preserves cross-arm correlation).
- Seed 13. B = 5000 reps for all 12-month quantities; B = 2000 for the
  window-length power curves.
- 12 months := 252 trading days; a window of M months := 21*M days.
- Sharpe := mean(daily)/std(daily,ddof=1)*sqrt(252), rf=0 (engine convention).

### Quantities (a)-(c), computed per control (GEM, SPY/SMA200) at each cost level

(a) Sampling std of the 12-month Sharpe of each arm (uncalibrated bootstrap),
    plus the std of the 12-month EDGE (blend Sharpe minus control Sharpe,
    jointly resampled) and the daily correlation blend-vs-control.

(b) Calibrated error rates of the literal promotion rule ("promote iff
    observed 12-month edge >= 0.20"):
    - H0 calibration: add the constant delta0 to the blend's daily returns
      such that its full-window Sharpe equals the control's (true edge = 0).
      FALSE-POSITIVE rate = P(observed edge >= 0.20 | H0).
    - H1 calibration: constant delta1 such that true edge = +0.20.
      FALSE-NEGATIVE rate = P(observed edge < 0.20 | H1). (At the exact design
      point this is ~50% by construction — reported honestly as the structural
      flaw of thresholding at the effect size itself.)

(c) Minimum window for 80% power against a true 0.20 edge, window grid
    M in {12, 24, 36, 60, 96, 120, 180, 240} months, three decision statistics:
    1. the literal rule (edge_hat >= 0.20);
    2. UNPAIRED-style Sharpe-difference test: reject H0 (edge <= 0) when
       edge_hat > the 95th percentile of the H0-calibrated bootstrap edge_hat
       at the same window (one-sided 5%);
    3. PAIRED test: statistic = annualized Sharpe of the daily DIFFERENCE
       series d_t = r_blend - r_control; critical value = 95th percentile of
       the same statistic under H0 calibration; power = fraction of H1 reps
       above it.
    Report the smallest grid M with power >= 0.80 per statistic (or "> 240m").

## SPA test (frozen)

`arch.bootstrap.SPA` (arch 8.0.0), losses = negative daily returns, benchmark =
each control in turn, model set = {blend_126_252}; circular block bootstrap,
block_size 21, reps 10000, seed 13. Window: full common window, 10 bps primary,
20 bps confirmatory. Report the consistent p-value (plus lower/upper) verbatim.
Note recorded ex-ante: with a single model, SPA reduces to a studentized
bootstrap test of mean loss difference — reported as such, no multiplicity
benefit claimed.

## Expectations (stated before running)

- SE of a 1-year Sharpe is ~sqrt((1+S^2/2)/1) ~= 1.0-1.2; with blend-control
  daily correlation ~0.7-0.9 the 12-month edge SD should land ~0.5-0.9.
  Hence FPR of the literal rule likely 35-45%, FNR ~50%: **12 months cannot
  resolve 0.20** — we expect to report the rule as statistically vacuous and
  propose the corrected rule (fidelity + drawdown + process compliance as the
  gate, Sharpe ordering as tiebreak; paired statistic for any numeric claim).
- Paired test should need a materially shorter window than the unpaired one
  (shared beta differences away), but plausibly still > 5 years at corr ~0.8.
- SPA p-values on the full window: expect NOT significant at 5% vs
  spy_sma200 (full-window Sharpes 0.83-0.9 vs 0.83 bar are close), possibly
  significant vs GEM (0.60). Reported verbatim either way.

## Deliverables and logging

- `power_boot.py` (analysis code), `power_results.csv` + `spa_results.csv`
  (machine-readable outputs), rows in `trials.csv` (schema per workstream:
  every ledger-engine run logged; engine=daily_ledger_v1, date=2026-07-02,
  source in {power_input, spa_input}; bootstrap/SPA summary rows logged with
  source in {power_analysis, spa_test} and n_trials_represented=1).
- Part 3 of the workstream (scripts/run_race_report.py + tests) embeds the
  measured Part-1 numbers as the power-corrected verdict language; it is
  reporting plumbing, not an experiment, and evaluates no configs.

## Decision rule for THIS study (what changes on which outcome)

- If FPR(12m) > 10% or FNR(12m) > 20% at 10 bps vs either control, the report
  language must say the 12-month Sharpe threshold is not decision-grade and
  the month-12 verdict must lean on fidelity/drawdown/process with Sharpe as
  tiebreak. (Given the ex-ante math we expect this branch.)
- The paired-test power curve is reported as the recommended numeric
  instrument regardless of outcome.
- No strategy adoption/rejection decision is taken from this study.
