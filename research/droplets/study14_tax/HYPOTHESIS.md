# STUDY 14 — Swedish account-structure math (ISK vs depå) — HYPOTHESIS

Date: 2026-07-02 (written BEFORE any computation was run)
Workstream: G (REAL_MONEY_SWEDEN). OWNER-AUTHORIZED expansion of the
quarterly spec budget (per batch instructions).

This is an ANALYTIC TAX/FRICTION MODEL, not a ledger backtest. No price
data is used; no strategy parameter is tuned. The daily-ledger engine is
not invoked because nothing here depends on return paths beyond a
constant-CAGR assumption (declared below). Engine field in trials.csv is
therefore `analytic_tax_v1` with a note referencing this file.

## Question

For a Swedish resident running the adopted blend_126_252 rotation
(~8x/yr one-way turnover, net CAGR scenarios 8/12/16%), which real-money
structure produces more terminal wealth over 10 years:

(a) ISK at a Swedish broker (UCITS re-mapped universe, extra frictions),
(b) vanlig depå at a US broker (Alpaca; US ETFs; 30% tax on gains
    realized ~annually at this turnover),
(c) reference: buy-and-hold SPY in a depå (tax deferred to year 10)?

## Fixed inputs (from primary sources, gathered before computing)

- ISK schablon 2026: statslåneränta 2025-11-30 = 2.55%; rate = SLR + 1pp
  = 3.55% (floor 1.25%); tax = 30% of schablonintäkt => 1.065% of the
  capital base above the tax-free allowance. Allowance = 300,000 SEK
  from 2026-01-01 (150,000 SEK during 2025), shared across ISK/KF/PEPP
  per person. Kapitalunderlag = (four quarter-opening values + all
  deposits during the year) / 4. (Skatteverket; Avanza; Fondkollen.)
- Depå: 30% capital-gains tax on realized net gains; at ~8x turnover and
  ~1-2 month average holding period effectively ALL gains realize in the
  year they accrue => after-tax growth factor (1 + 0.70*r) per year.
  Dividends also 30% (inside r). US 15% treaty WHT on dividends with
  W-8BEN, creditable against Swedish tax => no extra drag modeled.
- Buy-and-hold reference: tax only at final sale:
  terminal = W0 * [(1+r)^10 - 0.30*((1+r)^10 - 1)] (dividend-tax drag on
  ~1.3% SPY yield noted qualitatively, not modeled).

## Declared parameters

- Account sizes W0: 100k / 300k / 1M / 3M SEK. Horizon: 10 years.
- CAGR scenarios r: 8% / 12% / 16% constant (net of 10 bps/side US
  trading costs, i.e. the ledger convention).
- ISK extra friction f (vs the Alpaca implementation), subtracted from
  r in the ISK leg only, three pre-declared levels:
  - LOW  = 60 bps/yr  (Nordnet + valutakonto: courtage ~0.06-0.10%/side
    mid tier, Xetra spreads +3-7 bps/side, FX one-off, TER delta ~0)
  - MID  = 120 bps/yr (courtage ~0.15%/side, spread +5-10 bps/side,
    occasional auto-FX; the central estimate)
  - HIGH = 250 bps/yr (Avanza-style auto-FX 0.25% on every foreign-
    currency trade + min-courtage effects at small size)
  Derivation: extra per-side cost x bps times 8x one-way turnover.
- Schablon rate held constant at the 2026 level (1.065% above the
  allowance) for all 10 years; allowance held at 300k nominal.
  Sensitivity bounds reported: floor case 0.375%/yr, 2024-peak case
  1.086%/yr.
- Depå friction vs baseline: 0 (Alpaca commission-free, costs already in
  the ledger's 10 bps/side).
- Integer-share cash drag on ISK: reported separately (approx. residual
  ~0.5-0.75% of a 100k account idle => ~4-12 bps/yr), not inside f.

## Pre-registered decision rule

- Express results as after-tax terminal wealth and as annualized
  after-tax CAGR; ISK advantage quoted in equivalent bps/yr =
  CAGR_ISK_after_tax_and_friction - CAGR_depå_after_tax.
- Recommend ISK for a (size, CAGR) cell if the advantage at MID friction
  is >= +25 bps/yr. Recommend depå only if the advantage is negative at
  LOW friction. Otherwise call the cell "either / friction-dominated".
- Also report the breakeven friction f* per cell (the f at which ISK and
  depå tie), so the recommendation survives friction-estimate error.

## What would falsify the "ISK is the biggest lever" prior

If, at MID friction and 12% CAGR, the ISK advantage is < 100 bps/yr for
the 1M SEK account, the batch prompt's claim ("dwarfs every bps
droplet") is NOT supported and will be reported as such.
