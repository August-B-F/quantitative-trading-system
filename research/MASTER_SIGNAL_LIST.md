# Master Signal List

Every unique signal extracted from academic literature, grouped by type.
Signals marked **[HP]** are HIGH PRIORITY for an 8-ETF rotation system.

---

## 1. MOMENTUM SIGNALS

### 1.1 Time-Series Momentum (Absolute)
| Signal | Formula | Source | Priority |
|--------|---------|--------|----------|
| **12-Month TSMOM** | `sign(r_{t-12,t}) × (1/sigma_t)` | Moskowitz, Ooi, Pedersen (2012) | **[HP]** |
| **Absolute Momentum Filter** | Hold if 12M return > T-bill rate; else cash | Antonacci (2013) | **[HP]** |
| **10-Month SMA Rule** | Buy when price > 10M SMA; sell when below | Faber (2006) | **[HP]** |
| **Dual Momentum** | Relative ranking + absolute filter combined | Antonacci (2014) | **[HP]** |

### 1.2 Cross-Sectional Momentum (Relative)
| Signal | Formula | Source | Priority |
|--------|---------|--------|----------|
| **12-Month Relative Return** | Rank assets by trailing 12M return, hold top N | Multiple | **[HP]** |
| **Volatility-Adjusted Momentum** | `r_{t-12,t} / sigma_i` (Sharpe ranking) | van Zundert (2018) | **[HP]** |
| **VAA Weighted Momentum** | `12×1M + 4×3M + 2×6M + 1×12M return` | Keller & Keuning (2017) | **[HP]** |
| **Multi-Lookback Blend** | Average of 3M, 6M, 12M signals | ReSolve / Multiple | Medium |
| **Skip-Month Momentum** | 12M return excluding most recent month | Jegadeesh & Titman | Medium |

### 1.3 Momentum Enhancement Signals
| Signal | Formula | Source | Priority |
|--------|---------|--------|----------|
| **Continuous TREND Signal** | Continuous score vs binary +1/-1 | Baltas & Kosowski (2013) | **[HP]** |
| **Drawdown-Based Momentum** | Rank by max drawdown measures | MDPI JRFM (2021) | Medium |
| **Risk-Adjusted TSMOM (RAMOM)** | Multi-lookback vol-normalized returns | Dudler, Gmuer, Malamud (2014) | Medium |

---

## 2. REGIME DETECTION SIGNALS

### 2.1 Price-Based Regime Signals
| Signal | Formula | Source | Priority |
|--------|---------|--------|----------|
| **VIX Tercile Regime** | Rolling 252-day VIX percentile (33rd/67th) | RegimeFolio (2025) | **[HP]** |
| **Growth-Inflation 2×2 Regime** | SPY vs 200D SMA + inflation sector ratio | Varadi/CSS Analytics (2025) | **[HP]** |
| **Mahalanobis Turbulence** | `(y-mu)^T Σ^{-1} (y-mu)` on multi-asset returns | Kritzman & Li (2010) | **[HP]** |
| **Comomentum** | Excess comovement among momentum winners | Lou & Polk (2021) | Medium |
| **Inter-ETF Correlation** | Rolling pairwise correlation among top-ranked | Baltas & Kosowski (2013) | Medium |

### 2.2 Macro-Based Regime Signals
| Signal | Formula | Source | Priority |
|--------|---------|--------|----------|
| **Yield Curve Slope** | 10Y - 2Y Treasury spread | Multiple | **[HP]** |
| **Macro Momentum** | GDP forecast changes, yield curve moves, FX trends | Brooks/AQR (2017) | **[HP]** |
| **HY Spread** | ICE BofA High Yield OAS | RegimeFolio / Alpha Architect | Medium |
| **FRED-MD PCA Clustering** | 127 macro vars → PCA → k-means clustering | Oliveira et al. (2025) | Medium |
| **Stock-Bond Correlation** | Rolling 60-day corr(SPY, TLT) | Shu & Mulvey (2024) | Medium |

### 2.3 Breadth / Early Warning Signals
| Signal | Formula | Source | Priority |
|--------|---------|--------|----------|
| **Canary Universe** | EEM + AGG momentum as crash signal | Keller DAA (2018) | **[HP]** |
| **Breadth Momentum** | % of assets with positive momentum score | Keller VAA (2017) | **[HP]** |
| **Panic State Indicator** | Recent market decline + high VIX | Daniel & Moskowitz (2016) | **[HP]** |

---

## 3. CRASH PROTECTION SIGNALS

### 3.1 Volatility-Based Protection
| Signal | Formula | Source | Priority |
|--------|---------|--------|----------|
| **Constant Vol Targeting** | `w_t = sigma_target / sigma_{t-1}` (trailing 126-day) | Barroso & Santa-Clara (2015) | **[HP]** |
| **Dynamic Momentum Scaling** | `w_t = (1/2) × (mu_t / sigma^2_t)` | Daniel & Moskowitz (2016) | **[HP]** |
| **Inverse-Vol Weighting** | Position size ∝ 1/sigma_i for each ETF | Butler, Philbrick, Gordillo (2012) | **[HP]** |
| **Yang-Zhang Vol Estimator** | OHLC range-based vol (reduces turnover 35%) | Baltas & Kosowski (2013) | Medium |

### 3.2 Regime-Conditional Protection
| Signal | Formula | Source | Priority |
|--------|---------|--------|----------|
| **Momentum-to-Reversal Switch** | Switch from momentum to mean-reversion in high vol | Butt, Kolari, Sadaqat (2023) | **[HP]** |
| **Rapid Risk Reduction** | 50% position reduction over 15 days in crisis | Asif, Froemmel, Mende (2022) | Medium |
| **Risk Budget Cap** | Cap risk contribution per ETF (e.g., 12% total vol) | SCIRP (2023) | Medium |

---

## 4. VALUE / QUALITY OVERLAY SIGNALS

| Signal | Formula | Source | Priority |
|--------|---------|--------|----------|
| **Value + Momentum Blend** | Combine momentum rank with valuation metric | Asness, Moskowitz, Pedersen (2013) | **[HP]** |
| **Quality + Momentum Filter** | Integrated V+Q+M scoring | Beck & Nguyen (2026) | Medium |
| **Momentum + Mean-Reversion Combo** | Strongest allocation when both agree | JBF (2010) | Medium |
| **Slow + Fast Signal Agreement** | 12M momentum (slow) + 1M momentum (fast) | Goldman Sachs (2018) | Medium |

---

## 5. PORTFOLIO CONSTRUCTION SIGNALS

| Signal | Formula | Source | Priority |
|--------|---------|--------|----------|
| **Top-N Selection** | Hold top 3-4 ETFs by momentum score | Multiple | **[HP]** |
| **Inverse-Volatility Weights** | Weight ∝ 1/sigma_i within selected ETFs | AAA / Butler et al. (2012) | **[HP]** |
| **Ledoit-Wolf Shrinkage** | Covariance estimation for optimization | RegimeFolio (2025) | Medium |
| **Turnover Constraints** | Penalize excessive rebalancing | Statistical Jump Model (2024) | Medium |

---

## RECOMMENDED SIGNAL STACK FOR 8-ETF ROTATION

### Primary (implement first):
1. **12-Month Volatility-Adjusted Momentum** — rank ETFs by return/vol
2. **Absolute Momentum Filter** — only hold if 12M return > T-bills
3. **10-Month SMA Overlay** — additional crash protection
4. **Inverse-Vol Weighting** — normalize risk across selected ETFs

### Secondary (layer on top):
5. **Canary Universe** (EEM + AGG) — early crash warning
6. **Constant Vol Targeting** — scale total exposure by strategy vol
7. **VIX Regime** — adjust aggressiveness by vol regime

### Advanced (ML-enhanced):
8. **Statistical Jump Model** regime per asset
9. **Growth-Inflation 2×2 Regime** for tilt
10. **Deep Ensemble uncertainty gating**
