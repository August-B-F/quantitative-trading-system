# Financial Information Theory (NMI/Transfer Entropy)

**Citation:** Noguer i Alonso (2025). "Financial Information Theory." arXiv:2511.16339.

**Core mechanism:** Applies information-theoretic measures (entropy, KL divergence, mutual information, NMI, transfer entropy) to financial time series. NMI spikes during structural changes (2008, COVID), stays below 0.05 during normal periods (~77.9% of the time). Transfer entropy identifies directional information flow between assets.

**Signal:** (1) Rolling NMI between consecutive return windows. NMI > threshold signals regime break. (2) Transfer entropy identifies which ETFs "lead" -- allocate to leaders, avoid laggers. (3) Entropy-adjusted VaR for risk management. (4) Information-theoretic diversification criterion.

**Data needed:** Daily returns for ETF universe. Standard price data only.

**Performance:** Validated on S&P 500 2000-2025. NMI correctly identifies major regime changes.

**Weaknesses:** Framework paper, no direct portfolio backtest. NMI thresholds need calibration.

**Assessment:** Adds genuine novelty -- information theory is a different lens from HMM/jump models. NMI captures changes in *dependence structure*, not just levels. **Exactly what matters for rotation where correlations shift at regime breaks.**

**Application to 8-ETF rotation:** (1) Rolling NMI between each ETF pair as correlation regime indicator -- NMI spike means diversification is breaking down. (2) Transfer entropy to detect leading ETFs. (3) NMI regime signal as additional feature in regime detector ensemble.
