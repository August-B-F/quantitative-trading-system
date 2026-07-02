# STUDY 7 — Two-sleeve respec (pre-registered signal spec #3)

Date: 2026-07-02. Author: study7 droplet. Engine: `src/backtest/ledger.py`
(daily_ledger_v1), monthly month-end decisions filled at next open, cash
sleeve SHV, costs reported at 10 AND 20 bps/side. Decision rule evaluated
at 10 bps.

Written BEFORE any backtest of this study was run (CONSTITUTION rule 1).

## Diagnosis being tested (from code reading + existing baselines.json only)

Current two_sleeve = 0.6*TSMOM(12m, long-only, inv-63d-vol) + 0.4*GEM(12-1,
SPY/EFA vs SHV else AGG), 10% vol target. Full-window net Sharpe 0.67 vs
spy_sma200 bar 0.83.

1. **The vol target is near-inert**: blend CAGR 6.12% ~= 0.6*4.45 + 0.4*8.78
   = 6.18% and blend vol 9.55% vs target 10%. Prediction: removing it
   changes Sharpe by <= ~0.03.
2. **The TSMOM sleeve is the weak leg** (Sharpe 0.51 full, 0.21 post-2018,
   60% of book). Two mechanisms:
   a. single 12m horizon -> stale signals / slow re-entry (2009, 2020) and
      2022-23 bond whipsaw. Fix candidates: 3/6/12m majority ensemble, or
      Faber 10m-SMA rule.
   b. unlevered inverse-vol weighting concentrates in duration (IEF/LQD at
      5-7% vol dominate), a low-return bond fund in the 2010s with no
      leverage to compensate. Fix candidate: equal weight across ON assets.
3. GEM fallback AGG is duration too; IEF explicit fallback is a minor knob.

## Fixed ex-ante

- Universe (never changes): TSMOM_UNIVERSE = [SPY, EFA, EEM, IEF, TLT, LQD,
  GLD, DBC, VNQ]; GEM risk legs SPY/EFA; GEM fallback AGG (IEF only in C9);
  cash SHV. Calendar tickers for build_schedule: TSMOM_UNIVERSE + {SHV, AGG}
  (identical for every config so all start the same month-end, 2007-01-31,
  set by SHV's listing).
- Dev window: build_schedule start 2005-01-01, end 2017-12-31. Validation:
  2018-01-01..latest — ONE look, only if the dev decision rule PASSES.
- Insufficient history for a signal window -> asset skipped (current
  behavior). SHV hurdle falls back to 0.0 when SHV history is short
  (current behavior).

## Knob definitions (exact)

- Trend rules (per TSMOM asset, data <= as_of, adj_close):
  - `T12` (current): 252-td total return > SHV same-window return.
  - `ENS`: horizons {63, 126, 252} td; one vote per horizon iff asset
    return > SHV same-window return; ON iff >= 2 votes. Asset requires
    >= 253 bars (same as T12) else skipped.
  - `FAB`: ON iff last adj_close > mean(last 210 adj_closes) (Faber 2007
    10-month SMA; no cash hurdle). Requires >= 210 bars else skipped.
- Weighting across ON assets: `IV` = inverse-63d-vol (current); `EW` = 1/N.
  No ON assets -> 100% SHV (current behavior).
- Vol target on the combined book (min(1, target/realized-63d), excess to
  SHV): `VT10` = 0.10 (current), `VT12` = 0.12, `NONE` = no scaling.
- `frac` = TSMOM sleeve fraction: 0.6 (current) or 0.7.
- `gemfb` = GEM fallback: AGG (current) or IEF.

## Pre-registered configs (budget: 10; all monthly, same universe)

Reference (existing baseline, re-windowed, NOT counted in budget):
- R0 = T12 / IV / VT10 / 0.6 / AGG  (the current two_sleeve, dev window)

| id  | trend | weight | vt   | frac | gemfb | tests |
|-----|-------|--------|------|------|-------|-------|
| C1  | T12   | IV     | NONE | 0.6  | AGG   | D1: vol target inert? |
| C2  | T12   | EW     | VT10 | 0.6  | AGG   | D2b: bond overweight |
| C3  | ENS   | IV     | VT10 | 0.6  | AGG   | D2a fix A: ensemble |
| C4  | FAB   | IV     | VT10 | 0.6  | AGG   | D2a fix B: Faber |
| C5  | ENS   | EW     | NONE | 0.6  | AGG   | main combo A |
| C6  | FAB   | EW     | NONE | 0.6  | AGG   | main combo B |
| C7  | ENS   | EW     | VT12 | 0.6  | AGG   | is a loose target worth it |
| C8  | ENS   | EW     | NONE | 0.7  | AGG   | sleeve tilt |
| C9  | ENS   | EW     | NONE | 0.6  | IEF   | fallback knob |
| C10 | adaptive assembly (deterministic rule below); NOT run if it duplicates R0 or C1..C9 |

C10 assembly rule (fixed now, applied mechanically to dev 10bps Sharpes):
trend* = trend of argmax{R0, C3, C4}; weight* = weight of argmax{R0, C2};
vt* = vt of argmax{R0, C1}, overridden to VT12 iff C7 > max(C5, C6);
frac* = 0.7 iff C8 > C5 else 0.6; gemfb* = IEF iff C9 > C5 else AGG.

Justification in advance: C1-C4 are one-knob ablations of the two diagnosed
mechanisms plus the vol-target check; C5/C6 are the full-fix combos under
each trend rule; C7-C9 are single-knob perturbations around the expected
winner C5; C10 catches a cross-combination the ablations select that isn't
already covered. No other configs will be run; no grid.

## Ex-ante expectations

- C1 within +/-0.03 Sharpe of R0 (else diagnosis 1 is wrong).
- C3, C4 > R0 by 0.05-0.15; C2 > R0 modestly with higher vol.
- C5/C6 best overall, dev Sharpe hoped 0.85-1.00. If C5 and C6 both fail
  to beat R0 by >= 0.10, the diagnosis is wrong and the idea dies.
- C7 slightly below C5 Sharpe with shallower DD; C8 helps only if the fixed
  TSMOM sleeve out-Sharpes GEM; C9 ~ C5.

## Decision rule (binding, verbatim, evaluated at 10 bps on dev window)

Reference numbers measured once in Step-1 diagnostics (existing baselines
re-windowed to dev, exempt from budget):
- S_ts  = dev net Sharpe of R0 (current two_sleeve)
- S_bar = dev net Sharpe of spy_sma200 (rules exactly as
  scripts/run_baselines.py `_sma_trend_weights`: SPY iff close > 200d SMA
  of close, else SHY, month-end checks)

FINAL = config among C1..C10 with highest dev net Sharpe at 10 bps subject
to dev MaxDD no deeper than -25%; tie-break lower annual turnover.

PASS iff: FINAL dev Sharpe >= S_ts + 0.10 AND FINAL dev Sharpe >= S_bar -
0.05 AND FINAL dev MaxDD >= -25%. (Secondary, reported but NOT binding:
the literal full-window-derived constants 0.77 and 0.78.)

- PASS -> exactly one validation run of FINAL on 2018-01-01..latest at 10
  and 20 bps, reported verbatim, no re-picks.
- FAIL -> verdict: "two-sleeve is dead; controls only for the relaunch."
  No validation look is spent.

What kills the idea: no config satisfies the PASS condition, or every
config with Sharpe above the thresholds has dev MaxDD deeper than -25%.

## Exempt engineering diagnostics (no tuning, full or dev window)

- D0: dev re-window of existing baselines two_sleeve, tsmom, gem,
  spy_sma200 (references above).
- Dw: average TSMOM-sleeve weight in duration (IEF+TLT+LQD) vs
  equity/commodity at dev month-ends (checks diagnosis 2b).
- Dv: distribution of the vol-target scale at dev month-ends (checks
  diagnosis 1).

All configs logged to trials.csv (10 bps stats in columns, 20 bps in
notes), date=2026-07-02, engine=daily_ledger_v1.
