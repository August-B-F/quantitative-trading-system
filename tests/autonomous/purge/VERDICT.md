# VERDICT — What to ship

## Ship the ROBUST STACK

**Stats**: 29.80% CAGR / **1.92 Sharpe** / -12.84% MaxDD

**6 surviving layers** (out of 10 in P59):
1. **L1** — Drop VGT and XLK from universe (6-ETF stable: SOXX, QQQ, IGV, XLE, GLD, SHY)
2. **L3** — Classifier confidence gate at argmax proba ≥ 0.40
3. **L4** — Rank-aggregation momentum signal (weights 42:1, 63:3, 126:1) replacing pure 63d
4. **L5** — Regime-conditional transition universe: add TLT, AGG, XLV, XLF when classifier proba ≥ 0.50
5. **L6** — Classifier trained on CORE-50 + 7 credit/yield-curve/copper-gold features
6. **L9** — FULL boost: when trail9m return > +30% OR SPY 63d return > +12%, set top1 weight = 0.82

**Remove everything else**: no 62/38 split (use canonical 50/50), no FOMC window tightening, no self-DD trigger, no warm boost.

## Why ship Robust, not Full P59

The champion P59 (30.73/1.88/-12.66) had 10 layers. Four of them (L2, L7, L8, L10) were added to maximize full-sample CAGR. The purge tests show those four:

- **L2 (62/38 split)**: removing it *improves* Sharpe. Pure CAGR-chase.
- **L7 (FOMC tightening)**: -0.009 Sharpe loss when removed (dead weight). Fragile parameters.
- **L8 (DD trigger)**: -0.018 Sharpe (dead weight). Random-timing test shows only 76th percentile — random dates do nearly as well.
- **L10 (warm boost)**: -0.002 Sharpe (pure noise). 69th-percentile timing (below median random).

Together they push CAGR from 29.80 to 30.73 (+0.93pp) but Sharpe drops from 1.92 to 1.88 (-0.04). And the bootstrap comparison of Robust vs Full P59 is t=-1.22 (not statistically significant) — the extra CAGR is indistinguishable from noise.

Most telling: **Robust has +0.05 higher Sharpe in Period B (2018-2026)** than Full P59 (1.802 vs 1.750). Period B is the OOS-like half. The stripped layers were *actively hurting* the second half while looking good on full-sample CAGR. Classic overfitting.

## Honest answer to: how much of P59's improvement was real?

Full P59 vs canonical: **+7.12pp CAGR, +0.38 Sharpe**.
Robust vs canonical: **+6.19pp CAGR, +0.42 Sharpe**.

So of the +7.12pp CAGR improvement:
- **+6.19pp (87%) is load-bearing, robust alpha** (layers L1, L3, L4, L5, L6, L9).
- **+0.93pp (13%) is concentration leverage** (layers L2, L7, L8, L10) that doesn't improve Sharpe or per-half performance.

Of the +0.38 Sharpe improvement:
- **+0.42 Sharpe is the robust real gain.**
- **-0.04 Sharpe is the overfit layers dragging.**

In Sharpe terms, removing the overfit layers makes the strategy *strictly better*. The 30.73% CAGR number was misleading — it came from leveraging the robust stack slightly harder, not from additional alpha.

## What to document in production

The Robust stack has a clean story:
1. **Universe trim** (L1): drop redundant tech names to reduce correlation drag.
2. **Classifier with credit/yield-curve features** (L6): adds macro/credit regime awareness beyond CPI/PMI.
3. **Classifier confidence gate** (L3): only switch to fast lookback when model is confident.
4. **Rank-aggregation signal** (L4): combine 42d/63d/126d ranks with 63d dominant. The single biggest alpha source.
5. **Regime-conditional transition universe** (L5): when classifier flags macro transition, open the universe to defensive options (TLT, AGG, XLV, XLF).
6. **Equity-momentum boost** (L9): when trailing 9-month return is strong OR SPY 3-month return is strong, concentrate top-1 at 82%. Increases leverage during confirmed bull regimes.

All six layers have:
- Load-bearing Test 1 ablation impact OR in-stack positive rebuild impact
- Either era-neutral or era-skewed but net positive
- Timing significance (where applicable) from random-timing test
- Robust parameter neighborhoods (where applicable)

## One-line answer

**Ship Robust stack (29.80/1.92/-12.84). Lose 0.93pp CAGR, gain 0.04 Sharpe and statistical credibility. Forward floor +1.79pp/yr annualized (95% CI lower bound).**
