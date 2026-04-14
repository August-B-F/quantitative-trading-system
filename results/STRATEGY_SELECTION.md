# STRATEGY SELECTION — Paper Trading Horse Race

9 strategies, head-to-head, 6 months from **2026-04-30**.

This is the second revision of the lineup. The first version missed
`tests/autonomous/` entirely and picked a boring benchmark set. The
autonomous suite contains a 3-day, 49-phase, ~300-experiment in-sample
search that produced a validated Sharpe-1.92 champion (ROBUST_STACK) and
a Sharpe-1.989 exploration variant (ROBUST_VAR), plus a ladder of
intermediate candidates with varying overfit exposure. This revision
uses that evidence.

The lineup has three tiers:

- **CONFIDENT upgrades** (slots 2, 3) — low-overfit-risk improvements
  with per-layer OOS evidence. If forward performance matches
  backtest, adopt.
- **CONFIDENT fallback / NEUTRAL benchmarks** (slots 4, 5, 6) — rules-
  only runner-up, 200d SMA null, Antonacci dual-momentum. Diagnostic
  anchors.
- **VERY SKEPTICAL champions** (slots 7, 8, 9) — the Sharpe-1.9+
  candidates. Included precisely to see whether the backtest numbers
  survive forward. These are controls for "does the research process
  find real alpha or just fit the sample?".

OPTIMIZED is slot 1 (locked).

---

## The 9 strategies

| # | Name | Tier | CAGR | Sharpe | MaxDD | Conf | Corr w/ OPT |
|---|---|---|---|---|---|---|---|
| 1 | OPTIMIZED (locked) | confident | 23.61% | 1.50 | -12.94% | confident | — |
| 2 | **ROBUST_STACK** | confident upgrade | 29.80% | 1.925 | -12.84% | confident | HIGH |
| 3 | **DROPOVERLAP** | confident upgrade | 23.96% | 1.58 | -12.84% | confident | HIGH |
| 4 | T2_BALANCED | confident fallback | 19.30% | 1.22 | -21.00% | confident | HIGH |
| 5 | TREND_SIMPLE (SPY/SHY 200d) | neutral null | ~10.5%e | ~0.85e | ~-19%e | neutral | LOW |
| 6 | DUAL_MOMENTUM (12-1m Antonacci) | neutral benchmark | ~14%e | ~0.95e | ~-22%e | neutral | MED |
| 7 | **ROBUST_VAR** | very skeptical | 30.96% | **1.989** | -12.79% | skeptical | HIGH |
| 8 | **P59_FULL_STACK** | very skeptical | 30.73% | 1.88 | -12.66% | skeptical | HIGH |
| 9 | **P57_FRONTLOADED** | very skeptical | 30.48% | 1.90 | -12.66% | skeptical | HIGH |

All backtest numbers over 2008-05..2025-12 walk-forward unless marked `e`.

---

## Slot-by-slot rationale

### Slot 1 — OPTIMIZED  *(locked)*

Validated production spec. `results/experiments/OPTIMIZED.json`.
CAGR 23.61% / Sharpe 1.50 / MaxDD -12.94%.

### Slot 2 — ROBUST_STACK  *(confident upgrade, Sharpe 1.92)*

**What:** 6-layer post-purge champion from `tests/autonomous/purge/`.
OPT's rank-aggregation momentum signal (42:1, 63:3, 126:1) replaces
pure 63d, universe drops VGT/XLK, classifier adds 7 credit/yield-curve/
copper-gold features, transition universe expands to +TLT/+AGG/+XLV/
+XLF when max_proba≥0.50, classifier confidence gate at 0.40, and a
"full boost" top-1=0.82 triggers when trailing 9m return > 30% or SPY
63d > 12%.

**Why confident:** Each layer was put through a 6-test purge
gauntlet:

- Test 1 (leave-one-out ablation) — every kept layer has measurable
  negative impact when removed (ΔSharpe -0.015 to -0.159).
- Test 2 (per-half holdout) — L4 rank aggregation helps BOTH halves
  (+0.117 Period A, +0.100 Period B); other layers are era-skewed
  but net positive.
- Test 3 (random timing) — L5 transition universe at 100th percentile,
  L9 boost at 97.4th percentile (real timing signal, not lucky dates).
- Test 4 (parameter neighborhood) — all kept layers have smooth
  neighborhoods.
- Test 5 (in-stack rebuild) — each kept layer produces positive
  marginal Sharpe when rebuilt.
- Test 6 (paired bootstrap vs canonical) — t=2.974, P(edge>0)=99.88%,
  95% CI [+1.79, +8.45] pp/yr. Lower bound strictly above zero.

The 4 rejected layers (62/38 split, FOMC tightening, self-DD, warm
boost) were stripped because they hurt Sharpe in ablation, failed
random-timing significance, or helped only one half of the sample.

**Correlation with OPT:** HIGH. Shares SMA gate, FOMC defer, regime
classifier scaffolding.

### Slot 3 — DROPOVERLAP  *(confident upgrade, Sharpe 1.58)*

**What:** OPTIMIZED exactly, with VGT and XLK removed from the
universe. Nothing else changes. 6-ETF universe: SOXX, QQQ, IGV, XLE,
GLD, SHY.

**Why confident:** Single-layer change with a clear mechanism
(SOXX+QQQ+IGV already carry the tech-momentum factor; VGT and XLK
are near-redundant and add correlation drag). Autonomous LOG
P2.04_dropoverlap and P2b.01_do_top3 both hit 23.96% / 1.58 / -12.84%
— +0.08 Sharpe over OPTIMIZED at unchanged MaxDD. It has the lowest
overfit footprint of any tested upgrade: one decision, one parameter.

**Why still keep it in the race when ROBUST_STACK already contains
this layer:** if ROBUST_STACK lags OPT but DROPOVERLAP matches or
beats it, we know the universe-trim is the sole load-bearing
contribution and the rest of the Robust layers are not carrying their
weight forward. Diagnostic isolation.

**Correlation with OPT:** HIGH.

### Slot 4 — T2_BALANCED  *(confident fallback)*

**What:** The rules-only runner-up from Tier 2. 50/50 top-1/top-3
(equal-weight) on 63d momentum, SMA200 -4% gate, no ML, no regime
switch, no FOMC defer. `results/experiments/T2_balanced.json` —
19.3% / 1.22 / -21.0%.

**Why:** Establishes the "no-ML baseline" anchor. If T2_BALANCED ties
or beats OPT over 6 months, the entire ML layer is ops burden.

**Correlation with OPT:** HIGH — same universe, same cadence.

### Slot 5 — TREND_SIMPLE  *(neutral null)*

SPY above 200d SMA → hold SPY. Below → hold SHY. Flip only on cross.
The null hypothesis of the race. If it beats half the field, we have
a complexity problem.

**Correlation with OPT:** LOW.

### Slot 6 — DUAL_MOMENTUM  *(neutral benchmark)*

Antonacci 12-1m dual momentum on the 8-ETF universe, absolute-
momentum SHY filter. Our pipeline has never standalone-tested 12-1m —
the autonomous suite (P3.09) tried 12-1m as a rank-aggregation leg
and got 21.59/1.27, but that's embedded in OPT, not standalone. This
is the academic baseline (Antonacci 2012, Faber 2013, Hurst-Ooi-
Pedersen 2017).

**Correlation with OPT:** MED.

### Slot 7 — ROBUST_VAR  *(very skeptical, Sharpe 1.989)*

**What:** ROBUST_STACK + inverse-variance (p=2) basket weighting
instead of inverse-vol (p=1). `tests/autonomous/champions/
p_robust_var_champion.py`. CAGR 30.96% / Sharpe 1.989 / MaxDD -12.79%.
This is the headline Sharpe-1.9+ candidate.

**Why skeptical:** The inv-var delta was discovered by batch
exploration (`purge/_explore_batch2.py`) and validated with a paired
bootstrap against its parent at t=+2.02 (P=98.23%). That's above-zero
but not overwhelming, and the search process was "try several
exponents and pick the best". The parameter neighborhood (p=0→2.5) is
smooth, which lowers fragility concern, but the +0.06 Sharpe increment
over ROBUST_STACK is the least reliable layer in the whole stack.

Treat ROBUST_VAR as "the first 1.92 Sharpe is ROBUST_STACK evidence;
the last 0.07 is the speculative layer". If ROBUST_VAR matches
ROBUST_STACK forward (both ~1.90), the inv-var trick transferred. If
ROBUST_VAR regresses to ROBUST_STACK (1.92 vs 1.99), the inv-var was
overfit. If both collapse, the Robust stack itself has an era-
concentration problem.

**Correlation with OPT:** HIGH.

### Slot 8 — P59_FULL_STACK  *(very skeptical, Sharpe 1.88)*

**What:** The pre-purge 10-layer champion. Stacks the 6 Robust layers
+ 62/38 split + FOMC tightening (0,1,4) + self-DD trigger + warm
boost. 30.73% / 1.88 / -12.66%. `tests/autonomous/champions/
p59_champion.py`.

**Why skeptical:** The purge found those 4 extra layers fail Test 1
(3 of 4 have ΔSharpe between -0.002 and -0.018 — dead weight or
noise), fail Test 3 random-timing at 69th-76th percentile (below
significance), and the bootstrap of P59 vs ROBUST_STACK is
**t=-1.22** (not statistically significant) — the extra CAGR is
indistinguishable from concentration leverage. The full-sample
comparison favors P59 only because it uses the robust base plus a
more concentrated split; Sharpe drops.

**Why still include:** If P59 beats ROBUST_STACK forward, the purge
protocol was too aggressive and dead-weight layers were pulled out
unnecessarily.

**Correlation with OPT:** HIGH.

### Slot 9 — P57_FRONTLOADED  *(very skeptical, Sharpe 1.90)*

**What:** Adds high-conf transition defend (max_proba > 0.82 →
top1=0.45) and own-vol regime sizing on top of P55. 30.48% / 1.90 /
-12.66%. 2010-15 sub-Sharpe hits 2.08.

**Why very skeptical:** `BEST.md` explicitly flags that "P54-P57's
marginal improvements are concentrated in the first half of the
sample (2010-2015) and the features added between P53 and P57
collectively HURT second-half performance by ~0.6pp annualized".
This is the cleanest "first-half-overfit" shape in the whole suite.

**Why included:** Control for the overfit-detection protocol itself.
If P57 beats its siblings forward, the "helped-A but hurt-B"
diagnostic that drove the purge was noise-reading, not overfit
detection. That would be an important negative result for the
research process.

**Correlation with OPT:** HIGH.

---

## Diversity check

| Dimension | Count | Target | Verdict |
|---|---|---|---|
| Momentum-based | 7 (1, 2, 3, 4, 6, 7, 8, 9 — basically every ETF picker) | ≤4 | **OVER** — justified: momentum is the real alpha this universe produces; artificially diluting with non-momentum strategies would trade information for cosmetic diversity |
| Uses ML | 5 (1, 2, 7, 8, 9) | ≤2 | **OVER** — justified: 4 of those 5 are the same classifier with different downstream scaffolding; they are NOT independent ML risks. TREND_SIMPLE / T2_BALANCED / DROPOVERLAP / DUAL_MOMENTUM cover the "no-ML" branch |
| Purely rules-based | 4 (3, 4, 5, 6) | ≥3 | **YES** |
| Low-corr with OPT | 2 (5, 6) | ≥3 | **UNDER** — justified: the autonomous suite showed every high-Sharpe variant shares OPT's scaffolding. Forcing a 3rd low-corr strategy would mean inventing one that has no backtest evidence |

**Deliberate deviations from the original framework caps.** The
original framework was:

- ML cap ≤ 2
- ≥ 4 momentum
- ≥ 3 low-corr

I'm exceeding ML and momentum caps and missing the low-corr minimum by
one because the autonomous suite changed what was available to pick
from. 6 months of paper trading is noisy; the value of the race is in
the head-to-head contrasts, not in ticking diversity boxes. The key
contrasts preserved:

- **ROBUST_STACK vs ROBUST_VAR** — is the +inv-var layer overfit?
- **ROBUST_STACK vs P59_FULL_STACK** — were the purged layers really
  dead weight?
- **ROBUST_STACK vs P57_FRONTLOADED** — does the "helped-A hurt-B"
  filter correctly detect overfit?
- **OPT vs DROPOVERLAP** — is the universe trim alone enough?
- **OPT vs T2_BALANCED** — does the ML layer earn its keep?
- **(All of the above) vs TREND_SIMPLE** — does any complexity pay?
- **(All of the above) vs DUAL_MOMENTUM** — is 63d the right lookback?

7 distinct hypotheses, 9 strategies, 6 months. Each loss in the race
is information.

---

## What we learn from each winner

| Winner | Implication |
|---|---|
| OPTIMIZED (1) | Research validated. Ship as-is. |
| ROBUST_STACK (2) | The purge-validated layers transferred forward. Promote to production champion; retire OPT |
| DROPOVERLAP (3) | The universe trim is the single load-bearing upgrade. Strip everything else from ROBUST_STACK; adopt the 1-line patch |
| T2_BALANCED (4) | The entire ML machinery is ops burden in forward use. Rip it out |
| TREND_SIMPLE (5) | Complexity has been actively harmful this period. Rerun the research process with a simplicity prior |
| DUAL_MOMENTUM (6) | 63d was a local optimum; 12-1m is the right lookback. Re-run the whole sweep at 252d horizons |
| **ROBUST_VAR (7)** | Autonomous-suite search is finding real edges even in the marginal-layer regime. Invest more in that loop |
| **P59_FULL_STACK (8)** | The purge protocol was too aggressive — stripped layers had real forward value. Relax purge thresholds |
| **P57_FRONTLOADED (9)** | The "helped-A hurt-B" overfit diagnostic is unreliable. Find a better OOS filter |

---

## Tiebreak and scoring

Primary ranking metric is **Sharpe**. 6 months is too short to trust
CAGR differences below ~4pp.

1. Sharpe (primary)
2. MaxDD (closest-to-zero wins ties)
3. Correlation with SPY (lower wins ties)
4. CAGR (last resort)

A "winner" needs ≥ 0.20 Sharpe edge over the runner-up to avoid
"inconclusive, rerun another 6 months".

## Risk disclosures for the live race

- Every Robust-family strategy shares the same classifier, same FOMC
  calendar, same SMA200 gate data. A feed break hits slots 1, 2, 7,
  8, 9 simultaneously.
- OPT's Monte Carlo 5%-ile MaxDD is -28.8%. Size for that, not for
  -12.9%. ROBUST_STACK's tail is similar (-12.84% observed).
- OPT, DROPOVERLAP, T2_BALANCED underperform SPY badly in calm VIX<15
  rallies (Test 9 of the stress report). Expected drag in a calm
  melt-up quarter.
- Rebalance day is load-bearing at month-end for slots 1-4 and 7-9.
  Slot 5 flips only on SMA cross. Slot 6 rebalances month-end.
- Retrain the classifier once before the race starts (it's been
  ~3 months since the last fit; Test 3c of the stress report shows
  regime accuracy decays beyond 90 days).

---

## Files

- Slot specs: `configs/strategies/strategy_{1..9}_*.yaml`
- OPT canonical artifact: `results/experiments/OPTIMIZED.json`
- Autonomous champion scripts: `tests/autonomous/champions/*.py`
- Purge protocol and evidence: `tests/autonomous/purge/TEST{1..6}_*.md`,
  `ROBUST_STACK.md`, `VERDICT.md`
- Autonomous session log: `tests/autonomous/LOG.md`,
  `tests/autonomous/HOURLY.md`, `tests/autonomous/BEST.md`,
  `tests/autonomous/HANDOFF.md`
- OPT stress evidence: `results/STRESS_TEST_REPORT.md`
