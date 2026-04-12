# REGIME INTEGRATION REPORT

Walk-forward regime classifier (HistGB on CORE features, 4-class growth/inflation quadrants): mean fold accuracy = **0.665**.

Six experiments test how to connect regime predictions to the systematic momentum base strategies (T2_balanced and T2_3legCAGR_softML).

## Comparison table

| Strategy | Description | CAGR | Sharpe | MaxDD | n | vs T2_balanced Sharpe | vs T2_softML Sharpe |
|---|---|---|---|---|---|---|---|
| B3_top1_63d | Baseline B3: top-1 by 63d momentum (8 ETFs) | 19.4% | 1.00 | -22.3% | 189 | -0.22 | -0.24 |
| T2_balanced | 0.5*[top1+SMA200-4% gate] + 0.5*top3 (63d momentum) | 19.3% | 1.22 | -21.0% | 189 | +0.00 | -0.02 |
| T2_3legCAGR_softML | T2_3legCAGR base + soft ML EV gate (HistGB on macro) | 16.9% | 1.24 | -16.7% | 189 | +0.02 | +0.00 |
| E-R1 | T2_balanced structure w/ regime-conditional lookback (63d stable, 21d transition) | 21.2% | 1.34 | -21.0% | 189 | +0.12 | +0.09 |
| E-R2 | T2_balanced w/ regime-tilted top-3 weights (1.5x favored / 0.75x other) | 19.5% | 1.23 | -20.2% | 189 | +0.01 | -0.02 |
| E-R3 | T2_3legCAGR_softML w/ 0.5x EV weight on recessionary transitions | 15.6% | 1.21 | -16.7% | 189 | -0.01 | -0.03 |
| E-R4 | Regime-filtered universe (HG/LI, HG/HI, LG/LI, LG/HI eligible sets incl. TLT/XLV), top-3 by 63d mom within set, SMA200 gate | 11.3% | 0.86 | -22.8% | 189 | -0.36 | -0.38 |
| E-R5 | Dispersion×Regime: hi+stable→momentum; hi+trans→0.7*mom+0.3*SHY; lo+stable→QQQ; lo+trans→SHY | 15.3% | 1.04 | -20.1% | 189 | -0.18 | -0.20 |
| E-R6 | Kitchen sink final layer = L4_universe_tilt | 20.8% | 1.20 | -22.2% | 189 | -0.02 | -0.05 |

## Annual returns

| Year | B3_top1_63d | T2_balanced | T2_3legCAGR_softML | E-R1 | E-R2 | E-R3 | E-R4 | E-R5 | E-R6 |
|---|---|---|---|---|---|---|---|---|---|
| 2010 | 35.0% | 27.8% | 25.4% | 20.9% | 27.9% | 12.5% | 5.3% | 0.7% | 21.3% |
| 2011 | 15.5% | 15.6% | 2.5% | 18.3% | 14.9% | 3.5% | 2.0% | -14.5% | 14.1% |
| 2012 | -2.1% | 7.0% | 12.6% | 5.6% | 8.2% | 12.6% | 22.1% | 13.4% | 10.3% |
| 2013 | 23.5% | 24.7% | 18.2% | 24.7% | 25.0% | 18.2% | 27.8% | 35.8% | 26.9% |
| 2014 | 19.3% | 12.6% | 13.1% | 12.6% | 13.0% | 13.1% | 8.5% | 14.4% | 13.9% |
| 2015 | -4.3% | -3.6% | 1.3% | -5.6% | -2.1% | 1.3% | -1.0% | 7.6% | -4.5% |
| 2016 | 35.1% | 29.2% | 18.8% | 29.2% | 28.0% | 18.8% | -1.9% | 14.9% | 24.4% |
| 2017 | 25.1% | 26.3% | 20.3% | 23.1% | 27.1% | 15.2% | 26.2% | 18.9% | 27.7% |
| 2018 | -15.5% | -17.4% | -2.0% | -17.4% | -17.0% | -2.0% | -22.7% | -8.5% | -18.5% |
| 2019 | 30.5% | 32.0% | 36.9% | 31.9% | 31.6% | 33.3% | 19.1% | 23.1% | 26.4% |
| 2020 | 23.4% | 22.5% | 9.2% | 22.5% | 21.4% | 9.2% | 0.5% | 17.6% | 23.9% |
| 2021 | 43.1% | 30.8% | 16.9% | 29.8% | 31.5% | 16.9% | 26.2% | 27.3% | 27.9% |
| 2022 | 23.7% | 33.4% | 30.6% | 33.4% | 35.2% | 30.6% | 12.7% | 33.4% | 33.0% |
| 2023 | 9.7% | 13.9% | 19.8% | 20.7% | 14.3% | 26.1% | 22.3% | 15.7% | 19.6% |
| 2024 | 3.5% | 12.3% | 14.5% | 20.1% | 11.3% | 11.2% | 19.5% | 12.4% | 20.7% |
| 2025 | 73.5% | 58.7% | 46.3% | 76.9% | 60.6% | 43.6% | 34.6% | 47.6% | 88.5% |
| 2026 | -5.6% | -2.9% | -7.4% | 8.9% | -3.5% | -7.4% | -7.1% | -2.0% | -1.3% |

## Highlights

- Sharpe winner: E-R1: CAGR 21.2% / Sharpe 1.34 / MaxDD -21.0%
- CAGR winner: E-R1: CAGR 21.2% / Sharpe 1.34 / MaxDD -21.0%
- MaxDD winner: E-R3: CAGR 15.6% / Sharpe 1.21 / MaxDD -16.7%
- Reference T2_balanced: T2_balanced: CAGR 19.3% / Sharpe 1.22 / MaxDD -21.0%
- Reference T2_3legCAGR_softML: T2_3legCAGR_softML: CAGR 16.9% / Sharpe 1.24 / MaxDD -16.7%

## Kitchen-sink (E-R6) layer diagnostics

Final layer kept: **L4_universe_tilt**

| Layer | CAGR | Sharpe | MaxDD | Kept |
|---|---|---|---|---|
| L0_3leg_base | 19.9% | 1.15 | -22.7% | yes |
| L1_sma_gate | 18.9% | 1.14 | -23.6% | no |
| L2_ev_gate | 10.3% | 0.86 | -17.8% | no |
| L3_regime_lookback | 20.6% | 1.20 | -22.7% | yes |
| L4_universe_tilt | 20.8% | 1.20 | -22.2% | yes |
| L5_disp_sizing | 17.3% | 1.09 | -20.1% | no |

## Interpretation

No regime-integration strategy simultaneously hits CAGR>18%, Sharpe>1.15, and MaxDD>-20%.

Strategies that strictly improve over T2_balanced (Sharpe +≥0.02, CAGR ≥−1.5pp, MaxDD ≥−1pp): E-R1.