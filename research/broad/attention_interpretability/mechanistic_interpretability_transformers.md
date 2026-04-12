# Mechanistic Interpretability for Time Series Transformers

**Citation:** (2025). "Mechanistic Interpretability for Transformer-based Time Series Classification." arXiv:2511.21514.

**Core mechanism:** Adapts mechanistic interpretability tools from NLP (activation patching, attention saliency, sparse autoencoders) to time series transformers. Constructs causal graphs showing which attention heads matter, which timesteps drive decisions, and whether the model has learned real temporal structure or noise.

**Signal:** After training a transformer: (1) activation patching -- replace activations at specific heads and measure impact (identifies causally important components); (2) attention saliency -- maps which timesteps receive most attention from classification-critical heads; (3) sparse autoencoders -- decompose representations into interpretable features. A single early-layer patch can recover up to 0.89 true-class probability.

**Data needed:** A trained transformer model + training data. Post-hoc diagnostic.

**Performance:** Not a trading strategy. Value is diagnostic: tells you whether your transformer learned real patterns or noise.

**Weaknesses:** Demonstrated on time series classification, not financial forecasting specifically. Computationally expensive. Insights may not always be actionable.

**Assessment:** Important methodological paper for anyone using transformers on financial data. Provides tools to answer "is my attention model learning real patterns?" **Rigorous diagnostic that could save you from deploying overfit models.**

**Application to 8-ETF rotation:** Apply activation patching to your TFT. Patch each attention head with random activations, measure output change. Heads causing large changes are causally important. If they attend to recent macro events and regime transitions, model is learning real structure. If attending to arbitrary timesteps, model may be fitting noise.
