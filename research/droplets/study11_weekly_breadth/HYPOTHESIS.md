# HYPOTHESIS — Study 11: Weekly Cross-Sectional Breadth Spec (pre-registered)

Date: 2026-07-02. Droplet: `research/droplets/study11_weekly_breadth/`.
Engine: `src/backtest/ledger.py::run_ledger_backtest` (daily_ledger_v1).
Written BEFORE any backtest run. This spec runs under the OWNER-AUTHORIZED
expansion of the quarterly spec budget (noted in every trials.csv row).

## Object under study

The adopted monthly rotation makes ~12 low-breadth decisions/yr over 8 assets.
Grinold-Kahn: IR ≈ IC * sqrt(breadth) — the same per-decision edge spread over
more assets at faster cadence needs far less per-decision accuracy. Cheapest
honest test: weekly cross-sectional rotation over the liquid ETFs already on
disk. Weekly turnover makes COST the likely killer; turnover and cost drag are
first-class outputs.

## Universe (ex-ante, by rule — see `universe_survey.py`, rules U1-U5 frozen in
its header BEFORE it ran; no return data consulted)

U1 first bar <= 2010-01-04; U2 median close*volume over 2010-01-04..2017-12-29
>= $10M (threshold pre-declared); U3 exclude VIX products (_VIX, VIXY, UVXY)
and leveraged/inverse; U4 named twin pairs, keep higher median $vol member:
(SOXX,SMH)->SMH, (XLK,VGT)->XLK, (AGG,BND)->AGG, (VNQ,IYR)->IYR, (DBC,PDBC),
(GBTC,BITO); XBI and IBB both kept (different indexes/cap tilts, declared);
U5 SHV excluded (cash sleeve + hurdle asset).

The resulting 39 tickers (frozen):

AGG DBA DBC EEM EFA EWG EWJ EWZ FXE FXI FXY GDX GLD HYG IBB IEF IEI IWM IYR
LQD QQQ SHY SLV SMH SPY TIP TLT UNG USO UUP XBI XLB XLE XLF XLI XLP XLU XLV XLK

Survivorship caveat (declared): the universe is drawn from ETFs alive on disk
today — same limitation as every prior study in this repo.

## Fixed chassis (identical across all configs — never varied)

- Weekly decision calendar: last trading day of each calendar week (Friday, or
  earlier if holiday) on the union trading calendar of the 39 + SHV; fill at
  the next trading day's open (engine convention: Friday close -> Monday open).
- Common start: the first weekly decision date at which EVERY universe ticker
  and SHV has finite values for all leg returns (63, 126, 252 bars) and 63d
  vol. All configs share this calendar regardless of their own lookback needs
  (expected ~2011-01, since several tickers first-bar 2010-01-04).
- Biweekly cadence = every 2nd date of that same weekly calendar, starting at
  the first (indices 0, 2, 4, ...).
- Selection: top-N tickers by the config's blend rank score. Ties broken by
  descending score then ascending ticker symbol (deterministic).
- Weighting (fixed): inverse 63d realized vol (std of daily adj_close returns
  over the last 63 bars ending at the decision date, ddof=1; annualization
  cancels), normalized to sum 1.0 across the selected N.
- Gate (fixed): none. The absolute filter is the only risk-off.
- Absolute filter (when ON): selected ticker t is HELD iff
  mean over the config's legs L of [R_t(L) - R_SHV(L)] > 0, where
  R_x(L) = adj_close_x[d] / adj_close_x[d - L bars] - 1. Failing tickers'
  weights are dropped from the schedule; the ledger engine sweeps the
  remainder into cash_ticker=SHV, which trades at full cost like any ETF.
- A ticker with non-finite leg return or non-finite/zero vol at d is excluded
  from ranking that week (cannot occur after the common start by
  construction, but declared).
- All signals use adj_close data strictly <= decision date.
- Costs: 10 AND 20 bps per side. Cash sleeve SHV.
- Full re-weight at every decision (drift corrected back to target weights) —
  no-trade bands are DEAD per results/DROPLET_LEDGER.md and are not used.

## Signal definitions

For leg L: R_t(L) as above (skip = 0). Each leg's returns are ranked
cross-sectionally over the 39 tickers (ascending, method='average'); the
config score = equal-weight mean of the two leg ranks.
- blend_63_126:  legs (63, 0), (126, 0)
- blend_126_252: legs (126, 0), (252, 0)

## The 10 configs (frozen; config budget 10, all used)

| id | signal        | top-N | cadence  | abs filter |
|----|---------------|-------|----------|------------|
| A  | blend_126_252 | 8     | weekly   | on         |
| B  | blend_63_126  | 8     | weekly   | on         |
| C  | blend_126_252 | 5     | weekly   | on         |
| D  | blend_126_252 | 12    | weekly   | on         |
| E  | blend_126_252 | 8     | biweekly | on         |
| F  | blend_126_252 | 8     | weekly   | off        |
| G  | blend_63_126  | 5     | weekly   | on         |
| H  | blend_63_126  | 8     | biweekly | on         |
| I  | blend_126_252 | 12    | biweekly | on         |
| J  | blend_63_126  | 12    | weekly   | on         |

Design: A is the anchor (the adopted monthly signal moved to weekly breadth);
B/C/D/G/J map the signal x N surface at weekly; E/H/I probe biweekly as the
cost-mitigation lever; F isolates the absolute filter's contribution.

## Windows and data-split discipline

- DEV: 2010-01-01..2017-12-31 (effective start = common start, ~2011-01, per
  the universe constraint). All selection happens here. Ledger run:
  start = first decision date, end = 2017-12-31.
- VALIDATION: 2018-01-01..latest. Spent ONLY if the adoption bar below is
  met, on the single winner only, at 10 and 20 bps, reported verbatim. If the
  spec is killed on dev, the 2018+ look is NOT spent (holdout preserved).

## Decision rule (frozen — no post-hoc edits)

1. Run all 10 configs on DEV at 10 and 20 bps/side.
2. Winner W = argmax dev net Sharpe at 10 bps among the 10.
3. ADOPT iff BOTH: Sharpe_W(dev, 10 bps) >= 0.90 AND Sharpe_W(dev, 20 bps)
   >= 0.75. (It must beat monthly rotation decisively to justify ~4x the
   operational load.)
4. If adopted: ONE validation look 2018+ on W at both cost levels.
5. If killed: no validation look. Diagnosis of WHERE it died is pre-registered
   as: W is re-run once on DEV at 0 bps (source=diagnostic, cost-level probe of
   an existing config, NOT an adoption candidate). If Sharpe_W(dev, 0 bps)
   < 0.90 the signal itself is insufficient at this cadence/universe; if
   >= 0.90 but the net numbers miss, costs killed it and better execution
   (paid intraday data, MOC/OPG auctions) could in principle revive it.
6. Reference bars (context, not selection): spy_sma200 net Sharpe 0.83
   full-window (results/BASELINES.md); the adopted monthly blend dev Sharpe
   1.005/0.958 @10/20 bps on 2006-2017 (different window/universe — context
   only).

## Expectations (stated before running)

- Turnover: weekly full re-weight of a top-8-of-39 book -> expect 6-15x/yr,
  i.e. cost drag ~60-150 bps/yr at 10 bps and ~120-300 at 20 bps. Biweekly
  should roughly halve it.
- Inverse-63d-vol weighting over a mixed bond/equity/commodity universe
  concentrates hard into short-duration bonds (SHY/IEI/AGG vol is 5-20x lower
  than equity legs) whenever they crack the top-N -> the book will be
  defensive/low-vol much of the time; CAGR will look small, judge on Sharpe.
- Dev 2011-2017 is momentum-hostile (2011 crash, 2015-16 whipsaw). Prior:
  best dev Sharpe ~0.6-0.9 at 10 bps. I EXPECT this spec to fail the 0.90 bar
  — the value of the study is the measured verdict plus the signal-vs-cost
  attribution. The breadth thesis says otherwise; that is what we are testing.
- Kill condition (verbatim): Sharpe_W(dev,10) < 0.90 OR Sharpe_W(dev,20)
  < 0.75 -> KILLED, holdout unspent, attribution per rule 5.

## Logging

Every evaluated run (10 configs x 2 cost levels dev, <=1 diagnostic, <=2
validation) is one row in `research/droplets/study11_weekly_breadth/trials.csv`
(schema: trial_id,date,name,engine,window,sharpe,cagr,max_dd,
n_trials_represented,source,notes; date=2026-07-02, engine=daily_ledger_v1;
notes include cost level and "owner-authorized-budget-expansion").
