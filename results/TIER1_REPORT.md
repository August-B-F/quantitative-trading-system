# TIER 1 REPORT

Splitter: ExpandingSplitter (min_train=60mo, val=6mo, test=3mo, step=3mo, sample_every=5d, embargo=5d, halflife=36mo)

## Rotation Models

| Exp | Model | Features | Target | Acc | Top2 | RankCorr | WF CAGR | Sharpe | MaxDD | vs B0 | vs B2 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| E01_ridge_min_t2 | Ridge | MIN(13) | T2 | 14.8% | 33.3% | 0.028 | 4.1% | 0.29 | -50.9% | 3.2% | -15.2% |
| E02_histgb_core_t2 | HistGB | CORE(50) | T2 | 8.5% | 16.4% | -0.072 | 8.1% | 0.50 | -24.5% | -3.2% | -11.2% |
| E03_rf_core_t1 | RF | CORE(50) | T1 | 14.8% | 31.2% | nan | 9.9% | 0.55 | -49.3% | 3.2% | -9.3% |
| B0 | Random | n/a | n/a | 11.6% | ~25% | 0.000 | 12.0% | 0.69 | -25.8% | — | — |
| B2 | Systematic 63d | n/a | n/a | 22.8% | n/a | n/a | 19.2% | 1.00 | -21.7% | — | — |
| B1 | QQQ buy&hold | n/a | n/a | n/a | n/a | n/a | 17.7% | 1.01 | -22.2% | — | — |

## Drawdown Models (Mode C)

| Exp | Model | Precision | Recall | F1 | FPR | ModeC CAGR | Sharpe | ModeC MaxDD | B2 MaxDD |
|---|---|---|---|---|---|---|---|---|---|
| E04_histgb_core_t4 | HistGB CORE(50) | 28.6% | 30.0% | 0.293 | 8.9% | 19.9% | 1.07 | -21.7% | -21.7% |
| E05_logreg_core_t4 | LogReg CORE(50) | 9.8% | 25.0% | 0.141 | 27.2% | 11.5% | 0.73 | -21.7% | -21.7% |
| B3 | Always-no-DD | n/a | 0% | 0 | 0% | 19.2% | 1.00 | -21.7% | -21.7% |

## Annual Returns - Rotation

| Year | E01 | E02 | E03 |
|---|---|---|---|
| 2010 | 23.8% | 26.7% | 17.7% |
| 2011 | -10.6% | -22.5% | 18.0% |
| 2012 | -5.1% | 19.3% | 15.7% |
| 2013 | -5.8% | 9.4% | 3.8% |
| 2014 | 6.2% | 3.4% | 17.2% |
| 2015 | -4.3% | 8.3% | 0.3% |
| 2016 | 16.4% | 3.5% | 21.5% |
| 2017 | -0.8% | 15.6% | 37.6% |
| 2018 | -31.8% | -1.1% | -7.3% |
| 2019 | 18.0% | 20.0% | 49.3% |
| 2020 | -4.8% | 34.6% | 51.0% |
| 2021 | 11.1% | -9.7% | 9.6% |
| 2022 | 17.6% | 19.8% | 17.0% |
| 2023 | 8.3% | 8.1% | -10.7% |
| 2024 | 41.2% | 1.7% | -4.9% |
| 2025 | 46.8% | 27.8% | -23.4% |
| 2026 | -28.2% | -18.5% | -22.1% |

## Annual Returns - Drawdown Mode C

| Year | E04 ModeC | E05 ModeC |
|---|---|---|
| 2010 | 31.6% | 26.1% |
| 2011 | 22.2% | 11.3% |
| 2012 | -2.1% | -2.1% |
| 2013 | 20.4% | 18.8% |
| 2014 | 19.3% | 19.3% |
| 2015 | -4.3% | -4.3% |
| 2016 | 31.5% | 9.4% |
| 2017 | 22.2% | 10.5% |
| 2018 | -14.8% | -14.8% |
| 2019 | 29.4% | 18.7% |
| 2020 | 23.7% | -6.0% |
| 2021 | 42.7% | 47.1% |
| 2022 | 22.1% | -3.0% |
| 2023 | 14.0% | 7.3% |
| 2024 | 13.0% | 3.1% |
| 2025 | 73.5% | 74.5% |
| 2026 | -5.6% | -5.6% |

## Q&A

**Q1 (beat B0 by >5%?):** Best rotation = E01_ridge_min_t2 at 14.8% accuracy vs B0 11.6%, gap = 3.2%. NO.
**Q2 (beat B2 CAGR meaningfully?):** Best CAGR = E03_rf_core_t1 9.9% vs B2 19.2% (gap -9.3%, sharpe gap -0.45). NO (within noise).
**Q3 (drawdown signal?):** E04 recall=30.0%, precision=28.6%, E05 recall=25.0%, precision=9.8%.
E04 hits: 2020-03: prob=0.01 actual=0; 2022-04: prob=0.44 actual=0; 2022-09: prob=0.42 actual=0
E05 hits: 2020-03: prob=0.99 actual=0; 2022-04: prob=0.51 actual=0; 2022-09: prob=0.11 actual=0
**Q4 (Mode C reduces MaxDD?):** E04 ModeC MaxDD=-21.7% vs B2 -21.7% (improvement -0.0pp), CAGR 19.9% vs B2 19.2%. E05 ModeC MaxDD=-21.7% CAGR=11.5%.
**Q5 (linear vs nonlinear drawdown?):** E04 F1=0.293 vs E05 F1=0.141, gap=+0.152. NONLINEAR (E04 >> E05).
**Q6 (E03 prediction distribution):** {'SOXX': 54, 'QQQ': 8, 'XLK': 24, 'VGT': 10, 'IGV': 38, 'XLE': 34, 'GLD': 9, 'SHY': 12}. Train freq: [0.243, 0.058, 0.03, 0.019, 0.116, 0.224, 0.209, 0.102].
**Q7 (cross-sectional helps?):** E01 spearman=0.028, E02 spearman=-0.072, E03 (no expansion) accuracy=14.8%.
**Q8 (fold consistency):** Best model = E01_ridge_min_t2, fold acc mean=15.3% std=0.133 across 63 folds.