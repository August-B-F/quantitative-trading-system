# Modality-aware Transformer for Financial Time Series Forecasting

- **Authors:** Hajar Emami, Xuan-Hong Dang, Yousaf Shah, Petros Zerfos
- **Year:** 2023
- **Source:** arXiv:2310.01232

## Architecture

- 2 encoder layers, 1 decoder layer
- 8 attention heads, output dimension 512 per head
- Three specialized MHA types: Intra-modal, Inter-modal, Target-modal
- Feature-level attention preceding each MHA block
- Optimizer: Adam, lr=1e-4, batch_size=16, early stopping within 10 epochs
- Loss: MSE

## Input/Output

- **Input:** Numerical time series (interest rates) + categorical text (FED statements) + economic indicators (FRED)
- **Lookback:** 9 months
- **Prediction horizons:** 1, 3, 6 months

## Performance (U.S. Interest Rate Prediction)

Outperformed Transformer, Informer, Reformer, Autoformer baselines across 2, 5, 10, 30-year maturities.

## Application to 8-ETF Rotation System

Inter-modal attention could fuse ETF price data with macro text (FOMC minutes, economic reports). Feature-level attention automatically identifies which macro indicators matter for each ETF. Multi-horizon output enables forward-looking allocation.

## Known Failure Modes

- Requires NLP preprocessing for text modality
- Small batch size may limit generalization
- Tested only on interest rate forecasting (not equity/multi-asset)
