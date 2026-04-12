# HMM-LSTM Hybrid Detection of Market Regimes

- **Year:** 2024
- **Source:** ResearchGate / Academic Publication

## Architecture

- **Stage 1:** HMM identifies regime labels (bull, bear, static)
- **Stage 2:** LSTM uses regime probabilities as additional features for prediction
- Multi-step approach enriches LSTM with state probabilities + overall market state

## Performance

- Bear state recall: 88.89%
- Static state recall: 89.66%
- Bull state recall: 96.50%
- Overall accuracy: 94.45%
- Persistence rates >80% across all states

## Application to 8-ETF Rotation System

Use HMM to generate regime probabilities as input features for a downstream LSTM or Transformer that predicts ETF relative performance. Two-stage approach reduces overfitting vs end-to-end training.

## Known Failure Modes

- HMM regime labels may not align with economic intuition
- Two-stage training prevents end-to-end optimization
- May inherit HMM's tendency for too-frequent regime switches
