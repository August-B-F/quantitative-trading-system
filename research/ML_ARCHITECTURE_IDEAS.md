# ML Architecture Ideas

Every neural network / ML approach found for time-series classification or rotation prediction.

---

## 1. TRANSFORMER ARCHITECTURES

### 1.1 Temporal Fusion Transformer (TFT) **[HP — RECOMMENDED]**
- **Paper:** Lim et al. (2021), Google Cloud AI
- **Architecture:** LSTM + multi-head self-attention + Variable Selection Networks + Gated Residual Networks
- **Key innovation:** Three input types (static covariates, known future, historical observed)
- **Why it fits 8-ETF rotation:**
  - Static: ETF asset class encoding
  - Known future: calendar features, scheduled macro releases
  - Historical: returns, vol, macro indicators, regime probabilities
  - Multi-horizon output enables multi-step allocation
  - Variable importance scores per regime
- **Hyperparameters:** 8 heads, d_model=512-1024, lr=1e-4
- **Performance:** 7-36% improvement over baselines on vol forecasting

### 1.2 Modality-Aware Transformer (MAT)
- **Paper:** Emami et al. (2023), arXiv:2310.01232
- **Architecture:** 2 encoder + 1 decoder layers, 8 heads, 512-dim. Three specialized MHA: Intra-modal, Inter-modal, Target-modal
- **Key innovation:** Fuses numerical time series + text (FOMC minutes) + economic indicators
- **Application:** Combine ETF prices with macro text for allocation decisions
- **Hyperparameters:** lr=1e-4, batch=16, early stopping 10 epochs

### 1.3 Cross-Modal Temporal Fusion (CMTF)
- **Paper:** arXiv:2504.13522 (2025)
- **Architecture:** Tensor representation with WMA event decay + transformer classifier + multi-task group LASSO
- **Key innovation:** Stability selection (features retained if selected >=80% of folds). Temporal decay weighting for macro events.
- **Application:** Robust feature selection for regime-relevant signals

### 1.4 Stockformer
- **Paper:** arXiv:2502.09625 (2025)
- **Architecture:** 1D-CNN embedding (kernel=3) + ProbSparse Attention (O(L*logL))
- **Key innovation:** Granger causality for input stock selection; Stock Direction loss function
- **Warning:** "Transformers are harder to train than originally expected" — lr sensitivity, gradient collapse

### 1.5 LENS/PLUTUS Foundation Model
- **Paper:** arXiv:2408.10111 (2024)
- **Architecture:** 0.2B-5B params. TimeFormer with dual attention (Time-aware + Channel-aware)
- **Key innovation:** Pre-trained on 100B+ financial observations. Contrastive learning for noise robustness.
- **Caveat:** Struggles with "sudden market events". Requires 8x H100 GPUs for pre-training.

---

## 2. HYBRID ARCHITECTURES

### 2.1 HMM-LSTM Hybrid **[HP]**
- **Paper:** (2024), semiconductor equity markets
- **Architecture:** HMM (regime labels) → LSTM (prediction with regime features)
- **Performance:** 94.45% accuracy, bear recall 88.89%
- **Key advantage:** Two-stage reduces overfitting vs end-to-end
- **Application:** HMM generates regime probabilities as LSTM input features

### 2.2 HAELT (Hybrid Attentive Ensemble Learning Transformer)
- **Paper:** arXiv:2506.13981 (2025)
- **Architecture:** ResNet 1D-CNN → temporal attention → parallel LSTM+Transformer branches → dynamic ensemble
- **Key finding:** Transformer-only matched full model (F1=0.6397 vs 0.6421), marginal gains from complexity
- **Lesson:** Simpler architectures may suffice; added complexity has diminishing returns

### 2.3 RegimeFolio — Ensemble per Regime **[HP — RECOMMENDED]**
- **Paper:** arXiv:2510.14986 (2025)
- **Architecture:** VIX-tercile regime classifier → per-regime Random Forest + Gradient Boosting → Ledoit-Wolf MVO
- **Key innovation:** Separate models per regime. Features standardized per-regime. SHAP analysis reveals feature importance shifts.
- **Performance:** 137% total return vs 73.8% S&P (2020-2024), Sharpe 1.17 vs 0.66
- **Feature importance shifts:**
  - Low Vol: Momentum dominates (0.342)
  - Medium Vol: Mean-reversion dominates (0.267)
  - High Vol: Volatility dominates (0.456)

---

## 3. REINFORCEMENT LEARNING APPROACHES

### 3.1 DRL with Macro Regime Encoder **[HP]**
- **Paper:** Kazi et al. (2025), SSRN:5579472
- **Architecture:** LSTM macro regime encoder → macro/temporal/spatial-aware transformer → DRL agent
- **Assets:** 36 ETFs (scalable to 8)
- **Key innovation:** Regime encoder conditions RL policy on latent macro state
- **Application:** End-to-end learning of optimal allocation conditioned on regime

### 3.2 RL with Walk-Forward Validation
- **Paper:** arXiv:2512.12924 (2024)
- **Architecture:** RL agent with epsilon-greedy (0.7 train, 0.1 test)
- **Key finding:** Only 12% statistical power with 34 quarterly folds. "+0.60% quarterly in high-vol, -0.16% in stable markets"
- **Lesson:** Honest assessment — most academic strategies fail in live trading

---

## 4. REGIME DETECTION ML

### 4.1 Statistical Jump Model **[HP — RECOMMENDED]**
- **Paper:** Shu, Yu & Mulvey (2024), arXiv:2402.05272
- **Architecture:** Coordinate descent with jump penalty lambda
- **Why superior to HMM:** 14 regime switches vs 115 (33 years). 8x lower turnover.
- **Features:** 3 EWM downside deviations + 1 EWM return
- **Performance:** Sharpe 0.78 vs HMM 0.51

### 4.2 Jump Model + XGBoost Forecaster **[HP]**
- **Paper:** Shu et al. (2024), arXiv:2406.09578
- **Architecture:** JM (historical labels) → XGBoost (future prediction)
- **Features:** Return features (8) + macro features (VIX, yield curve, stock-bond corr)
- **Assets tested:** 12 — matches 8-ETF universe closely

### 4.3 GMM Regime Clustering **[HP]**
- **Paper:** Two Sigma (2020)
- **Architecture:** Gaussian Mixture Model on 17 factor returns
- **Regimes:** Crisis, Steady State, Inflation, Walking on Ice
- **Application:** Map current factor environment to 4 regimes

### 4.4 FRED-MD PCA + K-Means
- **Paper:** Oliveira et al. (2025), arXiv:2503.11499
- **Architecture:** 127 FRED-MD vars → PCA (61 components) → modified k-means
- **Regimes:** 6 macro regimes tested on 10 sector ETFs

---

## 5. UNCERTAINTY ESTIMATION

### 5.1 Deep Ensembles **[HP — RECOMMENDED]**
- **Paper:** Lakshminarayanan et al. (2017), NeurIPS
- **Method:** Train M=5 independent networks with random initialization
- **Output:** Mean = prediction, Variance = epistemic uncertainty
- **Application:** When ensemble disagreement is high, reduce position sizes or default to diversified allocation
- **Key advantage:** Simple, parallelizable, calibrated uncertainty on OOD inputs

---

## 6. DATA IMBALANCE SOLUTIONS

| Technique | When to Use | Implementation |
|-----------|-------------|----------------|
| **Focal Loss** | Severe imbalance, rare regimes critical | `FL(p) = -alpha*(1-p)^gamma * log(p)`, gamma=2 |
| **Class Weights** | Mild imbalance | `Weight = N_total / (N_classes * N_class_i)` |
| **SMOTE** | Small minority class | Synthetic interpolation in feature space |
| **Combined FL + Weights** | Best practice | Focal loss + inverse class frequency alpha |
| **Regime-Stratified Splits** | Walk-forward validation | Ensure all regimes in each training fold |

---

## 7. TRAINING BEST PRACTICES

### Walk-Forward Validation Protocol
- Training window: 252 days (1 year)
- Testing window: 63 days (1 quarter)
- Step size: 63 days (non-overlapping)
- Refit: Quarterly minimum
- **Never use K-fold or random splits for time series**
- Include realistic transaction costs ($1 fixed + 5bps slippage)
- Regime-stratified training folds

### Key Hyperparameters (Literature Consensus)
| Parameter | Value | Source |
|-----------|-------|--------|
| Attention heads | 8 | MAT, LENS |
| d_model | 512-1024 | MAT, LENS-S |
| Encoder layers | 2-4 | MAT, LENS |
| Learning rate | 1e-4 | Multiple |
| Batch size | 16-64 | MAT, HAELT |
| Lookback window | 60-252 days | JM, Walk-forward |
| Jump penalty (lambda) | 100 | JM |
| VIX regime thresholds | 33rd/67th rolling pctile | RegimeFolio |
| Ensemble members | 5 | Deep Ensembles |
| Dropout | 0.2-0.3 | HAELT |
| Early stopping | 10-30 epochs | MAT, HAELT |

---

## RECOMMENDED ARCHITECTURE STACK

### Tier 1 — Start Here (Low Complexity, Proven)
```
VIX Tercile Regime → Per-Regime Gradient Boosting → Inverse-Vol Weighting
```
- Inputs: momentum, RSI, MACD, rolling vol, macro (VIX, HY spread)
- Per-regime feature standardization
- SHAP for interpretability
- Walk-forward quarterly refit

### Tier 2 — Enhancement (Medium Complexity)
```
Statistical Jump Model → XGBoost Forecaster → Deep Ensemble (5 models) → Uncertainty-Gated Allocation
```
- Asset-specific regime detection
- Macro features: yield curve, VIX, stock-bond corr
- Uncertainty gating reduces allocation when models disagree

### Tier 3 — Advanced (High Complexity)
```
Temporal Fusion Transformer → Multi-Horizon Regime Prediction → RL-Based Allocation
```
- Full multimodal inputs (price + macro + text)
- Variable Selection Networks for automatic feature filtering
- End-to-end optimization of portfolio metrics
- Requires significant compute and careful overfitting prevention

### Critical Warnings
1. **Transformer-only ≈ full hybrid** (HAELT finding) — added complexity may not help
2. **>90% of academic strategies fail live** — honest walk-forward validation essential
3. **Momentum importance collapses in high-vol** — separate models per regime
4. **Statistical Jump Model beats HMM** on all practical metrics — prefer JM
5. **Foundation models struggle with sudden events** — pair with rule-based limits
6. **12% statistical power with 34 folds** — don't overfit to backtests
