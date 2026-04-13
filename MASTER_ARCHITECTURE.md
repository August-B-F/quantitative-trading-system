# MASTER ARCHITECTURE

Production specification for the regime-conditional ETF momentum rotation strategy.
This document is the single source of truth for the strategy rules. Where it
disagrees with code, the code is wrong.

═══════════════════════════════════════════════════════════════
SECTION 1 — EXECUTIVE SUMMARY
═══════════════════════════════════════════════════════════════

**What it does.** The system rotates monthly across a fixed 8-ETF universe
(7 risk ETFs + 1 short-Treasury cash proxy), ranking them by trailing total
return and holding a 50/50 blend of the single best ETF and an inverse-volatility
weighted basket of the top three. A machine-learning regime classifier toggles
the ranking lookback between 63 and 21 trading days based on whether the
growth-inflation environment is predicted to remain stable or transition over
the next 21 days. A simple SMA200 trend gate parks the top-1 leg in cash when
the broad market breaks down, and a calendar rule defers rebalances that would
otherwise execute immediately after FOMC meetings. Everything is rules-based
except the lookback toggle.

**Backtest performance** (walk-forward output: 2010-04 → 2026-03,
188 monthly rebalances — this is the full walk-forward window, not a
calendar filter; 10bps round-trip transaction costs assumed in the
20bps degradation budget):

| Metric | Strategy | SPY |
|---|---|---|
| CAGR | **23.61%** | 15.42% |
| Sharpe | **1.50** | 1.09 |
| MaxDD | **-12.94%** | -26.61% |

**Realistic forward expectation: ~23.5% CAGR, Sharpe ~1.55.** Headline numbers
blend three cross-sectional dispersion regimes; under a regime-rebalanced
forward view (1/3 weight each tercile) CAGR converges to ~23.5% and Sharpe
toward ~1.55. Do not size to peak-era numbers (29-36% CAGR for 2018-2020
starts) — those reflect a bullish dispersion mix, not a stable expectation.

**Three components on top of the base 63d momentum strategy:**

| Component | ΔCAGR | ΔSharpe | ΔMaxDD |
|---|---|---|---|
| E-R1: regime-conditional 63d/21d lookback switch | +1.9pp | +0.34 | — |
| M11: top-3 inverse-volatility weighting | +1.2pp | +0.06 | -1.6pp |
| M26_post_3d: defer rebalance 3 days after FOMC | +1.4pp | — | -6.5pp |

**The single ML component.** A HistGradientBoostingClassifier (4-class
growth-inflation quadrant, walk-forward retrained) predicts the quadrant 21
days forward. Its prediction is used **only** to choose between the 63d and
21d ranking lookback. It does **not** pick ETFs, does **not** size positions,
does **not** generate buy/sell signals. Sixteen-plus prior experiments at
ML-based ETF selection all failed; the lookback-timer interpretation is the
only one that survived walk-forward validation (99.8th percentile vs random
switch timing — see [results/LOOKBACK_TRIGGER_REPORT.md](results/LOOKBACK_TRIGGER_REPORT.md)).

**Three non-negotiables.** Each is on a measured cliff edge in the stress
tests and must be hard-pinned in production config:

1. **Stable lookback = 63 trading days.** Dropping to 42d collapses Sharpe
   from 1.50 to 1.13 (-7.2pp CAGR).
2. **`inflation_features__cpi_yoy` in CORE feature set.** Removal widens
   MaxDD from -12.94% to -18.68%.
3. **Rebalance = last trading day of month.** Mid-month, month-start, and
   random-day variants all drop Sharpe to ~1.17.

**What can go wrong.** The strategy is a calm-and-trending-market play that
also avoids the worst of crashes through lookback switching — it is *not* a
crash-alpha play. In quiet bull markets (VIX<15) it has historically lagged
SPY by ~30pp annualized over the affected months and the longest observed
SPY-underperformance streak is 13 months. The Monte Carlo 5th-percentile
MaxDD is -28.8%, ~2.2x the realized -12.94%, so size positions to that tail
rather than the headline. Roughly half of the M26 FOMC-deferral benefit is
concentrated in the single 2018 episode; expect that contribution to be
lumpy in live trading. The classifier degrades materially after ~12 months
without retraining (4-class accuracy 0.70 → 0.43 over five years stale).
And there is no intra-month drawdown stop in the current design — a flash
crash between month-ends is unprotected.

═══════════════════════════════════════════════════════════════
SECTION 2 — STRATEGY RULES
═══════════════════════════════════════════════════════════════

This section is the implementable specification. No ambiguity.

## 2.1 Universe

Fixed 8-ETF universe. **No additions, no removals**, ever. Universe
modifications were tested in M14-M18 of the candidate sweep — every variant
hurt risk-adjusted return.

| Ticker | Tracks | Why included | Inception |
|---|---|---|---|
| SOXX | iShares Semiconductor ETF | High-beta tech leadership leg | 2001-07-10 |
| QQQ | Invesco Nasdaq-100 | Broad large-cap tech | 1999-03-10 |
| XLK | SPDR Technology Select Sector | S&P tech sector exposure | 1998-12-16 |
| VGT | Vanguard Information Technology | Lower-cost tech alternative, slightly different basket | 2004-01-26 |
| IGV | iShares Expanded Tech-Software | Software-only tech tilt | 2001-07-10 |
| XLE | SPDR Energy Select Sector | Commodity / cyclical inflation hedge | 1998-12-16 |
| GLD | SPDR Gold Trust | Real-asset / monetary hedge | 2004-11-18 |
| SHY | iShares 1-3 Year Treasury Bond | Cash equivalent (used by SMA gate) | 2002-07-22 |

**Cash equivalent.** SHY. When the SMA200 trend gate fires, the top-1 leg
parks in SHY for that month. SHY can also organically appear in the top-3
ranking during stress regimes; this is allowed and is not treated specially.

**Data quirks.**
- VGT and XLK overlap heavily by construction; both are kept because the
  inverse-vol weighter occasionally splits between them when their realized
  vols diverge.
- GLD and XLE have low correlation to the tech cluster, which is what
  drives the high-dispersion regime described in Section 1.
- SHY total return is small but non-zero; do not approximate it as constant.

**Data history requirement.** All eight ETFs must have at least 200 trading
days of adjusted-close history before the first rebalance (200 needed for
SMA200; 126 would suffice for the 63d lookback alone).

## 2.2 Momentum signal

**Definition.** N-day total return computed from adjusted close prices:

```
return_Nd(ticker, t) = adj_close(ticker, t) / adj_close(ticker, t - N) - 1
```

Where N is in **trading days**, not calendar days. Adjusted close means
split- and dividend-adjusted (Yahoo Finance "Adj Close" or equivalent).

**Lookbacks.**
- Default (stable regime): **N = 63 trading days**.
- Transition regime: **N = 21 trading days**.
- The choice between them is governed by Section 2.5.

**Data requirement.** Daily adjusted close for all 8 ETFs and SPY.
Minimum 200 trading days of history before first rebalance. Updated each
trading day before market close on rebalance dates.

## 2.3 ETF ranking and selection

On each rebalance date:

1. Compute `return_Nd` for all 8 ETFs using the active lookback.
2. Rank ETFs 1 through 8 by return, descending. Rank 1 = highest return.
3. **Top-1 ETF** = the rank-1 ETF.
4. **Top-3 ETFs** = ranks 1, 2, 3.

The top-1 ETF is always also a member of the top-3 set.

## 2.4 Position sizing — inverse volatility weighting

The portfolio is split 50/50 between two legs:

- **Top-1 leg = 50% of capital.** All allocated to the rank-1 ETF (subject
  to the SMA gate in Section 2.6).
- **Top-3 leg = 50% of capital.** Allocated across ranks 1, 2, 3 by inverse
  **21d ATR** (vol proxy used in production; see
  `data/features/atr_21d.parquet` and `vol_proxy: atr_21d` in
  `configs/strategy.yaml`):

```
vol_i        = ATR(window=21d)_i        # 21d Average True Range
inv_vol_i    = 1 / vol_i
weight_i     = inv_vol_i / (inv_vol_1 + inv_vol_2 + inv_vol_3)
top3_alloc_i = weight_i * 0.50
```

**Final ETF weights** are the sum across legs. Because the rank-1 ETF
appears in both legs, its final weight is `0.50 + top3_alloc_1`.

**Worked example.** Suppose on a rebalance date:

| Rank | Ticker | 21d ATR (ann., illustrative) | inv_vol | top-3 share |
|---|---|---|---|---|
| 1 | SOXX | 32% | 3.125 | 0.305 |
| 2 | QQQ | 22% | 4.545 | 0.443 |
| 3 | XLE | 28% | 3.571 | 0.349 (rounded; sum = 1.000 after re-norm) |

Re-normalizing inv_vols (3.125 + 4.545 + 3.571 = 11.241):
- SOXX share: 3.125 / 11.241 = 0.278
- QQQ  share: 4.545 / 11.241 = 0.404
- XLE  share: 3.571 / 11.241 = 0.318

Top-3 leg allocations (× 0.50):
- SOXX: 13.9%
- QQQ:  20.2%
- XLE:  15.9%

Final weights (top-1 SOXX gets the full 50% top-1 leg plus its top-3 share):
- **SOXX: 50.0% + 13.9% = 63.9%**
- **QQQ:  20.2%**
- **XLE:  15.9%**
- (Remaining 0.0% in cash; the legs sum to 100%.)

Implied maximum single-ETF concentration is therefore around 65-70% in
practice (50% top-1 leg + ~15-20% top-3 share when the leader has a low
relative vol).

**Vol proxy:** 21d ATR (Average True Range) computed from daily OHLC —
the canonical production path loads `data/features/atr_21d.parquet`,
and `configs/strategy.yaml` pins `vol_proxy: atr_21d`. Use the same
window each rebalance; do not parameter-sweep. (The original M11 spec
called out 63d realized vol; the canonical code path uses 21d ATR and
that is what produces the 23.61/1.50/-12.94 canary.)

## 2.5 Regime-conditional lookback switch

This is the largest single contributor to excess returns. It uses an ML
classifier as a **lookback timer**, not as a regime predictor. The
quadrant-prediction accuracy (0.665 walk-forward, 4-class) is secondary
to the timing of when the prediction *disagrees with the current regime*.

**Quadrant definition** (verified from
[src/features/macro_features.py:261-267](src/features/macro_features.py#L261-L267)):

| Dimension | High | Low |
|---|---|---|
| Growth | ISM PMI > 50 | ISM PMI ≤ 50 |
| Inflation | CPI YoY ≥ 3.0% | CPI YoY < 3.0% |

Four classes:
- `HG/LI`: high growth, low inflation
- `HG/HI`: high growth, high inflation
- `LG/LI`: low growth, low inflation
- `LG/HI` (stagflation): low growth, high inflation

**Current regime** is the *actual* quadrant on the rebalance date, computed
from the latest released ISM PMI and CPI YoY values (forward-fill latest
available release; do not look ahead).

**Predicted regime** is the classifier's argmax for 21 trading days forward.

**Switch rule.**
- If `predicted_regime == current_regime` (stable): use the **63d** lookback.
- If `predicted_regime != current_regime` (transition): use the **21d** lookback.

**Transition firing rate.** ~28% of months (53 of 188 in backtest).

**Classifier specification.**
- Model: `HistGradientBoostingClassifier`
- Hyperparameters: `max_iter=200, max_depth=4, learning_rate=0.05,
  min_samples_leaf=20, l2_regularization=1.0, random_state=0`
- Features: CORE feature set from `configs/feature_sets.yaml` (50 features)
- Walk-forward splitter: `ExpandingSplitter(min_train_months=60, val_months=6,
  test_months=3, step_months=3, embargo_days=5, halflife_months=36)`
- Walk-forward accuracy: ~0.665
- Retrain cadence: **at least every 12 months**, quarterly preferred (matches
  the splitter's native step)

**Fallback if the classifier is unavailable** (model file corrupted, feature
inputs missing, retraining failed): use the **63d lookback always**. This
reverts the strategy to T2_balanced behavior (Sharpe ~1.22, still beating
SPY). Do not attempt to substitute a rule-based trigger — none of the
ten rule-based alternatives tested in
[results/LOOKBACK_TRIGGER_REPORT.md](results/LOOKBACK_TRIGGER_REPORT.md)
matched the classifier, and the best (`VIX > 25`) reached only Sharpe 1.39.

## 2.6 SMA200 trend gate

```
SMA200_t  = mean(SPY_adj_close[t-200 : t])
distance  = (SPY_adj_close_t - SMA200_t) / SMA200_t
```

- If `distance < -0.04` (SPY at least 4% below its 200d SMA): **override the
  top-1 leg to SHY** for that month. The top-3 leg is unaffected.
- If `distance >= -0.04`: proceed normally.

The -4% buffer prevents whipsaw around the SMA200 line. The gate fires
~17 of 188 months (9%) in backtest.

**Order of application.** The gate is evaluated *after* the regime
lookback is selected and *after* ranking — it is the final override on the
top-1 leg only. The top-3 inverse-vol leg always runs.

**Code anchor.** This behavior is implemented at
[`scripts/model/run_optimization_block.py:226`](scripts/model/run_optimization_block.py#L226)
— `top1_ret = np.where(spy_dist > -0.04, top1_ret, shy_ret)`. The
substitution applies to the top-1 leg's forward return *only*; the
top-k leg in lines 228-257 is untouched. The 23.61% CAGR / 1.50
Sharpe / -12.94% MaxDD headline numbers come from this exact code
path (strategy `E-R1` built at line 511, confirmed by
`results/FINAL_STRATEGY_VALIDATED.md`). An earlier draft of this
document briefly described the gate as "park the portfolio in SHY";
that wording was wrong — the worked example in §10.6 has always been
correct (SHY 50% + top-3 basket 50%) and is the ground truth.

## 2.7 Rebalancing schedule

**Frequency.** Monthly.
**Default day.** Last trading day of each calendar month, market-on-close.

**FOMC deferral rule (M26_post_3d).** Risk-off mechanism — avoid rebalancing
into immediate post-FOMC market reactions:

- Let `D` be the scheduled rebalance date.
- Let `F` be the date of any FOMC decision falling within the window
  `[D - 0 trading days, D - 2 trading days]` (i.e. the rebalance lands 0, 1,
  or 2 trading days *after* an FOMC decision).
- If such an `F` exists: defer the rebalance by **3 trading days**. New
  date = `min(D + 3 trading days, last index)`.
- Otherwise: rebalance on `D`.

Pre-FOMC and symmetric variants were tested in
[results/M26_FOLLOWUP.md](results/M26_FOLLOWUP.md); post-only at 3 days is
the optimal pick (CAGR 23.61, Sharpe 1.50, MaxDD -12.94 vs 22.69 / 1.38 /
-15.28 for pre-only and 23.41 / 1.43 / -12.94 for symmetric).

**FOMC calendar source.** Federal Reserve press release archive
(~8 meetings per year). Maintain manually or scrape from
`federalreserve.gov`. Required for production. Out-of-date calendar →
deferral simply doesn't fire and the strategy reverts to plain monthly,
which is non-fatal but loses the +1.4pp CAGR / -6.5pp MaxDD contribution.

Deferral fires ~10 of 188 rebalances (5%) in backtest.

**Month-end timing is non-negotiable.** Test 5 in
[results/STRESS_TEST_REPORT.md](results/STRESS_TEST_REPORT.md) showed
month-start, mid-month, and random-day timing all drop Sharpe from 1.50 to
~1.17 (median random CAGR 18.93% vs baseline 23.61% — a 4-5pp gap). The
mechanism is alignment between (a) the classifier's training calendar
(month-aligned folds), (b) the 21d forward window used by the model, and
(c) month-end ETF rebalancing flows.

## 2.8 Rebalancing procedure (step by step)

On each scheduled rebalance date:

1. **FOMC deferral check.** Is today within `[FOMC, FOMC + 2 trading days]`
   for any FOMC meeting? If yes → reschedule to today + 3 trading days
   and stop. If no → continue.
2. **Data refresh.** Download latest adjusted-close prices for all 8 ETFs
   plus SPY through today's close. Refresh latest released ISM PMI and
   CPI YoY values from FRED.
3. **SMA200 gate.** Compute SPY's distance from its 200-day SMA.
   - If `distance < -0.04`: set top-1 leg target = SHY 100%; jump to
     step 8 with the top-3 leg still computed normally.
4. **Regime classifier.** Run the classifier on latest macro features →
   `predicted_regime`. Compute `current_regime` from latest PMI / CPI.
   - If `predicted == current`: lookback = 63d.
   - If `predicted != current`: lookback = 21d.
   - If classifier unavailable: lookback = 63d (fallback).
5. **Compute returns.** N-day return for all 8 ETFs using the active lookback.
6. **Rank.** Identify top-1 and top-3.
7. **Position sizing.** Apply 50/50 split with inverse-vol top-3 weighting
   per Section 2.4.
8. **Compare to current holdings.** Compute trades = target − current.
9. **Execute.** Market-on-close at the day's adjusted prices. Log every
   weight, rank, return, vol, and the regime/classifier inputs that
   produced the decision.
10. **Persist.** Write the decision record (date, predicted regime,
    current regime, lookback used, ranks, target weights, executed weights,
    SMA gate state, FOMC deferral state) to the trade log.

## 2.9 Edge cases

These cases are fully specified — no open decisions remain. Where the
current backtest makes an implicit choice that differs from the
production rule, the production rule governs live trading and the
backtest's behavior is recorded for transparency.

| Case | Production rule |
|---|---|
| Two ETFs have identical N-day returns | **Lower-volatility ETF ranks higher.** Tiebreaker metric: 63-day realized volatility (daily log returns, trailing 63 trading days, annualized). If that is also equal within float tolerance, fall back to alphabetical ticker order. This is consistent with the inverse-vol sizing philosophy in §2.4 — when two names look identical on return, prefer the one with cleaner risk. Backtest uses pandas `rank(method='first')` (universe-array order), which is not used in production. |
| Data feed delayed/missing for one ETF | **Exclude that ETF from ranking for the month and rank the remaining 7.** If the missing ETF is currently held, hold it for one additional month (do not force-sell on a data gap — a stale price is less damaging than a blind liquidation at an unknown mark). If **2 or more ETFs** are missing on a rebalance date, hold all current positions unchanged for the month and fire an alert per §6.4 — do not attempt a partial rebalance on a degraded universe. |
| Classifier produces equal probabilities for two regimes | Use `argmax` (first wins on tie). If neither equals the current regime, treat as a transition (21d). If exactly one equals current, use the non-current one's tie-break — i.e. if there's any ambiguity, lean toward 63d (the safer fallback). |
| New ETF in universe has < 63d of history | Cannot occur — universe is fixed and all members have > 20 years of history. If a corporate action (split, ticker change) breaks the adj-close series, treat as "data missing" and exclude that ETF for the affected month. |
| VIX data unavailable | Not used in the production strategy (VIX appears only in stress tests and ablations). No action needed. |
| SHY is the top-ranked ETF by momentum | Treated normally — SHY gets 50% top-1 weight + its inverse-vol top-3 share. This is rare but legitimate (it occurred in 2015 and 2022 in the backtest). Inverse-vol naturally over-weights SHY in the top-3 leg because of its tiny realized vol; this is the desired behavior. |
| Deferred rebalance date falls on the next month-end (or later) | **The deferred date IS the rebalance date for that month — even if it spills into the next calendar month.** If an FOMC deferral pushes the scheduled month-end rebalance past the calendar boundary (e.g. late-January FOMC pushes the Jan 31 rebalance to Feb 3), the resulting date *becomes* January's rebalance; do NOT execute a second rebalance on Jan 31 and do NOT also fire the ordinary Feb month-end rebalance for that same event. The following month (February) then rebalances normally on its own schedule (Feb 28 / 29). No "5-trading-day cooldown skip" — spacing is handled by the deferral itself, not by skipping subsequent months. |
| FRED macro release delayed (PMI, CPI not yet published) | Use the most recent available release (forward-fill). Missing macro data degrades classifier accuracy but does not break it; if all macro inputs are missing for >30 days, fall back to the 63d-always rule. |
| FOMC calendar not loaded | Treat as "no FOMC in window" → no deferral. Monitor and alert; the strategy degrades to plain month-end (loses M26 contribution). |

═══════════════════════════════════════════════════════════════
SECTION 3 — RISK MANAGEMENT
═══════════════════════════════════════════════════════════════

## 3.1 Built-in risk controls

The strategy has four risk controls baked into the rules. None of them are
discretionary overrides; all are deterministic functions of price and
calendar data.

1. **SMA200 trend gate** (Section 2.6). Top-1 leg parks in SHY when SPY is
   more than 4% below its 200d SMA. Active in ~9% of months, present in
   3 of the top-5 historical drawdowns.
2. **Top-3 diversification.** Even when one ETF dominates the top-1 leg, the
   top-3 leg holds a vol-weighted basket of three names, which prevents
   single-name concentration above ~65-70%.
3. **Inverse-volatility weighting** in the top-3 leg automatically de-risks
   high-volatility positions (e.g. during stress in semiconductors, SOXX's
   share of the top-3 leg shrinks).
4. **FOMC post-deferral** (Section 2.7). Avoids rebalancing into the
   immediate post-FOMC reaction window. Mechanism confirmed in Q4 2018,
   where it absorbs ~6pp of cumulative drawdown.

## 3.2 Position limits

- **Maximum single ETF weight.** Up to ~89% in practice. The earlier
  ~65-70% estimate was wrong: it assumed inv-vol weighting would
  meaningfully diversify the top-3 leg. In reality the canonical research
  code (and the production port in
  [src/strategy/position_sizing.py](src/strategy/position_sizing.py#L33))
  uses **raw $-units ATR-21d** as the inverse-vol proxy, not
  price-normalized vol. Lower-priced ETFs therefore dominate the top-3
  inv-vol leg whenever they appear in it. Worked example, 2026-04-10
  signal (top-3 = XLE / SOXX / GLD): ATR-21d in $ = 1.68 / 11.82 / 11.88
  → top-3 inv-vol weights 77.94 / 11.06 / 11.00% → final weights after
  the 50/50 split are **XLE 88.97% / SOXX 5.53% / GLD 5.50%**. Single-name
  cap is therefore *structurally* ~90%, not ~70%, when the rank-1 ETF is
  also the cheapest in the top-3 by share price. This is canonical
  research behavior — changing it (e.g. price-normalizing the ATR proxy)
  would break the 23.61/1.50/-12.94 canary and is out of scope for v1.x.
- **Cash (SHY) position.** Effectively binary at the top-1-leg level: the
  top-1 leg is either 50% in the rank-1 ETF or 50% in SHY (when the SMA
  gate fires). The top-3 leg can also hold SHY when it ranks in the top
  three by momentum. Partial cash positions outside this mechanism are
  not part of the design.
- **No leverage.** Weights always sum to 100% of capital (or less, if a
  data exclusion leaves a slot empty).
- **No short positions.** Long-only.

## 3.3 Drawdown management

- **Observed MaxDD (backtest):** -12.94%, occurring in the 2018-01-25 →
  2019-03-25 episode.
- **Monte Carlo 5th-percentile MaxDD:** -28.8% (10,000 bootstrapped paths
  × 180 months). **Size positions to this number, not the realized -12.94%.**
- **Top-5 historical drawdowns:** all between -10.1% and -12.9%, all of
  2-15 month duration. The SMA gate was active in 3 of 5; M26 deferrals
  triggered in 2 of 5.

**No intra-month drawdown stop.** This is a known gap. The SMA gate only
re-evaluates at month-end; a flash crash that happens between month-ends
is unprotected. If this is unacceptable for live trading, a daily SMA200
check (with the same -4% trigger) could be added as a future enhancement,
but it would change the strategy's character and would need to be
re-stress-tested. **For now: pre-commit to the monthly cadence or do not
go live.**

## 3.4 Degradation detection and fallback

**Classifier degradation budget.** The classifier can degrade significantly
before disabling it is justified. From Test 3b
([results/STRESS_TEST_REPORT.md](results/STRESS_TEST_REPORT.md)): even at a
50% random-flip rate of the top-1 pick, median Sharpe stays at 1.29 — well
above the 1.22 of the no-classifier T2_balanced fallback. **Threshold for
disabling the classifier:** sustained walk-forward 4-class accuracy below
0.55 over two consecutive retraining windows. Below that, the lookback
toggle is mostly noise; revert to 63d-always.

**Fallback hierarchy.**
1. **Classifier unavailable / failed retraining** → 63d lookback always
   (T2_balanced behavior, Sharpe ~1.22).
2. **Price data unavailable for one ETF** → exclude that ETF from ranking
   for the affected month; recompute top-1/top-3 from the remaining 7.
3. **FRED macro data unavailable / stale** → forward-fill latest available
   values. If staleness > 30 days, fall back to (1).
4. **All data unavailable** → hold SHY 100% until resolved; do not trade
   on stale data.
5. **FOMC calendar missing** → no deferral; revert to plain month-end.

**Monitoring triggers** (detailed thresholds will live in Section 6 of this
document once written):

| Signal | Investigate at | Disable component at |
|---|---|---|
| Walk-forward classifier accuracy | < 0.60 | < 0.55 (sustained 2 windows) |
| Live drawdown | > -15% | > -25% (kill switch) |
| Rolling 12m vs SPY | < -10pp | < -25pp (sustained 18 months) |
| `cpi_yoy` data continuity | Any missed/revised release | Definition change → re-validate |
| FOMC calendar drift | Deferral rate < 2% or > 10% per year | Manual review |

## 3.5 Expected underperformance periods

These are **by design**, not malfunctions. The strategy must be held
through them. Pre-commitment is required before going live.

- **Calm bull markets (VIX < 15).** Strategy trails SPY by ~30pp annualized
  during these months. This regime accounted for 65 of 188 backtest months
  (~35%). The drag comes from the SMA-gate-protected top-1 leg sometimes
  parking in SHY and from the inv-vol top-3 leg over-weighting lower-vol
  (lower-return) names during quiet rallies.
- **SPY > 15% trailing-12m.** Excess return -11.6pp annualized. 102 of
  188 months. The strategy is a defensive momentum tilt, not a melt-up
  participation play.
- **Longest observed SPY-underperformance streak: 13 months.** Expect
  similar or longer in live.
- **High-dispersion regimes.** When energy/gold diverge sharply from tech
  (XLE/GLD vs the cluster), Sharpe collapses to ~1.12 (still positive
  excess at +5pp, but the risk-adjusted edge halves). 63 of 188 months.

**Pre-commitment statement** (read aloud before going live):
> *I understand the strategy will trail SPY for multi-quarter periods,
> sometimes by double-digit percentages annualized. I will not disable
> components, change parameters, or override trades during these periods.
> If I am unwilling to hold through 13+ months of underperformance, I
> should not run this strategy.*

---

## Document history

- **v1.0** — Sections 1-3 written from FINAL_STRATEGY_VALIDATED,
  OPTIMIZED_STRATEGY, STRESS_TEST_REPORT, PROJECT_SUMMARY, M26_ANALYSIS,
  M26_FOLLOWUP, LOOKBACK_TRIGGER_REPORT, SIGNAL_ANALYSIS_REPORT.
  Quadrant thresholds verified against
  [src/features/macro_features.py:261-267](src/features/macro_features.py#L261-L267).
- **v1.1** — Pre-production pass: (a) §2.6 SMA gate confirmed against
  code (`scripts/model/run_optimization_block.py:226` — top-1 leg
  only swaps to SHY, top-3 inverse-vol leg unaffected); §10.6 worked
  example already agreed. (b) §2.9 edge cases: tiebreak, missing-feed,
  and deferred-collision rules locked (no more NEEDS DECISION). (c)
  §8.1 OECD CLI gap: **RESOLVED 2026-04-12.** USSLIND (discontinued),
  CFNAI (max corr 0.36), and USPHCI (max corr 0.64) all evaluated and
  rejected — none clear the 0.70 retest floor. oecd_cli retained with
  forward-fill; staleness risk accepted as a WARNING-level monitoring
  alert (`check_oecd_age`, `configs/alerts.yaml::oecd_cli_age`).
  §9.4 Step 0 downgraded from BLOCKER to monitoring alert.

═══════════════════════════════════════════════════════════════
SECTION 4 — DATA PIPELINE
═══════════════════════════════════════════════════════════════

## 4.1 Data sources — strategy operation (monthly rebalance)

These sources must be healthy on each rebalance day, or the fallback
hierarchy from §3.4 fires.

### 4.1.1 Price data (BLOCKING)

| Field | Value |
|---|---|
| Provides | Daily OHLCV + adjusted close for 8-ETF universe + SPY (and EXTRA tickers TLT/DBC/XLF/XLI/XLV/AGG/EEM/IWM for features) |
| Source | Yahoo Finance v8 chart API |
| Fetcher | [src/data/fetchers/yahoo.py](src/data/fetchers/yahoo.py) |
| Storage | `data/clean/prices/{TICKER}.parquet` |
| Frequency | Daily, fetched on rebalance day after market close |
| Lookback needed | ≥ 252 trading days (SMA200 + 63d momentum) |
| Typical latency | Live within seconds of the 16:00 ET close; adjusted-close revisions flow overnight on ex-dividend days |
| Failure mode | Defer rebalance 1 trading day and retry. If unavailable 3 consecutive trading days: hold current positions and alert. If one ETF is missing but the rest are healthy, exclude that ETF from ranking for this month (§2.9) |

### 4.1.2 Macro data — classifier inputs (DEGRADED-MODE tolerable)

The regime classifier's CORE feature set (50 features, from
[configs/feature_sets.yaml](configs/feature_sets.yaml)) is not purely
macro — most entries are price-derived (vol/return/ATR/cross-sectional
ranks across the universe + EXTRA tickers). The true FRED/macro
dependencies within CORE are:

| CORE feature | Series / source | Freq | Pub lag | Fetcher | File |
|---|---|---|---|---|---|
| `inflation_features__cpi_yoy` | FRED `CPIAUCSL` (12m % chg) | monthly | ~15 days after month-end | [fred.py](src/data/fetchers/fred.py) | `data/clean/macro/cpi_yoy.parquet` |
| `inflation_features__cpi_mom` | FRED `CPIAUCSL` (1m % chg) | monthly | ~15 days | fred.py | `cpi_mom.parquet` |
| `inflation_features__breakeven_5y` | FRED `T5YIE` | daily | ~1 day | fred.py | `breakeven_5y.parquet` |
| `inflation_features__breakeven_10y` | FRED `T10YIE` | daily | ~1 day | fred.py | `breakeven_10y.parquet` |
| `activity_features__ism_pmi` | **PROXY** (not true ISM) — z-composite of FRED `INDPRO` 12m log-change + `TCU` level deviation, rescaled to PMI 50-center | monthly | ~15 days | fred.py | `ism_manufacturing_pmi.parquet` (marked PROXY in DATA_CATALOG) |
| `activity_features__capacity_utilization` | FRED `TCU` | monthly | ~15 days | fred.py | `capacity_utilization.parquet` |
| `activity_features__initial_claims_4wma` | FRED `ICSA` (4w MA) | weekly | ~5 days | fred.py | `initial_claims.parquet` |
| `activity_features__oecd_cli` | FRED `USALOLITONOSTSAM` | monthly | ~45 days; **FRED series stopped publishing 2023-12; forward-filled; staleness accepted — see §8.1 resolution 2026-04-12** | fred.py | `oecd_cli_us.parquet` |
| `activity_rail_traffic__rail_traffic_ma4w` | FRED `RAILFRTCARLOADSD11` (substitute for AAR, which is PDF-only) | monthly | ~10 days | [aar.py](src/data/fetchers/aar.py) / fred.py | `rail_traffic.parquet` |
| `consumer_features__consumer_credit_yoy` | FRED `TOTALSL` (12m % chg) | monthly | ~45 days | fred.py | `consumer_credit_total.parquet` |
| `cross_asset_oil_gold__oil_gold_ratio` | Derived: WTI oil / gold — **no external source beyond the price fetchers already listed** | daily | ~1 day | derived | `data/clean/alternative/` |
| `positioning_margin_debt_per_spy_px__margin_debt_per_spy_px` | FRED `BOGZ1FL663067003Q` ÷ SPY close (FINRA is Akamai-blocked) | quarterly | ~60 days | fred.py | `margin_debt_fred.parquet` |
| `regime_growth_inflation__regime_lg_hi_stagflation` | Derived from CPI YoY + PMI proxy thresholds | monthly | inherits max lag of inputs | derived | — |
| `vol_features__vix` | Yahoo `^VIX` close | daily | ~0 days | yahoo.py | `data/clean/macro/vix.parquet` |

The remaining ~35 CORE features are price-derived (vol_21/42/63,
returns_12_1, returns_126, atr_14, quality_52w_high, quality_dist_sma200,
quality_voladj_mom_126, quality_golden_cross, volume_trend_21_63,
cross_sectional_mom_rank_126, cross_asset_eem_spy) computed from the same
Yahoo price pulls in §4.1.1 — no additional fetches required.

**Publication-lag rule (critical, avoids lookahead):** on rebalance date
`D`, use the most recent *released* value as of `D`, not the most recent
*period*. FRED releases are stamped with both the reference period and
the release date; the pipeline must forward-fill from the most recent
value where `release_date ≤ D`. The `.shift(1)` in
[engineer.py:78-86](src/features/engineer.py#L78-L86) enforces the T-1
close-of-data rule for price features; macro features inherit the lag
policy from [sentiment_features.py](src/features/sentiment_features.py)
(AAII +1d, COT +4d, margin debt +30d, CAPE +30d, SIA semi +45d, news
+1d).

**Forward-fill policy:** up to 45 trading days for monthly series,
5 trading days for weekly, 2 trading days for daily. Beyond that → data
is "stale" for classifier purposes. If any monthly CORE feature is stale
> 60 days → fall back to 63d-always (§3.4).

### 4.1.3 VIX (clarification)

VIX appears in CORE as `vol_features__vix`, an **input to the
classifier**, not to the inverse-vol position sizer. The inverse-vol
weighting in §2.4 uses **21d ATR computed from ETF daily OHLC**
(`data/features/atr_21d.parquet`), not VIX. VIX being
unavailable therefore only degrades the classifier by one of 50 input
features; the position sizer is unaffected.

### 4.1.4 FOMC calendar

| Field | Value |
|---|---|
| Source | `federalreserve.gov` press-release archive (~8 meetings/year, ~1 year forward known) |
| Format | List of FOMC decision dates |
| Update | Manual or scraped, at minimum annually |
| Failure mode | If calendar is absent or stale, deferral rule simply does not fire — strategy reverts to plain month-end rebalance (loses +1.4pp CAGR / -6.5pp MaxDD from M26). Safe default. |

### 4.1.5 SPY SMA200 (derived)

Not a separate data source — computed from SPY adjusted close
([engineer.py:161](src/features/engineer.py#L161)) as a **simple** (not
exponential) moving average over a 200 trading-day window, lagged one
day. Requires 200 trading days of SPY history before first rebalance.

## 4.2 Data sources — classifier training (quarterly retrain)

Retraining consumes the full CORE feature set above plus every other
panel used to *build* the master panel. The training pipeline does not
require new sources relative to §4.1; it re-reads all 1051 raw feature
columns assembled in session 5.0 and filters to CORE via
`configs/feature_sets.yaml`.

**Sources that are only meaningful for retraining (not daily op):**

| Category | Purpose | Catalog path | If disappears |
|---|---|---|---|
| Sentiment (AAII/NAAIM/COT/CBOE PCR/CNN F&G reconstructed/FRED margin) | Not in CORE post-SHAP except `margin_debt_per_spy_px`. | `data/clean/sentiment/` | Classifier retrains on remaining CORE — no material accuracy loss (Test A5 shows top-3 features alone reach 72.8%) |
| Fundamental (Shiller CAPE, SP500 P/E, SIA semi) | Not in CORE. | `data/clean/fundamental/` | No impact on CORE retrain |
| Experimental / alternative (GitHub commits, Google Trends, Wikipedia, Reddit, TSA, EIA energy, Port LA) | EXTENDED set only. | `data/clean/alternative/` | No impact on CORE retrain |

Ablation anchor (from
[results/FEATURE_IMPORTANCE_REPORT.md](results/FEATURE_IMPORTANCE_REPORT.md)
§A5): removing `cpi_yoy` alone costs 6.3pp classifier accuracy;
removing CPI+PMI+rail costs 13pp. As long as these three plus the
price-derived vol/return features remain, retraining succeeds.

## 4.3 Data flow

```
Yahoo v8 ──→ data/clean/prices/{TICKER}.parquet
   │
   ├──→ rolling_return(N=63 or 21) ──→ ETF ranking ─────────┐
   ├──→ rolling 63d std * √252 ──→ inverse-vol weights ─────┤
   ├──→ SPY 200d SMA ──→ SMA200 trend gate ─────────────────┤
   └──→ vol/atr/returns/cross-sectional features ──────────┐│
                                                           ││
FRED (CPI, TCU, INDPRO, T5YIE, T10YIE, ICSA, TOTALSL,      ││
      USALOLITONOSTSAM, RAILFRTCARLOADSD11,                ││
      BOGZ1FL663067003Q) ──→ macro feature builders ──────┐││
                                                          ▼▼▼
                                           [CORE panel, 50 feats]
                                                          │
                                           HistGB classifier
                                                          │
                                       predicted quadrant (21d fwd)
                                                          │
                                     compare to current quadrant
                                                          │
                                          lookback ∈ {63d, 21d}
                                                          │
FRB FOMC calendar ──→ post-FOMC [0..+2]d test ──→ deferral ┤
                                                          ▼
                                      position sizing → trade log
                                            (data/clean/trade_log.parquet)
```

## 4.4 Data quality checks

Run on every fetch:

- **Staleness**: last row ≥ `today − max_lag[frequency]`. Alert otherwise.
- **Gap detection**: no interior NaN runs longer than the forward-fill
  limit (§4.1.2).
- **Outlier detection**: |z| > 6 on daily returns for any price series
  triggers manual review (most commonly a bad split).
- **Schema lock**: column names/types match the expected schema; any
  drift blocks the run.
- **Adjusted-close consistency**: `adj_close / close` is non-decreasing
  over rolling 252d (detects stale splits/dividends).
- **Cross-field consistency**: for each ETF, `low ≤ min(open, close) ≤
  max(open, close) ≤ high`; volume ≥ 0.

**Auto-correct vs alert:**
- Forward-fill ≤ limit → auto.
- Forward-fill > limit → alert, defer rebalance.
- Any hard schema violation → alert, halt; do not trade on reformatted
  data without human review.

**Forward-fill kill switch:** if any CORE feature is stale more than 60
days and no substitute exists, the classifier goes to fallback mode
(63d-always); see §3.4.

## 4.5 Data storage

- **Raw pulls**: `data/raw/` (keep as audit trail).
- **Clean panels**: `data/clean/{prices,macro,sentiment,fundamental,
  alternative,calendar}/` — parquet, DatetimeIndex named `date`, sorted
  ascending, UTC-naive.
- **Feature panels**: `data/features/{price,macro,sentiment,interaction,
  targets}/*.parquet` — one file per logical feature group, columns
  per-ticker or per-signal.
- **Master panel**: `data/features/master_panel.parquet` (shape
  (5351, 902), date index 2005-01-03..2026-04-10).
- **Retention**: keep all historical data indefinitely; walk-forward
  retraining needs the full history. Do not prune.
- **Backup**: daily snapshot of `data/clean/` and `data/features/` to a
  second disk or object store; weekly off-site snapshot. The master
  panel + feature_sets.yaml + trained model joblib is the minimum
  "cold-start" bundle needed to resume trading.

═══════════════════════════════════════════════════════════════
SECTION 5 — ML CLASSIFIER SPECIFICATION
═══════════════════════════════════════════════════════════════

## 5.1 Purpose

The classifier's single job: **decide whether this month uses the 63d or
21d ranking lookback.** Nothing else. It does not pick ETFs, predict
returns, size positions, or forecast drawdowns. The 4-class quadrant
prediction is an intermediate output; what matters at the strategy level
is whether `predicted != current`, which flips the lookback.

Walk-forward 4-class accuracy is 0.665 — decent but not what the
strategy is graded on. The validated edge is the timing of the
disagreement events: 53 switches over 188 months (~28% firing rate),
99.8th percentile vs random switch timing
([results/LOOKBACK_TRIGGER_REPORT.md](results/LOOKBACK_TRIGGER_REPORT.md)).
Optimizing classifier accuracy is explicitly *not* the goal — the
top-3-feature variant reaches 72.8% accuracy but yields Sharpe 1.46 vs
1.50 for the 50-feature model
([results/FEATURE_IMPORTANCE_REPORT.md](results/FEATURE_IMPORTANCE_REPORT.md)).

## 5.2 Architecture

- **Model**: `sklearn.ensemble.HistGradientBoostingClassifier`
- **Hyperparameters** (pinned, verified against §2.5):
  - `max_iter=200`
  - `max_depth=4`
  - `learning_rate=0.05`
  - `min_samples_leaf=20`
  - `l2_regularization=1.0`
  - `random_state=0`
  - `max_leaf_nodes`: sklearn default (31)
  - `class_weight`: None (imbalance handled by sample-decay weights,
    not class reweighting)
  - `early_stopping`: off at training time; validation fold is used
    *outside* the estimator via the walk-forward harness.
- **Input**: CORE feature matrix (50 columns) from
  [configs/feature_sets.yaml](configs/feature_sets.yaml), preprocessed
  per §5.4.
- **Output**: 4-class argmax over growth-inflation quadrants
  `{HG/LI, HG/HI, LG/LI, LG/HI}`.
- **Switch conversion**: `switch_to_21d := predicted_class != current_class`,
  where `current_class` is derived from the latest released PMI and CPI
  YoY on the rebalance date (see §2.5 quadrant thresholds).

## 5.3 Feature list

Full 50-feature CORE set is authoritative in
[configs/feature_sets.yaml](configs/feature_sets.yaml) (lines 1-51).
Abridged by dependency tier:

**Tier A — load-bearing macro (removal costs ≥ 5pp classifier accuracy
or ≥ 5.7pp strategy MaxDD):**

| # | Feature | Source | Computation | Lag | Stationary? | SHAP rank |
|---|---|---|---|---|---|---|
| 1 | `inflation_features__cpi_yoy` | FRED CPIAUCSL | 12m % change | ~15d | no (level) → differenced at fold | **1** |
| 2 | `activity_features__ism_pmi` (PROXY) | FRED INDPRO + TCU composite | z-score, PMI-50 rescale | ~15d | yes | **2** |
| 3 | `activity_rail_traffic__rail_traffic_ma4w` | FRED RAILFRTCARLOADSD11 | 4-week MA | ~10d | no → diff | **3** |
| 4 | `cross_asset_oil_gold__oil_gold_ratio` | derived from WTI/gold | level ratio | ~1d | no → diff | **4** |
| 5 | `activity_features__capacity_utilization` | FRED TCU | level | ~15d | yes | **5** |
| 6 | `consumer_features__consumer_credit_yoy` | FRED TOTALSL | 12m % change | ~45d | no → diff | **6** |

**Tier B — price-derived (no external fetch; always available if prices
are available):** `vol_21d__{SOXX,TLT,XLV,XLI,IWM}`,
`vol_42d__{SOXX,QQQ,TLT,XLE,XLI,XLV}`, `vol_63d__{SOXX,QQQ,TLT,XLV}`,
`atr_14d__{DBC,SPY,XLE}`, `returns_12_1_mom__{DBC,XLE}`,
`returns_126d__{XLE,XLV,AGG}`, `returns_42d__XLV`,
`quality_52w_high_ratio__{XLE,XLI,XLV,IWM}`,
`quality_dist_sma200__XLE`, `quality_voladj_mom_126d__{XLE,XLV,SHY}`,
`quality_golden_cross__DBC`, `volume_trend_21_63__SOXX`,
`cross_sectional_mom_rank_126d__GLD`,
`cross_asset_eem_spy__eem_minus_spy_63d`. All computed by
[engineer.py](src/features/engineer.py) with `.shift(1)`.

**Tier C — other macro/regime:** `inflation_features__{cpi_mom,
breakeven_5y, breakeven_10y}`, `activity_features__{initial_claims_4wma,
oecd_cli}`, `positioning_margin_debt_per_spy_px__margin_debt_per_spy_px`,
`regime_growth_inflation__regime_lg_hi_stagflation`, `vol_features__vix`.

Non-stationary columns (ADF flagged, 184/902 in master panel) are
differenced **per fold at training time**, not in the panel build — see
[src/features/assemble_master_panel.py](src/features/assemble_master_panel.py).

## 5.4 Training procedure

**Walk-forward splitter**:
[`ExpandingSplitter`](src/model/walk_forward.py#L136-L225) with

```
min_train_months = 60
val_months = 6
test_months = 3
step_months = 3
sample_every_n_days = 5
embargo_days = 5
target_horizon = 21        # 21 trading days forward
decay_halflife_months = 36
```

Train samples are exponentially downweighted with
`w = exp(-age_months / (2 * 36))` where `age_months` is measured from
the fold's `test_start` back to each train sample date. Purging removes
any train sample whose `[t, t + 21]` forward window overlaps `val_start`
or `test_start`, with an additional 5-day embargo
([walk_forward.py:29-49](src/model/walk_forward.py#L29-L49)).

**Preprocessing**:
[`FeaturePreprocessor`](src/model/preprocessing.py#L11-L59) with
`clip_sigma=5.0`:

1. `fit` is called **per fold**, on train samples only.
2. NaN imputation: column-wise median from the train fold.
3. Standardization: weighted mean and weighted variance using the decay
   sample weights from the splitter, so recent train samples dominate
   the scaler.
4. Clip to `[-5σ, +5σ]`.
5. `transform` (same fitted params) is applied to val and test samples.

Columns with > 30% NaN on the train slice are dropped *at master-panel
build time* (see session 5.0 notes in
[data/FEATURE_CATALOG.md](data/FEATURE_CATALOG.md)), not at fold time.

**Training target**: growth-inflation quadrant label observed at
`t + 21` trading days, where the label is derived from released PMI and
CPI YoY *as-of* that future date. Quadrant thresholds:
- growth: PMI > 50 high, ≤ 50 low
- inflation: CPI YoY ≥ 3.0% high, < 3.0% low

Threshold source-of-truth:
[src/features/macro_features.py:261-267](src/features/macro_features.py#L261-L267).

**Class balancing**: none (no `class_weight`, no SMOTE). Recency decay
weights already compensate for older-era class imbalance sufficiently
for the WF accuracy target.

## 5.5 Retraining schedule

- **Cadence**: quarterly (matches `step_months=3`). Minimum acceptable
  cadence is annual. Do not exceed 24 months between retrains — stale
  model accuracy decays from ~0.70 at 1y to ~0.43 at 5y (4-class,
  barely above the 0.25 random baseline).
- **Out-of-cycle trigger**: if trailing-12-month strategy Sharpe drops
  below 1.15.
- **Procedure**:
  1. Refresh all fetchers (§4.1, §4.2) and rebuild `data/clean/`.
  2. Rebuild the master panel via `assemble_master_panel.py`.
  3. Refit the `ExpandingSplitter` over the full available history.
  4. Fit HistGB per fold, record out-of-fold predictions.
  5. Evaluate walk-forward accuracy on the most recent 12-month window
     of out-of-fold predictions.
  6. Compare new model vs current production model on the overlapping
     last-12m slice (same splitter config).
  7. **Deploy decision**:
     - new ≥ current OR new within 2pp of current → deploy new.
     - new > 2pp worse → keep current, open incident, investigate data.
  8. Log: model version, training range, WF accuracy per fold, feature
     availability summary, any data anomalies hit during the run.

- **Stale-model fallback**: if retraining fails or is ≥ 24 months
  overdue → revert to 63d-always (§3.4), keep the existing model file
  as reference but do not use its output.

## 5.6 Model versioning

- **Version ID**: date-based, `vYYYYqQ` (e.g. `v2026q2`).
- **Artifacts per version**:
  - `models/regime_classifier_{version}.joblib` — trained HistGB
  - `models/regime_classifier_{version}_preprocessor.joblib` — fitted
    FeaturePreprocessor (one per fold, keyed by fold_id)
  - `models/regime_classifier_{version}_metadata.json` — CORE feature
    list, training date range, WF accuracy, git commit hash, data
    panel fingerprint (hash of master_panel.parquet header)
- **Rollback**: keep the previous version live as `models/previous/` for
  at least one full retrain cycle.
- **Production symlink**: `models/regime_classifier_current.joblib` →
  the active version. The rebalance script reads only the symlink.

## 5.7 Classifier risks (from stress tests)

- **`cpi_yoy` is load-bearing.** Ablation (§A5 of
  FEATURE_IMPORTANCE_REPORT): removing it costs 6.3pp accuracy and
  widens strategy MaxDD from -12.94% to -18.68%. CPI data continuity
  is a first-class monitoring concern (§6.4).
- **Feature stability across eras**: Spearman ρ of mean |SHAP| rankings
  across {early, mid, late} buckets is 0.71–0.78 — stable but not
  perfect. Monitor for ranking drift after each retrain.
- **Top-3 vs top-50 tradeoff**: the top-3 feature set hits 72.8%
  accuracy (higher than the 66.5% full model) but only Sharpe 1.46 vs
  1.50. The other ~47 CORE features contribute to *switch timing
  quality* even when they don't move accuracy. **Do not simplify to
  top-3.** This is counterintuitive and has been verified; see §B2 of
  FEATURE_IMPORTANCE_REPORT.
- **Degradation budget**: strategy stays above the no-classifier
  baseline (T2_balanced Sharpe 1.22) even at a 50% random-flip rate of
  the top-1 pick (median Sharpe 1.29 at 50% flip, Test 3b). Very wide
  margin — do not pre-emptively disable the classifier on minor
  accuracy dips.
- **Disable threshold**: sustained WF 4-class accuracy < 0.55 over two
  consecutive retraining windows (6 months) → revert to 63d-always.
- **OECD CLI stop-publish**: FRED `USALOLITONOSTSAM` stopped updating
  2023-12. The feature is ffill'd in the panel. Monitor; if it becomes
  stale > 60 days at retrain time, drop it from CORE and retrain.

═══════════════════════════════════════════════════════════════
SECTION 6 — MONITORING AND OPERATIONS
═══════════════════════════════════════════════════════════════

## 6.1 Daily monitoring (automated, no human required)

- **Feed health**: each fetcher in
  [src/data/fetchers/](src/data/fetchers/) reports last-row date and
  row count. Alert if any price series lags > 1 trading day or any
  macro series lags beyond its forward-fill window (§4.1.2).
- **Rebalance calendar**: is today a scheduled month-end? If yes, is an
  FOMC deferral pending? Log the answer either way.
- **Holdings drift**: current realized weights vs last-rebalance target
  weights. Alert if drift > 5pp on any single name (indicates missed
  trade or corporate action).
- **Model file integrity**: hash-check the production classifier
  joblib against the metadata file.

## 6.2 Monthly monitoring (post-rebalance)

- Strategy return for the month vs SPY.
- Which ETFs were selected; which lookback (63d or 21d) was used.
- SMA200 gate state (fired / not fired, SPY distance from SMA).
- Regime classifier inputs: current quadrant, predicted quadrant,
  switch decision. If the switch fired, log whether the realized 21d
  outcome confirmed the transition.
- FOMC deferral state.
- Rolling 12-month Sharpe, CAGR, MaxDD, tracking error vs SPY.
- Concentration: max single-name weight and effective number of names.

## 6.3 Quarterly monitoring (retraining window)

- Walk-forward classifier accuracy on the most recent 12 months
  (matches retrain cadence from §5.5).
- Feature availability: any CORE feature that went stale, NaN > 10%, or
  had its series discontinued (e.g. OECD CLI).
- Retraining comparison per §5.5 step 6.
- Strategy performance vs the realistic-forward expectation (§1:
  ~23.5% CAGR, Sharpe ~1.55 regime-rebalanced; do not grade against
  peak-era numbers).
- Monte Carlo drawdown check: is current drawdown within the
  5th-percentile envelope (-28.8%)?

## 6.4 Alert triggers

| Severity | Condition | Action |
|---|---|---|
| IMMEDIATE | Price data unavailable for > 1 trading day | Defer rebalance; page on-call |
| IMMEDIATE | Live strategy drawdown > -15% from peak | Page; review, do not auto-disable |
| IMMEDIATE | Live strategy drawdown > -25% (kill switch) | Halt trading, go to SHY 100%, review |
| IMMEDIATE | Any CORE feature has release-hash change or definition revision (e.g. CPI rebase) | Pause retraining until validated |
| WARNING | Trailing 12m Sharpe < 1.0 | Investigate |
| WARNING | Trailing 12m vs SPY < -10pp | Investigate (expected per §3.5, but log) |
| WARNING | WF classifier accuracy < 0.60 over last 12m | Investigate feature drift |
| WARNING | CPI feed interrupted > 30 days | Begin fallback prep |
| WARNING | FOMC deferral rate < 2% or > 10% of rebalances annually | Manual calendar review |
| INFO | FOMC deferral activated | Log only |
| INFO | SMA200 gate activated | Log, verify that SPY distance matches expected calc |
| INFO | Regime switch fired (21d lookback used) | Log with predicted/current quadrant |

## 6.5 Disable conditions

**Disable the classifier only (revert to 63d-always):**

- WF accuracy < 0.55 sustained over two consecutive retrain windows
  (6 months).
- CPI feed dead > 60 days with no substitute and no released data.
- Trailing 12m strategy Sharpe < 0.8 *and* switch-HELPFUL rate is zero
  over that window (the lookback toggle is actively costing return).

In all three cases: keep everything else (SMA gate, FOMC deferral,
inv-vol, universe). Classifier fallback is T2_balanced, Sharpe ~1.22.

**Disable the entire strategy (go to SHY 100% or cash):**

- Multiple price feeds down simultaneously for > 3 trading days.
- Sustained MaxDD > -25% from peak (§6.4 IMMEDIATE kill switch).
- Market-structure event with no historical parallel (brokerage
  outage, ETF universe halted, currency regime break). Requires human
  judgment — the automated rule is: "if the pre-commitment statement
  in §3.5 no longer applies to the world you see, do not trade."

Re-enabling after a halt requires: (a) green feed health for
5 consecutive trading days, (b) retraining classifier on refreshed
data, (c) manual sign-off against this document.

═══════════════════════════════════════════════════════════════
SECTION 7 — WHAT WE TESTED AND WHAT FAILED
═══════════════════════════════════════════════════════════════

Complete experiment catalog from the research phase. One line per run.
Sources are [results/TIER1_REPORT.md](results/TIER1_REPORT.md),
[TIER1B_REPORT.md](results/TIER1B_REPORT.md),
[TIER2_REPORT.md](results/TIER2_REPORT.md),
[REGIME_INTEGRATION_REPORT.md](results/REGIME_INTEGRATION_REPORT.md),
[OPTIMIZATION_REPORT.md](results/OPTIMIZATION_REPORT.md),
[LOOKBACK_TRIGGER_REPORT.md](results/LOOKBACK_TRIGGER_REPORT.md),
[M26_ANALYSIS.md](results/M26_ANALYSIS.md),
[M26_FOLLOWUP.md](results/M26_FOLLOWUP.md).

Legend: "pass" means the run cleared the 50%-haircut rule (`+0.5pp CAGR
or +0.03 Sharpe, MaxDD not >2pp worse`) vs the relevant base. Baselines:
B0 random (CAGR 12.0, Sharpe 0.69), B2 63d momentum (CAGR 19.2, Sharpe
1.00), T2_balanced (CAGR 19.3, Sharpe 1.22), E-R1 (CAGR 21.2, Sharpe 1.34).

## 7.1 Tier 1 — ML rotation and drawdown baselines

- **E01** — Ridge on MIN(13) features, target T2 — CAGR 4.1%, Sharpe 0.29, MaxDD -50.9% — FAIL: linear model, acc 14.8% barely above random
- **E02** — HistGB on CORE(50), target T2 — CAGR 8.1%, Sharpe 0.50, MaxDD -24.5% — FAIL: acc 8.5%, RankCorr -0.072 (anti-signal)
- **E03** — RF on CORE(50), target T1 — CAGR 9.9%, Sharpe 0.55, MaxDD -49.3% — FAIL: acc 14.8%, collapses to SOXX/IGV/XLE (train-freq mismatch)
- **E04** — HistGB CORE, target T4 drawdown classifier (Mode C) — CAGR 19.9%, Sharpe 1.07, MaxDD -21.7% — FAIL: precision 28.6%, misses real drawdowns (2020-03 prob 0.01)
- **E05** — LogReg CORE, target T4 drawdown classifier — CAGR 11.5%, Sharpe 0.73 — FAIL: F1 0.141, linear under-fits tactical DDs
- **B2 (sys)** — 63d momentum baseline — CAGR 19.2%, Sharpe 1.00 — reference

## 7.2 Tier 1B — alternative ML approaches (all failed)

- **EA1** — regime classifier → ETF map — CAGR 8.4%, Sharpe 0.49, MaxDD -40.6% — FAIL: high regime acc (68.3%) does not translate to picks
- **EA2** — leadership persistence binary — CAGR 12.3%, Sharpe 0.70 — FAIL: acc 55.6% but drifts into laggards
- **EA3** — HistGB CORE fwd42 regression — CAGR 10.3%, Sharpe 0.59 — FAIL: Δ vs B2 -8.9pp
- **EA4** — HistGB CORE fwd63 regression — CAGR 16.0%, Sharpe 0.84 — FAIL: closest but -3.3pp CAGR vs B2
- **EA5** — risk signal overlay — F1 0.122 AUC 0.551, overlay CAGR 6.5% — FAIL: no signal
- **EB1** — large HistGB EXTENDED T2 — CAGR 8.1%, Sharpe 0.49, MaxDD -49.9% — FAIL: capacity hurts
- **EB2** — MLP small CORE T2 — CAGR 5.3%, Sharpe 0.34, MaxDD -48.4% — FAIL
- **EB3** — MLP big EXT T2 — run failed to complete — FAIL
- **EB4** — deep HistGB ALL features — CAGR 10.5%, Sharpe 0.56, MaxDD -55.9% — FAIL: more features = more overfitting
- **EC1** — specialist team of 5 models + rules — CAGR 7.2%, Sharpe 0.47 — FAIL: individual heads score ~60% but composition destroys edge
- **EC2** — stacked meta-learner — CAGR 15.7%, Sharpe 0.75 — FAIL: still -3.5pp vs B2
- **ED1** — k-NN similarity — CAGR 6.5%, Sharpe 0.40 — FAIL
- **ED2** — contrarian (invert E03) — CAGR 1.1%, Sharpe 0.29 — FAIL: confirms E03 is noise, not inverse-signal
- **ED3** — signal disagreement heuristic — CAGR 15.9%, Sharpe 0.83 — FAIL
- **ED4** — LSTM temporal overlay — CAGR 14.5%, Sharpe 0.92 — FAIL
- **ED5** — dispersion predictor + overlay — CAGR 18.2%, Sharpe 0.99 — FAIL by 0.01 Sharpe (best Tier-1B run; still below B2)
- **ED6** — ensemble of all rotation models — CAGR 10.2%, Sharpe 0.58 — FAIL: averaging junk yields junk

## 7.3 Tier 2 — hybrid structures

- **B3_top1_63d** — top-1 63d 8-ETF baseline — CAGR 19.4%, Sharpe 1.00, MaxDD -22.3% — reference
- **T2_top3_63d** — equal-weight top-3 63d — CAGR 17.8%, Sharpe 1.20, MaxDD -21.1% — PARTIAL: Sharpe +0.20 vs B3 but CAGR -1.6pp
- **T2_balanced** — 0.5 (top1+SMA gate) + 0.5 top3 — CAGR 19.3%, Sharpe 1.22, MaxDD -21.0% — **PASS**: becomes the no-classifier fallback
- **T2_balanced_60_40** — 60/40 split variant — CAGR 19.5%, Sharpe 1.20 — FAIL: no upside over 50/50
- **T2_3leg** — top1 + top3 + multi-horizon — CAGR 18.2%, Sharpe 1.17, MaxDD -19.4% — FAIL
- **T2_3legCAGR** — 63d+126d CAGR blend — CAGR 19.9%, Sharpe 1.15, MaxDD -22.7% — FAIL on Sharpe
- **T2_3legCAGR_softML** — 3leg + ML EV gate — CAGR 16.9%, Sharpe 1.24, MaxDD -16.7% — FAIL on CAGR
- **T2_balanced_softML** — CAGR 14.0%, Sharpe 1.14, MaxDD -14.1% — FAIL: soft ML gate cuts 5.4pp CAGR
- **T2_3leg_softML** — CAGR 13.3%, Sharpe 1.13 — FAIL

## 7.4 Regime integration (E-R1..E-R6)

- **E-R1** — 63d stable / 21d transition lookback switch on T2_balanced — CAGR 21.2%, Sharpe 1.34, MaxDD -21.0% — **PASS**: +0.12 Sharpe vs T2_balanced; becomes the spine of the final strategy
- **E-R2** — regime-tilted top-3 weights — CAGR 19.5%, Sharpe 1.23 — FAIL
- **E-R3** — softML + 0.5x EV on recession transitions — CAGR 15.6%, Sharpe 1.21 — FAIL
- **E-R4** — regime-filtered universe (eligibility sets incl. TLT/XLV) — CAGR 11.3%, Sharpe 0.86, MaxDD -22.8% — FAIL: same failure mode as EA1
- **E-R5** — dispersion × regime 4-branch rule — CAGR 15.3%, Sharpe 1.04 — FAIL
- **E-R6** — kitchen sink (L0..L5 layers) — CAGR 20.8%, Sharpe 1.20, MaxDD -22.2% — FAIL: only L3 lookback and L4 universe tilt passed per-layer; stacking added nothing
- **REGIME_3FEAT** — 3-feature classifier (cpi_yoy+pmi+rail) — regime acc 72.8%, strategy CAGR 22.6%, Sharpe 1.46 — FAIL (vs 50-feat 23.61%/1.50): higher accuracy, lower strategy Sharpe. Do not simplify.

## 7.5 Optimization sweep M01–M27 (on E-R1 base)

- **M01** — 63/42 lookback — CAGR 18.6%, Sharpe 1.19 — FAIL: -2.6pp CAGR, confirms 42d cliff
- **M02** — 126/21 — CAGR 19.4%, Sharpe 1.18, MaxDD -29.2% — FAIL: MaxDD +8.2pp worse
- **M03** — 126/42 — CAGR 16.9%, Sharpe 1.04 — FAIL
- **M04** — 63/10 — CAGR 20.0%, Sharpe 1.25 — FAIL: -1.2pp CAGR
- **M05** — avg(63,126) stable / 21d — CAGR 20.3%, Sharpe 1.23 — FAIL: blending the cliff is worse than pinning
- **M06** — avg(21,63,126) / avg(10,21) — CAGR 19.6%, Sharpe 1.20 — FAIL
- **M07** — 100% top3 EW — CAGR 18.3%, Sharpe 1.24 — FAIL: drops top-1 leg
- **M08** — 40/60 top1/top3 — CAGR 20.6%, Sharpe 1.34 — FAIL (flat Sharpe)
- **M09** — 60/40 top1/top3 — CAGR 21.7%, Sharpe 1.32 — FAIL: +0.52pp CAGR but Sharpe -0.01 below haircut
- **M10** — 50/50 top1/top2 — CAGR 20.5%, Sharpe 1.24 — FAIL
- **M11** — **top3 inverse-vol weighted** — CAGR 22.4%, Sharpe 1.40, MaxDD -19.4% — **PASS**: +1.24pp CAGR, +0.06 Sharpe, +1.59pp MaxDD
- **M12** — top3 momentum-score weighted — CAGR 21.1%, Sharpe 1.23 — FAIL
- **M13** — 50/50 top1/top4 — CAGR 20.8%, Sharpe 1.34 — FAIL
- **M14** — +TLT (9 ETF) — CAGR 18.6%, Sharpe 1.23 — FAIL: universe expansion hurts
- **M15** — +DBC (9 ETF) — CAGR 18.5%, Sharpe 1.17, MaxDD -25.9% — FAIL
- **M16** — +TLT+DBC (10 ETF) — CAGR 16.4%, Sharpe 1.08 — FAIL
- **M17** — drop XLK/VGT/IGV, add XLF/XLI/XLV — CAGR 19.1%, Sharpe 1.24 — FAIL: sector rotation off-tech loses the tech-leadership edge
- **M18** — M17 + TLT + DBC — CAGR 14.0%, Sharpe 0.96 — FAIL
- **M19** — + soft EV gate — CAGR 14.1%, Sharpe 1.19 — FAIL: -7.1pp CAGR
- **M20** — + HY-IG z>1.5 → 60% — CAGR 20.9%, Sharpe 1.37 — FAIL
- **M21** — + VIX>30 → 50% — CAGR 19.8%, Sharpe 1.29 — FAIL
- **M22** — + yield-curve inverted 63d → 70% — CAGR 20.5%, Sharpe 1.33 — FAIL
- **M23** — + signal-disagreement → 70% — CAGR 20.2%, Sharpe 1.32 — FAIL
- **M24** — weekly check, 3pp threshold — CAGR 10.4%, Sharpe 0.67 — FAIL: weekly breaks month-end alignment
- **M25** — weekly check, 5pp threshold — CAGR 10.4%, Sharpe 0.67 — FAIL (same)
- **M26** — defer FOMC week 5d symmetric — CAGR 21.1%, Sharpe 1.32 — FAIL at this spec but pointed to the right mechanism; follow-up M26_post_3d PASSED
- **M27** — defer quad witching 5d — CAGR 20.5%, Sharpe 1.30 — FAIL

## 7.6 Lookback trigger replacements (T01–T10)

Tests whether a rule replaces the ML classifier. All on OPTIMIZED spec.

- **Regime (ML)** — HistGB 66.5% acc — CAGR 23.61%, Sharpe 1.50, MaxDD -12.94% — **PASS / REFERENCE** (99.8th percentile vs random)
- **T01** — VIX > 25 — CAGR 21.57%, Sharpe 1.39, MaxDD -14.53% — FAIL: best rule-based but -0.11 Sharpe
- **T02** — VIX > 20 — CAGR 17.85%, Sharpe 1.15, MaxDD -17.82% — FAIL: fires too often
- **T03** — VIX > 30 — CAGR 21.48%, Sharpe 1.38 — FAIL
- **T04** — SPY 21d rvol > 63d median — CAGR 17.54%, Sharpe 1.15 — FAIL
- **T05** — VIX chg > 5 pts over 21d — CAGR 21.13%, Sharpe 1.38 — FAIL
- **T06** — HY-IG credit z > 1 — CAGR 20.35%, Sharpe 1.32 — FAIL
- **T07** — VIX>25 OR HY-IG z>1 — CAGR 20.18%, Sharpe 1.31 — FAIL
- **T08** — cross-sec 63d disp < 5% — CAGR 15.05%, Sharpe 0.98 — FAIL
- **T09** — top1-top2 gap < 2pp — CAGR 19.94%, Sharpe 1.30 — FAIL
- **T10** — random 28% fire rate (500 runs) — median CAGR 19.14%, Sharpe 1.24 — baseline: classifier sits at 99.8th percentile

## 7.7 FOMC deferral follow-ups

- **M26_5d symmetric** — CAGR 22.01%, Sharpe 1.34, MaxDD -13.80% — FAIL: pick-drift -2.92pp on 9/28 changes
- **M26_3d symmetric** — CAGR 23.41%, Sharpe 1.43, MaxDD -12.94% — CLOSE but not optimal
- **M26_7d / M26_10d** — wider windows — CAGR 21.5/21.9%, Sharpe 1.32/1.41 — FAIL
- **M26b FOMC+CPI week** — CAGR 22.01%, Sharpe 1.34 — FAIL
- **M26c +NFP week** — CAGR 21.81%, Sharpe 1.33 — FAIL
- **M26d +quad witching** — CAGR 21.52%, Sharpe 1.32 — FAIL
- **M26_pre_3d** — defer only pre-FOMC 3d — CAGR 22.69%, Sharpe 1.38, MaxDD -15.28% — FAIL
- **M26_post_3d** — defer only when rebalance lands 0-2d after FOMC, by 3d — CAGR 23.61%, Sharpe 1.50, MaxDD -12.94% — **PASS (final)**. Ex-2018 CAGR 25.75% / Sharpe 1.63 confirms harmless-to-helpful outside the one dependent episode.

## 7.8 Key Takeaways

Read this before attempting to improve the strategy.

1. **Cross-sectional ML ETF selection is a dead end in this universe.**
   16+ experiments across Tier 1, Tier 1B and Tier 2 tried it — none
   beat plain 63d momentum on Sharpe after the 50% haircut. The best
   attempt (ED5 dispersion overlay) missed by 0.01 Sharpe. Every
   direction that feeds a classifier/regressor directly into picks has
   been explored and failed. Stop retrying. Signals that shine in
   cross-validation consistently evaporate in walk-forward — E03's
   14.8% in-sample accuracy and E05's 99% 2020-03 "hit" probability
   that fired on a nothing-month are the representative failure modes.

2. **ML works only as a lookback timer, not as a label predictor.** The
   same HistGB that fails at selection (66.5% acc on 4-class quadrants)
   succeeds at timing 63d↔21d switches at the 99.8th percentile vs
   random (see §2.5, [LOOKBACK_TRIGGER_REPORT.md](results/LOOKBACK_TRIGGER_REPORT.md)).
   This is the *only* surviving ML contribution. The signal is in
   *when* prediction disagrees with current regime, not in the regime
   label — which is why raising accuracy (top-3-feature model, 72.8%)
   makes strategy Sharpe *worse* (1.46 vs 1.50). Do not simplify.

3. **63d is a cliff edge, not a tunable.** `lb_stable = 42` collapses
   Sharpe to 1.13 (-7.2pp CAGR). The cliff is downward only. Blending
   (M05 avg(63,126)) does not insulate — it lands at 22.69%/1.37,
   still below 63d pinned. Treat as non-negotiable (see §2.5, §1).

4. **`cpi_yoy` is load-bearing for drawdown containment, not returns.**
   Removing any one of the top-5 SHAP features leaves strategy Sharpe
   ≥ 1.38 — but removing `cpi_yoy` alone widens MaxDD from -12.94% to
   -18.68% (+5.74pp). Nothing else touches the drawdown profile. CPI
   data continuity deserves first-class monitoring attention (§6.4);
   all other macro feeds are tolerable at the drawdown budget.

5. **Dispersion regime dominates forward expectation, not start date.**
   Test 4's 13pp start-date CAGR range (23.2% from 2012, 36.3% from
   2020) is a dispersion artifact, not fragility. Tercile buckets
   (STRESS Part 2): low-disp 25.0%/Sharpe 1.97, med 25.2%/1.61, high
   20.5%/1.12. Under a regime-rebalanced forward view CAGR converges
   to ~23.5% and Sharpe to ~1.55. Size to this (§8.4), not the
   headline.

6. **The FOMC edge is post-only and mostly one episode.** M26_post_3d
   is asymmetric for a reason — post-only (Sharpe 1.50) beats pre-only
   (1.38) and symmetric (1.43). Mechanism: avoid rebalancing *into* a
   post-decision reaction. Ex-2018 net contribution is +0.58pp CAGR
   and +0.00pp MaxDD — the 2018 episode supplies ~6pp of cumulative
   drawdown absorption on its own. Forward benefit will be lumpy. It
   is still harmless-to-helpful outside 2018 — keep it, but do not
   credit it as systematic return.

7. **Month-end timing is structural alignment, not arbitrary.**
   Mid-month, month-start, and 200 random-day variants all collapse
   Sharpe to ~1.17 (STRESS Part 3). Mechanism: three-way alignment
   between the classifier's month-aligned training folds, the 21d
   forward target window, and month-end ETF-flow dynamics. A refactor
   that breaks any one likely breaks the strategy. Non-negotiable
   (§2.7).

8. **Universe expansion always hurts.** M14-M18 tested adding TLT / DBC
   / sector rotations. Every variant lost ≥2pp CAGR and/or +3pp MaxDD.
   The 8-ETF universe is a ceiling — do not add "diversification"
   ETFs. The tech-led core + GLD/XLE/SHY hedges is exactly calibrated
   to the dispersion regime mix the strategy depends on.

═══════════════════════════════════════════════════════════════
SECTION 8 — KNOWN RISKS AND FORWARD EXPECTATIONS
═══════════════════════════════════════════════════════════════

## 8.1 Data risks

### OECD CLI gap (RESOLVED 2026-04-12: retain with forward-fill + monitoring alert; CFNAI and USPHCI both rejected)

FRED series `USALOLITONOSTSAM` (OECD Composite Leading Indicator, US)
**stopped publishing at the end of 2023-12**. The CORE feature
`activity_features__oecd_cli` is currently forward-filled from the
stale December 2023 value — as of this document's date (2026-04-12)
that is ~28 months stale, far outside the 45-trading-day forward-fill
limit in §4.1.2.

**Resolution (v1.1).** The obvious replacement candidate — Philadelphia
Fed / FRB `USSLIND` (State Coincident Leading Index, proxied here as a
national leading index) — was **evaluated and rejected**:

1. **USSLIND is itself discontinued.** FRED hosts data only through
   **2020-02-01** (458 monthly observations, 1982-01 → 2020-02). The
   series has not been updated in six years; it cannot replace a
   feature that only went stale in 2023-12. Verified by direct fetch
   of `https://fred.stlouisfed.org/graph/fredgraph.csv?id=USSLIND`.
2. **Correlation on the usable overlap (2006-01 → 2019-12, 151
   monthly points) is weak anyway:** Pearson 0.52 on levels, 0.63 on
   3-month changes, 0.72 on 12-month changes. All below the 0.85
   adoption threshold even before the availability problem.

**Retained decision: keep `oecd_cli` in CORE with forward-fill,
pending a Test-3a-style ablation.** Test 3a
([STRESS_TEST_REPORT §3a](results/STRESS_TEST_REPORT.md)) did not
include `oecd_cli` — it sits in Tier C of §5.3, not top-5 — so the
marginal impact of dropping it has not yet been measured. Based on
analogous Tier-C ablations in
[FEATURE_IMPORTANCE_REPORT.md](results/FEATURE_IMPORTANCE_REPORT.md)
we expect the impact to be small (single-digit bps on Sharpe), but
this is an inference, not a measurement.

**Forward candidates tested 2026-04-12 (both rejected):**

- **CFNAI** (`CFNAI`, Chicago Fed National Activity Index). Monthly,
  currently publishing through **2026-02**. Correlations with
  `oecd_cli` on the 2000-02 → 2023-12 overlap (258 monthly points):
  levels **0.297**, 3m-change **0.360**, 12m-change **0.322**. Max
  0.36, far below the 0.70 retest floor and the 0.85 adoption
  threshold. **REJECTED.** CFNAI is a broader activity diffusion
  index and its dynamics simply do not track the OECD amplitude-
  adjusted leading composite at any horizon used by the classifier.
- **USPHCI** (`USPHCI`, US Philadelphia Fed Coincident Index).
  Monthly, currently publishing through **2025-12**. Correlations
  on the same overlap: levels **0.013** (USPHCI is a rising level
  index, oecd_cli is amplitude-adjusted around 100), 3m-change
  **0.642**, 12m-change **0.348**. Max 0.64, below the 0.70 floor.
  **REJECTED.** Coincident rather than leading — the dynamics
  decouple from oecd_cli across most of the sample.
- **OECD website direct CSV** (`stats.oecd.org`) — not pursued; would
  require a new fetcher. Scoped as last-resort future work.

**Resolution.** Keep `oecd_cli` in CORE with forward-fill. The staleness
risk is explicitly accepted: it is a Tier-C feature (§5.3, not top-5)
and ablation evidence from analogous Tier-C features
([FEATURE_IMPORTANCE_REPORT.md](results/FEATURE_IMPORTANCE_REPORT.md))
suggests single-digit-bps Sharpe impact. The current canonical canary
(23.61% / 1.50 / -12.94%) is computed **with** the forward-filled
oecd_cli; as long as the canary holds, the feature is not hurting
production.

**Monitoring (§6, alerts):** `oecd_cli` age > 90 days → WARNING,
> 365 days → recurring WARNING (but NOT an auto-fallback trigger —
ML classifier tolerates this Tier-C feature going stale). See
`configs/alerts.yaml` and `src/risk/monitoring.py::check_oecd_age`.

**Reproducibility:** the correlation tests are scripted for human
re-run at
[`scripts/test_usslind_swap.py`](scripts/test_usslind_swap.py) and
[`scripts/test_cfnai_swap.py`](scripts/test_cfnai_swap.py) — re-run
periodically in case CFNAI/USPHCI dynamics shift or FRED resumes OECD
CLI publishing.

### ISM PMI proxy (verified; flag in monitoring)

The CORE feature `activity_features__ism_pmi` is **not the true ISM
Manufacturing PMI** — ISM series are paywalled. The implementation is
a composite of two public FRED series, rescaled to the PMI 50-center:

- **FRED `INDPRO`** — Industrial Production Index (monthly, ~15d lag)
- **FRED `TCU`** — Total Capacity Utilization (monthly, ~15d lag)

The z-composite is built in
[src/features/macro_features.py](src/features/macro_features.py) and
flagged as `PROXY` in [data/DATA_CATALOG.md](data/DATA_CATALOG.md) at
the row for `ism_manufacturing_pmi.parquet`. Both `INDPRO` and `TCU`
are confirmed in the FRED fetcher catalog
([fred.py L162-163](src/data/fetchers/fred.py#L162-L163)).

**Implication.** Any analysis quoting "PMI > 50" is using the proxy's
50-center, not an actual ISM release. For production:

- Do **not** replace the proxy with a different series silently —
  the classifier was trained against this exact composite and the
  quadrant labels in §2.5 use the proxy's threshold.
- If a licensed ISM feed becomes available, **retrain the classifier
  from scratch** before swapping; the label distribution will shift.
- Monitor INDPRO and TCU release dates as first-class dependencies
  (§6.4); any revision cascades through the PMI proxy.

### Other data risks

- **Margin debt via FRED Z.1** (`BOGZ1FL663067003Q`) — quarterly, ~60d
  publication lag. FINRA direct is Akamai-blocked. If Z.1 stops
  publishing the feature goes stale; bounded impact because
  `positioning_margin_debt_per_spy_px` is Tier C.
- **Rail traffic proxy** — `RAILFRTCARLOADSD11` is the FRED
  substitute for AAR (PDF-only). Tier A (-1.88pp CAGR on ablation)
  but drawdown-neutral.
- **Yahoo Finance `^VIX`** — the VIX ticker is `^VIX` (with caret),
  confirmed in [phase1_download.py L27](scripts/phase1_download.py#L27).
  `VIXY` is a 1x ETF and `UVXY` is 2x leveraged — neither is the
  classifier input. Classifier uses spot `^VIX` close.

## 8.2 Regime risks

- **Low-dispersion → high-dispersion transition.** If the forward
  regime mix shifts toward high-dispersion (XLE/GLD-led divergence)
  Sharpe drops from ~1.6 to ~1.12 (STRESS Part 2). Excess return stays
  positive but risk-adjusted edge halves. This is the #1 forward risk
  and it is not controllable.
- **Calm bull market (VIX < 15).** -30.3pp excess vs SPY in 65/188
  months (Test 9). Multi-quarter underperformance is expected;
  longest observed 13 months (§3.5).
- **Classifier regime drift.** Walk-forward accuracy 0.70 → 0.57 →
  0.43 at 1y / 3y / 5y of no retraining (Test 3c). Retrain cadence
  of 12 months minimum, quarterly preferred (§5.5).
- **SMA gate whipsaw.** The -4% buffer has held in backtest but a
  sustained market near `SMA200 ± 4%` would increase turnover and
  drag. Monitor the gate-fire rate (§6.4 target: 5-15% of rebalances
  per year).

## 8.3 Execution / live-trading risks

- **Turnover is high.** Annual turnover ~12.3x (≈full rotation per
  month). Break-even transaction cost vs SPY is ~55.8 bps; the 20 bps
  budget leaves Sharpe 1.33 and +5.2pp vs SPY (Test 6). Above 30 bps
  the edge compresses rapidly. Execute in liquid windows only; favour
  MOC or TWAP into the close.
- **Top-1 concentration.** Realized max single-name weight ~67%
  (§3.2). Account-level leverage and cash buffer must accommodate
  this without forced trims.
- **Corporate actions.** Splits, distributions, and ticker changes
  are not modeled at the decision layer — a split-adjustment bug in
  the Yahoo feed could flash a spurious momentum rank. The adj-close
  consistency check (§4.4) catches this, but alert fatigue is a risk.
- **FOMC calendar drift.** If the Fed schedule changes (extra or
  cancelled meeting) and the calendar is not updated, M26 deferrals
  mis-fire. Degradation is graceful (strategy reverts to plain
  month-end) but the +1.4pp CAGR / -6.5pp MaxDD contribution is lost.
- **No intra-month stop.** A flash crash between month-ends is
  unprotected — accepted design choice (§3.3). Pre-commit to it.
- **Data vendor outages.** Yahoo v8 has no SLA. Production needs a
  secondary price feed (see §9.4 step 4).

## 8.4 Forward return scenarios

Base case and stress envelopes. Headline numbers reproduce the
canonical `OPTIMIZED.json` run; regime-conditional numbers are from
[STRESS_TEST_REPORT Part 2](results/STRESS_TEST_REPORT.md) and Test 8.

| Scenario | CAGR | Sharpe | MaxDD | Source / note |
|---|---|---|---|---|
| Headline (2008-2025 realized) | 23.61% | 1.50 | -12.94% | backtest; reference only |
| Regime-rebalanced base case | ~23.5% | ~1.55 | -13 to -15% | 1/3 weight per dispersion tercile — **use as forward expectation** |
| Low-dispersion regime (tight cluster) | 25.0% | 1.97 | — | 64/190 months; 2023-2025 era; +11.2pp vs SPY |
| Medium-dispersion regime | 25.2% | 1.61 | — | 63/190 months; +17.8pp vs SPY (strongest excess) |
| High-dispersion regime (XLE/GLD vs tech) | 20.5% | 1.12 | — | 63/190 months; +5.1pp vs SPY; risk-adjusted edge halves |
| Monte Carlo 5th-percentile | 16.1% | 1.06 | **-28.8%** | 10,000 × 180mo; size to this tail |
| Monte Carlo 95th-percentile | 31.7% | — | -11.8% | do not plan for |
| P(3y cumulative < 0) | 0.64% | — | — | Test 8 |
| P(underperform SPY over 5y) | 22.1% | — | — | Test 8 |
| P(CAGR > 15% over 10y) | 93.9% | — | — | Test 8 |
| Longest SPY-underperf streak | — | — | 13 months | Test 7 (§3.5) |
| 20 bps cost case | 20.6% | 1.33 | -13.4% | Test 6 |
| Classifier stale 5y | — | — | — | acc 0.43 (near random); strategy effectively reverts to 63d-always behavior |

**Bottom line for position sizing.** Do not size to 23.61%/1.50. Size
to **~23.5% CAGR, ~1.55 Sharpe, -29% tail MaxDD**. If the forward
regime mix tilts high-dispersion, expect ~20% CAGR / 1.1 Sharpe for
the duration.

═══════════════════════════════════════════════════════════════
SECTION 9 — PRODUCTION BUILD PLAN
═══════════════════════════════════════════════════════════════

## 9.1 Module structure

Proposed layout for the live-trading build. Research code in
`scripts/` and `src/` is kept as reference; production code lives in
a separate tree that imports only from `src/data/fetchers`,
`src/features`, and `src/model`.

```
production/
├── config/
│   ├── strategy.yaml        # pinned params (see 9.2)
│   ├── universe.yaml        # 8-ETF list, SHY as cash
│   ├── data_sources.yaml    # FRED series IDs, Yahoo tickers
│   ├── fomc_calendar.yaml   # decision dates, maintained manually
│   └── feature_set.yaml     # copy of configs/feature_sets.yaml::core
├── src/
│   ├── data_refresh.py      # wraps src/data/fetchers/*, writes data/clean/
│   ├── feature_build.py     # wraps src/features/*, rebuilds master panel
│   ├── classifier.py        # load joblib, predict, version-check
│   ├── decision.py          # Section 2.8 step-by-step in code
│   ├── sizer.py             # inverse-vol weighting (§2.4)
│   ├── gate.py              # SMA200 trend gate (§2.6)
│   ├── fomc.py              # post-3d deferral logic (§2.7)
│   ├── execution.py         # broker adapter, MOC submit
│   └── monitor.py           # §6.x alert checks
├── tests/
│   ├── test_canary_regression.py   # see 9.3 item 1
│   ├── test_gate_boundary.py
│   ├── test_fomc_edge_cases.py     # late-Jan FOMC edge (§2.9)
│   ├── test_sizer_determinism.py
│   └── test_classifier_fallback.py
├── models/
│   ├── regime_classifier_current.joblib   # symlink to active version
│   ├── regime_classifier_vYYYYqQ.joblib
│   └── regime_classifier_vYYYYqQ_metadata.json
├── logs/
│   ├── trade_log.parquet
│   ├── decision_log.parquet     # per-rebalance snapshot
│   └── alerts/
└── run_rebalance.py          # entry point, cron-driven on month-end
```

## 9.2 Config files

Nothing that affects backtest numbers lives in code. Strategy config
is a single pinned YAML that externalizes every parameter named in
Sections 2 and 5:

```yaml
# production/config/strategy.yaml
lookback_stable: 63            # non-negotiable (§2.5, §1)
lookback_transition: 21        # non-negotiable (§2.5)
top1_leg_weight: 0.50
top3_leg_weight: 0.50
top3_weighting: inverse_vol    # M11 (§2.4)
vol_window: 63                 # trading days
sma_window: 200                # SMA200 (§2.6)
sma_threshold: -0.04           # -4% buffer
rebalance_schedule: last_trading_day_of_month    # non-negotiable (§2.7)
fomc_post_days: 2              # window = [FOMC, FOMC+2td] (§2.7)
fomc_deferral_days: 3          # M26_post_3d
classifier_path: models/regime_classifier_current.joblib
classifier_fallback: lookback_stable_always      # §3.4
core_features_yaml: configs/feature_sets.yaml
core_features_key: core
retrain_cadence_months: 3      # quarterly; annual minimum
retrain_disable_accuracy: 0.55 # 2-window sustained (§6.5)
cost_budget_bps: 20            # degradation budget (§3.4)
monte_carlo_p05_max_dd: -0.288 # sizing anchor (§3.3)
```

```yaml
# production/config/universe.yaml
etfs: [SOXX, QQQ, XLK, VGT, IGV, XLE, GLD, SHY]
cash_proxy: SHY
reference: SPY                 # for SMA200 gate
extra_for_features:            # §4.1.1
  [TLT, DBC, XLF, XLI, XLV, AGG, EEM, IWM]
```

## 9.3 Testing requirements

Every merge to `production/` must pass:

1. **Canary regression test** (non-negotiable). Run the full
   walk-forward backtest (2010-04 → 2026-03, 188 months — the complete
   WF output, NOT a calendar filter; canonical invocation
   `scripts/run_backtest.py` with no `--start`/`--end`) on every code
   change. Assert:
   - CAGR within **0.5pp of 23.61%** (allowed 23.11% – 24.11%)
   - Sharpe within 0.05 of 1.50
   - MaxDD within 1pp of -12.94%
   
   Implementation: `tests/test_canary_regression.py` loads
   `results/experiments/OPTIMIZED.json` as canonical and re-runs the
   harness. **If it drifts, something changed** — do not rationalize,
   find the delta.

2. **Determinism test.** Two consecutive runs of the same date must
   produce byte-identical decision_log rows (modulo timestamps).
   Random seeds in classifier/splitter are pinned at `random_state=0`
   (§5.2).

3. **Fallback test.** Delete the model joblib → decision layer must
   emit a "classifier unavailable → 63d fallback" decision without
   crashing and produce a valid trade plan (§3.4).

4. **Edge case tests.** Every row in §2.9 needs a test:
   - tie in momentum returns → chosen tiebreaker fires
   - one ETF's price feed missing → exclusion works
   - classifier returns equal probabilities → fall back to 63d
   - deferred rebalance lands on next month-end → skip-or-execute rule
   - FRED macro stale > 60 days → fall back to 63d-always
   - FOMC calendar missing → no deferral, no crash

5. **Data integrity test.** Run the §4.4 checks against a fresh
   `data/clean/` pull; schema / staleness / adj-close consistency
   must all pass before the decision layer runs.

6. **Classifier retrain repro.** A fresh retrain on a frozen data
   snapshot must reproduce the prior joblib's walk-forward accuracy
   within ±1pp (catches silent feature-pipeline drift).

## 9.4 Deployment sequence

**Step 0 — OECD CLI gap (RESOLVED 2026-04-12, downgraded from
BLOCKER to monitoring WARNING).** All three viable replacements have
been tested and rejected: USSLIND (itself discontinued 2020-02, max
corr 0.72), CFNAI (max corr 0.36), USPHCI (max corr 0.64). None
clear the 0.70 retest floor, let alone the 0.85 adoption threshold.
**Decision:** retain `oecd_cli` in CORE with forward-fill. The
canonical canary (23.61% / 1.50 / -12.94%) is computed with this
forward-filled Tier-C feature, so live deployment is not blocked on
it. Staleness is tracked as a WARNING-level alert
(`configs/alerts.yaml::oecd_cli_age`, >90d → WARNING, >365d →
recurring WARNING) and checked by
`src/risk/monitoring.py::check_oecd_age`. Re-run
`scripts/test_cfnai_swap.py` and `scripts/test_usslind_swap.py`
quarterly in case FRED resumes publication or dynamics shift. See
§8.1.

**Step 1 — Freeze the canonical artifact.** Copy
`results/experiments/OPTIMIZED.json` to
`production/reference/canonical.json`. This is the bar the canary
test checks against. Freeze the model joblib and feature set YAML
alongside.

**Step 2 — Build production tree.** Scaffold `production/` per §9.1,
wire tests per §9.3. Canary test must pass before moving on.

**Step 3 — Data pipeline dry run.** Run the full data refresh +
feature build + classifier inference path from cold on a scratch
machine. Verify master panel fingerprint matches the reference and
every CORE feature is within its staleness budget (§4.1.2).

**Step 4 — Broker + secondary feed integration.** Pick a broker with
MOC execution support. Configure a secondary price feed (IEX Cloud,
Polygon, or a second yfinance-compatible mirror) as the fallback per
§3.4.

**Step 5 — Paper trading (minimum 3 months, preferably 6).** Run the
live rebalance loop against a paper account at 1x sizing. Log every
decision; diff against a back-fill backtest for the same months.

**Step 6 — Paper trade review.** Check:
- no decision-layer exceptions
- alert thresholds calibrated (not too chatty, not silent)
- execution slippage vs MOC benchmark
- trade log matches decision log

**Step 6.5 — Paper vs backtest reconciliation (BLOCKER, between
Steps 6 and 7).** Before scaling or going live: verify paper trading
monthly returns are **within 2pp of backtest for the same months**.
Reconcile any month that is off by more. Typical causes: (a)
data-timing differences (Yahoo end-of-day vs intraday pull), (b)
execution slippage vs MOC assumption, (c) rebalancing logic mismatch
(e.g. FOMC deferral not firing). **Do not advance to Step 7 with
unresolved deltas > 2pp.**

**Step 7 — Live deployment at reduced size.** Start at 25% of target
capital. Run for one full quarter, hit a classifier retraining cycle
while live. Verify the canary still passes with the fresh classifier.

**Step 8 — Scale to target.** Only after Step 7 closes clean. Re-read
the §3.5 pre-commitment statement aloud. Size to the Monte Carlo
tail (-28.8%), not headline (-12.9%).

**Step 9 — Ongoing.** Quarterly retrain cadence (§5.5). Monthly
report per §6.2. Quarterly performance vs forward expectation per
§6.3. Annual audit of this document against the running system.

═══════════════════════════════════════════════════════════════
SECTION 10 — REPLICATION CHECKLIST
═══════════════════════════════════════════════════════════════

Step-by-step to reproduce the strategy from scratch.

## 10.1 Environment

- **Python**: 3.10+ (the codebase uses match statements and
  `from __future__ import annotations` freely; 3.10 is the floor).
- **Key packages** (from
  [requirements.txt](requirements.txt) — minimum versions):
  - `numpy >= 1.26.0`
  - `pandas >= 2.1.0`
  - `scipy >= 1.12.0`
  - `scikit-learn >= 1.4.0` (classifier + preprocessing)
  - `pyarrow >= 14.0.0` (parquet I/O)
  - `yfinance >= 0.2.36` (price fetcher)
  - `fredapi >= 0.5.0` (macro fetcher; `pandas-datareader` as fallback)
  - `pyyaml >= 6.0.1` (configs)
  - `pandas-market-calendars >= 4.4.0` (trading-day arithmetic)

## 10.2 Yahoo Finance tickers (exact strings)

Confirmed via [scripts/phase1_download.py](scripts/phase1_download.py)
and [data/DATA_CATALOG.md](data/DATA_CATALOG.md).

| Purpose | Ticker | Notes |
|---|---|---|
| Strategy universe | `SOXX`, `QQQ`, `XLK`, `VGT`, `IGV`, `XLE`, `GLD`, `SHY` | 8 ETFs |
| Reference (SMA200 gate) | `SPY` | |
| Feature tickers (vol/atr/returns inputs) | `TLT`, `DBC`, `XLF`, `XLI`, `XLV`, `AGG`, `EEM`, `IWM` | |
| Volatility index | `^VIX` | **`^VIX` with caret** — not `VIX`, not `VIXY` (which is a 1x ETF), not `UVXY` (2x leveraged). The classifier uses spot ^VIX close. |

Yahoo field required: **Adjusted Close** (`Adj Close`, dividend and
split adjusted). Do not use unadjusted close.

## 10.3 FRED series IDs (exact)

Confirmed against
[src/data/fetchers/fred.py L130-L220](src/data/fetchers/fred.py#L130-L220)
SERIES catalog. All macro CORE features derive from this set.

| CORE feature | FRED series ID | Frequency | Note |
|---|---|---|---|
| `inflation_features__cpi_yoy` | `CPIAUCSL` | monthly | 12m % change |
| `inflation_features__cpi_mom` | `CPIAUCSL` | monthly | 1m % change |
| `inflation_features__breakeven_5y` | `T5YIE` | daily | |
| `inflation_features__breakeven_10y` | `T10YIE` | daily | |
| `activity_features__ism_pmi` | `INDPRO` + `TCU` composite | monthly | **PROXY — not true ISM**; see §8.1. Implemented in [src/features/macro_features.py](src/features/macro_features.py). The classifier was trained against this proxy; do not silently substitute licensed ISM. |
| `activity_features__capacity_utilization` | `TCU` | monthly | |
| `activity_features__initial_claims_4wma` | `ICSA` | weekly | 4-week MA at feature-build |
| `activity_features__oecd_cli` | `USALOLITONOSTSAM` | monthly | **STOPPED PUBLISHING 2023-12.** Retained with forward-fill; staleness accepted (§8.1, resolved 2026-04-12). Replacements tested + rejected: USSLIND (discontinued), CFNAI (max corr 0.36), USPHCI (max corr 0.64). Tier-C feature; canonical canary is computed with fwd-filled value. Monitored via `check_oecd_age` (WARNING >90d). |
| `activity_rail_traffic__rail_traffic_ma4w` | `RAILFRTCARLOADSD11` | monthly | Substitute for AAR (PDF-only) |
| `consumer_features__consumer_credit_yoy` | `TOTALSL` | monthly | 12m % change |
| `positioning_margin_debt_per_spy_px__margin_debt_per_spy_px` | `BOGZ1FL663067003Q` | quarterly | Z.1 Flow of Funds; FINRA direct is Akamai-blocked |
| `cross_asset_oil_gold__oil_gold_ratio` — WTI leg | `DCOILWTICO` | daily | WTI spot |
| `cross_asset_oil_gold__oil_gold_ratio` — Gold leg | `GOLDAMGBD228NLBM` | daily | London AM gold fix |

Additional FRED series used in the broader feature panel (non-CORE
but pulled by `fred.py`): see `SERIES` catalog at
[fred.py:130-220](src/data/fetchers/fred.py#L130-L220).

## 10.4 FOMC calendar

Source: `federalreserve.gov` press-release archive. Pull the list of
FOMC meeting decision dates (roughly 8/year). Store as a YAML list of
`YYYY-MM-DD` strings. Maintain manually or scrape annually. See
§2.7, §4.1.4.

## 10.5 Build steps

1. `git clone` the repo; `pip install -r requirements.txt`.
2. Configure FRED API key in `.env` (`FRED_API_KEY=...`).
3. Run `python scripts/phase1_download.py` to fetch prices.
4. Run `python scripts/phase2_*` to fetch macro and alternative data.
5. Run `python scripts/phase3_*` to build clean panels.
6. Run `python src/features/assemble_master_panel.py` to build
   `data/features/master_panel.parquet`.
7. Validate the CORE feature list matches
   `configs/feature_sets.yaml::core` (**50 entries** — see §5.3).
8. Run the classifier walk-forward training harness in
   `src/model/walk_forward.py`.
9. Run `scripts/model/stress_harness.py --validate` — must reproduce
   23.61% / 1.50 / -12.94% exactly. If it does, the replication is
   good.

**Canonical window clarification.** The canary numbers
(23.61% / 1.50 / -12.94%, n=188) reflect the full walk-forward
**output** window (~2010-04 → 2026-03), which is what the WF splitter
emits given the current master panel and `min_train_months=60`. This
is NOT a calendar filter — `scripts/run_backtest.py --start None
--end None` (i.e. defaults, no explicit window) is the canonical
invocation. Passing any narrower `--start`/`--end` slices the WF
output and will *not* reproduce the canonical stats.

## 10.6 Worked numerical example

**Pick: rebalance date 2019-01-25 (inside the Q4-2018 drawdown
window, DD#1 in §3.3).** This month sits immediately inside the
2018-01-25 → 2019-03-25 drawdown envelope (STRESS Test 7), SPY is
just recovering from its December low so the SMA200 gate is near its
threshold, and FOMC deferrals cluster nearby (3 deferrals across the
full DD window per §3.4).

> **Illustrative — not from a saved per-rebalance log.** The reports
> archive aggregate outputs (annual returns, drawdown windows,
> deferral counts) but not per-rebalance feature-level traces. Values
> below are representative of the month's known state per the
> sources cited, with realistic numbers for vol / ranking / weights.
> **Do not cite as exact numbers from the canonical run.**

**Inputs on 2019-01-25 (close):**

- Rebalance date: 2019-01-25 (last trading day of January 2019)
- SPY close: ~263 (post-Dec-2018 rally)
- SPY 200d SMA: ~275
- SPY distance from SMA200: (263-275)/275 ≈ **-4.4%**
- FOMC decisions nearby: most recent was 2018-12-19; next is
  2019-01-30 (*after* this rebalance, not before) → no M26 post-3d
  window applies to this rebalance date (the deferral fires on
  2019-02-28 instead; cf. M26_ANALYSIS Q4-2018 aggregate).

**Step 1 — FOMC deferral check (§2.8 step 1).** Most recent FOMC
2018-12-19. Window `[D, D+2 trading days]` does not contain
2018-12-19. **No deferral.**

**Step 2 — Data refresh (§2.8 step 2).** Pull prices for 8 ETFs +
SPY + EXTRA tickers through 2019-01-25 close. Latest CPI YoY release:
December 2018 CPI released 2019-01-11, YoY = **1.9%**. Latest PMI
proxy: December 2018 composite → PMI proxy ≈ **54** (INDPRO above
trend, TCU ~78.8).

**Step 3 — SMA200 gate (§2.6, §2.8 step 3).** Distance -4.4% <
-0.04. **Gate FIRES.** Top-1 leg → SHY 100%. Top-3 leg still
computed normally.

**Step 4 — Regime classifier (§2.5, §2.8 step 4).**
- Current regime (from Step 2): PMI proxy > 50 (high growth),
  CPI YoY 1.9% < 3% (low inflation) → **HG/LI**.
- Classifier prediction for 2019-02-25 (21td fwd): **HG/LI**.
- `predicted == current` → stable → **lookback = 63 trading days.**

**Step 5 — Compute 63d returns (§2.2, §2.8 step 5)** over the window
2018-10-24 → 2019-01-25 (Q4 sell-off + January rally; moderate
sector dispersion):

| ETF | ~63d return |
|---|---|
| GLD | +6.8% |
| IGV | +4.5% |
| QQQ | +3.2% |
| XLK | +2.8% |
| VGT | +2.5% |
| SHY | +0.4% |
| SOXX | -1.5% |
| XLE | -6.2% |

**Step 6 — Rank (§2.3, §2.8 step 6).** Descending:
`GLD > IGV > QQQ > XLK > VGT > SHY > SOXX > XLE`.

- Raw Top-1: **GLD** (before SMA override)
- Top-3: **GLD, IGV, QQQ**

**Step 7 — Position sizing (§2.4, §2.8 step 7).**

- **Top-1 leg (50%)**: SMA gate FIRED → **SHY 50%** (override, §2.6).
- **Top-3 leg (50%)**: inverse-vol over `{GLD, IGV, QQQ}` with
  63d annualized realized vols GLD≈11%, IGV≈22%, QQQ≈19%.
  - `inv_vol`: GLD 9.09, IGV 4.55, QQQ 5.26 → sum 18.90
  - shares: GLD 0.481, IGV 0.241, QQQ 0.278
  - × 0.50: **GLD 24.1%, IGV 12.0%, QQQ 13.9%**

**Final weights** (the SMA-overridden top-1 leg goes to SHY; the
top-3 leg allocates normally without folding in the top-1 allocation,
because the top-1 leg has been forcibly reassigned):

- **SHY: 50.0%**
- **GLD: 24.1%**
- **IGV: 12.0%**
- **QQQ: 13.9%**

Sum 100.0%. Effective equity exposure ≈ 50% (top-3 leg only). This
is the "defensive" month profile — roughly half in cash during the
worst of the Q4-2018 aftermath, which is exactly the M26 + SMA-gate
mechanism §3.1 is built around.

**Step 8 — Execute (§2.8 step 9).** `target − current`, submit as
MOC orders.

**Step 9 — Log (§2.8 step 10).** Decision log record:

```
{date: 2019-01-25,
 current_regime: HG/LI,
 predicted_regime: HG/LI,
 lookback_used: 63,
 top1_raw: GLD,
 top3_raw: [GLD, IGV, QQQ],
 sma_distance: -0.044,
 sma_gate_fired: true,
 fomc_deferred: false,
 target_weights: {SHY: 0.500, GLD: 0.241, IGV: 0.120, QQQ: 0.139}}
```

For the *next* month (2019-02-28), the FOMC on 2019-01-30 lands in
the `[D, D-2td]` preceding window at end-February, and M26_post_3d
fires — which is part of the aggregate "3 deferrals across the
2018-01-25 → 2019-03-25 DD window" reported in STRESS_TEST Test 7.
