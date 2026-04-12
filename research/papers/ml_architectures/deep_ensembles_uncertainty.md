# Simple and Scalable Predictive Uncertainty Estimation using Deep Ensembles

**HIGH PRIORITY**

- **Authors:** Lakshminarayanan, Pritzel, Blundell
- **Year:** 2017
- **Source:** NeurIPS; arXiv:1612.01474

## Methodology

- Train M independent neural networks (typically M=5) with random initialization on same data
- Ensemble prediction = uniformly-weighted Gaussian mixture
- Mean of ensemble = point prediction
- Variance of ensemble = epistemic uncertainty estimate
- Optional adversarial training for robustness

## Application to 8-ETF Rotation System

Train 5+ independent regime classifiers. When ensemble disagreement (variance) is high, reduce position sizes or default to diversified allocation. **Uncertainty gating** prevents overconfident regime calls during transition periods.

## Key Advantage

Simple, parallelizable, no hyperparameter tuning beyond standard NN training. Produces calibrated uncertainty that degrades gracefully on out-of-distribution inputs.

## Known Failure Modes

- Computational cost scales linearly with ensemble size
- Requires diverse initialization for meaningful disagreement
- May underestimate uncertainty for truly novel market conditions
