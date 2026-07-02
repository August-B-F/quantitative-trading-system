# HYPOTHESIS — Study 4: Blended Momentum Ensemble (pre-registered signal spec #1)

Date: 2026-07-02. Droplet: `research/droplets/study4_blended_momentum/`.
Engine: `src/backtest/ledger.py::run_ledger_backtest` (daily_ledger_v1). Written BEFORE any backtest run.

## Object under study

The live rotation strategies pin `lookback_stable=63d` after an in-sample "cliff at 42d" —
flagged by the audit as overfit. Literature (Jegadeesh-Titman horizons; Asness/AQR composite
momentum; Barroso-Santa-Clara / Daniel-Moskowitz vol-scaling) says momentum robustness comes
from AVERAGING horizons and from vol-adjusting returns before ranking, not from a magic
lookback. We test whether a blended and/or vol-adjusted ranking signal beats the pinned 63d
incumbent on the SAME chassis, with the ranking signal as the ONLY degree of freedom.

## Fixed chassis (identical across all configs — ex-ante, never varied)

- Universe (ex-ante, the live 8): SOXX, QQQ, XLK, VGT, IGV, XLE, GLD, SHY.
- Monthly: decision at the last trading day of each month (intersection calendar of the 8 +
  SPY), fill at next day's open (engine convention).
- Gate: if SPY adj_close <= SMA200(SPY adj_close) at the decision date, the whole book is
  {SHY: 1.0}. Otherwise:
- Selection: top-3 tickers by the config's blended rank score; weights = inverse 63d realized
  vol (std of daily adj_close returns over last 63 bars, annualized), normalized to sum 1.0.
- Common start: a config returns no weights until EVERY universe ticker and SPY have >= 274
  bars (252+21+1, the longest leg) — so all configs share the same first decision
  (expected ~2006-02-28) regardless of their own lookback needs.
- Costs: 10 AND 20 bps per side. Cash sleeve SHV (declared; weights always sum to 1 so it is
  never held beyond day 0).
- All signals use adj_close data strictly <= decision date.

## Signal definitions

For ticker t at decision date d, a LEG is (L, skip, voladj):
- raw leg score r = adj_close[d - skip bars] / adj_close[d - L bars] - 1
- if voladj: r = r / vol, vol = std(daily adj_close returns over the same window
  [d-L+1 .. d-skip], ddof=1) * sqrt(252). Non-finite/zero vol => ticker excluded that month.
- Blend: each leg's scores are cross-sectionally ranked over the 8 tickers
  (ascending, method='average'); the config score = equal-weight mean of leg ranks.

## The 9 configs (frozen; config budget 10, we use 9)

| id | name                    | legs (L, skip, voladj)                          |
|----|-------------------------|--------------------------------------------------|
| a  | pin_63 (INCUMBENT)      | (63,0,raw)                                       |
| b  | pin_252_21              | (252,21,raw)                                     |
| c  | blend_63_126_252        | (63,0,raw),(126,0,raw),(252,0,raw)               |
| d  | blend_21_63_126_252     | (21,0,raw),(63,0,raw),(126,0,raw),(252,0,raw)    |
| e  | voladj_63               | (63,0,va)                                        |
| f  | voladj_blend_63_126_252 | (63,0,va),(126,0,va),(252,0,va)                  |
| g  | blend_skip252           | (63,0,raw),(126,0,raw),(252,21,raw)              |
| h  | voladj_blend_skip252    | (63,0,va),(126,0,va),(252,21,va)                 |
| i  | blend_126_252           | (126,0,raw),(252,0,raw)                          |

Justification for h, i (in advance): (h) combines the two literature mechanisms (vol-adjust +
skip-month) — if f and g help independently this is the natural composite; (i) drops fast legs
entirely — at monthly cadence fast legs may only add churn, and turnover matters at 20 bps.

## Windows and data-split discipline

- DEV (design/tune): 2005-01-01..2017-12-31. Ledger run start = first common decision date,
  end = 2017-12-31. All selection happens here.
- VALIDATION: 2018-01-01..latest. EXACTLY ONE look, on the adopted config only, at 10 and
  20 bps, reported verbatim whatever it shows.

## Decision rule (frozen — no post-hoc edits)

1. Run all 9 configs on DEV at 10 and 20 bps.
2. Winner W = argmax dev Sharpe at 10 bps among the 8 challengers (b..i).
3. ADOPT W iff BOTH:
   - A (margin): Sharpe_W - Sharpe_a >= 0.05 at 10 bps AND at 20 bps.
   - B (not one-year luck): for every calendar year Y in the dev window, recomputing Sharpe on
     dev daily NAV returns with year Y excluded leaves Sharpe_W(-Y) >= Sharpe_a(-Y) at 10 bps.
   Otherwise ADOPT the incumbent (a) and declare the 63d pin adequate — the blended-ensemble
   idea is dead for this universe/cadence. That null kills the idea; there is no retry.
4. The single validation look is spent on the ADOPTED config (W if adopted, else a).
5. Reference bar: the rotation promotion bar is spy_sma200 net Sharpe 0.83 (full window,
   10 bps, results/BASELINES.md). Validation context: spy_sma200 2018+ Sharpe is 0.64.

## Cliff test (pre-registered robustness MEASUREMENT, not selection)

On the dev window at 10 bps: perturb each single lookback leg of the dev-Sharpe winner W by
+/-20% (one leg at a time, others fixed; 63->50/76, 126->101/151, 252->202/302; skip stays 21),
and the incumbent's 63->50/76 as contrast. These perturbations are NOT adoption candidates —
none can be adopted regardless of Sharpe. A robust ensemble should barely move; the incumbent
is expected to show the cliff the audit flagged.

## Expectations (stated before running)

- Expect f (voladj blend) to top dev Sharpe, beating a by ~0.05-0.15: horizon averaging cuts
  timing noise; vol-adjust stops high-vol SOXX from dominating ranks on raw return alone.
- Expect b (12-1 alone) weakest of the blends here: slow exit in a concentrated tech universe.
- Expect blends to show lower turnover than pin_63 (more stable ranks), helping at 20 bps.
- Kill condition (verbatim): no challenger clears rule 3 => incumbent adequate, idea dead.

## Logging

Every config evaluated (9 dev configs x 2 cost levels, cliff perturbations, 1 validation look
x 2 cost levels) is one row in `research/droplets/study4_blended_momentum/trials.csv`
(engine=daily_ledger_v1, date=2026-07-02, cost level in notes; source in
{dev, cliff_test, validation}).
