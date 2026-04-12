# A New Approach to the Economic Analysis of Nonstationary Time Series and the Business Cycle

**HIGH PRIORITY — Foundational**

- **Authors:** James D. Hamilton
- **Year:** 1989
- **Source:** Econometrica, 57(2), 357-384

## Core Method

The foundational regime-switching model. An autoregressive model where parameters (mean, variance) depend on an unobserved state variable S_t that follows a first-order Markov chain:

```
y_t = mu_{S_t} + phi_1(y_{t-1} - mu_{S_{t-1}}) + ... + epsilon_t
epsilon_t ~ N(0, sigma^2_{S_t})
```

Transition probability matrix P = [[p11, 1-p11], [1-p22, p22]]. Estimation via Maximum Likelihood with EM algorithm (Baum-Welch).

## Regimes

2 states (expansion/recession for GDP; bull/bear for financial). Typical findings: p(stay in expansion) ~ 0.90-0.97, p(stay in recession) ~ 0.75-0.90.

## Data Used

Quarterly U.S. GNP, 1951-1984.

## Application to 8-ETF Rotation System

Foundational framework — estimate a Markov switching model on equity returns or macro indicators to infer regime probabilities. Use filtered probabilities P(S_t = bear | data up to t) to scale equity exposure in real-time.

## Known Failure Modes

- Assumes fixed number of regimes
- Transition probabilities are time-invariant (unrealistic)
- Estimation sensitive to initial conditions
- Posterior regime probabilities slow to update during sudden transitions
