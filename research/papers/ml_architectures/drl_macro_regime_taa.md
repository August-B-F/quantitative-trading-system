# Tactical Asset Allocation Using Deep Reinforcement Learning And Latent Macroeconomic Conditions

- **Authors:** Tauseef Kazi, Ken Abbott, Joe Wayne Byers
- **Year:** 2025
- **Source:** SSRN #5579472

## Architecture

- LSTM-based macroeconomic regime shift encoder
- Macro, temporal, and spatially aware transformer agent
- Deep Reinforcement Learning framework
- Allocates across 36 ETFs (multiple geographies and asset classes)

## Key Innovation

Regime shift encoder conditions the RL agent's policy on detected macroeconomic regime, enabling adaptive allocation without explicit regime labels. End-to-end training optimizes for portfolio metrics directly.

## Application to 8-ETF Rotation System

Scale down from 36 to 8 ETFs. LSTM regime encoder detects macro shifts; transformer agent learns optimal allocation conditioned on regime state.

## Known Failure Modes

- RL training instability and sample inefficiency
- Requires substantial computational resources
- Reward shaping choices significantly impact learned policy
- Overfitting risk on limited financial episodes
