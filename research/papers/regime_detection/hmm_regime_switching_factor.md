# Regime-Switching Factor Investing with Hidden Markov Models

- **Authors:** Various
- **Year:** 2020
- **Source:** J. Risk Financial Manag. 2020, 13(12), 311 (MDPI)

## Core Signal / Method

Uses Hidden Markov Models to detect market regimes (bull/bear/transition), then rotates between factor models accordingly. HMM identifies regime shifts from return distributions.

## Reported Performance (2004-2026)

- Annualized return: 19.41%
- Sharpe Ratio: 1.22
- Max Drawdown: -19.54%

## Application to 8-ETF Rotation System

Use HMM as a regime detection overlay. Train on returns of a broad market index to classify current regime. In bull regimes, hold high-momentum offensive ETFs. In bear regimes, shift to defensive ETFs (bonds, gold). The HMM can serve as the ML overlay on top of systematic momentum rules.

## Known Failure Modes

- Regime classification lag (HMM updates with a delay)
- Model risk from incorrect state estimation
- Sensitivity to number of hidden states chosen
- Overfitting on training period
