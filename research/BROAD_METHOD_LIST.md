# Broad Method List

New methods and architectures NOT already in ML_ARCHITECTURE_IDEAS.md or REGIME_METHODS.md, worth testing for the 8-ETF rotation system.

---

## 1. ENSEMBLE / MODEL COMBINATION METHODS

### 1.1 Bayesian Hierarchical Stacking **[RECOMMENDED]**
- **What:** Model combination weights that vary as function of covariates (VIX, regime, yield curve), with partial pooling via hierarchical prior to prevent overfitting
- **Why it matters:** Different models work in different regimes. This learns which model to trust when, without overfitting the weight function
- **Implementation:** Stan or PyMC. Feed out-of-fold predictions from each candidate model + regime covariates
- **Source:** Yao, Vehtari, Gelman (2022) Bayesian Analysis
- **Effort:** Medium | **Expected Impact:** High

### 1.2 Bayesian Predictive Decision Synthesis (BPDS)
- **What:** Learns model combination weights optimized for the downstream *decision* (portfolio allocation), not forecast accuracy
- **Why it matters:** The best forecaster is not always the best input to the portfolio optimizer
- **Implementation:** Sequential MCMC over K candidate model outputs
- **Source:** Tallman & West (2024) arXiv:2405.01598
- **Effort:** Medium-High | **Expected Impact:** Moderate

### 1.3 Decision by Supervised Learning (DSL)
- **What:** Train models to directly predict optimal portfolio weights, not returns. Average 50-100 independent runs
- **Why it matters:** Bypasses predict-then-optimize error propagation
- **Implementation:** NN with walk-forward Sharpe-optimal weights as labels
- **Source:** arXiv:2503.13544 (2025)
- **Effort:** Medium | **Expected Impact:** Moderate

---

## 2. REGIME DETECTION METHODS

### 2.1 Asset-Specific SJM with Random Forest Forecaster **[RECOMMENDED]**
- **What:** Per-ETF regime detection via Statistical Jump Model, with RF predicting next-month regime. Only ~10 transitions in 22 years per asset
- **Why it matters:** Per-asset regimes are more actionable than single market state. SJM's jump penalty dramatically reduces false signals
- **Implementation:** SJM + sklearn RandomForest + Black-Litterman
- **Source:** Shu, Yu, Mulvey (2024) Annals of Operations Research
- **Effort:** Medium | **Expected Impact:** High

### 2.2 Score-Driven Bayesian Online Changepoint Detection (BOCPD) **[RECOMMENDED]**
- **What:** Online regime detection where within-regime parameters evolve via score-driven updates (not static). Non-parametric in number of regimes
- **Why it matters:** Handles intra-regime drift that HMMs miss. Run-length posterior gives probability of regime change
- **Implementation:** Extend Adams-MacKay BOCPD with GAS observation model
- **Source:** Tsaknaki, Lillo, Mazzarisi (2023) arXiv:2307.02375
- **Effort:** Medium | **Expected Impact:** High

### 2.3 Semi-Parametric Regime Transitions
- **What:** Replace logistic/probit transition function in Markov-switching with kernel-learned nonparametric function
- **Why it matters:** Captures nonlinear covariate interactions (VIX x sentiment) driving regime transitions
- **Source:** Chen et al. (2025) arXiv:2604.04963
- **Effort:** High | **Expected Impact:** Moderate (needs validation)

### 2.4 TDA Persistence Landscapes for Crash Proximity
- **What:** Algebraic topology on multivariate returns. Rising Lp-norm = approaching crash (250-day lead)
- **Why it matters:** Coordinate-invariant, captures structural topology changes invisible to correlation/volatility
- **Source:** Gidea & Katz (2018) Physica A
- **Effort:** Medium-High | **Expected Impact:** Moderate (strategic overlay)

### 2.5 LPPLS Bubble Detection
- **What:** Log-periodic power law singularity model. Multi-scale confidence indicator for bubble proximity
- **Why it matters:** 200+ years of S&P 500 validation. Battle-tested in real-time since 2009
- **Source:** Shu & Song (2024) / Sornette group
- **Effort:** Medium | **Expected Impact:** Moderate (tail-risk overlay)

---

## 3. CALIBRATION / UNCERTAINTY METHODS

### 3.1 Temporal Conformal Prediction (TCP) **[RECOMMENDED]**
- **What:** Online-calibrated prediction intervals via Robbins-Monro scheme. Distribution-free, handles non-stationarity
- **Why it matters:** 29% narrower intervals than historical simulation with maintained coverage. Trivially wraps any base model
- **Implementation:** Any quantile forecaster + online Robbins-Monro correction
- **Source:** arXiv:2507.05470 (2025)
- **Effort:** Low | **Expected Impact:** Moderate-High

### 3.2 Skewed Student-t Distribution Output Head
- **What:** Replace model's final layer with 4 outputs (mu, sigma, nu, gamma) of skewed Student-t. Train with NLL loss
- **Why it matters:** Captures fat tails and asymmetry. Strictly dominates Gaussian outputs for financial returns
- **Implementation:** Change output layer + loss function. Minimal architectural change
- **Source:** arXiv:2508.18921 (2025)
- **Effort:** Low | **Expected Impact:** Low-Moderate

### 3.3 Conformal Predictive Portfolio Selection
- **What:** Distribution-free prediction intervals at portfolio level. Maximin lower bound selects allocation
- **Why it matters:** Safety net for worst-case portfolio outcomes
- **Source:** Kato (2024) arXiv:2410.16333
- **Effort:** Low-Medium | **Expected Impact:** Moderate

---

## 4. PORTFOLIO CONSTRUCTION / OPTIMIZATION METHODS

### 4.1 Smart Predict-then-Optimize (SPO+) **[RECOMMENDED]**
- **What:** Train return predictor with decision-focused loss (portfolio loss, not MSE). Backpropagates through optimizer
- **Why it matters:** "Forecast accuracy != decision quality." Directly tested on ETFs with monthly rebalancing
- **Implementation:** cvxpylayers for differentiable optimization + SPO+ loss
- **Source:** arXiv:2601.04062 (2026)
- **Effort:** Medium | **Expected Impact:** Moderate (50-100 bps)

### 4.2 Model Predictive Control (MPC)
- **What:** Multi-period lookahead optimization; execute only first period, then re-plan. Incorporates transaction costs in planning horizon
- **Why it matters:** 30-50% turnover reduction vs. single-period optimization. Smooths regime-transition whipsawing
- **Implementation:** Convex programming with 3-6 month lookahead
- **Source:** Nystrup et al. (2021) / Boyd et al. (2017)
- **Effort:** Medium | **Expected Impact:** Moderate

### 4.3 Regime-Switching DRO-CVaR
- **What:** Distributionally robust optimization where ambiguity set changes per regime. Wasserstein ball radius adapts automatically
- **Why it matters:** Principled uncertainty handling -- automatically conservative when uncertain
- **Source:** Pun, Wang, Yan (2023) SSRN 4378930
- **Effort:** Medium-High | **Expected Impact:** Moderate

### 4.4 RL within Bayesian Hierarchical Risk Parity
- **What:** RL agent adjusts allocations within risk parity guardrails. Prevents RL overfitting via constrained action space
- **Why it matters:** Gets RL adaptation benefits without extreme allocation risk
- **Source:** Kang & Tian (2025) arXiv:2508.11856
- **Effort:** High | **Expected Impact:** Moderate

---

## 5. SIGNAL PROCESSING / FEATURE ENGINEERING

### 5.1 Regime-Conditional Kalman Filtering
- **What:** Kalman filter parameters change with detected regime. High-vol: faster adaptation. Low-vol: slower, trust prior
- **Why it matters:** Addresses momentum whipsawing in choppy markets
- **Source:** Kang (2025/2026) arXiv:2601.05716
- **Effort:** Medium | **Expected Impact:** Moderate

### 5.2 Matched Filter Normalization
- **What:** Normalize volume signals by market cap instead of average volume. 30-100% signal quality improvement
- **Why it matters:** One-line change with substantial feature quality improvement from signal processing theory
- **Source:** Kang (2024/2025) arXiv:2512.18648
- **Effort:** Very Low | **Expected Impact:** Low-Moderate

### 5.3 FA-Sparse MIDAS Nowcasting
- **What:** Factor extraction + LASSO sparsity in mixed-frequency MIDAS framework. Adaptively switches between dense and sparse info
- **Why it matters:** Dense info dominates in crises, sparse in calm. More timely regime detection than official GDP
- **Source:** Beyhum & Striaukas (2023) JBES
- **Effort:** Medium-High | **Expected Impact:** Moderate

---

## 6. ARCHITECTURE INNOVATIONS

### 6.1 X-Trend Cross-Attention Transfer
- **What:** Cross-attention from context set of known regime episodes to new target window. Zero-shot capability on novel regimes
- **Why it matters:** Transfer learning across asset classes and regime types
- **Source:** arXiv:2310.10500 (2023/2024)
- **Effort:** High | **Expected Impact:** Moderate-High

### 6.2 EXFormer Multi-Scale Trend-Aligned Attention
- **What:** Parallel conv branches at different scales, then attention on trend-aligned representations. Dynamic variable selector
- **Why it matters:** Interpretable time-varying feature importance. Trend alignment improves attention quality
- **Source:** arXiv:2512.12727 (2025/2026)
- **Effort:** Medium-High | **Expected Impact:** Moderate

### 6.3 Mechanistic Interpretability for Transformers
- **What:** Activation patching, attention saliency, sparse autoencoders for diagnosing what financial transformers learn
- **Why it matters:** Answers "is my model learning real patterns or noise?" before deployment
- **Source:** arXiv:2511.21514 (2025)
- **Effort:** Medium | **Expected Impact:** Diagnostic (prevents overfit deployment)

### 6.4 Adaptive Thompson Sampling (CADTS)
- **What:** Non-stationary combinatorial bandit with discounted posteriors. Model-free consensus signal
- **Why it matters:** Principled alternative to fixed lookback windows. Automatic regime forgetting
- **Source:** arXiv:2410.04217 (2024)
- **Effort:** Low | **Expected Impact:** Low-Moderate

---

## IMPLEMENTATION PRIORITY MATRIX

| Priority | Method | Effort | Impact | Why First |
|----------|--------|--------|--------|-----------|
| 1 | **TCP Prediction Intervals** | Low | High | Wraps any model, immediate uncertainty quantification |
| 2 | **Matched Filter Normalization** | Very Low | Low-Med | One-line change, free improvement |
| 3 | **Bayesian Hierarchical Stacking** | Medium | High | Principled regime-conditional ensemble |
| 4 | **Asset-Specific SJM + RF** | Medium | High | Per-ETF regimes with minimal turnover |
| 5 | **SPO+ Decision-Focused Training** | Medium | Moderate | Better portfolios from same predictions |
| 6 | **Score-Driven BOCPD** | Medium | High | Online regime detection without retraining |
| 7 | **Skewed Student-t Output** | Low | Low-Med | Better calibrated uncertainty for free |
| 8 | **MPC Multi-Period Optimization** | Medium | Moderate | 30-50% turnover reduction |
| 9 | **X-Trend Cross-Attention** | High | Med-High | Transfer learning across regimes |
| 10 | **TDA Persistence Landscapes** | Med-High | Moderate | Novel crash early warning |
