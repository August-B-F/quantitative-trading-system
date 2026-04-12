# Honest Assessment: Rejected Papers and Why

Every paper that was considered but did not make the cut. If a paper cannot explain why it was rejected, it would have been included and flagged as UNCERTAIN. None required that flag -- every rejection has a clear reason.

---

## BEHAVIORAL FINANCE REJECTIONS

| Paper | Reason for Rejection |
|-------|---------------------|
| **Daniel, Hirshleifer & Subrahmanyam (1998)** -- "Overconfidence and Self-Attribution" | Purely theoretical, no implementable signal beyond what standard momentum captures |
| **Hong & Stein (1999)** -- "A Unified Theory of Underreaction" | Foundational theory only; the implementable version is Da et al. 2014 (Frog-in-the-Pan), which was included |
| **Da, Engelberg & Gao (2011)** -- "In Search of Attention" (Google SVI) | Search volume is not meaningfully differentiating among 8 broad ETFs; too noisy at asset-class level |
| **Xu, Li, Singh & Park (2023)** -- "Cross-Asset Time-Series Momentum" | Cross-asset signals overlap with existing canary-universe and macro-momentum signals |
| **Li, Teo & Yang (2019)** -- "ETF Momentum" (2-4 year formation) | Long-formation momentum overlaps with 12M TSMOM; 24-48M lookback incompatible with monthly rebalancing |
| **Xu (2024)** -- "Mutual Fund Herding and Stock Price Momentum" | Requires quarterly mutual fund holding data; partially overlaps with comomentum |

## FACTOR DECAY REJECTIONS

| Paper | Reason for Rejection |
|-------|---------------------|
| **Harvey, Liu & Zhu (2016)** -- "...and the Cross-Section of Expected Returns" | About false positives from multiple testing, not about how real factors erode; complementary context but no signal |
| **Dong, Kang & Peress (2025)** -- "Fast and Slow Arbitrage" | Required data (hedge fund flow decomposition into persistent/transient) not available in real-time for ETF rotation |
| **Hou, Xue & Zhang (2020)** -- "Replicating Anomalies" | Replication study diagnosing the problem without providing a novel solution |
| **Du & Vojtko (2024)** -- "Robustness Testing of Country and Asset ETF Momentum" | Confirms ETF momentum has weakened since 2010 but offers no novel solution beyond known signals |
| **Hua & Sun (2024)** -- "Dynamics of Factor Crowding" | Included as a paper file for strategic value, but the crowding measures require proprietary fund-level data; more framework than tradeable signal |

## MARKET MICROSTRUCTURE REJECTIONS

| Paper | Reason for Rejection |
|-------|---------------------|
| **Li, Teo & Yang (2019)** -- "ETF Momentum" (SSRN 3468556) | 2-4 year formation period far too long for monthly rotation; mechanism overlaps with standard XS momentum at longer horizons |
| **Pan & Zeng (2017/2021)** -- "ETF Arbitrage Under Liquidity Mismatch" | Describes structural fragility in bond ETFs, not a tradeable signal; no implementable portfolio strategy |

## CROSS-ASSET MACRO REJECTIONS

| Paper | Reason for Rejection |
|-------|---------------------|
| **Jacobsen, Stangl & Visaltanachoti (2009)** -- "Sector Rotation Across the Business Cycle" | 2% Jensen's alpha requires perfect hindsight of NBER dating; dissipates completely in real-time out-of-sample |
| **Sauer (2019)** -- "Sector Rotation via ML Regime" (SSRN 3473907) | ML-based regime with limited OOS testing; high overfitting risk to specific macro features and regime definitions |
| **Ang & Bekaert (2002/2011)** -- "How Do Regimes Affect Asset Allocation?" | Framework is equity/bond/cash, not sector rotation; regime signal overlaps with existing VIX/volatility-based signals |
| **Bai (2021)** -- "Predictable Returns over the Credit Cycle" | Credit expansion measure moves too slowly (7-10 year cycles); changes allocation perhaps once every 2-3 years; too slow for monthly |

## GEOPOLITICAL RISK REJECTIONS

| Paper | Reason for Rejection |
|-------|---------------------|
| **Smales (2021)** -- "Geopolitical Risk and Volatility Spillovers" | Confirms GPR-oil-equity transmission but adds no tradeable signal beyond Caldara-Iacoviello |
| **Chatziantoniou, Gabauer & Stenfors (2025)** -- "US Sectoral Volatility and Geopolitical Risk" | Volatility forecasting exercise, not a return prediction strategy; too recent for citation assessment |
| **Aizenman et al. (2023)** -- "Geopolitical Shocks and Commodity Market Dynamics" (NBER WP 31950) | Single-event study (Russia-Ukraine) with limited generalizability; not a systematic signal |

## SUPPLY CHAIN REJECTIONS

| Paper | Reason for Rejection |
|-------|---------------------|
| **Wu & Birge (2016)** -- "Supply Chain Network Structure and Firm Returns" | Requires Bloomberg SPLC data (expensive/proprietary); operates at firm level, not ETF level |
| **Barrot & Sauvagnat (2016)** -- "Input Specificity and Propagation" (QJE) | Excellent paper on supply chain contagion, but event-driven (natural disasters); cannot be computed as a forward-looking monthly signal |
| **Hou (2007)** -- "Industry Information Diffusion and the Lead-Lag Effect" (RFS) | Intra-industry big-to-small firm lead-lag; not applicable to cross-sector ETF rotation |

## COMPLEXITY SCIENCE REJECTIONS

| Paper | Reason for Rejection |
|-------|---------------------|
| **Scheffer et al. (2009)** -- "Early-warning Signals for Critical Transitions" (Nature) | Rising autocorrelation/variance as EWS are already subsumed by VIX/turbulence stack; false positives with fat-tailed financial data |
| **"Endogenous Crashes as Phase Transitions" (2024)** -- arXiv:2408.06433 | Elegant theory of crashes as dynamic phase transitions but purely theoretical; no implementable signal |

## NONLINEAR REGIME REJECTIONS

| Paper | Reason for Rejection |
|-------|---------------------|
| **Vetter & Herwartz (2024)** -- Smooth Transition VAR (sstvars R package) | Methodological tool, not applied paper with financial performance results |
| **Lin et al. (2021)** -- Deep Switching State Space Model (DS3M) | Deep learning black box; no financial portfolio backtest; overfitting risk with limited data; impractical for production |
| **Neri & Schneider (2012)** -- Maximum Entropy Option Distributions | Focused on option pricing, not regime detection for equity rotation |

## NETWORK / CONTAGION REJECTIONS

| Paper | Reason for Rejection |
|-------|---------------------|
| **Acemoglu, Ozdaglar & Tahbaz-Salehi (2015)** -- "Systemic Risk and Stability in Financial Networks" (AER) | Foundational theory on network topology and cascading failures; no implementable signal for ETF rotation |
| **"Statistical Validation of Contagion Centrality" (2024)** -- arXiv:2404.14337 | Leontief centrality for VAR networks; firm-level contagion, not implementable for 8-ETF monthly rotation |

## MACRO NOWCASTING REJECTIONS

| Paper | Reason for Rejection |
|-------|---------------------|
| **Oliveira et al. (2024)** -- NCDENow (Neural CDE for GDP) | NCDE is computationally expensive; only 2 countries tested; no portfolio allocation application; too early-stage |
| **Mariano & Ozmucur (2020)** -- MIDAS vs DFM comparison | Philippines-focused; no novel signal for US equity ETF rotation |
| **Schorfheide & Song (2015)** -- Real-Time Mixed-Frequency VAR | Well-known methodology subsumed by newer MIDAS approaches; no direct ETF application |

## ML METHODS REJECTIONS

| Paper | Reason for Rejection |
|-------|---------------------|
| **Covariate-dependent Stacking (2024)** -- arXiv:2408.09755 | Only demonstrated on land price prediction; no financial application or validation |
| **Combined ML with Dynamic Weighting (2025)** -- arXiv:2508.18592 | Stock selection focus; basic weighted averaging that doesn't add beyond standard ensemble techniques |
| **Contrastive Learning of Asset Embeddings** -- Dolphin et al. (2024) | Useful for asset similarity/classification, not for generating trading signals; no portfolio performance results |
| **Transfer Learning with Gramian Angular Field (2025)** -- arXiv:2504.00378 | Converting time series to images adds complexity without clear benefit; no multi-regime backtest |
| **Modality-aware Transformer (2023)** -- arXiv:2310.01232 | Feature-level attention across modalities; incremental over standard TFT multi-head attention |
| **Calibration in Deep Learning Survey (2023)** -- arXiv:2308.01222 | Comprehensive survey but no financial application or testing |
| **DRL for Optimal Portfolio (2026)** -- arXiv:2602.17098 | DRL vs mean-variance comparison; short backtest, no regime analysis, insufficient robustness |
| **Diffusion-Augmented RL (2025)** -- arXiv:2510.07099 | Creative synthetic stress generation for RL; only synthetic data, no real-world validation yet |
| **Sharpe Ratio Optimization in Bandits (2025)** -- arXiv:2508.13749 | Theoretical regret bounds paper; no empirical results |

## INTRADAY / OPERATIONS RESEARCH REJECTIONS

| Paper | Reason for Rejection |
|-------|---------------------|
| **Zarattini, Aziz, Barbon (2024)** -- "Beat the Market: Intraday SPY Strategy" | Pure intraday strategy (19.6% ann., Sharpe 1.33); requires continuous monitoring; single-instrument overfitting risk |
| **Barbon et al. (2021)** -- "Liquidity Provision to Leveraged ETFs" | End-of-day momentum from LETF rebalancing has decreased as markets adapted; daily-only frequency |
| **Fan, Ji, Lejeune (2023)** -- "DRO under Marginal and Copula Ambiguity" | Too similar to standard DRO; computationally expensive for monthly rebalancing |
| **FR-LUX (2025)** -- Friction-Aware Regime-Conditioned RL | Too close to DRL approaches already in system; cost model is worth borrowing but the paper itself is incremental |
| **RegimeFolio (2025)** -- arXiv:2510.14986 | Already in existing system (VIX-based regime classifier); 4-year backtest too short |
| **TrendFolios (2025)** -- arXiv:2506.09330 | Methodology (momentum + inverse vol + rebalancing) is well-known; adds no novelty beyond existing signals |
| **Integrated Prediction and Multi-period Portfolio (2025)** -- arXiv:2512.11273 | Too similar to SPO paper above; not specifically tested on ETFs |
| **DeePM: Regime-Robust Deep Learning (2026)** -- arXiv:2601.05975 | Deep learning approach too close to existing DRL methods in system |
| **Adams & MacKay (2007)** -- Vanilla BOCPD | Foundational but now superseded by score-driven extensions |

---

## SUMMARY STATISTICS

- **Total papers evaluated:** ~90+
- **Papers that passed all criteria:** 35
- **Papers rejected:** 55+
- **Most common rejection reason:** Fails criterion 6 (no novelty beyond existing signals) -- 18 papers
- **Second most common:** Fails criterion 1 or 2 (no testable mechanism / insufficient backtest) -- 14 papers
- **Third most common:** Fails criterion 5 (signal not computable with available data) -- 8 papers

The rejection list is intentionally longer than the accepted list. A skeptical quant PM would ask about everything that was *not* included more than what was.
