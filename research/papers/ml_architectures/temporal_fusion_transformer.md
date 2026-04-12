# Temporal Fusion Transformers for Interpretable Multi-horizon Time Series Forecasting

**HIGH PRIORITY**

- **Authors:** Bryan Lim, Sercan O. Arik, Nicolas Loeff, Tomas Pfister (Google Cloud AI)
- **Year:** 2021
- **Source:** International Journal of Forecasting, Vol. 37(4), pp. 1748-1764
- **Links:** [arXiv](https://arxiv.org/abs/1912.09363)

## Architecture Details

- Recurrent layers (LSTM) for local temporal processing
- Interpretable multi-head self-attention for long-term dependencies
- **Variable Selection Networks (VSN):** softmax-gated feature importance scoring
- **Gated Residual Networks (GRN)** with ELU activations
- Gating layers (GLU) to suppress unnecessary components
- Three input types: static covariates, known future inputs, observed historical inputs
- Multi-horizon output (predicts multiple future timesteps simultaneously)

## Financial-Specific Handling

- Variable selection explicitly filters noise features (critical for low SNR financial data)
- Interpretable attention weights reveal which past timesteps matter most
- Static covariates can encode asset-level metadata
- Multi-horizon output enables multi-step-ahead regime forecasting

## Application to 8-ETF Rotation System

- **Known future inputs:** calendar features, scheduled economic releases
- **Static covariates:** ETF sector/asset class encoding
- **Observed inputs:** returns, volatility, macro indicators
- **Output:** probability distribution over future returns per ETF at multiple horizons
- Variable importance scores reveal which features drive allocation decisions per regime

## Reported Performance

Outperformed DeepAR, MQRNN, and other baselines. 7-36% improvement in P50/P90 quantile losses across electricity, traffic, retail, and volatility datasets.

## Known Failure Modes

- Requires careful hyperparameter tuning
- Performance degrades with very short sequences
- Attention can overfit to spurious temporal patterns in low-SNR regimes
