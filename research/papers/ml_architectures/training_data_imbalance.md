# Training Data Imbalance Solutions for Financial ML

**HIGH PRIORITY**

- **Sources:** Multiple papers and surveys

## Techniques Comparison

| Technique | When to Use | Implementation |
|-----------|-------------|----------------|
| **Focal Loss** | Severe imbalance, minority class critical | `FL(p) = -alpha*(1-p)^gamma * log(p)`, gamma=2 typical |
| **Class Weights** | Mild imbalance | `Weight = N_total / (N_classes * N_class_i)` |
| **SMOTE** | Small minority class samples | Synthetic interpolation in feature space |
| **Combined FL + Weights** | Best practice | Focal loss with alpha proportional to inverse class frequency |
| **Regime-stratified sampling** | Walk-forward splits | Ensure each training fold contains examples of all regimes |

## Application to 8-ETF Rotation System

Regime classification inherently has class imbalance — crisis periods are rare but critical to detect. Use focal loss (gamma=2) with class weights for regime classifiers. Ensure walk-forward folds are regime-stratified so the model sees crisis examples in every training window.

## Key Findings

- Standard cross-entropy loss causes models to ignore rare crisis regimes
- SMOTE should be applied only to training folds, never test folds
- Focal loss automatically down-weights easy examples and focuses on hard ones
- Combining focal loss with class weights provides best results for financial regime detection
