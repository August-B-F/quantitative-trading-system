# Study 9 — Real intraday data from Alpaca (measurement study, pre-registered)

Date: 2026-07-02 (written BEFORE any bar was fetched or analyzed).
Owner: research/droplets/study9_intraday/ (Workstream B, owner-authorized
expansion of the quarterly spec budget).
Type: **measurement study**, not a strategy spec. No backtest configs are
tuned here; the deliverable is measured execution-cost numbers that replace
the folklore estimates currently baked into our 10/20 bps/side assumptions,
plus a go/kill input for two recorded leads (`cls` pre-close orders, `opg`
open-auction orders — see results/DROPLET_LEDGER.md "LEADS").

## Data source and honesty constraints (declared ex-ante)

- Alpaca market-data API (data.alpaca.markets), free plan = **IEX feed**.
  IEX is ~2-3% of consolidated volume; opening/closing auction prints
  occur on the primary exchange and are **absent** from IEX trade data.
  Every measurement below is therefore a *proxy* measured on IEX prints,
  compared against the official consolidated open/close in our parquets
  (data/clean/prices/*.parquet). If IEX coverage makes a measurement
  meaningless (e.g. zero bars in the window for SHY), we report that as a
  data-quality null, not a number.
- GET requests only, to market-data endpoints only. Never any order or
  account-mutating endpoint.
- Symbols (fixed ex-ante): SOXX, QQQ, XLE, GLD, SHY, SPY.
  (Four candidate-universe names spanning liquidity tiers + the gate
  ticker SPY + the park asset SHY.)
- Window: as far back as the IEX feed allows (probe first, document depth).
- All timestamps converted to America/New_York. A minute bar timestamped
  09:30 covers trades 09:30:00-09:30:59.
  "Minutes 1-5" = bars stamped 09:30..09:34. "Last 10 minutes" = bars
  stamped 15:50..15:59. "15:45 decision price" = close of the 15:44 bar
  (i.e. the last price a 15:45 signal computation could have seen).

## What we measure and the decision thresholds (all declared ex-ante)

### (a) Effective open execution
Per symbol/day: `open_slip_bps = 1e4 * (VWAP(bars 09:30..09:34) / official_open - 1)`,
sign flipped for sells is symmetric, so we report the signed drift and the
absolute cost `|open_slip_bps|` separately. Also per-minute VWAP vs official
open for minutes 0..9 to see the decay profile.
- **Decision**: the executor currently submits market orders at/just after
  the open and the ledger assumes the official auction open. If the mean
  *absolute* gap for minutes 1-5 exceeds **10 bps** on the liquid names
  (SPY/QQQ/GLD) or **20 bps** on SOXX/XLE, the backtest's open assumption
  is materially optimistic and we must either (i) recommend `opg` auction
  orders (fidelity fix) or (ii) add the measured gap to the cost model.
- **Delay question**: if the per-minute spread proxy (below) at minute 5+
  is lower than minute 0 by more than the mean signed drift over minutes
  0-5 (i.e. waiting saves more in spread than it costs in drift), verdict
  = "delay N minutes"; otherwise "stay immediate".

### (b) Spread / trading-cost proxy, open vs close
Per symbol/day: mean over the window of `1e4 * (high - low) / close` on
1-min bars, for window A = 09:30..09:34 and window B = 15:45..15:54.
Supplement (recent days only, if the free plan serves historical quotes):
actual IEX top-of-book bid/ask spread sampled in both windows.
- **Decision threshold**: if window B's proxy is lower than window A's by
  **>= 25%** consistently (median across days, all 6 symbols agreeing in
  direction), the afternoon is declared the cheaper execution window and
  this becomes a supporting argument for the `cls` lead; otherwise the
  "open is expensive" folklore is declared unsupported for our names.

### (c) Close drift — feasibility input for the `cls` lead
Per symbol/day:
- `close_drift_bps = 1e4 * (official_close / close(15:44 bar) - 1)` —
  how far the price moves between the 15:45 signal snapshot and the
  official close (the fill a `cls` order receives). Report mean, median
  of |.|, p90 of |.|.
- `last10_vwap_gap_bps = 1e4 * (VWAP(15:50..15:59) / official_close - 1)`
  — the cost of working the close manually instead of the auction.
- **Rank-flip test** (ties to the shadow study the ledger says the lead
  needs; study15 does not exist in this tree, so this is the first cut):
  recompute the blend_126_252 cross-sectional ranks over the candidate
  universe [SOXX, QQQ, XLK, VGT, IGV, XLE, GLD, SHY] on each day in the
  intraday sample, once with official closes and once with the 15:44
  proxy close substituted for the last day (for the symbols we have;
  XLK/VGT/IGV fall back to official close — noted as a limitation, their
  15-min move is highly correlated with QQQ's so flips are *under*counted
  slightly). Report the fraction of days on which the top-3 set differs,
  and the same fraction restricted to month-end +0/+5/+10/+15 decision
  days. Gate flips (SPY vs its SMA200) counted the same way.
- **Decision thresholds**: the `cls` lead SURVIVES this feasibility check
  if median |close_drift_bps| <= **15 bps** on the rotation legs AND the
  top-3 flip rate on decision days is <= **10%**. It is KILLED here if
  the flip rate exceeds **20%** (the claimed +46-50 bps/yr cannot survive
  re-deciding 1-in-5 rebalances on stale ranks). Between 10-20%: verdict
  "needs the full shadow study before any spec".

## Budget

This is a measurement study: no strategy configs are evaluated, so the
<=10-config signal budget is untouched. Every measurement row still goes
to trials.csv with engine=daily_ledger_v1 only where the ledger engine is
actually used (rank-flip uses raw parquet closes, noted as source=
alpaca_iex+parquet). Notes column carries "owner-authorized batch".

## Kill criteria for the study itself

If the IEX feed serves < 1 year of minute history, or > 20% of days are
missing the 09:30..09:34 window for the liquid names, the open-execution
measurement is declared unmeasurable on free data and we say so.
