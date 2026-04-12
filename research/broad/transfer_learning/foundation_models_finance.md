# Time Series Foundation Models in Finance (Negative Result)

**Citation:** Rahimikia, E. et al. (2025). "Re(Visiting) Time Series Foundation Models in Finance." arXiv:2511.18578.

**Core mechanism:** First large-scale test of whether generic time series foundation models (TSFMs) transfer to finance. Tests zero-shot, fine-tuned, and finance-native pre-training across 34 years, 94 countries, ~2 billion observations.

**Key finding:** Off-the-shelf pre-trained TSFMs (TimeGPT, Chronos, etc.) perform POORLY in zero-shot and fine-tuning for financial forecasting. Finance-native pre-training significantly outperforms. General transfer does NOT work for finance.

**Data needed:** Large-scale financial time series for pre-training.

**Performance:** Finance-native pre-training >> fine-tuned generic >> zero-shot generic.

**Weaknesses:** Primarily a negative result for transfer learning. Finance-native pre-training requires substantial data and compute.

**Assessment:** Extremely important empirical result. **Saves you from wasting time on generic foundation models.** Well-executed study with a credible dataset.

**Application to 8-ETF rotation:** Do NOT use generic pre-trained models (TimeGPT, Chronos) for ETF predictions. If exploring foundation architectures, pre-train from scratch on financial data. Better yet: treat this as evidence that your domain-specific models are the right approach.
