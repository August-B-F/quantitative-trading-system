# Bandit Networks with CADTS

**Citation:** (2024). "Improving Portfolio Optimization Results with Bandit Networks." arXiv:2410.04217.

**Core mechanism:** Frames asset selection as non-stationary combinatorial multi-armed bandit. Combinatorial Adaptive Discounted Thompson Sampling (CADTS) uses discounted posteriors to adapt to regime changes. Bandit network combines multiple bandit algorithm outputs.

**Signal:** Each ETF is an arm. CADTS maintains discounted posterior for each arm's reward distribution. Thompson sampling draws from posteriors to select top-k ETFs. Discount factor controls how quickly old regime data is forgotten. Multiple bandit instances ensembled.

**Data needed:** Monthly returns per ETF. No features needed -- purely reward-driven.

**Performance:** Out-of-sample Sharpe 20% higher than best classical model on S&P 500 stocks.

**Weaknesses:** Tested on stocks, not ETFs. With 8 arms, exploration/exploitation is trivial. Performance gains may partly come from momentum bias in Thompson Sampling.

**Assessment:** Intellectually clean framework. Non-stationarity handling is real contribution. **With 8 ETFs, may not add much over simpler ranking, but adaptive discounting for regime handling is useful.**

**Application to 8-ETF rotation:** Run CADTS as parallel "consensus signal." When bandit and main model agree, increase conviction. The adaptive discounting automatically downweights old regime data. Simple to implement; principled alternative to fixed lookback windows.
