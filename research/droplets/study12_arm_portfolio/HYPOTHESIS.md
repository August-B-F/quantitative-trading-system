# STUDY 12 — Portfolio of arms (allocation study, no new signals)

Date: 2026-07-02. Author: study12 droplet (Workstream E). Engine:
`src/backtest/ledger.py` (daily_ledger_v1), monthly month-end decisions
filled at next open, cash sleeve SHV, costs reported at 10 AND 20
bps/side. Decision rule evaluated at 10 bps.

Written BEFORE any backtest of this study was run (CONSTITUTION rule 1).
This batch runs under an explicit OWNER-AUTHORIZED expansion of the
quarterly spec budget (noted in trials.csv).

## Question

The race frames the three arms as competitors; capital sees them as
diversifiers. Does a FIXED-WEIGHT book of
{blend_126_252 (single-tranche month-end, for comparability), GEM,
SPY/SMA200} beat the best single arm on Sharpe AND MaxDD, net of costs?

## Arms (frozen specs, verbatim from existing code — no new signals)

- **BLEND** = `src/strategy/rotation.py::blend_rotation_weights` exactly:
  mean of 126d/252d cross-sectional ranks over
  [SOXX,QQQ,XLK,VGT,IGV,XLE,GLD,SHY], top-3 inverse-63d-vol,
  SPY/SMA200 (adj_close) gate to SHY. SINGLE-TRANCHE month-end (the
  4-tranche book is the honest live spec; single-tranche is used here so
  all three arms share one decision date — conclusions inherit ~+0.15-0.18
  Sharpe of month-end date luck per study 2 and are haircut accordingly).
- **GEM** = `src/strategy/sleeves.py::gem_weights` exactly: Antonacci
  12-1, SPY/EFA winner vs SHV hurdle, else AGG.
- **SMA** = SPY/SMA200 exactly as `scripts/run_baselines.py::
  _sma_trend_weights`: SPY iff close > 200d SMA of close at decision,
  else SHY.

## Fixed ex-ante

- Tickers: union of arm needs = [SOXX,QQQ,XLK,VGT,IGV,XLE,GLD,SHY,SPY,
  EFA,AGG,SHV]. Cash sleeve SHV. No universe changes.
- Common calendar: INTERSECTION of all 12 tickers' trading calendars.
  Decision dates: last trading day of each month on that calendar.
  Common window starts at the first month-end where ALL THREE arms
  return valid weights (expected 2007-01-31, set by SHV's listing via
  the intersection calendar; GEM returns None before its history fills).
- Dev window: decisions from common start through 2017-12-31; NAV
  simulated to 2017-12-31. Validation: 2018-01-01..latest — ONE look,
  spent only on the single FINAL book if the dev decision rule passes,
  with the last pre-2018 decision carried forward (engine convention).
- Each arm's NAV, and each book, runs through `run_ledger_backtest` at
  10 and 20 bps/side.

## Pre-declared combination rules (exactly three books, NO optimization)

Book weights are fractions of one account, held fixed; the book is
rebalanced back to its fixed arm fractions at every month-end decision.

1. **EW**: 1/3 BLEND, 1/3 GEM, 1/3 SMA.
2. **IVOL**: weights proportional to 1 / (annualized daily vol of the
   arm's DEV-window NAV at 10 bps), normalized. Dev-window vol (not
   full-window) so the weights are implementable ex-ante at 2018-01-01
   — "inverse-full-window-vol" computed on 2018+ data would be
   look-ahead. Weights computed once, frozen, stated in RESULTS.
3. **CONV** (conviction-weighted by validation evidence): 50% BLEND /
   25% GEM / 25% SMA.

Nothing else will be combined. No weight search, no grid.

## Cost / netting assumption (stated per the mandate)

Each book is simulated as ONE ledger schedule: at each decision date d,
target ticker weight = sum over arms of (arm fraction x that arm's
ticker weight at d). The ledger engine trades from the DRIFTED book to
that netted target, so overlapping tickers (SPY appears in GEM and SMA;
SHY in BLEND and SMA) net automatically — this models the book funded
in a single account with one next-open execution. For the
separate-accounts alternative we also report the UN-NETTED cost drag =
sum of arm-fraction-weighted arm cost drags; the difference is the
measured netting benefit. No cross-account netting is assumed anywhere.

## Diagnostics (exempt, descriptive — no tuning)

- D1: arm correlation matrix of daily and monthly NAV returns at 10 bps,
  dev window (and full window — the arms are already-published
  baselines/candidate, so their 2018+ NAVs are not a new look).
- D2: per-book netted vs un-netted annualized cost drag.
- D3: arm re-windows on the common window (references R1-R3, exempt from
  budget like study 7's R0/D0).

## Configs charged to the budget: 3 (EW, IVOL, CONV; each reported at
both cost levels, one config per book per study-4 convention).

## Ex-ante expectations

- Daily arm correlations 0.45-0.75 (all long US-equity beta; BLEND and
  SMA share the identical gate asset and similar gate timing); monthly
  correlations similar or higher. Diversification benefit therefore
  limited.
- BLEND dev Sharpe ~1.0 vs GEM ~0.5-0.7 and SMA ~0.8-0.9: mixing in
  lower-Sharpe arms at 0.5-0.75 correlation most likely DILUTES Sharpe.
  Expected ordering: CONV closest to BLEND, EW lowest.
- Books may still cut MaxDD/vol if arm drawdowns are imperfectly
  synchronized (2022 hurt gate strategies at different depths). A
  Sharpe-AND-MaxDD win is possible but not expected; an honest null
  ("fund blend alone") is the likelier outcome.

## Decision rule (binding, verbatim, evaluated at 10 bps on dev window)

References (exempt): S_blend = BLEND arm dev Sharpe on the common
window; DD_blend = BLEND arm dev MaxDD; likewise for GEM and SMA.
"Best single arm" = the arm with the highest dev Sharpe at 10 bps
(expected: BLEND).

FINAL = the book among {EW, IVOL, CONV} with the highest dev net Sharpe
at 10 bps; tie-break shallower dev MaxDD.

PASS iff: FINAL dev Sharpe >= best-single-arm dev Sharpe AND FINAL dev
MaxDD >= best-single-arm dev MaxDD (i.e., no deeper) AND both
conditions also hold at 20 bps.

- PASS -> exactly one validation run of FINAL on 2018-01-01..latest at
  10 and 20 bps, reported verbatim, no re-picks. Recommend funding as a
  book iff FINAL validation Sharpe >= BLEND's published single-tranche
  validation Sharpe (0.822 @10bps / 0.771 @20bps) AND validation MaxDD
  no deeper than BLEND's (-17.04% / -18.03%).
- FAIL -> verdict: "no fixed-weight book beats the best arm; race arms
  separately AND fund the best arm alone; books add dilution, not
  diversification." No validation look is spent on any book.

What kills the idea: no book satisfies the PASS condition. Partial
outcomes (e.g., MaxDD win with Sharpe loss) are reported honestly as
context for the account-structure recommendation but do NOT trigger a
validation look.

All configs and references logged to
research/droplets/study12_arm_portfolio/trials.csv (schema:
trial_id,date,name,engine,window,sharpe,cagr,max_dd,
n_trials_represented,source,notes; date=2026-07-02,
engine=daily_ledger_v1; notes flag the OWNER-AUTHORIZED budget
expansion).
