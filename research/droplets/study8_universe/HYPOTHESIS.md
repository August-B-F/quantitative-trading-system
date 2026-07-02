# STUDY 8 — Universe legitimacy of blend_126_252 (frozen-rule EVALUATION)

Date: 2026-07-02. Droplet: `research/droplets/study8_universe/`.
Engine: `src/backtest/ledger.py::run_ledger_backtest` (daily_ledger_v1).
Written BEFORE any backtest of this study was run (CONSTITUTION rule 1).
This batch runs under an explicit OWNER-AUTHORIZED expansion of the
quarterly spec budget (noted in every trials.csv row).

## Question

The live universe [SOXX,QQQ,XLK,VGT,IGV,XLE,GLD,SHY] was assembled in 2026
AFTER 15 years of tech dominance (STRATEGY_WEAKNESSES.md admits it). If the
blend_126_252 edge exists ONLY on that universe, it is hindsight beta
wearing a momentum costume. This study applies the frozen blend chassis
VERBATIM to ex-ante universes. It is an EVALUATION of a frozen rule, not
tuning: zero parameter changes, no selection among configs, no adoption
decision rides on any number here except the universe-robustness verdict.

## Frozen chassis (identical for every universe — nothing varies)

Exactly the adopted candidate (src/strategy/rotation.py,
configs/strategies/candidate_blend_rotation.yaml; study4 harness
conventions so U1 ties out to the study4 ledger numbers):

- score = mean of cross-sectional ranks (ascending, average ties) of 126d
  and 252d trailing total returns (adj_close, data <= decision date).
- top-3 by score, inverse-63d-realized-vol weighted (annualized, ddof=1).
- Gate: SPY adj_close <= SMA200(SPY adj_close) at decision -> {SHY: 1.0}.
- Monthly decision at the last trading day of each month on the
  INTERSECTION calendar of universe + SPY; fill next open; cash SHV.
- Common-start gate (study4 convention, MIN_BARS = 274 = 252+21+1): no
  weights until EVERY universe ticker + SPY has >= 274 bars, so each
  universe has one well-defined start.
- Costs: 10 AND 20 bps per side. Interpretation rule binds at 10 bps.
- Single-date month-end schedules (offset 0) for ALL universes and ALL
  baselines: study 2 says never compare candidates on different rebalance
  days; all runs here share the same decision-day convention, so RELATIVE
  comparisons are fair. Absolute levels carry ~+0.15-0.18 Sharpe of
  month-end date luck (study 2) — noted, irrelevant to the comparison.

## Universes (fixed ex-ante; data availability checked BEFORE this file,
## no return was looked at)

Adaptation rule, declared now: a listed ticker enters its universe iff its
parquet exists in data/clean/prices/ AND its first bar is <= 2006-12-31
(so the common-start gate leaves a meaningful dev window). Applying it:
XLY parquet is MISSING (vendor set has no XLY); XLRE first bar 2015-10-08
fails the history rule. Both exclusions are data-driven, decided here,
before any backtest.

- **U1 incumbent (8):** SOXX, QQQ, XLK, VGT, IGV, XLE, GLD, SHY
- **U2 ex-ante sectors (10):** XLB, XLE, XLF, XLI, XLK, XLP, XLU, XLV
  (8 of the 9 1998-vintage SPDR sectors; XLY missing) + GLD + SHY
- **U3 ex-ante cross-asset (10):** SPY, QQQ, IWM, EFA, EEM, VNQ, GLD,
  DBC, TLT, SHY (DBC first bar 2006-02-06 -> U3 common start ~2007-03)
- **U4 incumbent minus semis (7):** QQQ, XLK, VGT, IGV, XLE, GLD, SHY

SHY is inside every rank pool (as in U1). top_n stays 3 everywhere.

## Baselines (per-universe reference, not tuned)

Each universe's own gate-only baseline: 100% SPY when SPY adj_close >
SMA200(SPY adj_close) at month-end decision, else 100% SHY; same
common-start gate on the SAME universe's tickers (so start dates match),
same calendar, fill, engine, costs. This is the SPY/SMA200-equivalent of
the candidate's own gate (adj_close convention, rotation.py). The official
BASELINES.md spy_sma200 rows (net Sharpe 0.83 full window @10bps) are also
reported for context.

## Windows

- DEV: schedules built from 2005-01-01, ledger end 2017-12-31.
- FULL: same schedules, ledger end = latest (2026-06-30/07-01).
Both windows are allowed here because this is an evaluation of a frozen
rule (owner-authorized); no parameter may change in response to anything
measured, and nothing here spends the candidate's validation look (the
2018+ look was already spent by study4).

## Interpretation rule (binding, declared now, verbatim)

The candidate's edge is **universe-robust** iff U2 AND U3 each beat their
OWN gate-only baseline on net Sharpe at 10 bps over BOTH the dev window
and the full window (four comparisons, all must pass). If the edge exists
only on U1, the finding is stated plainly: the incumbent universe is
hindsight-selected and the relaunch candidate's edge is not
universe-robust. No middle verdict may be invented after seeing numbers;
partial passes are reported as NOT universe-robust with the failing cells
named.

## Pre-declared decomposition metrics (diagnostics, no adoption decision)

1. U1 vs U4 deltas (Sharpe/CAGR/MaxDD, both windows, both costs): the
   semis-leg contribution.
2. U1 average decision-level target weight by bucket over risk-on months
   (semis = SOXX; other tech = QQQ,XLK,VGT,IGV; energy = XLE; gold = GLD;
   defensive = SHY), plus top-3 selection frequency per ticker, plus
   average daily ledger weight per ticker.
3. Same bucket table for U2 (sectors) for contrast.

## Expectations (stated before running)

- U1 will show the best absolute numbers — that is partly WHY it was
  chosen in 2026 and proves nothing by itself.
- Honest prior: sector momentum (U2) and cross-asset momentum (U3) are
  real but weaker effects in the literature; a plausible outcome is
  U2/U3 beating their gate baselines by a small margin on the full
  window but not on both windows. If U2/U3 fail everywhere the verdict
  is that the chassis has no demonstrated edge beyond its universe.
- U1 minus U4 expected material (SOXX is the highest-octane leg); if U4
  ~= U1 the semis story is overrated and concentration risk is lower
  than feared.

## Runs and logging (all logged, none hidden)

4 universes x 2 windows x 2 costs = 16 strategy runs; 4 x 2 x 2 = 16
gate-baseline runs. Every run is one row in
`research/droplets/study8_universe/trials.csv` (schema:
trial_id,date,name,engine,window,sharpe,cagr,max_dd,n_trials_represented,
source,notes; date=2026-07-02, engine=daily_ledger_v1, notes include
"owner-authorized-budget-expansion" and the cost level). No config
selection occurs, so no validation look is spent by this study.

## Deliverable

The verdict under the interpretation rule + a recommended EX-ANTE
universe rule for all future specs, written as a rule (e.g. "all SPDR
sectors + broad asset classes with >= 15y history"), never as a list
picked by performance.
