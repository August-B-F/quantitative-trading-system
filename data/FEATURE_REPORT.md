# FEATURE_REPORT.md

Generated: 2026-04-12T15:24:31.353296+00:00

## Inventory
- Total raw feature columns: 1051
- Surviving (after dedup): 886
- Dropped by |corr|>=0.95: 165
- Non-stationary (p>0.05): 184

### Per-category counts

| category | count |
|---|---|
| alternative | 201 |
| calendar | 22 |
| fundamental | 11 |
| interaction | 64 |
| macro | 95 |
| price | 561 |
| sentiment | 97 |

## Panel
- Shape: (5351, 902)
- Date range: 2005-01-03 .. 2026-04-10
- Features: 886, Targets: 16

### NaN% by year

| year | nan% |
|---|---|
| 2005 | 35.3 |
| 2006 | 19.8 |
| 2007 | 18.7 |
| 2008 | 18.5 |
| 2009 | 18.6 |
| 2010 | 10.7 |
| 2011 | 9.2 |
| 2012 | 9.1 |
| 2013 | 9.2 |
| 2014 | 9.3 |
| 2015 | 6.8 |
| 2016 | 3.9 |
| 2017 | 3.9 |
| 2018 | 2.9 |
| 2019 | 3.2 |
| 2020 | 4.6 |
| 2021 | 4.6 |
| 2022 | 4.2 |
| 2023 | 4.0 |
| 2024 | 6.5 |
| 2025 | 6.0 |
| 2026 | 5.4 |

## Feature sets
- CORE: 50
- EXTENDED: 120
- MINIMAL: 13

Recommended training start: **2006-01-03 00:00:00** (first day with core NaN < 10%)

## Correlation-dropped features (top 30)

| dropped | kept | corr |
|---|---|---|
| quality_drawdown_252d__QQQ | quality_52w_high_ratio__QQQ | 1.0 |
| quality_drawdown_252d__VGT | quality_52w_high_ratio__VGT | 1.0 |
| quality_drawdown_252d__XLE | quality_52w_high_ratio__XLE | 1.0 |
| quality_drawdown_252d__GLD | quality_52w_high_ratio__GLD | 1.0 |
| quality_drawdown_252d__SHY | quality_52w_high_ratio__SHY | 1.0 |
| quality_drawdown_252d__SPY | quality_52w_high_ratio__SPY | 1.0 |
| quality_drawdown_252d__XLI | quality_52w_high_ratio__XLI | 1.0 |
| quality_drawdown_252d__IWM | quality_52w_high_ratio__IWM | 1.0 |
| momentum_spreads_63d__spy_minus_gld_63d | relative_strength_63d__GLD | 1.0 |
| vol_features__vix_regime_low | regime_vix__vix_regime_low | 1.0 |
| vol_features__vix_regime_medium | regime_vix__vix_regime_medium | 1.0 |
| vol_features__vix_regime_high | regime_vix__vix_regime_high | 1.0 |
| vol_features__vix_regime_extreme | regime_vix__vix_regime_extreme | 1.0 |
| momentum_spreads_63d__spy_minus_eem_63d | cross_asset_eem_spy__eem_minus_spy_63d | 1.0 |
| gtrends_gold_buy__gtrends_gold_buy_raw | gtrends_buy_gold__gtrends_buy_gold_raw | 1.0 |
| gtrends_gold_buy__gtrends_gold_buy_ma4w | gtrends_buy_gold__gtrends_buy_gold_ma4w | 1.0 |
| gtrends_gold_buy__gtrends_gold_buy_accel | gtrends_buy_gold__gtrends_buy_gold_accel | 1.0 |
| timing__is_sp_rebalance_week | timing__is_quad_witching_week | 1.0 |
| quality_drawdown_252d__EEM | quality_52w_high_ratio__EEM | 1.0 |
| quality_drawdown_252d__XLK | quality_52w_high_ratio__XLK | 1.0 |
| quality_drawdown_252d__IGV | quality_52w_high_ratio__IGV | 1.0 |
| quality_drawdown_252d__XLV | quality_52w_high_ratio__XLV | 1.0 |
| quality_drawdown_252d__DBC | quality_52w_high_ratio__DBC | 1.0 |
| quality_drawdown_252d__XLF | quality_52w_high_ratio__XLF | 1.0 |
| quality_drawdown_252d__SOXX | quality_52w_high_ratio__SOXX | 1.0 |
| quality_drawdown_252d__TLT | quality_52w_high_ratio__TLT | 1.0 |
| quality_drawdown_252d__AGG | quality_52w_high_ratio__AGG | 1.0 |
| atr_21d__SHY | atr_14d__SHY | 1.0 |
| atr_21d__AGG | atr_14d__AGG | 1.0 |
| atr_21d__TLT | atr_14d__TLT | 0.9997 |
| _+135 more_ | | |

## Top 20 features by mutual information vs T1 8-class target
_(diagnostic only — full-sample MI, DO NOT use for training selection)_

| MI | feature |
|---|---|
| 0.7202 | consumer_features__consumer_credit_yoy |
| 0.6347 | activity_features__capacity_utilization |
| 0.6064 | activity_features__ism_pmi |
| 0.5934 | inflation_features__cpi_yoy |
| 0.5854 | activity_features__oecd_cli |
| 0.3539 | inflation_features__cpi_mom |
| 0.3386 | activity_features__initial_claims_4wma |
| 0.3086 | atr_14d__XLE |
| 0.2910 | activity_rail_traffic__rail_traffic_ma4w |
| 0.2908 | atr_14d__DBC |
| 0.2397 | cross_asset_oil_gold__oil_gold_ratio |
| 0.2377 | positioning_margin_debt_per_spy_px__margin_debt_per_spy_px |
| 0.2105 | atr_14d__SPY |
| 0.1897 | vol_63d__SOXX |
| 0.1849 | vol_63d__QQQ |
| 0.1844 | vol_63d__XLV |
| 0.1727 | vol_63d__TLT |
| 0.1719 | vol_42d__XLI |
| 0.1625 | vol_42d__QQQ |
| 0.1525 | vol_42d__XLE |

## Validation
- Shape check: PASS
- Lookahead audit: features are inputs (all upstream .shift(1) lagged), targets are TARGET_-prefixed forward returns. Spot check PASS.
- T1 target alignment: argmax(TARGET_FWD21_*) matches TARGET_T1_winner_ticker on spot-checks.