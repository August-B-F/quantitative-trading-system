# AI Improvement Plan

**Date:** 2026-04-11
**Prerequisite:** Read [AI_DIAGNOSIS.md](AI_DIAGNOSIS.md) first.

---

## Part B: Architecture Decision

### Parameter Counts vs Sample Budget

For monthly ETF rotation with a 36-month training window (36 samples), or a 60-month window (60 samples):

| Architecture | Parameters | Ratio @36 samples | Ratio @60 samples | Verdict |
|---|---|---|---|---|
| Current Transformer (3x4L, 256d) | ~6,056,000 | 168,222:1 | 100,933:1 | **Impossible.** Cannot generalize. |
| Small Transformer (2L, 32d) | ~25,000 | 694:1 | 417:1 | **No.** Still 40-70x over budget. |
| LSTM (2 layers, 64 hidden) | ~55,000 | 1,528:1 | 917:1 | **No.** Way over budget. |
| LSTM (1 layer, 32 hidden) | ~8,000 | 222:1 | 133:1 | **No.** Still 13-22x over budget. |
| XGBoost (max_depth=4, 100 trees) | ~400-800 effective | 11-22:1 | 7-13:1 | **Marginal.** Tight at 36, viable at 60. |
| Random Forest (100 trees, max_depth=4) | ~400-800 effective | 11-22:1 | 7-13:1 | **Marginal.** Same as XGBoost. |
| Logistic Regression (top 7 features) | ~7-35 (with classes) | 1-5:1 | 1-2:1 | **Yes.** Comfortably within range. |
| Ridge Regression (top 10 features) | ~10-50 | 1-7:1 | 1-4:1 | **Yes.** Within range. |

### Recommendation

**Primary: XGBoost or Ridge Regression** with 7-12 features and 60-month training window.

Logistic/Ridge regression is the safe choice - it has enough samples to estimate parameters reliably. XGBoost adds nonlinear splits but is at the boundary; regularization (max_depth=3-4, min_child_weight, subsampling) is critical.

**Do NOT use a transformer or LSTM.** There is no sample count at which these become viable for monthly ETF rotation:
- LSTM (1L, 32h): needs >800 samples → 67+ years of monthly data. Not available.
- Transformer (2L, 32d): needs >2,500 samples → 200+ years. Absurd.

The only scenario where deep models become viable is if you switch to daily prediction with truly independent samples AND the prediction target has learnable signal at daily frequency. Even then, a small LSTM/Transformer would need careful validation.

### Viability Thresholds

| Architecture | Min Samples for 10:1 Ratio | Min Months of Data |
|---|---|---|
| Logistic Regression (7 features) | 70 | ~6 months (with 8 ETFs) |
| Ridge Regression (10 features) | 100 | ~12 months |
| XGBoost (depth=4, 100 trees) | 4,000-8,000 | 30-60 months (w/ 8 ETFs cross-sectional) |
| LSTM (1L, 32h) | 80,000 | 830+ months (**69 years**) |
| Transformer (2L, 32d) | 250,000 | 2,600+ months (**217 years**) |

Note: XGBoost's effective parameters are much lower than its raw tree node count because max_depth constraints and regularization reduce effective complexity. In practice, XGBoost with 60 monthly samples x 8 ETFs = 480 cross-sectional observations is workable if features are kept under 12.

---

## Part C: Prediction Target Evaluation

### Current Target: 5-Class Stock Direction (3-day horizon)

**Problems:**
1. Not aligned with trading strategy (monthly ETF rotation, not daily stock trading)
2. 5 classes with fuzzy boundaries (what distinguishes "sell" from "strong sell" at 2.5% threshold?)
3. The Hold class absorbs most samples, starving other classes
4. 3-day returns are dominated by noise (signal-to-noise ratio << 1)

### Alternative Targets

#### T1: 8-Class Classification (Which ETF Wins Next Month)
- **Loss:** CrossEntropy with class weights
- **Samples per month:** 1 (the winner is one of 8 ETFs)
- **Problem:** With 36-60 months, only 36-60 labels exist. No model can learn 8-class classification from 36 samples reliably. Ties and near-ties add label noise.
- **Learnability:** LOW. Too many classes for the sample size.

#### T2: Regression on 8 Forward Returns (Predict Next-Month Return for Each ETF)
- **Loss:** MSE or Huber
- **Samples:** 36-60 months x 8 ETFs = 288-480 cross-sectional observations
- **Advantage:** Continuous target captures magnitude. argmax(predicted returns) gives rotation signal. Cross-sectional structure provides 8x more samples than T1.
- **Problem:** Penalizes correct-direction-wrong-magnitude predictions. Monthly returns have high variance.
- **Learnability:** MODERATE. Rank correlation (Spearman) is the right metric, not MSE. With 12 features and 480 samples, ridge regression can estimate this.
- **Metric:** Spearman rank correlation between predicted and actual returns.

#### T3: Pairwise Ranking (Learning to Rank)
- **Loss:** Pairwise hinge or ListNet
- **Samples:** C(8,2) = 28 pairs per month x 36-60 months = 1,008-1,680 pairwise comparisons
- **Advantage:** Only needs to get ORDER right, not magnitude. More samples than T1 or T2.
- **Problem:** 28 pairs per month inflates sample count artificially (same underlying 8 returns). Pairwise samples are correlated.
- **Learnability:** MODERATE-HIGH for simple models. Pairwise logistic regression is well-suited.
- **Metric:** Kendall tau, NDCG.

#### T4: Binary Drawdown Prediction (>5% Loss Next Month: Yes/No)
- **Loss:** Binary CrossEntropy with heavy class weighting
- **Samples:** 36-60 months x 8 ETFs = 288-480 samples (binary: simpler than T1-T3)
- **Advantage:** Much simpler problem. Cleaner signal (drawdowns have different feature signatures than normal months). Directly useful as risk gate for the systematic strategy.
- **Problem:** Drawdowns are rare (~10-15% of months). Class imbalance, but manageable with 2 classes.
- **Learnability:** HIGHEST. Binary classification with few features from limited samples is the most tractable ML problem. VIX, momentum, credit spreads are known drawdown predictors.
- **Metric:** Precision at 80% recall (catch 80%+ of drawdowns while minimizing false alarms).

#### T5: Predict Systematic Strategy's Next Signal
- **Loss:** 8-class CrossEntropy
- **Samples:** Same as T1 (36-60)
- **Problem:** Circular. If you can predict which ETF will have the best 63-day momentum next month, you already have a better signal than momentum itself. And if you can't, you're just approximating the momentum calculation, which is simpler done directly.
- **Learnability:** LOW. Same sample constraint as T1, plus circularity.

### Recommendation

**Primary Target: T4 (Binary Drawdown Prediction)**

Reasons:
1. **Most learnable** with 36-60 samples. Binary classification with 7-10 features is the sweet spot for small-sample ML.
2. **Directly useful.** The systematic strategy already works (23% CAGR). The AI doesn't need to beat it - it needs to protect it. Avoiding even one major drawdown per year improves risk-adjusted returns significantly.
3. **Cleaner signal.** Drawdowns correlate with observable precursors (VIX spikes, yield curve inversions, momentum crashes, credit spread widening). These are fundamentally different from predicting which ETF will be best.
4. **Graceful degradation.** If the model is wrong and predicts a drawdown that doesn't happen, you go to cash for one month - low opportunity cost. If it's wrong and misses a drawdown, you're no worse than the base strategy.

**Backup Target: T2 (Regression on 8 Forward Returns)**

Reasons:
1. Cross-sectional structure provides 8x sample multiplier
2. Continuous output is more informative than classification
3. Ridge regression can handle this with 10-12 features
4. Even weak rank correlation (Spearman > 0.1) can improve ETF selection

---

## Part D: Training Procedure Fixes

### 1. Walk-Forward Design

**Current problem:** The training code uses a fold-based split that doesn't match the actual trading frequency (monthly rebalancing).

**Fixed design:**

```
Training Window:  Test 36m, 48m, 60m (start with 60m for more data)
Validation:       6 months held out from end of training window
Test:             3 months forward, NEVER seen during training or validation
Roll Forward:     3 months at a time
Min Windows:      12 (= 3 years of test data across all folds)
```

**Timeline example (60m training, 2018-2025 data):**

```
Fold 1:  Train 2013-01 to 2017-12 | Val 2018-01 to 2018-06 | Test 2018-07 to 2018-09
Fold 2:  Train 2013-04 to 2018-03 | Val 2018-04 to 2018-09 | Test 2018-10 to 2018-12
...rolling forward 3 months each time...
Fold 24: Train 2019-01 to 2023-12 | Val 2024-01 to 2024-06 | Test 2024-07 to 2024-09
```

**CRITICAL: Feature computation cutoff = signal date.** Every rolling statistic (SMA, RSI, volatility, momentum) must use ONLY data available on the signal date. No forward-looking information in any feature, including:
- Rolling windows that extend past the signal date
- Forward-filled values from future dates
- Macro indicators released after the signal date (GDP revisions, etc.)

### 2. Feature Selection (Without Lookahead)

**Maximum features = training_samples / 5:**
- 36 months x 8 ETFs = 288 samples → max ~57 features (generous)
- But with temporal autocorrelation → effective samples ~60-80 → max 12-16 features
- **Conservative budget: 7-12 features**

**Method 1: Domain Knowledge (preferred for small samples)**

Top 10 features with strongest theoretical justification for ETF rotation:

| # | Feature | Justification |
|---|---|---|
| 1 | 63-day momentum (relative to SHY) | Antonacci dual momentum; the basis of the winning strategy |
| 2 | 21-day momentum | Shorter-term trend confirmation |
| 3 | VIX level | Regime indicator; high VIX predicts drawdowns |
| 4 | VIX change (21-day) | Rising VIX = deteriorating conditions |
| 5 | 20-day realized volatility | Risk scaling; vol clusters |
| 6 | Yield curve slope (TLT proxy) | Recession indicator; flight to quality |
| 7 | Cross-sectional momentum dispersion | High dispersion = strong trends, rotation works |
| 8 | 12-month momentum | Long-term trend; Jegadeesh-Titman |
| 9 | Sector relative strength (vs SPY) | Captures rotation within sectors |
| 10 | Gold momentum (GLD) | Risk-off indicator; safe haven demand |

**Method 2: Data-Driven Selection (on training fold ONLY)**

```python
# Per fold:
from sklearn.feature_selection import mutual_info_regression
mi_scores = mutual_info_regression(X_train, y_train)
top_k = np.argsort(mi_scores)[-12:]  # top 12 features

# Stability check: save selected features per fold
# If top-12 changes by >50% between folds → selection is unstable → use fixed domain set
```

**Rule: If feature selection is unstable across folds (>50% turnover), default to the fixed domain knowledge set above.**

### 3. Calibration

**After training each fold:**
1. Apply temperature scaling on the validation fold (L-BFGS optimization of T)
2. Evaluate Expected Calibration Error (ECE) on the test fold
3. Compute reliability diagram (predicted confidence vs actual accuracy in 10 bins)

**Decision threshold:**
- If ECE > 0.15: confidence scores are unreliable. Use binary signal (trade / don't trade) instead of continuous position sizing.
- If ECE < 0.10: confidence can be used for position sizing (Kelly fraction * confidence)

**For T4 (drawdown prediction):**
- Platt scaling (logistic calibration) after the main model
- Report precision-recall curve, not just accuracy
- Set decision threshold to achieve 80% recall (catch most drawdowns, accept some false alarms)

### 4. Ground Truth Logging

**Every prediction must save:**

```json
{
  "date": "2024-07-01",
  "fold": 15,
  "predicted_class": 0,
  "predicted_probabilities": {"drawdown": 0.72, "no_drawdown": 0.28},
  "confidence": 0.72,
  "actual_outcome": "drawdown",
  "actual_returns": {
    "SOXX": -0.08, "QQQ": -0.05, "XLK": -0.04,
    "VGT": -0.06, "IGV": -0.03, "XLE": 0.02,
    "GLD": 0.01, "SHY": 0.003
  },
  "regime_label": "bear",
  "features_used": ["momentum_63d", "vix_level", "vol_20d", ...],
  "feature_values": [0.12, 22.5, 0.015, ...],
  "model_type": "xgboost",
  "training_window": "2019-01 to 2023-12"
}
```

**Saved to:** `/results/experiments/<experiment_id>/predictions.jsonl` (one JSON per line)

**No exceptions.** Every prediction, every fold. This is the only way to diagnose whether the model adds value after the fact.

---

## Part E: Experiment Design

### CRITICAL RULE
**Do NOT run Tier 2 unless at least one Tier 1 model beats random baseline + 5% on the primary metric out-of-sample. If no model beats random with 7-12 features and 36-60 samples, the signal doesn't exist at this frequency/granularity. Accept it and use AI only for drawdown protection (T4) or not at all.**

### Tier 1: Fundamental Questions (Run All)

| ID | Architecture | Features | Target | Training Window | Purpose |
|---|---|---|---|---|---|
| E00 | Current Transformer | All 68 | 5-class | Current | **Baseline: label shuffle test.** Confirm model doesn't learn signal. |
| E01 | Ridge Regression | Top 7 (domain) | T2 (regression) | 60 months | Simplest model, strongest prior. Can linear predict returns? |
| E02 | XGBoost (depth=3, 100 trees) | Top 12 (domain) | T2 (regression) | 60 months | Nonlinear, but regularized. |
| E03 | Random Forest (depth=4, 100 trees) | Top 12 (domain) | T1 (8-class) | 60 months | Classification alternative to E02. |
| E04 | XGBoost (depth=3, 100 trees) | Top 12 (domain) | T4 (drawdown) | 60 months | Drawdown detection - most tractable problem. |
| E05 | Logistic Regression | Top 7 (domain) | T4 (drawdown) | 60 months | Simplest drawdown detector. |

**Metrics for each experiment:**
- E01-E02: Spearman rank correlation (pred vs actual returns), OOS
- E03: Top-1 and Top-2 accuracy, OOS
- E04-E05: Precision at 80% recall, AUROC, OOS
- All: Walk-forward backtest return when integrated with systematic strategy vs pure systematic baseline

**Baselines for each experiment:**
1. Random baseline (shuffled predictions)
2. Always-hold-SPY (passive benchmark)
3. Pure systematic strategy (no AI, momentum-only rotation)

### Tier 2: Only If Tier 1 Shows Signal (Any Model Beats Random + 5%)

| ID | Architecture | Features | Target | Notes |
|---|---|---|---|---|
| E06 | LSTM (1L, 32 hidden) | Top 12 | Best from Tier 1 | Sequence model - only if samples > 200 effective |
| E07 | Best Tier 1 model | Top 12 | Best target | Regime-conditional (separate models per HMM regime) |
| E08 | Ensemble (E01 + E02 + E03) | Mixed | T2 | Average predicted returns across models |
| E09 | Best Tier 1 model | Top 20 | Best target | Expanded features (only with 60m window) |
| E10 | Pairwise Logistic Regression | Top 10 | T3 (ranking) | Learning-to-rank alternative |

### Tier 3: Only If Tier 2 Shows Genuine OOS Edge > Random + 5%

| ID | Architecture | Notes |
|---|---|---|
| E11 | Deep ensemble (5x best Tier 1/2 model, different seeds) | Calibration improvement |
| E12 | Small Transformer (2L, 32d) | ONLY if training samples > 80 effective |
| E13 | Heterogeneous ensemble (best tree + best linear + best sequence) | Diversity-based ensemble |
| E14 | Conformal prediction wrapper on best model | Uncertainty quantification |

### Experiment Output Format

Every experiment saves to `/results/experiments/<experiment_id>.json`:

```json
{
  "experiment_id": "E01",
  "architecture": "ridge_regression",
  "target": "T2_regression",
  "feature_set": ["momentum_63d", "momentum_21d", "vix_level", ...],
  "feature_count": 7,
  "training_window_months": 60,
  "hyperparameters": {"alpha": 1.0},
  "n_folds": 24,
  "n_train_samples_per_fold": 480,
  "n_test_samples_per_fold": 24,
  "results": {
    "oos_spearman_rank_corr": 0.08,
    "oos_spearman_pvalue": 0.12,
    "per_class_accuracy": null,
    "ece": 0.09,
    "walk_forward_cagr": 0.19,
    "walk_forward_sharpe": 0.85,
    "walk_forward_max_drawdown": -0.22
  },
  "baselines": {
    "random_spearman": 0.00,
    "spy_hold_cagr": 0.14,
    "systematic_only_cagr": 0.23,
    "systematic_only_sharpe": 0.96
  },
  "verdict": "Does not beat systematic baseline. AI adds no value for return prediction."
}
```

### Post-Experiment Analysis

After all tiers complete, write `/results/EXPERIMENT_RANKING.md`:

1. Rank all experiments by primary metric
2. Compare every experiment to the three baselines
3. Statistical significance: bootstrap confidence intervals on OOS metrics
4. **Honest verdict:** Does the AI add value? If the answer is no, say so plainly.

**Expected outcome (honest prediction):**

Based on the diagnosis, the most likely results are:
- E01-E03 (return prediction): Spearman correlation near zero OOS. The systematic momentum strategy already captures the predictable component of returns.
- E04-E05 (drawdown prediction): **Best chance of success.** Drawdowns have observable precursors. Even weak signal (AUROC > 0.6) is useful as a risk gate.
- E06-E14: Unlikely to be reached. If Tier 1 shows no signal for return prediction, the honest answer is: **use AI only for drawdown protection, or not at all.**

The winning systematic strategy (23% CAGR, 0.96 Sharpe) is already very strong. The AI's most realistic role is not to beat it, but to reduce its worst drawdowns (-28.4% max drawdown → target -15-20%) by predicting when to go to cash.

---

## Implementation Priority

1. **Immediately:** Run E00 (label shuffle test) to confirm diagnosis
2. **Week 1:** Implement E04 + E05 (drawdown prediction with simple models)
3. **Week 2:** Implement E01 + E02 + E03 (return prediction with simple models)
4. **Week 3:** Evaluate Tier 1 results. Write EXPERIMENT_RANKING.md.
5. **Week 4+:** If any Tier 1 model shows signal, proceed to Tier 2. Otherwise, stop and accept the systematic strategy is sufficient, optionally enhanced with T4 drawdown gating.

### What NOT to Do

1. Do NOT try to fix the transformer architecture. The problem is not the architecture - it's the data size.
2. Do NOT add more features. More features with the same samples = more overfitting.
3. Do NOT use daily samples to inflate sample counts. Daily samples with 40-day overlapping windows are not independent.
4. Do NOT run hundreds of experiments. With 60 samples, every experiment increases the risk of finding spurious signal.
5. Do NOT claim the AI "adds value" unless it beats the systematic baseline on truly OOS data with statistical significance (p < 0.05).
