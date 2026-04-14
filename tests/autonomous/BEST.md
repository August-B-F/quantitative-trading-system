# Best Results

## SHIPPING CHAMPION (2026-04-14) — ROBUST-VAR
**`champions/p_robust_var_champion.py`** — CAGR **30.96%** / Sharpe **1.989** / MaxDD **-12.79%**
- Net of 10 bps/side execution: **29.49% / 1.910**
- Period A (2010-2017): 2.251   Period B (2018-2026): **1.890**
- Bootstrap vs canonical: t=+3.22, P=99.96%, 95% CI ann **[+2.42, +9.77] pp/yr**
- Bootstrap vs previous Robust (inv-ATR): t=+2.02, P=98.23%, 95% CI **[+0.06, +1.80] pp/yr**

**The only delta vs `p_robust_champion.py` is `BASKET_VOL_EXP = 2.0`** (inverse-variance weighting of the non-top1 basket, previously inverse-ATR = inverse-vol).

Discovery: `purge/_explore_batch2.py`. Validation: `purge/_validate_inv_var*.py`, `purge/_final_bootstrap.py`. Full writeup: `purge/VALIDATION.md`.

Parameter neighborhood (exponent p): 0.0→1.78, 0.5→1.86, 1.0→1.93, 1.5→1.96, **2.0→1.99**, 2.5→2.00, 3.0→2.00. Monotone smooth — not a fragile spike.

### Previous champion (ROBUST, still in repo as `p_robust_champion.py`)
**6-layer Robust stack** — CAGR **29.80%** / **Sharpe 1.92** / MaxDD -12.84%

Surviving 6 of 10 layers after the 6-test purge gauntlet (LAYERS.md, PROTOCOL.md, VERDICT.md in /tests/autonomous/purge/):
1. **L1** — drop VGT/XLK from universe (stable: SOXX,QQQ,IGV,XLE,GLD,SHY)
2. **L3** — classifier confidence gate at max_proba ≥ 0.40
3. **L4** — rank-aggregation momentum (42:1, 63:3, 126:1)  ← the single biggest alpha source
4. **L5** — regime-conditional transition universe (+TLT,+AGG,+XLV,+XLF when proba ≥ 0.50)
5. **L6** — classifier CORE-50 + 7 credit/yield-curve/copper-gold features
6. **L9** — FULL boost (trail9m > 30% OR SPY 63d > 12% → top1 = 0.82). Otherwise top1 = 0.50 (canonical split).

**Stripped and discarded** (4 of 10):
- **L2** (62/38 split) — removing it actually IMPROVES Sharpe
- **L7** (FOMC window tightening to 0,1,4) — dead weight (-0.009 Sharpe); fragile parameters
- **L8** (self-DD trigger) — dead weight (-0.018 Sharpe); 76th percentile random-timing
- **L10** (warm boost) — pure noise (-0.002 Sharpe); 69th percentile random-timing

Per-half:
- Period A (2010-2017): 26.33 CAGR / 2.255 Sharpe / -5.33% MaxDD
- Period B (2018-2026): 33.07 CAGR / **1.802** Sharpe / -12.84% MaxDD

**Robust has +0.05 higher Sharpe in Period B (OOS-like) than Full P59** (1.802 vs 1.750). This is the strongest robustness evidence.

Bootstrap vs canonical: t=+2.97, P(edge>0)=99.88%, 95% CI ann [+1.79, +8.45] pp/yr.
Bootstrap Robust vs Full P59: **t=-1.22, NOT statistically significant** — the extra P59 layers' CAGR is indistinguishable from noise. P59 wins on mean CAGR but loses on Sharpe; P59's extras are concentration leverage, not alpha.

### Legacy full-stack champion (NOT RECOMMENDED for production)
~~P59 = 30.73% CAGR / 1.88 Sharpe / -12.66% MaxDD~~ — superseded by Robust. Kept in `champions/p59_champion.py` for reference and as part of session history.

### Robust champion (OOS-validated, recommended for production)
**P59 = P53 + full-boost weight 0.82 + DD weight 0.40** — CAGR 30.73% / Sharpe 1.88 / MaxDD -12.66%

P59 stacks two OOS-validated parameter tweaks over P53:
1. Full-boost top1 weight: 0.75 → **0.82** (more aggressive when boost triggers)
2. DD-mode top1 weight: 0.45 → **0.40** (more aggressive defense when DD triggers)

Both tweaks were independently validated on first-half (2010-2017) AND second-half (2018-2026) edge over baseline. Combined:
- First half edge: P53 +7.83 → **P59 +8.20pp annualized**
- Second half edge: P53 +3.20 → **P59 +3.74pp annualized**
- Full-period bootstrap t = **3.352** (was P53 3.241), 95% CI lower **+2.53pp/yr** (was P53 +2.22)

Both wider top1 sizes (more concentration when winning, more diversification when losing) push slightly more aggressive Kelly. The asymmetry stays.

P58 fallback (one tweak only): CAGR 30.37 / Sharpe 1.88
P53 fallback (no tweaks): CAGR 30.20 / Sharpe 1.88

P58 is P53 with one tiny tweak: increase the FULL boost weight from 0.75 to 0.78. This was found via OOS-discipline search: every candidate was required to improve OR stay flat in BOTH halves of the sample independently. P58 was the only candidate that **strictly improved both halves**:
- First half (2010-2017): +7.97pp annualized edge (was +7.83 in P53)
- Second half (2018-2026): **+3.36pp annualized edge** (was +3.20 in P53)
- Full-period bootstrap t = 3.274, P(edge>0) = 99.99%, 95% CI lower +2.31pp/yr

P53 fallback (almost identical, very slightly more conservative): CAGR 30.20 / Sharpe 1.88 / MaxDD -12.66.

P53 is the highest-CAGR variant whose marginal features all help BOTH halves of the sample independently. Per-half attribution showed:
- P46 baseline: first half +7.02pp, second half +1.89pp edge over baseline
- P49 (self-DD): first -0.33, second +0.25 ← helps OOS-style second half
- P51 (asymmetric Kelly): first +0.98, second +0.74 ← helps both halves
- P52 (SPY 63d boost): first +0.09, second +0.26 ← helps both
- **P53 (warm boost): first +0.07, second +0.06 ← helps both, max second-half edge +3.20pp**
- P54 (signal margin): first +0.51, second **-0.43** ← OVERFIT
- P57 (high-conf trans + own-vol): first +0.58, second **-0.17** ← OVERFIT

Forward expectation under P53: ~3pp/yr edge over baseline annualized = ~26.6% forward CAGR.

### Full-sample best (kept as reference, marginal forward edge expected)
**P57 = P55 + high-conf trans defend (thr=0.82) + own-vol regime sizing** — CAGR 30.48% / Sharpe 1.90 / MaxDD -12.66% (FULL SAMPLE)

⚠ Per-year edge analysis shows P54-P57's marginal improvements are concentrated in the first half (2010-2017). The features added between P53 and P57 (signal margin, stagflation defend, high-conf trans defend, own-vol regime) collectively HURT second-half performance by ~0.6pp annualized. They look great on full sample because the first half dominates the unweighted mean.

Stacked two new triggers on P55:
- High-conf trans defend at threshold **0.82** (was 0.85 in P56 — tighter).
- Own-vol regime: when realized 12m vol < 12% concentrate (0.75); when > 25% defend (0.45).

Bootstrap t=**3.444** (was 3.402 in P56), 95% CI lower bound **+2.51pp/yr** (was +2.40). The CI floor crossing 2.5%/yr is a notable threshold.

**P56 fallback** — 30.34/1.90/-12.66

When classifier is VERY confident about a regime transition (max_proba > 0.85 AND in transition state), set top1=0.45 (defend instead of chase). Mechanism: very high classifier confidence in regime change = big shift coming = wait it out.

2010-15 Sharpe **2.08**. Full Sharpe **1.90** (highest yet). Bootstrap t=3.402, P=100%, CI lower bound +2.40pp/yr.

**P55 fallback** — 30.27/1.89/-12.66

When the **current** regime (CPI/PMI-derived, not classifier prediction) is LG_HI stagflation, force top1=0.45 (defend). 10 months in 190. Stagflation is the known-worst regime for tech momentum so a regime-class override is principled.

Bootstrap t=3.379, P(edge>0)=100%, CI lower bound +2.37pp/yr. Marginal +0.04 CAGR but strict improvement on every robustness metric.

**P54 fallback** — CAGR 30.23% / Sharpe 1.89 / MaxDD -12.66%

When rank-1 score is within 0.3 ranks of rank-2 (uncertain top), set top1=0.45 (de-concentrate). Tight margin = low signal confidence = bet less. Bootstrap P(edge>0) hits **100.00%** for the first time. 2010-15 sub-period Sharpe **2.06** with MaxDD -5.22%. t-stat 3.350 (was 3.241).

**P53 fallback** — CAGR 30.20% / Sharpe 1.88 / MaxDD -12.66%

4-state Kelly with intermediate warmup boost:
- **DD mode** (trail3m < -2%): top1 = 0.45
- **Full boost** (trail9m > +30% OR SPY 63d > +12%): top1 = 0.75
- **Warm boost** (trail6m > +25% OR SPY 21d > +10%): top1 = 0.70
- **Normal**: top1 = 0.62

The warmup state captures partial-confirmation periods where the strategy is doing well but not yet at full-boost levels. 2010-15 sub-period Sharpe hits **2.00**.

Marginal +0.08pp CAGR over P52 with same Sharpe / MaxDD. Bootstrap t improves 3.197 → 3.241. Accepted with caveat: 4-state has 4 thresholds vs P52's 3, slightly more overfitting risk.

The two boost triggers are time-horizon orthogonal: 9m self-equity captures sustained strategy momentum; SPY 63d captures short-term market-wide breakouts that haven't yet shown up in the slow 9m signal. Activating on either condition adds 10 extra boost months over P51.

The asymmetric thresholds reflect loss aversion: react FAST to drawdowns (3m / -2%) but require PATIENT confirmation for hot streaks (9m / +30%). DD detection should be reactive; boost confirmation should be deliberate.

Bootstrap improvements vs P52 are marginal:
- t-stat: P52 3.197 → P53 **3.241**
- P(edge > 0): P52 99.99% → P53 99.99%
- 95% CI lower bound: P52 +2.17pp/yr → P53 **+2.22pp/yr**

**Previous champion (conservative fallback)**: **P52 = 30.12/1.88/-12.66** (3-state, simpler, only +0.08 CAGR worse).

**Self-DD rule**: track strategy's own trailing 6-month return. When it drops below 0%, switch top1/top3 split from 62/38 to **45/55** (de-concentrate during own drawdowns). Triggers in 9 of 190 months (5%). When trailing 6m return ≥ 0%, use the canonical 62/38 split.

This is "trade your own equity curve" — a Kelly-like protective response that reduces leader-bet aggression precisely when the strategy itself is signaling stress. Mechanism makes sense: in own-drawdown periods, the rank-1 pick is more likely to be wrong (regime shift in progress), so diversifying more across top-3 reduces single-leader risk.

Bootstrap improvement is the cleanest evidence this is real:
- t-stat: P47 2.779 → P49 **2.915**
- P(edge > 0): P47 99.88% → P49 **99.96%**
- 95% CI lower bound: P47 +1.36pp/yr → P49 **+1.58pp/yr** (notably stronger floor)

**Previous champion (fallback): P47 = 28.95/1.84/-12.66** (no self-DD logic).

Marginal upgrade over P46. Trans universe grows from [TLT, AGG, XLV] to [TLT, AGG, XLV, XLF]. XLF is picked as top-1 only once in 190 months; the gain comes from XLF entering the top-3 inv-vol basket during transition regimes, where its financials exposure is orthogonal to bonds+defensive equity. Specifically improves 2010-15 MaxDD from -6.36% to -5.75%.

**Previous champion** (conservative fallback): **P46 = 28.85/1.83/-12.66** (drop XLF, identical otherwise).

Extra classifier features (beyond canonical CORE 50) — 7 total:
- `cross_asset_credit_appetite__hyg_minus_tlt_21d`
- `credit_features__hy_ig_spread`
- `credit_features__hy_ig_spread_z252`
- `yield_curve_features__yc_slope_10y_2y`
- `yield_curve_features__yc_slope_10y_2y_chg63`
- `yield_curve_features__real_rate_10y`
- `cross_asset_copper_gold__copper_gold_ratio` ← rescues 2021-26 regime dependence

**Transition universe (P47 extension)**: in high-confidence transition (proba >= 0.50), expand stable → `[SOXX, QQQ, IGV, XLE, GLD, SHY, TLT, AGG, XLV, XLF]`. XLF added in Phase 50b based on the architectural finding that broad optionality beats class-specific pre-selection. It provides yield-curve-steepening exposure (financials benefit from curve steepening) that's orthogonal to TLT (long duration), AGG (aggregate bond), and XLV (defensive sector).

**Dropped noise features** (LOO ablation — Phase 45):
- `credit_features__hy_ig_spread_chg63` — LOO removal IMPROVED result by +0.37pp (was net-negative).
- `regime_credit__credit_regime_tight` — LOO removal was a no-op (0.0 delta).

The 6 surviving features all showed LOO drops ≥0.32pp CAGR individually, so each has measurable marginal contribution. Biggest contributor: `yc_slope_10y_2y` (LOO drop -1.58pp). Classifier WF accuracy is 0.667 with pruned set (vs 0.679 with full 8), but strategy performance is BETTER — accuracy and alpha aren't perfectly aligned.

Cached as `cache/pred_proba_p46.pkl`.

**Why copper_gold_ratio works**: Classic growth-vs-safety signal (copper = industrial demand, gold = risk-off flight). It specifically rescued the 2021-26 sub-period where P45's credit/yc features became noise — 2021-26 was a commodity-cycle dominated era, and the copper/gold ratio tracked the post-COVID reflation and subsequent growth slowdown. Adding it brought P45's 2021-26 CAGR from 38.53 back up to 40.14, matching P42 while keeping the strong 2010-20 gains.

**What did NOT help** (tested and ruled out): `breakeven_5y_chg21`, `breakeven_10y_chg21`, `baa_aaa_spread` (Phase 46b). The `baa_aaa_spread` case is notable — it raised WF classifier accuracy to 0.693 (best ever) but hurt strategy CAGR to 26.90. Stark reminder that accuracy ≠ alpha.

⚠ Caveat: the subset was selected by looking at LOO performance. Still technically in-sample. But the fact that individual LOO drops of the 6 surviving features match their expected informational content (yield curve slope is foundational, real rate drives regime, credit spread is risk appetite) lowers the overfitting concern.

Previous champion (conservative fallback): **P42 = 28.03/1.74/-12.66** (no cross-asset classifier extras).

Full champion recipe:
- Universe (stable): [SOXX, QQQ, IGV, XLE, GLD, SHY]  
- Universe (transition, when classifier proba>=0.50 and pred!=current): add [TLT, AGG, XLV]
- Stable momentum signal: rank aggregation across 42d, 63d, 126d returns with weights (1, 3, 1)
- Classifier confidence gate: switch to 21d lookback only when max_proba >= 0.40
- 62/38 top-1/top-k split  
- FOMC deferral window: only trigger on rebalances that fall on FOMC day itself (post=1), defer 4 trading days
- SMA200 gate buffer: -4% (canonical, unchanged)
- Stable-regime momentum signal = weighted average rank across 42d, 63d, and 126d return tables (weights **1, 3, 1**). 63d dominates (60% of signal weight); 42d and 126d flank.
- **Two-tier regime-conditional universe**: stable months always use `[SOXX, QQQ, IGV, XLE, GLD, SHY]`. Transition months are split into two confidence tiers:
  - **High-confidence transition** (predicted != current AND max_proba >= 0.50): use defensive expansion `[..., TLT, AGG, XLV]`.
  - **Low-confidence transition** (max_proba < 0.50): revert to stable universe (no expansion — low-confidence moves are treated as noise).
  - The signal-level classifier gate at 0.40 still applies (low-confidence switches become stable 63d lookback); the universe-level tier threshold at 0.50 is independent — it gates universe, not signal.
- Universe: drop VGT and XLK.
- Split: 62/38 top-1/top-k.
- Classifier gate: switch to 21d only if argmax proba >= 0.40.
- Full-period delta vs canonical baseline: **+6.59pp CAGR, +0.38 Sharpe, +0.28pp MaxDD**. Post-50%-haircut: +3.30pp CAGR → ~26.91%.
- **Bootstrap robustness (Phase 46)**: paired t=**2.739** (best yet), P(edge>0)=**99.84%**, 95% CI on annualized edge **[+1.30, +7.51]** pp/yr — lower bound strongly above zero.
- **Rolling 36m Sharpe**: P46 beats baseline in **90.8%** of 188 rolling windows. Median rolling Sharpe 1.63 vs 1.31.
- **Factor regression (Phase 47)**: P46 alpha regressed on 6 macro factor changes. Intercept **t=+3.23** (strongly significant). R² = 0.044 — factors explain <5% of alpha variance. copper/gold change coefficient NOT significant (t=+0.61), so the champion's alpha is NOT mechanically tracking copper/gold — it's classifier-timing skill using copper/gold as a regime indicator.
- **Turnover (Phase 48)**: P46 mean monthly turnover 0.915 (vs baseline 1.022). P46 trades ~10% LESS than baseline despite higher concentration. Rank aggregation smooths the signal.
- **2021-26 sub-period bootstrap (Phase 48b)**: P(edge > 0 in 2021-26) = **only 70.9%** (vs 99.84% full period). The copper/gold rescue of 2021-26 is real on average but has wider dispersion than earlier sub-periods. 2010-15 and 2016-20 edges are much more statistically robust than 2021-26.
- **Sub-period stability (every window beats baseline on both CAGR and Sharpe, including 2016-2020 which was a weak spot for prior champions)**:
  | period | baseline | champ | d_cagr | d_sharpe | d_dd |
  |---|---|---|---|---|---|
  | full | 23.61/1.50/-12.94 | 30.20/1.88/-12.66 | +6.59 | +0.38 | +0.28 |
  | 2010-2015 | 13.74/1.18/-10.11 | 24.70/2.00/ -5.75 | +10.96 | +0.82 | +4.36 |
  | 2016-2020 | 20.54/1.24/-12.94 | 25.07/1.47/-12.66 | +4.53 | +0.23 | +0.28 |
  | 2021-2026 | 38.37/2.06/-10.22 | 40.60/2.21/ -5.91 | +2.23 | +0.15 | +4.31 |
- **Cost stability (from Phase 11):** champion edge vs baseline = +2.23/+2.23/+2.21/+2.19/+2.17pp at 0/5/10/20/30 bps — flat. Not turnover-driven.
- **Component attribution (incremental CAGR over baseline):**
  | layer | CAGR | Sharpe |
  |---|---|---|
  | baseline | 23.61 | 1.50 |
  | +dropoverlap | 23.96 | 1.58 |
  | +62/38 split | 24.34 | 1.54 |
  | +gate40 | 24.49 | 1.55 |
  | +rankagg(1,2,1) | 25.84 | 1.60 |
  | +rankagg(1,2.5,1) | **26.52** | **1.65** |
  Rank aggregation is the single biggest contributor (+1.35 to +2.03pp alone).
- Caveat: only the 2010-2015 and first-half windows show MaxDD worse than baseline (~2pp) — but Sharpe still improves in those windows, so risk-adjusted return is better.
- Caveat 2: weight combination was selected out of a 10-variant grid. Aggressive haircut still leaves +0.5-0.7pp CAGR edge; more weight combos around this neighborhood could dilute confidence.

### ⚠ Robustness concern (from Phase 4 sub-period test)
- 2010-2015: +0.71pp CAGR, +0.03 Sharpe, MaxDD WORSE (-2pp). Marginal.
- 2016-2020: **-1.23pp CAGR**, -0.02 Sharpe, DD slightly better. **LOSS.**
- 2021-2026: +2.77pp CAGR, +0.13 Sharpe, DD much better. STRONG win.
- The full-period edge is almost entirely from 2021-2026 (dispersion regime favorable to 60/40 concentration).
- **Cost-robust**: the edge holds steady at 0/5/10/20/30 bps. Not turnover-driven.
- **Rolling-window robust**: champion beats baseline in **100% of 188 36-month rolling Sharpe windows**. Median rolling Sharpe champion 1.55 vs baseline 1.31.
- **Statistically significant**: paired monthly bootstrap t=2.03, P(edge>0)=98.14%, 95% CI on annualized edge [+0.20, +5.28]pp (point estimate +2.62).
- Conclusion: the "improvement" is regime-dependent. Under 50% haircut the full edge is ~0.34pp CAGR — within backtest noise. **Treat as a tentative champion, not a validated upgrade.** A prudent production decision might be to stay with the canonical 50/50 and leave the universe drop optional. Further validation needed (Monte Carlo, different splitter folds).

## History of champions
- 2026-04-13 18:55 local: **P53 = P52 + 4-state warmup boost** — 30.20/1.88/-12.66. 2010-15 Sharpe hits 2.00. Bootstrap t=3.241. (Marginal — caveat noted)
- 2026-04-13 18:40 local: P52 = P51 + SPY 63d > 12% boost trigger — 30.12/1.88/-12.66.
- 2026-04-13 18:25 local: P51 = P47 + asymmetric Kelly (DD 3m/-2%, boost 9m/+30%) — 29.92/1.87/-12.66.
- 2026-04-13 18:10 local: P50 = P47 + symmetric 6m/6m Kelly (0%/25%) — 29.58/1.86/-12.66.
- 2026-04-13 17:50 local: P49 = P47 + self-DD adaptive sizing — 29.20/1.86/-12.66. (DD-only half of P50)
- 2026-04-13 17:30 local: P47 = P46 + XLF in trans universe — 28.95/1.84/-12.66.
- 2026-04-13 17:00 local: P46 = P45 + copper_gold_ratio — 28.85/1.83/-12.66.
- 2026-04-13 16:50 local: P45 = P42 + 6 pruned credit/yc features — 28.71/1.81/-12.66.
- 2026-04-13 16:45 local: P44 classifier retrained on CORE+credit+yc — 28.34/1.78/-12.66 (superseded by pruned version).
- 2026-04-13 16:30 local: P42 P27 + FOMC (post=1, defer=4) — 28.03/1.74/-12.66.
- 2026-04-13 16:15 local: P27 tier-proba50 regime-uni — 27.77/1.75/-12.66.
- 2026-04-13 (earlier): P25 regime-universe +TLT+AGG+XLV + rankagg — 27.50/1.74/-12.66.
- 2026-04-13 20:45: P24 regime-universe +TLT+AGG + rankagg — 27.28/1.72/-12.66.
- 2026-04-13 20:15: P23 regime-universe +TLT + rankagg — 27.01/1.70/-12.66.
- 2026-04-13 19:00: P12 W4 rankagg(42:1,63:3,126:1) — 26.79/1.67/-12.66.
- 2026-04-13 18:30: P11 rankagg(42:1,63:2.5,126:1) — 26.52/1.65/-12.66.
- 2026-04-13 18:00: P10b rankagg(42:1,63:2,126:1) + champ stack — 25.84/1.60/-12.66. (dethroned by 2.5-weight variant)
- 2026-04-13 17:30: P6b.03 gate40 + 62/38 split + dropoverlap — 24.49/1.55/-12.83. (dethroned by rankagg)
- 2026-04-13 15:30: P2b.02_do_split60_40 — 24.28/1.55/-12.68. (dethroned by gate40)
- 2026-04-13 15:22: P2.04 dropoverlap — 23.96/1.58/-12.84.
- 2026-04-13 init: Canonical baseline 23.61/1.50/-12.94.

## Other notable passes (did not become champion but genuine)
- P2.10 top4+dropoverlap — 22.86/1.60/-11.38. Best Sharpe & MaxDD seen; CAGR cost -0.75pp. Sharpe-optimal variant.
- P2.01 drop_QQQ — 23.99/1.54/-13.85.
- P2.08 top4+60/40 split — 24.00/1.51/-14.09. Highest CAGR of the passes; MaxDD cost.
- P1.01 top4 — 23.71/1.54/-13.90.

