# Matched Filter for Financial Signal Normalization

**Citation:** Kang (2024/2025). "Optimal Signal Extraction from Order Flow: A Matched Filter Perspective on Normalization and Market Microstructure." arXiv:2512.18648.

**Core mechanism:** From signal processing: optimal normalization of a financial signal depends on the signal-generating process. Market cap normalization is the "matched filter" for institutional investors; trading value normalization is optimal for volume-targeting traders.

**Signal:** For each ETF, compute order flow or volume imbalance. Normalize by market cap (NOT trading volume). Achieves 1.32-1.97x higher correlation with future returns vs. trading value normalization. Improvement comes from matching normalization to the signal-generating process.

**Data needed:** Daily volume, price, and market cap data per ETF.

**Performance:** Validated on 2.7M stock-day observations (2020-2024). Monte Carlo confirms bidirectional: matched filters achieve up to 1.99x higher signal correlation.

**Weaknesses:** Korean market data. Improvement is on signal quality (correlation), not directly portfolio Sharpe. Requires understanding marginal trader identity.

**Assessment:** Clean, testable contribution from signal processing theory. 30-100% signal quality improvement is substantial. **Not data mining -- 80+ years of matched filter theory backing it.**

**Application to 8-ETF rotation:** When computing volume-based signals (unusual volume, accumulation/distribution), normalize by float-adjusted market cap rather than average daily volume. One-line code change, potentially meaningful feature quality improvement.
