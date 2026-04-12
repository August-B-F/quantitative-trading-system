# EXFormer: Multi-Scale Trend-Aware Transformer

**Citation:** (2025/2026). "EXFormer: A Multi-Scale Trend-Aware Transformer with Dynamic Variable Selection for Foreign Exchange Returns Prediction." arXiv:2512.12727.

**Core mechanism:** Multi-scale attention using parallel convolutional branches with different receptive fields to align observations by local slope (trend). Dynamic variable selector assigns time-varying importance weights to 28 exogenous covariates, providing interpretability.

**Signal:** (1) Multi-scale conv branches compute trend features at short/medium/long horizons. (2) Self-attention operates on trend-aligned representations, not raw prices. (3) Squeeze-and-excitation block recalibrates channel importance. (4) Dynamic variable selector outputs time-varying feature importance. Directional accuracy improvement of 8.5-22.8% over random walk.

**Data needed:** Price data + exogenous variables (adaptable to any feature set).

**Performance:** 18-25% cumulative returns over ~1 year with Sharpe >1.8.

**Weaknesses:** Only tested on FX (3 pairs). One-year backtest is short. Sharpe >1.8 on daily FX is suspicious. Transaction costs at institutional FX levels.

**Assessment:** Architecture innovations (trend-aligned attention, dynamic variable selection) are sound engineering. Dynamic variable selector is genuinely useful for interpretability. **Performance numbers should be treated with skepticism, but the architecture ideas are worth adopting.**

**Application to 8-ETF rotation:** Adopt multi-scale trend-aligned attention for TFT. Pre-process features through multi-scale conv extractors before attention. Add dynamic variable selector to monitor which macro features model relies on over time.
