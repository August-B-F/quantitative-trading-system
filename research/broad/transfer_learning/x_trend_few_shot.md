# X-Trend: Few-Shot Learning for Trend Following

**Citation:** (2023/2024). "Few-Shot Learning Patterns in Financial Time-Series for Trend-Following Strategies." arXiv:2310.10500v2.

**Core mechanism:** Uses cross-attention to transfer trend patterns from a "context set" of known financial regimes to make forecasts on new, unseen regimes. Model identifies similar historical patterns and adapts without retraining. Can take zero-shot positions on entirely novel assets.

**Signal:** Maintain context set of labeled regime episodes (trending up/down, ranging, crisis) across multiple asset classes. For new target window, cross-attention compares target's pattern to all context episodes, computes similarity-weighted forecasts. Architecture is a cross-attentive network processing (context_set, target_query) pairs.

**Data needed:** Multi-asset price history across equities, FX, commodities, fixed income. Richer context set = better transfer.

**Performance:** Sharpe improvement of 18.9% over neural forecaster and 10x over conventional TSMOM (2018-2023). Zero-shot on unseen assets achieves 5x Sharpe improvement.

**Weaknesses:** 2018-2023 test period is short (5 years). 10x improvement over TSMOM is partly because TSMOM crashed in this period. Context set requires some curation. Transaction costs not explicitly modeled.

**Assessment:** Cross-attention transfer mechanism is genuinely novel. Zero-shot capability impressive. **Magnitude likely overstated but mechanism is sound and additive.**

**Application to 8-ETF rotation:** Build context set from 8 ETFs' historical regime episodes plus additional assets. Use cross-attention to identify which historical patterns resemble current conditions. Provides transfer-learning-based regime signal complementing HMM detection.
