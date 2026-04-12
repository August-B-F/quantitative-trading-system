# FEATURE IMPORTANCE REPORT — Regime Classifier Internals

Walk-forward HistGB regime classifier on CORE feature set (50 features).
Full WF accuracy: **0.6650** across 63 folds.

## A1 — Top 15 features by mean |SHAP|

| Rank | Feature | Mean abs SHAP | Primary regime push | Direction |
|---|---|---|---|---|
| 1 | `inflation_features__cpi_yoy` | 0.7299 | HG/LI (tech) | higher value pushes |
| 2 | `activity_features__ism_pmi` | 0.5917 | LG/LI (defensive) | higher value pushes |
| 3 | `activity_rail_traffic__rail_traffic_ma4w` | 0.3730 | LG/LI (defensive) | higher value pushes |
| 4 | `cross_asset_oil_gold__oil_gold_ratio` | 0.1971 | HG/HI (energy) | higher value pushes |
| 5 | `activity_features__capacity_utilization` | 0.1605 | HG/LI (tech) | higher value pushes |
| 6 | `consumer_features__consumer_credit_yoy` | 0.1488 | HG/HI (energy) | higher value pushes |
| 7 | `atr_14d__DBC` | 0.1256 | LG/LI (defensive) | higher value pushes |
| 8 | `vol_42d__XLE` | 0.1243 | HG/LI (tech) | higher value pushes |
| 9 | `returns_12_1_mom__XLE` | 0.1014 | LG/LI (defensive) | higher value pushes |
| 10 | `cross_sectional_mom_rank_126d__GLD` | 0.0995 | HG/LI (tech) | higher value pushes |
| 11 | `positioning_margin_debt_per_spy_px__margin_debt_per_spy_px` | 0.0949 | LG/HI (stagflation) | higher value pushes |
| 12 | `activity_features__oecd_cli` | 0.0949 | LG/HI (stagflation) | higher value pushes |
| 13 | `inflation_features__breakeven_10y` | 0.0764 | HG/HI (energy) | higher value pushes |
| 14 | `inflation_features__breakeven_5y` | 0.0740 | HG/HI (energy) | higher value pushes |
| 15 | `atr_14d__SPY` | 0.0737 | LG/HI (stagflation) | higher value pushes |

**Sanity check vs economic theory:** expected drivers include CPI/PCE trends (inflation axis), PMI / OECD CLI / industrial production (growth axis), and credit spreads / VIX (cross-cutting risk).

> ⚠️  Suspicious top-5 features (don't match growth/inflation/risk theme): #4: `cross_asset_oil_gold__oil_gold_ratio`

## A2 — Per-regime top 5 drivers (most positive signed SHAP)

### HG/LI (tech)

| Feature | Signed SHAP (push toward) | Abs SHAP |
|---|---|---|
| `inflation_features__cpi_yoy` | +0.3537 | 1.3169 |
| `vol_42d__XLE` | +0.2021 | 0.3357 |
| `activity_features__capacity_utilization` | +0.1678 | 0.1905 |
| `cross_sectional_mom_rank_126d__GLD` | +0.0946 | 0.1681 |
| `cross_asset_oil_gold__oil_gold_ratio` | +0.0755 | 0.0843 |

### HG/HI (energy)

| Feature | Signed SHAP (push toward) | Abs SHAP |
|---|---|---|
| `cross_asset_oil_gold__oil_gold_ratio` | +0.1638 | 0.2348 |
| `inflation_features__breakeven_5y` | +0.1198 | 0.2041 |
| `consumer_features__consumer_credit_yoy` | +0.0778 | 0.3369 |
| `inflation_features__breakeven_10y` | +0.0640 | 0.2098 |
| `returns_12_1_mom__XLE` | +0.0267 | 0.0765 |

### LG/LI (defensive)

| Feature | Signed SHAP (push toward) | Abs SHAP |
|---|---|---|
| `activity_rail_traffic__rail_traffic_ma4w` | +0.5014 | 0.5873 |
| `atr_14d__DBC` | +0.2909 | 0.2930 |
| `cross_asset_oil_gold__oil_gold_ratio` | +0.1391 | 0.1395 |
| `activity_features__ism_pmi` | +0.1046 | 1.3248 |
| `positioning_margin_debt_per_spy_px__margin_debt_per_spy_px` | +0.0966 | 0.1013 |

### LG/HI (stagflation)

| Feature | Signed SHAP (push toward) | Abs SHAP |
|---|---|---|
| `positioning_margin_debt_per_spy_px__margin_debt_per_spy_px` | +0.1239 | 0.1301 |
| `activity_features__oecd_cli` | +0.1017 | 0.1240 |
| `atr_14d__SPY` | +0.0949 | 0.1041 |
| `atr_14d__XLE` | +0.0500 | 0.0522 |
| `vol_63d__SOXX` | +0.0254 | 0.0317 |

## A3 — Feature stability across time periods

Rank-correlation of per-feature mean |SHAP| between period buckets:

| Comparison | Spearman ρ | Verdict |
|---|---|---|
| early → mid | 0.7102 | stable — consistent signals |
| mid → late | 0.7803 | stable — consistent signals |
| early → late | 0.7523 | stable — consistent signals |

## A4 — Feature reduction

| Features | Accuracy | Δ vs full |
|---|---|---|
| All (50) | 0.6650 | — |
| Top 15 | 0.6557 | -0.93pp |
| Top 10 | 0.7497 | +8.47pp |
| Top 7 | 0.6545 | -1.05pp |
| Top 5 | 0.7104 | +4.54pp |
| Top 3 | 0.7280 | +6.30pp |

**Minimum set above 63% accuracy:** Top 3 → 0.7280

Features: `inflation_features__cpi_yoy`, `activity_features__ism_pmi`, `activity_rail_traffic__rail_traffic_ma4w`

## A5 — Ablation (remove top-N features)

| Removed | n remaining | Accuracy | Δ vs full |
|---|---|---|---|
| (none) | 50 | 0.6650 | +0.00pp |
| inflation_features__cpi_yoy | 49 | 0.6020 | -6.30pp |
| inflation_features__cpi_yoy, activity_features__ism_pmi | 48 | 0.5079 | -15.70pp |
| inflation_features__cpi_yoy, activity_features__ism_pmi, activity_rail_traffic__rail_traffic_ma4w | 47 | 0.5348 | -13.02pp |

> ⚠️  **Fragility flag:** removing the #1 feature drops accuracy by more than 5pp. The classifier depends heavily on this single signal — log this for the risk section.

---

## Follow-up — 3-feature classifier deployed in full strategy

Retrained the regime classifier using only the top-3 SHAP features:
- `inflation_features__cpi_yoy`
- `activity_features__ism_pmi`
- `activity_rail_traffic__rail_traffic_ma4w`

Then ran the full OPTIMIZED strategy (E-R1 + M11 + M26_post_3d) with this thinner classifier, keeping every other component identical.

| Classifier | Regime acc | CAGR | Sharpe | MaxDD |
|---|---|---|---|---|
| 50 features (CORE) | 66.50% | 23.61% | 1.50 | -12.94% |
| 3 features (top SHAP) | 72.80% | 22.60% | 1.46 | -12.94% |

### B2 switch hit-ratio comparison

| Category | 50-feat | 3-feat |
|---|---|---|
| HELPFUL | 0 | 0 |
| NEUTRAL_CORRECT | 1 | 1 |
| NEUTRAL_WRONG | 25 | 15 |
| HARMFUL | 27 | 25 |
| **Total switches** | 53 | 41 |

**Verdict:** 3-feature classifier is close but slightly below the full-feature model on Sharpe. Trade-off between simplicity and edge; keep 50-feature as default.