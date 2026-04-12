# Temporal Conformal Prediction (TCP)

**Citation:** (2025). "Temporal Conformal Prediction (TCP): A Distribution-Free Statistical and Machine Learning Framework for Adaptive Risk Forecasting." arXiv:2507.05470.

**Core mechanism:** Combines ML quantile forecaster with online conformal calibration using modified Robbins-Monro scheme. Specifically designed for non-stationary time series, addressing exchangeability violation that plagues standard conformal methods in finance.

**Signal:** Train any quantile regression model. Apply online conformal correction: at each step, adjust quantile threshold based on whether previous interval covered realized value. Produces adaptive prediction intervals maintaining long-run coverage despite non-stationarity.

**Data needed:** Any features you already use. Wraps around any base forecaster.

**Performance:** Near-nominal coverage across S&P 500, Bitcoin, Gold. Reduces interval width by 29% vs. historical simulation while maintaining coverage.

**Weaknesses:** Robbins-Monro learning rate trades off coverage accuracy vs. interval width adaptivity. In extremely fast regime changes, coverage can temporarily drop.

**Assessment:** Very practical and implementable. Online calibration is computationally trivial. 29% interval width reduction is meaningful for position sizing. **Legitimate improvement over naive historical VaR.**

**Application to 8-ETF rotation:** Wrap predictions with TCP intervals. Use for: (1) position sizing -- less allocation to wider-interval ETFs; (2) regime detection -- rapid widening signals change; (3) confidence weighting -- only act on predictions where interval excludes zero.
