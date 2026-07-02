# STUDY 10 — Structural-flow calendar specs (pre-registered)

Date: 2026-07-02, written BEFORE any backtest of these specs was run.
Batch runs under an explicit OWNER-AUTHORIZED expansion of the quarterly
spec budget (noted in trials.csv). Engine: `src/backtest/ledger.py`
(`run_ledger_backtest` / `load_prices`), daily_ledger_v1. These are
calendar rules with ZERO tunable parameters — the full-window run is the
test; the two halves are the robustness split. No dev/validation
distinction applies. Nothing in this file may be edited after results
exist (CONSTITUTION rules 1, 8).

## Shared terms

- Universe, fixed ex-ante: Spec 1 & 3 trade SPY with SHV as the cash
  sleeve; Spec 2 trades QQQ only. No other tickers.
- Windows: FULL = 2005-01-01..2026-06-30 (SPY data end). HALF1 =
  2005-01-01..2015-12-31. HALF2 = 2016-01-01..2026-06-30.
- **Deploy bar (all three specs): net Sharpe > 0.4 in BOTH halves at
  the spec's realistic cost, else DEAD.** No excuses tier; the bar is
  not "beats SPY", it is the pre-declared absolute bar above, because
  these are low-exposure satellite overlays, not core replacements.
- Engine mapping, declared up front: the ledger engine fills a decision
  dated at the close of day d at the NEXT trading day's OPEN, using
  dividend-consistent `adj_open = open * adj_close / close`. The
  literature specs are close-to-close; the implementable version
  therefore shifts each boundary by one overnight (enter at next open,
  exit at next open). This is the honest, executable version and is the
  one being tested. Gross numbers = same schedule at `cost_bps=0`.
- SHV lists 2007-01-11; before that the cash sleeve earns 0 (engine
  semantics). SHV legs are charged the same per-side cost as SPY legs
  by the engine (conservative vs. an SPY-only cost assumption).
- Per-spec cost realism is stated below. Per batch instructions, 10 and
  20 bps/side sensitivity runs are also logged for each spec (same
  config re-costed, not new trials).
- Per-trade edge: per-episode fill-to-fill adjusted-open return
  (entry-fill open -> exit-fill open), reported gross in bps with
  t-stat = mean/std*sqrt(n); Spec 2's episode is one overnight leg.

## Spec 1 — TURN-OF-MONTH (TOM)

Literature: Lakonishok & Smidt (1988); McConnell & Xu (2008): US equity
returns concentrate in the turn-of-month window; mechanism is
institutional flow (month-end pension/401k contributions, fund
rebalancing), not forecasting.

Rule (verbatim, zero parameters): long SPY from the CLOSE of T-4 (the
4th-to-last trading day of each month) to the CLOSE of T+3 (the 3rd
trading day of the next month); SHV otherwise.

Implementation: decision {SPY:1.0} dated T-4, decision {all cash} dated
T+3; engine fills at the opens of T-3 and T+4 respectively. ~12
episodes/yr, ~24 switch fills/yr, each switch trades ~200% notional
(SPY leg + SHV leg). Realistic cost: **2 bps/side** (SPY/SHV are the
two most liquid ends of the book) => ~96 bps/yr engine cost drag.
Expected exposure ~6/21 = ~29%.

Deploy: net Sharpe > 0.4 in BOTH halves at 2 bps/side. Kill otherwise.

## Spec 2 — OVERNIGHT (QQQ close -> next open)

Literature: Cooper, Cliff & Gulen (2008); Lou, Polk & Skouras (2019):
virtually all of the equity premium in major index ETFs accrues
overnight (close to open); mechanism is order-flow imbalance at the
open / institutional intraday supply, not forecasting.

Rule (verbatim, zero parameters): long QQQ from every CLOSE to the next
OPEN, flat intraday, every trading day.

Implementation: this leg structure (enter at close, exit at next open)
cannot be expressed as a next-open-fill weight schedule, so the daily
NAV ledger is compounded directly from the engine's own return
decomposition: overnight return = adj_open_t / adj_close_{t-1} - 1
with `adj_open = open * adj_close / close`, exactly the ledger's
`_build_return_frames` convention (the function itself is called to
produce the series). NAV_t = NAV_{t-1} * (1 + overnight_t) *
(1 - 2*c/1e4) on every held night (one round trip per day, ~250/yr).

Cost realism DECIDES this spec: report gross AND net at **1 and 2
bps/side** (~250 and ~500 bps/yr of cost). The realistic cost for a
retail-executable MOC-buy/MOO-sell pair is taken as **2 bps/side**
(primary); 1 bps/side is the optimistic bound.

Deploy: net Sharpe > 0.4 in BOTH halves at 2 bps/side (primary). If it
passes only at 1 bps/side it is DEAD as speced but recorded as a lead.

## Spec 3 — PRE-FOMC DRIFT

Literature: Lucca & Moench (2015): large average excess returns accrue
in the ~24h before SCHEDULED FOMC announcements; mechanism is
resolution of monetary-policy uncertainty / dealer positioning, not
forecasting.

Rule (verbatim, zero parameters): long SPY from the CLOSE 2 trading
days before each scheduled FOMC decision day to the CLOSE of the
decision day; SHV otherwise. Calendar source:
`data/clean/calendar/events.parquet`, `is_fomc_day == 1`.

Ex-ante exclusion, declared before running: the calendar flags 4 known
UNSCHEDULED intermeeting decisions (2008-01-22, 2008-10-08, 2020-03-03,
2020-03-16, per the public FOMC historical record — the years showing
10 and 9 flagged days). An emergency meeting's entry point (2 trading
days prior) is unknowable ex-ante, so these are excluded; the spec uses
scheduled meetings only (8/yr).

Implementation: decision {SPY:1.0} dated D-2 (close), decision {all
cash} dated D (close); engine fills at the opens of D-1 and D+1. ~8
episodes/yr, ~16 switch fills/yr. Realistic cost: **2 bps/side** =>
~64 bps/yr engine drag. Expected exposure ~16 days/yr = ~6%.

Deploy: net Sharpe > 0.4 in BOTH halves at 2 bps/side. Kill otherwise.

## Reporting

Per spec: gross and net CAGR, net Sharpe, net MaxDD, exposure fraction,
per-trade edge (bps, gross, fill-to-fill) with t-stat, for FULL, HALF1,
HALF2. Verdict per spec against the bar above. If any spec deploys:
sizing suggestion as a 5-10% satellite overlay and estimated
portfolio-level add. All evaluated configs logged to
`research/droplets/study10_calendar/trials.csv`.
