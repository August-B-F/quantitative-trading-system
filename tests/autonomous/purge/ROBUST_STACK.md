# ROBUST STACK — the final answer

## Surviving layers (6 of 10)

| Layer | Description | Evidence |
|-------|-------------|----------|
| **L1** | Drop VGT and XLK from universe (6-ETF stable [SOXX,QQQ,IGV,XLE,GLD,SHY]) | Test 1: load-bearing (ΔSh -0.159). Test 2: era-skewed (helps B +0.232, slightly hurts A). Kept because removing it costs the most of any single layer. |
| **L3** | Classifier confidence gate at max_proba ≥ 0.40 for regime switch | Test 1: marginal (ΔSh -0.025). Test 5: in-stack still adds +0.024 Sharpe. Marginal but stack-positive. |
| **L4** | Rank-aggregation momentum signal (42:1, 63:3, 126:1) replacing pure 63d | **THE KEY LAYER.** Test 1: -0.143. Test 2: +0.117 A / +0.100 B (only layer that clearly helps BOTH halves). Test 4: all parameters smooth. The real alpha. |
| **L5** | Regime-conditional transition universe (+TLT, +AGG, +XLV, +XLF when classifier proba ≥ 0.50) | Test 1: -0.082. Test 3: 100th percentile timing — classifier transitions genuinely matter, not random. Test 4: L5_tier smooth. |
| **L6** | Classifier CORE-50 + 7 credit/yield-curve/copper-gold features | Test 1: -0.114. Era-skewed (Test 2: helps A +0.370, slight B drag -0.030). Kept because load-bearing overall even if A-biased. |
| **L9** | FULL boost trigger (trail9m > +30% OR SPY 63d > +12% → top1 = 0.82) | Test 1: -0.015 (marginal). Test 3: 97.4th percentile timing (real signal). Test 5: in-stack adds +0.031 Sharpe. The only Kelly-style layer that survived. |

## Rejected layers (4 of 10)

| Layer | Why rejected |
|-------|--------------|
| **L2** (62/38 split) | **Test 1: removing it IMPROVES Sharpe by +0.054**. Test 4: every neighborhood value worse than no-L2 baseline. Pure CAGR-chase at the cost of Sharpe. |
| **L7** (tightened FOMC window) | Test 1: -0.009 Sharpe (dead weight). Test 4: fragile parameters — only the exact (0,1,4) helps. Overfit. |
| **L8** (self-DD trigger at 3m/-2% → 0.40) | Test 1: -0.018 (dead weight). Test 3: 76th percentile timing (random dates do nearly as well). Test 5: in-stack adds only +0.002 Sharpe. |
| **L10** (warm boost at 6m/+25% OR SPY 21d/+10% → 0.70) | Test 1: -0.002 (pure noise). Test 3: 69th percentile timing — below median. Test 4: all values give 1.882-1.884 (no signal). Pure noise. |

## Robust stack stats

| Metric | Canonical | Robust | Full P59 |
|--------|-----------|--------|----------|
| CAGR | 23.61% | **29.80%** | 30.73% |
| Sharpe | 1.50 | **1.92** | 1.88 |
| MaxDD | -12.94% | -12.84% | **-12.66%** |
| Period A Sharpe | 1.547 | 2.255 | **2.278** |
| Period B Sharpe | 1.547 | **1.802** | 1.750 |
| Period A MaxDD | -10.11% | **-5.33%** | -5.75% |
| Period B MaxDD | -12.66% | -12.84% | **-12.66%** |

**Robust wins on Sharpe, on Period B Sharpe, on Period A MaxDD**. Full P59 wins on CAGR, on Period A Sharpe, and Period B MaxDD. The Robust vs Full P59 bootstrap shows t=-1.22 (NOT statistically significant) — P59's extra CAGR is indistinguishable from noise.

**The P59 extras (L2, L7, L8, L10) together added +0.93pp CAGR and -0.04 Sharpe and mostly from concentration leverage, not real alpha.**

## Bootstrap significance (10,000 iterations paired vs canonical baseline)

| Strategy | t-stat | P(edge>0) | Mean ann | 95% CI ann |
|----------|--------|-----------|----------|------------|
| Robust | +2.974 | 99.88% | +4.98pp | [+1.79, +8.45] |
| Full P59 | +3.352 | 99.99% | +5.85pp | [+2.53, +9.51] |
| Robust vs Full P59 | -1.220 | 10.76% | -0.83pp | [-2.18, +0.49] |

Robust's 95% CI lower bound is +1.79pp/yr annualized — statistically meaningful forward floor. Full P59's lower bound is +2.53pp/yr (higher), but Robust has better Sharpe so it's a Kelly-more-efficient strategy.
