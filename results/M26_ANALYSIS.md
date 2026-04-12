# M26 DEEP DIVE — FOMC Deferral on OPTIMIZED Strategy

Tests whether FOMC rebalancing deferral (M26) improves the OPTIMIZED strategy (E-R1 + M11 inverse-vol) rather than just the E-R1 baseline.

## TL;DR

- OPTIMIZED base: CAGR **22.24%**, Sharpe 1.39, MaxDD -19.43%
- OPTIMIZED + M26 (5d): CAGR **22.01%**, Sharpe 1.34, MaxDD -13.80%
- d: CAGR -0.23pp, Sharpe -0.04, MaxDD +5.63pp
- **Verdict: INCLUDE M26**

## Test 1 — M26 on OPTIMIZED

Defer scheduled month-end rebalance by 5 trading days if date falls within ±2 trading days of an FOMC decision.

| Strategy | CAGR | Sharpe | MaxDD | d vs base |
|---|---|---|---|---|
| OPTIMIZED | 22.24% | 1.39 | -19.43% | — |
| + M26 (5d) | 22.01% | 1.34 | -13.80% | dCAGR -0.23pp, dDD +5.63pp |

Deferrals triggered: 28 / 190 rebalances.

### Annual returns

| Year | OPTIMIZED | +M26 | d |
|---|---|---|---|
| 2010 | +24.03% | +24.03% | +0.00pp |
| 2011 | +16.10% | +16.24% | +0.14pp |
| 2012 | +6.99% | -0.31% | -7.30pp |
| 2013 | +20.96% | +27.49% | +6.53pp |
| 2014 | +9.08% | +3.48% | -5.60pp |
| 2015 | -0.46% | -5.92% | -5.46pp |
| 2016 | +29.96% | +34.62% | +4.66pp |
| 2017 | +26.48% | +29.11% | +2.63pp |
| 2018 | -13.59% | -0.68% | +12.91pp |
| 2019 | +28.75% | +26.09% | -2.66pp |
| 2020 | +26.23% | +26.23% | +0.00pp |
| 2021 | +28.71% | +34.76% | +6.06pp |
| 2022 | +33.58% | +30.11% | -3.47pp |
| 2023 | +20.93% | +27.42% | +6.49pp |
| 2024 | +22.99% | +20.98% | -2.01pp |
| 2025 | +67.57% | +48.54% | -19.04pp |
| 2026 | +16.13% | +14.67% | -1.46pp |

## Test 2 — Deferral window sensitivity

| Window | CAGR | Sharpe | MaxDD |
|---|---|---|---|
| defer_3d | 23.41% | 1.43 | -12.94% |
| defer_5d | 22.01% | 1.34 | -13.80% |
| defer_7d | 21.54% | 1.32 | -18.84% |
| defer_10d | 21.91% | 1.41 | -17.82% |

## Test 3 — Multi-event stacking (5d defer)

| Variant | Events | CAGR | Sharpe | MaxDD | Deferred |
|---|---|---|---|---|---|
| M26a_FOMC | FOMC ±2 | 22.01% | 1.34 | -13.80% | 28 |
| M26b_FOMC_CPI | + CPI week | 22.01% | 1.34 | -13.80% | 28 |
| M26c_FOMC_CPI_NFP | + NFP week | 21.81% | 1.33 | -13.80% | 32 |
| M26d_all_events | + quad witching | 21.52% | 1.32 | -13.47% | 37 |

## Test 4 — Drawdown deep dive

### Top-5 drawdowns (OPTIMIZED base)

| Start | Trough | End | DD | FOMC in range |
|---|---|---|---|---|
| 2018-01-25 | 2018-10-31 | 2019-09-27 | -19.43% | 14 |
| 2019-12-30 | 2020-02-25 | 2020-05-26 | -12.6% | 4 |
| 2021-12-29 | 2021-12-29 | 2022-02-23 | -10.22% | 1 |
| 2015-05-26 | 2015-12-30 | 2016-06-28 | -10.11% | 9 |
| 2012-03-29 | 2012-04-25 | 2012-08-29 | -8.22% | 3 |

### Top-5 drawdowns (OPTIMIZED + M26)

| Start | Trough | End | DD | FOMC in range |
|---|---|---|---|---|
| 2014-06-30 | 2015-12-30 | 2016-07-26 | -13.8% | 16 |
| 2018-01-25 | 2018-02-23 | 2019-01-25 | -12.94% | 8 |
| 2019-04-25 | 2019-04-25 | 2019-06-28 | -12.66% | 2 |
| 2019-12-30 | 2020-02-25 | 2020-05-26 | -12.6% | 4 |
| 2024-11-29 | 2025-01-28 | 2025-05-23 | -12.51% | 4 |

### Targeted windows

| Period | Base cum | M26 cum | d | FOMC | Deferred |
|---|---|---|---|---|---|
| March 2020 | +12.08% | +12.08% | +0.00pp | 3 | 0 |
| Q4 2018 | -6.24% | +1.21% | +7.45pp | 4 | 1 |
| 2022 | +33.58% | +30.11% | -3.47pp | 8 | 2 |

## Test 5 — False cost check

- Deferred rebalances: **28**
- Top-1 pick differed after 5d shift: **9** (32%)
- Top-k set differed: **22**
- When top-1 changed: better=2, worse=7, avg dret=-2.92pp

Pick-change examples (first 20):

| Date | Base top1 | M26 top1 | dret |
|---|---|---|---|
| 2011-01-25 | SOXX | XLE | -1.06% |
| 2012-01-25 | SOXX | GLD | -5.67% |
| 2012-04-25 | QQQ | XLK | -1.94% |
| 2012-10-24 | XLE | GLD | +0.60% |
| 2014-10-31 | QQQ | IGV | -5.31% |
| 2018-09-27 | IGV | VGT | +6.85% |
| 2022-07-26 | SHY | XLE | -5.86% |
| 2024-03-22 | SOXX | XLE | -1.60% |
| 2025-01-28 | XLE | IGV | -12.26% |

## Verdict

- MaxDD improvement: **+5.63pp** (threshold >4pp)
- CAGR drop       : **+0.23pp** (threshold <1pp)
- Mechanism (FOMC in target drawdowns): **yes**
- **Decision: INCLUDE M26 in OPTIMIZED**
