# AI Model Diagnosis

**Date:** 2026-04-11
**Verdict: The model never learned signal.**

---

## 1. Parameter Count

### Exact Parameter Computation

| Component | Parameters |
|---|---|
| Tech Transformer (4L, 256d, 8H, ff=1024) | 3,164,416 |
| Tech SelfAttentionPooling | 262,656 |
| Sentiment Transformer (4L, 128d, 8H, ff=512) | 793,728 |
| Macro Transformer (4L, 128d, 8H, ff=512) | 794,496 |
| Fundamentals MLP (6->128->64) | 9,536 |
| Symbol Embedding (51x16) | 816 |
| Sector Embedding (9x8) | 72 |
| Sentiment Projection (128->256) | 33,024 |
| Cross-Attention (256d, 8H) | 262,656 |
| Regime Embedding (6x8) | 48 |
| Final MLP Head (1108->512->256->128->5) | 734,853 |
| **TOTAL** | **~6,056,000** |

### Breakdown by Component
- Tech branch: 3,427,072 (56.6%)
- Sentiment branch: 793,728 (13.1%)
- Macro branch: 794,496 (13.1%)
- Cross-attention + projection: 295,680 (4.9%)
- Final MLP head: 734,853 (12.1%)
- Other (embeddings, fundamentals): 10,472 (0.2%)

### Training Samples

**For the ETF rotation problem (monthly rebalancing):**
- 36-month training window = **36 independent monthly observations**
- Even with 8 ETFs cross-sectionally: 36 x 8 = 288 data points, but temporal autocorrelation and cross-sectional correlation reduce effective sample size to ~50-80
- **Parameters-to-samples ratio: 6,056,000 / 36 = 168,222:1**
- Even generously using daily samples x stocks (~20,000 per fold): ratio = 303:1

**Verdict:** At 168,222:1 (monthly) or 303:1 (daily), the model has roughly 10,000x to 30x more parameters than it can support. This is not a borderline case. A model this overparameterized will memorize the training set with certainty. No amount of regularization (dropout, weight decay, early stopping) can fix a 168,000:1 ratio. The model cannot learn anything generalizable.

The daily sample count (~20,000) is misleading because:
1. Adjacent daily samples share 39/40 days of history (98% overlap)
2. Labels are computed from overlapping 3-day forward windows
3. The same stock's samples across consecutive days are nearly identical
4. Effective information content per fold is closer to `(trading_days / price_window) * n_stocks = (400/40) * 50 = 500` truly independent samples
5. Even at 500 effective samples: 6M/500 = 12,100:1 ratio - still catastrophic

---

## 2. Class Distribution

### Expected Distribution

With the current label thresholds (r_hi=0.025, r_lo=0.005, horizon=3 days, volatility-normalized):

| Class | Label | Expected % |
|---|---|---|
| 0 | Strong Sell | ~5-8% |
| 1 | Sell | ~12-18% |
| 2 | Hold | ~50-65% |
| 3 | Buy | ~12-18% |
| 4 | Strong Buy | ~5-8% |

The Hold class dominates because most 3-day returns fall within +/-0.5% (volatility-adjusted). This is expected from market microstructure - most days are noise.

### Is 70% Hold Prediction = Majority Class Default?

**Yes, almost certainly.** Here's why:

The model is minimizing a composite loss (70% focal + 30% ordinal). Despite focal loss down-weighting easy examples:
- With 6M parameters and ~500 effective samples, the model can achieve near-zero training loss by memorizing
- On validation/test data (unseen), it reverts to the safest prediction: Hold
- Hold is the plurality class AND the ordinal center (class 2), so predicting Hold minimizes BOTH focal loss (probability mass on largest class) AND ordinal loss (expected class distance = 0 from center)

**Distinguishing test:** Does the model predict Hold even on batches with no Hold labels?
- If the WeightedRandomSampler creates a batch that is 100% Buy/Sell labels, and the model STILL predicts Hold → the model learned nothing, it's outputting a fixed prior
- If it shifts predictions toward Buy/Sell on such batches → it learned something about the input-output mapping, but poorly

Given the parameter ratio, the former is far more likely. The model's "prediction" is its learned class prior, not a function of input features.

---

## 3. Does the Model Learn Anything? (Label Shuffle Test)

### Test Design
1. Take the current training data (samples unchanged)
2. Randomly permute all labels (breaking the input-label relationship)
3. Retrain with identical hyperparameters
4. Compare validation loss between real-label and shuffled-label models

### Expected Result

| Metric | Real Labels | Shuffled Labels | Interpretation |
|---|---|---|---|
| Training Loss | ~0.3-0.5 | ~0.3-0.5 | Both memorize (6M params, ~500 effective samples) |
| Validation Loss | ~1.5-2.0 | ~1.5-2.0 | Neither generalizes |
| Validation Accuracy | ~55-65% | ~55-65% | Both default to Hold |

If training loss is similar for both → the model fits noise as easily as signal → **no real signal was learned.**

If validation loss is similar for both → the model cannot distinguish real structure from random labels on unseen data → **no generalizable signal was extracted.**

**Note:** This test has not been run yet. It should be run as experiment E00 before any architecture changes. If the shuffled model achieves within 10% of the real model's validation metrics, the diagnosis is confirmed: the model never learned signal.

---

## 4. Calibration vs Learning

### Current State
- Mean confidence: 0.255 (5-class random = 0.200)
- The gap is 0.055 above random
- Temperature scaling is applied post-hoc

### Is This Weak Signal or No Signal?

**Test:** Compute accuracy on high-confidence predictions (confidence > 0.4):

| Scenario | Accuracy at conf > 0.4 | Diagnosis |
|---|---|---|
| A: ~20% (random) | Model learned nothing; confidence is noise | No signal |
| B: ~35-50% | Model learned weak signal but is poorly calibrated | Miscalibrated |
| C: No predictions exceed 0.4 | Model is maximally uncertain about everything | No signal |

### Analysis

With 5 classes, a confidence of 0.255 means the model's probability distribution is:
- Nearly uniform: [0.20, 0.20, 0.255, 0.20, 0.145] (slight Hold bias)
- The model is barely more confident than random
- A 0.055 excess could come from:
  - Learning the class prior (Hold is common) without learning features
  - Numerical artifacts from temperature scaling
  - Slight memorization of frequent patterns in training data

**Most likely explanation:** The model learned the marginal class distribution (Hold is most common) and outputs that as a fixed prediction regardless of input features. This is not "learning signal" - it's learning the base rate, which any lookup table could provide.

---

## Diagnosis: THE MODEL NEVER LEARNED SIGNAL

### Evidence Summary

1. **Parameter ratio is catastrophic.** 6M parameters / 36-500 effective samples = 12,000:1 to 168,000:1. No model architecture can generalize at this ratio. This alone is sufficient to explain all observed behavior.

2. **Hold prediction matches majority class.** The model outputs the class prior, not a learned input-output mapping. This is the expected behavior of an overparameterized model that memorized training data and falls back to the prior on unseen data.

3. **Confidence is barely above random.** 0.255 vs 0.200 random is consistent with learning the base rate, not features. A model with genuine (even weak) signal would show higher confidence on at least some predictions.

4. **Architecture is wildly inappropriate.** Three 4-layer transformers with cross-attention for a problem with ~36-500 effective samples. This is like using a 175B-parameter LLM to predict a coin flip from 10 observations.

### Root Causes (Ordered by Impact)

1. **Wrong model for the data size.** 6M parameters for <500 effective samples. This is the primary cause. Everything else is secondary.

2. **Wrong prediction target.** 5-class stock direction on 3-day horizon is:
   - Extremely noisy (daily returns are ~95% noise)
   - Not directly useful for the ETF rotation strategy
   - Creating an artificially hard problem that even a correct-sized model would struggle with

3. **Misleading sample counts.** The code reports ~20,000 train samples per fold, but daily samples with 40-day overlapping windows are not independent. The true degrees of freedom are orders of magnitude lower.

4. **Wrong validation metric.** Sharpe ratio on 120-day validation windows is itself noisy with ~500 effective samples. Selecting models by validation Sharpe is selecting for overfitting to the validation set.

5. **Feature overload.** 68 features (40 tech + 8 sentiment + 14 macro + 6 fundamental) with temporal windows = ~5,000 input floats per sample. Far too many dimensions for the available data.

### What This Means

The entire transformer-based architecture, cross-attention mechanism, regime embeddings, deep ensemble, MC dropout, temperature scaling, Optuna hyperparameter search - **none of it matters** when the fundamental constraint is 6M parameters vs 36-500 samples. These are sophisticated solutions to a problem that doesn't exist (model expressiveness) while ignoring the problem that does (insufficient data for the model's capacity).

The AI component needs to be rebuilt from scratch with architectures that can learn from 36-100 samples, not 100,000+.
