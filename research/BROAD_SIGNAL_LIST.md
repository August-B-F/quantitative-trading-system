# Broad Signal List

New signals NOT already in MASTER_SIGNAL_LIST.md. Every signal here passed at least 5 of 6 filtering criteria.

---

## 1. BEHAVIORAL / MICROSTRUCTURE SIGNALS

| Signal | Formula / Method | Source | Data | Priority |
|--------|-----------------|--------|------|----------|
| **Information Discreteness** | `ID = sgn(PRET) × [%neg - %pos]` over formation period; more negative = stronger momentum | Da, Gurun, Warachka (2014) RFS | Daily OHLC | **HIGH** |
| **52-Week High Nearness** | `Price / 52-Week High`; rank ETFs by nearness; no long-run reversal unlike standard momentum | George & Hwang (2004) JF | Daily price | **HIGH** |
| **Capital Gains Overhang** | `CGO = (P - RP) / P` where RP is turnover-weighted avg cost basis; subsumes standard momentum | Grinblatt & Han (2005) JFE | Daily price + volume | Medium |
| **Left-Tail VaR Persistence** | Compute 5% VaR from daily returns; avoid ETFs with recent extreme tail events | Atilgan et al. (2020) JFE | Daily returns | Medium |
| **ETF Flow Contrarian** | Net creation/redemption normalized by AUM; penalize extreme recent inflows | Brown, Davies, Ringgenberg (2021) RoF | Shares outstanding, AUM | Medium |
| **Overnight/Intraday Ratio** | Decompose close-to-close into overnight + intraday; trust overnight momentum more | Lou, Polk, Skouras (2019) JFE | Daily open + close | Medium |

## 2. CROSS-ASSET MACRO SIGNALS

| Signal | Formula / Method | Source | Data | Priority |
|--------|-----------------|--------|------|----------|
| **Excess Bond Premium** | Residual from regressing credit spreads on default risk; rising EBP = risk-off | Gilchrist & Zakrajsek (2012) AER | Fed publishes monthly, since 1973 | **HIGH** |
| **Sector Credit Relative Value** | Compare sector-level HY spread changes vs. equity; credit improving faster = cheap | Klein (2013/2021) Wagner Award | Sector HY OAS indices | **HIGH** |
| **Baltic Dry Index Trend** | 3-month % change in BDI; positive = overweight cyclicals | Bakshi, Panayotov, Skoulakis (2011) | FRED DBDRY (free) | Medium |
| **GSCPI Supply Chain Stress** | NY Fed index; elevated = penalize supply-chain-dependent ETFs | Benigno et al. (2022) NY Fed | newyorkfed.org (free) | Medium |
| **GPR Threats Index** | Text-based geopolitical risk; spikes = defensive tilt + energy overweight | Caldara & Iacoviello (2022) AER | matteoiacoviello.com (free) | Medium |
| **Industry Lead-Lag** | Leading sector returns (energy, materials, financials) predict market 1-2M ahead | Hong, Torous, Valkanov (2007) JFE | Ken French library (free) | Low |

## 3. COMPLEXITY / NETWORK SIGNALS

| Signal | Formula / Method | Source | Data | Priority |
|--------|-----------------|--------|------|----------|
| **Absorption Ratio (delta-AR)** | Fraction of variance in top eigenvectors; standardized 2-week change signals crashes | Kritzman et al. (2011) JPM | Daily returns for 50+ assets | **HIGH** |
| **TDA Persistence Landscape Lp-Norm** | Persistent homology on multivariate returns; rising Lp-norm = crash approach (250-day lead) | Gidea & Katz (2018) Physica A | Daily returns, 4+ indices | Medium |
| **LPPLS Bubble Confidence** | Log-periodic power law fit across multiple scales; high confidence = bubble proximity | Shu & Song (2024) / Sornette | Daily price series | Medium |
| **Financial Chaos Index (FCIX)** | 3rd-order tensor eigenvalue from cross-sectional price changes; regime classification | Ataei et al. (2021) Physica A | Daily prices, 500+ stocks | Low |
| **Elastic DCCR** | Multiscale detrended cross-correlation; short-term MST contraction = stress | Daethey et al. (2025) | Daily returns | Low |
| **NMI Regime Detection** | Normalized mutual information between consecutive return windows; spikes = regime break | Noguer i Alonso (2025) | Daily returns | Low |
| **Transfer Entropy Lead-Lag** | Directional information flow between ETFs; allocate to leaders | Noguer i Alonso (2025) | Daily returns | Low |

## 4. CALIBRATION / UNCERTAINTY SIGNALS

| Signal | Formula / Method | Source | Data | Priority |
|--------|-----------------|--------|------|----------|
| **TCP Prediction Intervals** | Online-calibrated conformal intervals; width = uncertainty measure for sizing | TCP (2025) | Any base model output | **HIGH** |
| **Conformal Portfolio Selection** | Distribution-free intervals at portfolio level; maximin lower bound selects allocation | Kato (2024) | Historical portfolio returns | Medium |

---

## RECOMMENDED ADDITIONS TO SIGNAL STACK

### Tier 1 -- Add Immediately (free data, simple to compute, strong evidence):
1. **Information Discreteness (ID)** -- momentum quality filter, trivial to compute from daily data
2. **52-Week High Nearness** -- drop-in replacement/blend for 12M return, more crash-resistant
3. **Excess Bond Premium** -- Fed-published monthly, strongest recession predictor
4. **Absorption Ratio (delta-AR)** -- simple PCA-based crash timing from existing data

### Tier 2 -- Add Next (moderate effort, strong evidence):
5. **Sector Credit Relative Value** -- cross-market signal, credit leads equity
6. **TCP Prediction Intervals** -- calibrated uncertainty wrapping any model
7. **Overnight/Intraday Momentum Ratio** -- free from daily OHLC
8. **GSCPI + BDI** -- free macro indicators for cyclical tilting

### Tier 3 -- Research Priority (novel, needs prototyping):
9. **TDA Persistence Landscapes** -- topology-based crash early warning
10. **LPPLS Bubble Detection** -- battle-tested bubble model
11. **NMI/Transfer Entropy** -- information-theoretic regime detection

---

## META-SIGNALS (Not Trading Signals, But Critical Context)

| Insight | Source | Implication |
|---------|--------|-------------|
| Published anomalies deliver ~50% of backtest return | McLean & Pontiff (2016) JF | Haircut all signal expectations by half |
| International momentum less arbitraged than US | Jacobs & Muller (2020) JFE | Trust international ETF momentum more |
| Mechanical signals decay hyperbolically; complex ones persist | arXiv:2512.11913 (2025) | Multi-step composite signals are more defensible |
| Post-decimalization anomalies halved in liquid markets | Chordia et al. (2014) JAE | ETFs are the most liquid -- expect most decay |
| Generic foundation models fail in finance | Rahimikia et al. (2025) | Do NOT use TimeGPT/Chronos; train on financial data |
