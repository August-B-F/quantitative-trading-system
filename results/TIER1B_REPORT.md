# TIER 1B REPORT — Alternative Approaches

Splitter: ExpandingSplitter (min_train=60mo, val=6mo, test=3mo, step=3mo, sample_every=5d, embargo=5d). Cross-sectional expansion where noted. Monthly aggregation.

Baselines (from results/baselines.json):
- **B0 random**: acc 11.6%, CAGR 12.0%, Sharpe 0.69, MaxDD -25.8%
- **B1 QQQ buy&hold**: CAGR 17.7%, Sharpe 1.01, MaxDD -22.2%
- **B2 systematic 63d momentum**: acc 22.8%, CAGR 19.2%, Sharpe 1.00, MaxDD -21.7%

## Rotation / Prediction Models

| Exp | Approach | Acc | Top2 | WF CAGR | Sharpe | MaxDD | Δ CAGR vs B2 |
|---|---|---|---|---|---|---|---|
| B2 | systematic 63d momentum | 22.8% | n/a | 19.2% | 1.00 | -21.7% | 0.0% |
| B0 | random | 11.6% | n/a | 12.0% | 0.69 | -25.8% | -7.3% |
| EA1 | regime classifier → ETF map | 68.3% | n/a | 8.4% | 0.49 | -40.6% | -10.8% |
| EA2 | leadership persistence (binary) | 55.6% | n/a | 12.3% | 0.70 | -28.0% | -6.9% |
| EA3 | HistGB CORE fwd42 regression | 8.0% | 25.5% | 10.3% | 0.59 | -21.1% | -8.9% |
| EA4 | HistGB CORE fwd63 regression | 13.4% | 25.7% | 16.0% | 0.84 | -30.1% | -3.3% |
| EB1 | large HistGB EXTENDED T2 | 11.1% | 25.9% | 8.1% | 0.49 | -49.9% | -11.1% |
| EB2 | MLP small (128,64) CORE T2 | 13.8% | 25.4% | 5.3% | 0.34 | -48.4% | -14.0% |
| EB3 | MLP big (256,128,64) EXT T2 | — | — | — | — | — | FAILED |
| EB4 | deep HistGB ALL features T2 | 18.5% | 25.9% | 10.5% | 0.56 | -55.9% | -8.8% |
| EC1 | specialist team (5 models + rules) | n/a | n/a | 7.2% | 0.47 | -44.2% | -12.0% |
| EC2 | stacked meta-learner | 18.3% | n/a | 15.7% | 0.75 | -26.3% | -3.5% |
| ED1 | k-NN similarity | 15.8% | n/a | 6.5% | 0.40 | -38.2% | -12.8% |
| ED2 | contrarian (invert E03) | 6.3% | n/a | 1.1% | 0.29 | -10.8% | -18.2% |
| ED3 | signal disagreement heuristic | n/a | n/a | 15.9% | 0.83 | -29.9% | -3.3% |
| ED4 | LSTM temporal overlay | n/a | n/a | 14.5% | 0.92 | -17.9% | -4.7% |
| ED5 | dispersion predictor + overlay | n/a | n/a | 18.2% | 0.99 | -20.5% | -1.1% |
| ED6 | ensemble of all rotation models | n/a | n/a | 10.2% | 0.58 | -36.0% | -9.1% |

## Risk Signal Experiments

| Exp | Metric | Value | Notes |
|---|---|---|---|
| EA5 | F1 / AUC | 0.122 / 0.551 | overlay CAGR 6.5% vs weekly sys 9.8% |
| ED5 | pred-vs-actual dispersion corr | 0.338 | overlay CAGR 18.2%, MaxDD -20.5% |
| ED4 | pred-avg sign accuracy | 0.516 | corr 0.132 |

## Annual Returns — Top 3 Models vs B2

| Year | ED5 | EA4 | ED3 | B2 ref |
|---|---|---|---|---|
| 2010 | 33.1% | n/a | 37.1% | — |
| 2011 | -15.7% | n/a | 19.1% | — |
| 2012 | 12.9% | n/a | -4.9% | — |
| 2013 | 35.8% | n/a | 16.3% | — |
| 2014 | 14.6% | n/a | 26.9% | — |
| 2015 | -3.4% | n/a | -13.2% | — |
| 2016 | 16.0% | n/a | 32.8% | — |
| 2017 | 34.2% | n/a | 37.3% | — |
| 2018 | -3.6% | n/a | -7.2% | — |
| 2019 | 23.5% | n/a | 11.0% | — |
| 2020 | 23.0% | n/a | 43.2% | — |
| 2021 | 42.7% | n/a | 25.4% | — |
| 2022 | 23.7% | n/a | 11.4% | — |
| 2023 | 10.0% | n/a | -3.0% | — |
| 2024 | 0.5% | n/a | -3.2% | — |
| 2025 | 73.5% | n/a | 51.3% | — |
| 2026 | -5.6% | n/a | 3.2% | — |

Top 3 legend: **ED5** = dispersion predictor + overlay; **EA4** = HistGB CORE fwd63 regression; **ED3** = signal disagreement heuristic

## Q&A

**Q1 (any approach beat B2 in WF CAGR?):** Best = **ED5** (dispersion predictor + overlay) CAGR 18.2% vs B2 19.2% (Δ -1.1%). NO.
**Q2 (reduce MaxDD >5pp with CAGR >17%?):** NO. No approach met both thresholds.
**Q3 (which BLOCK showed most promise?):**
  - Block A best = **EA4** (HistGB CORE fwd63 regression) CAGR 16.0% Sharpe 0.84
  - Block B best = **EB4** (deep HistGB ALL features T2) CAGR 10.5% Sharpe 0.56
  - Block C best = **EC2** (stacked meta-learner) CAGR 15.7% Sharpe 0.75
  - Block D best = **ED5** (dispersion predictor + overlay) CAGR 18.2% Sharpe 0.99
**Q4 (specialists show individual skill?):** M1 regime fold acc = 65.7%, M3 momentum fold acc = 58.1%. Team combined CAGR = 7.2%.
**Q5 (contrarian inversion > random?):** inverted acc = 6.3% vs random 11.6%. Original E03 = 14.8%.
**Q6 (dispersion prediction works?):** pred-vs-actual corr = 0.338. Overlay CAGR 18.2%.
