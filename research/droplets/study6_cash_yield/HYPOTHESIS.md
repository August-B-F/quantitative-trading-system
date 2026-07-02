# STUDY 6 — Cash drag & yield droplets (engineering measurements)

Date: 2026-07-02. Author: study6_cash_yield droplet.
Type: ENGINEERING measurement study — nothing is tuned on returns, so the
full window 2005..2026 is allowed and the 10-config signal budget does not
apply. All portfolio numbers come from `src/backtest/ledger.py`
(`run_ledger_backtest`), reported at 10 AND 20 bps/side, cash sleeve SHV
unless the cash sleeve IS the object under study. Every ledger run is
logged to `trials.csv` in this folder.

BIL note (declared ex-ante): `data/clean/prices/BIL.parquet` does NOT
exist. The cash-sleeve menu is therefore {SHV, SHY, pure 0%-cash}. BIL is
reported as UNAVAILABLE, not silently substituted.

## Droplet 1 — idle-cash drag in the executor

Mechanism under study (src/execution/executor.py):
- line 105: `usable_equity = equity * 0.99` — all order notionals sized to
  99% of equity.
- line 19 / 362: `BUY_CASH_HEADROOM = 0.995` — buys rescaled to 99.5% of
  post-sell cash when they exceed it.
- line 11 / 92: `NOISE_FRACTION = 0.01` — deltas < 1% of equity never trade,
  so accumulated cash below ~1% per ticker is never redeployed.
- line 21 / 378: orders < $1 dropped.

What I will measure:
1. Empirical steady-state uninvested fraction: for every successful
   strategy execution in logs/rebalance_log.json (April–June 2026),
   cash_frac = 1 − sum(post_rebalance_weights). Report mean/min/max across
   strategy-rebalances.
2. Analytical steady-state model of the same quantity from the three
   constants above (to sanity-check the empirical number and to predict the
   post-fix level).
3. Price it: drag_bps/yr = mean_cash_frac × (expected portfolio return −
   cash yield). Alpaca paper cash earns 0%. Expected portfolio return is
   NOT re-estimated: I use the ledger-engine full-window CAGR band of the
   relevant books — equal_weight_8 13.50%/yr (universe proxy, BASELINES.md)
   and spy_buy_hold 10.87%/yr — and report the drag as a band.

Decision rule (fixed now): recommend the residual-cash sweep (exact
file:line + new constants) iff the priced drag ≥ 5 bps/yr at the midpoint.
If measured steady-state cash_frac < 0.3%, the fix is not worth code risk:
recommendation becomes DO NOT DO.

## Droplet 2 — cash-sleeve yield: SHY vs SHV (vs BIL: unavailable)

What I will measure:
1. Per-ETF: full-window and last-3y annualized total return, vol, MaxDD
   from adj_close parquets; SHY calendar-2022 return (duration risk).
2. Ledger runs (the ONLY portfolio runs in this study), full window,
   each at 10 and 20 bps/side:
   - spy_sma200 parking in SHY (reproduces the baseline; parking asset SHY)
   - spy_sma200 parking in SHV
   - spy_sma200 parking in pure 0% cash (prices the "any yield vs none" gap)
   - tsmom (MOP spec) OFF-sleeve in SHV (reproduces baseline)
   - tsmom OFF-sleeve in SHY
   = 5 schedule configs × 2 cost levels = 10 ledger runs, all logged.
   No other variants will be run; this list is final.

Decision rule (fixed now): recommend a parking-asset change iff the
full-window CAGR delta ≥ 10 bps/yr AND the higher-yield asset does not
reduce the strategy's full-window net Sharpe. If |delta| < 10 bps/yr:
verdict "immaterial, keep SHV for executor cash / keep per-spec asset for
sleeves". The SHY-2022 question is answered by comparing full-window CAGR
delta vs the incremental 2022 drawdown contribution — reported, not used
to re-pick.

## Droplet 3 — fractional dust / NOISE_FRACTION

What I will measure from logs/rebalance_log.json (successful executions):
1. Per-ticker |post_rebalance_weight − target_weight| distribution — how
   much drift one rebalance leaves.
2. How much of that drift is below NOISE_FRACTION=0.01 (i.e. would NEVER
   be corrected at the next rebalance) vs above.
3. Cost of NOISE_FRACTION=0.005: count deltas in [0.005, 0.01) per
   rebalance from the same logs, extra annual turnover = 12 × their mean
   summed size, extra cost = turnover × cost_bps. Recovery: reduction in
   persistent per-position mis-weight (reported as tracking improvement in
   weight terms; no alpha claim attached to it).

Decision rule (fixed now): recommend NOISE_FRACTION 0.005 iff its extra
cost < 5 bps/yr AND the observed uncorrectable drift at 0.01 exceeds 0.5%
mean absolute per-position deviation. Otherwise DO NOT DO.

## Kill criteria summary
- D1 dead if steady-state cash < 0.3% or priced drag < 5 bps/yr.
- D2 dead (no change) if parking-asset CAGR delta < 10 bps/yr.
- D3 dead if 0.005 costs ≥ 5 bps/yr or drift at 0.01 is < 0.5%/position.

validation_look: N/A — engineering study, nothing tuned, no 2018+ look
consumed.
