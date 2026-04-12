# Experiment Ranking

**Status:** PENDING - No experiments have been run yet.
**Last Updated:** 2026-04-11

---

## Experiment Grid

### Tier 1 (Fundamental Questions)

| ID | Architecture | Target | Features | Window | Primary Metric | Result | vs Random | vs Systematic |
|---|---|---|---|---|---|---|---|---|
| E00 | Current Transformer | 5-class | All 68 | Current | Label shuffle comparison | PENDING | - | - |
| E01 | Ridge Regression | T2 (regression) | 7 domain | 60m | Spearman rho | PENDING | - | - |
| E02 | XGBoost (d=3) | T2 (regression) | 12 domain | 60m | Spearman rho | PENDING | - | - |
| E03 | Random Forest (d=4) | T1 (8-class) | 12 domain | 60m | Top-1 accuracy | PENDING | - | - |
| E04 | XGBoost (d=3) | T4 (drawdown) | 12 domain | 60m | Precision@80%recall | PENDING | - | - |
| E05 | Logistic Regression | T4 (drawdown) | 7 domain | 60m | Precision@80%recall | PENDING | - | - |

### Tier 2 (Conditional on Tier 1 Signal)

| ID | Architecture | Target | Status |
|---|---|---|---|
| E06 | LSTM (1L, 32h) | Best from T1 | BLOCKED (awaiting Tier 1) |
| E07 | Best T1 + regime split | Best target | BLOCKED |
| E08 | Ensemble (E01+E02+E03) | T2 | BLOCKED |
| E09 | Best T1 + 20 features | Best target | BLOCKED |
| E10 | Pairwise LogReg | T3 (ranking) | BLOCKED |

### Tier 3 (Conditional on Tier 2 Edge > Random + 5%)

| ID | Architecture | Status |
|---|---|---|
| E11 | Deep ensemble (5x best) | BLOCKED (awaiting Tier 2) |
| E12 | Small Transformer | BLOCKED |
| E13 | Heterogeneous ensemble | BLOCKED |
| E14 | Conformal prediction | BLOCKED |

---

## Baselines

| Baseline | CAGR | Sharpe | Max Drawdown |
|---|---|---|---|
| Random predictions | ~0% (expected) | ~0 | varies |
| Always hold SPY | 14.2% | ~0.65 | ~-34% |
| Systematic momentum (no AI) | 23.0% | 0.96 | -28.4% |

---

## Verdict

**PENDING** - Experiments have not been run.

Expected honest assessment will be written here after all applicable tiers complete.

Key question: Does the AI add measurable, statistically significant value over the pure systematic momentum strategy?
