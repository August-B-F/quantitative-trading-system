# SIGNAL ANALYSIS REPORT — Strategy Attribution & Correlation

OPTIMIZED strategy: E-R1 (regime-conditional 63d/21d momentum) + M11 (top-3 inverse-vol) + M26_post_3d (defer 3 trading days when within 0–2d after an FOMC decision).

Walk-forward monthly rebalances analyzed: **188**
- V0 (base 63d top-1): CAGR 19.03%, Sharpe 0.99
- V4 (final): CAGR 23.61%, Sharpe 1.50, MaxDD -12.94%

## B1 — Component attribution

Contribution of each layer = ΔV between successive variants on the same monthly schedule.
Base row reports geometric (compounded) properties; incremental rows report additive monthly Δ.

| Component | Active months | Avg Δ when active | Total contribution | Best month | Worst month |
|---|---|---|---|---|---|
| Base 63d top1 | 188 | +1.622% | +272.94pp | 2021-01-26 (+19.78%) | 2019-04-25 (-15.75%) |
| Regime switch (21d trans) | 53 | +0.970% | +51.41pp | 2026-02-25 (+23.67%) | 2010-07-27 (-6.65%) |
| Top-3 inv-vol blend | 188 | -0.113% | -21.18pp | 2023-09-27 (+5.93%) | 2025-12-30 (-11.47%) |
| SMA200 gate | 17 | +0.022% | +0.38pp | 2022-05-24 (+6.18%) | 2011-09-28 (-3.79%) |
| M26 post-3d defer | 10 | +1.666% | +16.66pp | 2025-10-31 (+6.16%) | 2019-03-25 (-2.88%) |

## B2 — Regime switch detailed analysis

Total switch-active months: **53**

| Category | Count | % |
|---|---|---|
| HELPFUL | 0 | 0.0% |
| NEUTRAL_CORRECT | 1 | 1.9% |
| NEUTRAL_WRONG | 25 | 47.2% |
| HARMFUL | 27 | 50.9% |

**HELPFUL + NEUTRAL** = 26/53 = 49.1%  → ⚠️  below 70% bar.

<details><summary>Switch month detail (first 25 rows)</summary>


| Date | Cur reg | Pred reg | Correct? | 63d pick | 21d pick | Δ (21−63) | Category |
|---|---|---|---|---|---|---|---|
| 2010-07-27 | hg_li | lg_li | N | GLD | IGV | -6.65% | HARMFUL |
| 2010-08-31 | hg_li | lg_li | N | IGV | GLD | -1.03% | HARMFUL |
| 2010-09-29 | hg_li | lg_li | N | IGV | QQQ | +0.48% | HARMFUL |
| 2010-10-25 | hg_li | lg_li | N | GLD | XLE | +3.67% | HARMFUL |
| 2010-11-30 | hg_li | lg_li | N | SOXX | SOXX | +0.00% | NEUTRAL_WRONG |
| 2010-12-29 | hg_li | lg_li | N | XLE | XLE | +0.00% | NEUTRAL_WRONG |
| 2011-01-25 | hg_li | lg_li | N | SOXX | SOXX | +0.00% | NEUTRAL_WRONG |
| 2011-02-23 | hg_li | lg_li | N | XLE | XLE | +0.00% | NEUTRAL_WRONG |
| 2011-03-30 | hg_li | lg_li | N | XLE | XLE | +0.00% | NEUTRAL_WRONG |
| 2011-10-31 | hg_hi | lg_hi_stagflation | N | GLD | XLE | +3.13% | HARMFUL |
| 2011-11-29 | hg_hi | lg_hi_stagflation | N | IGV | SHY | +6.40% | HARMFUL |
| 2012-01-25 | hg_hi | hg_li | N | SOXX | SOXX | +0.00% | NEUTRAL_WRONG |
| 2012-02-23 | hg_hi | hg_li | N | QQQ | IGV | -2.49% | HARMFUL |
| 2012-03-29 | hg_hi | hg_li | Y | QQQ | QQQ | +0.00% | NEUTRAL_CORRECT |
| 2015-05-26 | lg_li | hg_li | N | IGV | IGV | +0.00% | NEUTRAL_WRONG |
| 2015-06-30 | lg_li | hg_li | N | IGV | SHY | -2.59% | HARMFUL |
| 2015-07-27 | lg_li | hg_li | N | IGV | QQQ | -0.44% | HARMFUL |
| 2015-08-31 | lg_li | hg_li | N | SHY | GLD | -2.52% | HARMFUL |
| 2015-09-29 | lg_li | hg_li | N | SHY | GLD | +2.82% | HARMFUL |
| 2015-10-26 | lg_li | hg_li | N | SOXX | SOXX | +0.00% | NEUTRAL_WRONG |
| 2015-11-23 | lg_li | hg_li | N | SOXX | QQQ | -2.41% | HARMFUL |
| 2015-12-30 | lg_li | hg_li | N | SOXX | SOXX | +0.00% | NEUTRAL_WRONG |
| 2017-10-31 | hg_li | lg_li | N | SOXX | SOXX | +0.00% | NEUTRAL_WRONG |
| 2017-11-29 | hg_li | lg_li | N | SOXX | SOXX | +0.00% | NEUTRAL_WRONG |
| 2017-12-28 | hg_li | lg_li | N | VGT | XLE | -3.97% | HARMFUL |

</details>


## B3 — Annual attribution

| Year | V0 base | + Switch | + Top-3 IV | + SMA gate | + M26 defer | = TOTAL |
|---|---|---|---|---|---|---|
| 2010 | 35.01% | -3.53pp | -2.37pp | -2.87pp | +0.00pp | 24.03% |
| 2011 | 15.54% | +9.53pp | -12.28pp | +1.69pp | +0.00pp | 16.10% |
| 2012 | -2.12% | -2.49pp | +11.47pp | +0.00pp | +0.00pp | 6.99% |
| 2013 | 23.52% | +0.00pp | -2.15pp | +0.00pp | +1.63pp | 22.92% |
| 2014 | 19.34% | +0.00pp | -9.18pp | +0.00pp | -1.28pp | 7.73% |
| 2015 | -4.31% | -5.15pp | +10.18pp | -1.41pp | +0.00pp | -0.46% |
| 2016 | 35.05% | +0.00pp | -4.64pp | +0.47pp | +0.00pp | 29.96% |
| 2017 | 25.08% | -3.97pp | +4.88pp | +0.00pp | +0.00pp | 26.48% |
| 2018 | -15.48% | +0.00pp | +2.74pp | -1.25pp | +9.90pp | -3.88% |
| 2019 | 30.51% | +0.00pp | -2.73pp | +0.00pp | -1.07pp | 27.62% |
| 2020 | 23.42% | +0.00pp | +5.62pp | -3.66pp | +0.00pp | 26.23% |
| 2021 | 43.08% | +1.33pp | -13.13pp | +0.00pp | +0.00pp | 28.71% |
| 2022 | 23.72% | +0.00pp | -1.34pp | +6.69pp | +0.00pp | 33.58% |
| 2023 | 9.73% | +6.18pp | +2.88pp | +0.00pp | +0.00pp | 20.93% |
| 2024 | 3.48% | +9.48pp | +7.31pp | +0.00pp | -0.06pp | 22.91% |
| 2025 | 73.46% | +16.44pp | -22.06pp | +0.70pp | +7.54pp | 80.44% |
| 2026 | -11.27% | +23.59pp | +3.61pp | +0.00pp | +0.00pp | 16.13% |

## C1 — SPY market correlation asymmetry

| Regime | Corr w/ SPY | Strategy avg | SPY avg | n |
|---|---|---|---|---|
| SPY up months | 0.247 | +3.16% | +3.59% | 124 |
| SPY down months | 0.180 | -0.61% | -3.28% | 64 |
| All months | 0.438 | — | — | 188 |

- **Upside capture:** 87.9%
- **Downside capture:** 18.6%

## C2 — Factor correlations

| Factor | Correlation |
|---|---|
| SPY | 0.438 |
| MTUM | 0.341 |
| VLUE | 0.339 |
| QUAL | 0.411 |
| GLD | 0.142 |
| TLT | -0.151 |

MTUM correlation **on switch months**: 0.329  vs  **off switch months**: 0.344
> ✅ Regime switch reduces MTUM correlation during transitions (as designed).

## C3 — Performance by ACTUAL growth-inflation regime

| Actual regime | Months | Strategy CAGR | SPY CAGR | Excess |
|---|---|---|---|---|
| HG/LI | 85 | 19.21% | 17.01% | +2.20pp |
| HG/HI | 40 | 28.07% | 15.81% | +12.26pp |
| LG/LI | 53 | 28.23% | 11.97% | +16.27pp |
| LG/HI | 10 | 20.13% | 7.62% | +12.51pp |