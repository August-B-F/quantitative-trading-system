# FEATURE_REPORT.md

Generated: 2026-05-13T08:32:02.864471+00:00

## Inventory
- Total raw feature columns: 1051
- Surviving (after dedup): 1013
- Dropped by |corr|>=0.95: 38
- Non-stationary (p>0.05): 483

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
- Shape: (5351, 1029)
- Date range: 2005-01-03 .. 2026-04-10
- Features: 1013, Targets: 16

### NaN% by year

| year | nan% |
|---|---|
| 2005 | 73.4 |
| 2006 | 71.5 |
| 2007 | 71.1 |
| 2008 | 71.0 |
| 2009 | 71.1 |
| 2010 | 64.2 |
| 2011 | 62.8 |
| 2012 | 62.8 |
| 2013 | 62.8 |
| 2014 | 62.9 |
| 2015 | 60.7 |
| 2016 | 58.2 |
| 2017 | 58.2 |
| 2018 | 57.3 |
| 2019 | 57.5 |
| 2020 | 58.8 |
| 2021 | 58.8 |
| 2022 | 58.4 |
| 2023 | 58.3 |
| 2024 | 60.4 |
| 2025 | 57.8 |
| 2026 | 22.0 |

## Feature sets
- CORE: 50
- EXTENDED: 120
- MINIMAL: 13

Recommended training start: **2006-07-12 00:00:00** (first day with core NaN < 10%)

## Correlation-dropped features (top 30)

| dropped | kept | corr |
|---|---|---|
| vol_features__vix_regime_low | regime_vix__vix_regime_low | 1.0 |
| vol_features__vix_regime_medium | regime_vix__vix_regime_medium | 1.0 |
| vol_features__vix_regime_high | regime_vix__vix_regime_high | 1.0 |
| vol_features__vix_regime_extreme | regime_vix__vix_regime_extreme | 1.0 |
| momentum_spreads_63d__spy_minus_eem_63d | cross_asset_eem_spy__eem_minus_spy_63d | 1.0 |
| gtrends_gold_buy__gtrends_gold_buy_raw | gtrends_buy_gold__gtrends_buy_gold_raw | 1.0 |
| gtrends_gold_buy__gtrends_gold_buy_ma4w | gtrends_buy_gold__gtrends_buy_gold_ma4w | 1.0 |
| gtrends_gold_buy__gtrends_gold_buy_accel | gtrends_buy_gold__gtrends_buy_gold_accel | 1.0 |
| timing__is_sp_rebalance_week | timing__is_quad_witching_week | 1.0 |
| mom63_when_yc_inverted__VGT | mom63_when_yc_inverted__XLK | 0.9965 |
| mom63_when_cpi_hot__VGT | mom63_when_cpi_hot__XLK | 0.9944 |
| mom63_x_aaii_spread__VGT | mom63_x_aaii_spread__XLK | 0.9924 |
| mom63_x_pcr_total_z__VGT | mom63_x_pcr_total_z__XLK | 0.9918 |
| mom63_when_yc_normal__VGT | mom63_when_yc_normal__XLK | 0.9914 |
| positioning_cot_ust10y_mm_net__cot_ust10y_mm_net | positioning_cot_ust10y_comm_vs_spec__cot_ust10y_comm_vs_spec | 0.9907 |
| mom63_when_cpi_cool__VGT | mom63_when_cpi_cool__XLK | 0.9901 |
| mom63_x_vix_regime__VGT | mom63_x_vix_regime__XLK | 0.9892 |
| gtrends_bankruptcy__gtrends_bankruptcy_raw | gtrends_bankruptcy__gtrends_bankruptcy_ma4w | 0.9887 |
| mom63_when_yc_inverted__XLK | mom63_when_yc_inverted__QQQ | 0.9862 |
| mom63_when_cpi_hot__XLK | mom63_when_cpi_hot__QQQ | 0.9846 |
| gtrends_inflation__gtrends_inflation_raw | gtrends_inflation__gtrends_inflation_ma4w | 0.9834 |
| consumer_features__cb_consumer_conf | consumer_features__umich_sentiment | 0.9826 |
| mom63_x_aaii_spread__XLK | mom63_x_aaii_spread__QQQ | 0.9813 |
| mom63_x_pcr_total_z__XLK | mom63_x_pcr_total_z__QQQ | 0.9809 |
| mom63_when_yc_normal__XLK | mom63_when_yc_normal__QQQ | 0.9775 |
| gtrends_semiconductor_shortage__gtrends_semiconductor_shortage_raw | gtrends_semiconductor_shortage__gtrends_semiconductor_shortage_ma4w | 0.977 |
| gtrends_ai_stocks__gtrends_ai_stocks_raw | gtrends_ai_stocks__gtrends_ai_stocks_ma4w | 0.9762 |
| gtrends_housing_crash__gtrends_housing_crash_raw | gtrends_housing_crash__gtrends_housing_crash_ma4w | 0.9758 |
| gtrends_unemployment__gtrends_unemployment_raw | gtrends_unemployment__gtrends_unemployment_ma4w | 0.9731 |
| mom63_when_cpi_cool__XLK | mom63_when_cpi_cool__QQQ | 0.9726 |
| _+8 more_ | | |

## Top 20 features by mutual information vs T1 8-class target
_(diagnostic only — full-sample MI, DO NOT use for training selection)_

| MI | feature |
|---|---|
| 0.8588 | activity_features__capacity_utilization |
| 0.8204 | sp500_pe |
| 0.8071 | consumer_features__consumer_credit_yoy |
| 0.7936 | inflation_features__pce_core_yoy_3m_trend |
| 0.7491 | activity_features__oecd_cli |
| 0.7225 | inflation_features__cpi_yoy_3m_trend |
| 0.6370 | activity_features__ism_pmi |
| 0.6106 | inflation_features__cpi_yoy |
| 0.5222 | liquidity_features__fed_balance_sheet_yoy |
| 0.4570 | positioning_cot_nasdaq_comm_vs_spec__cot_nasdaq_comm_vs_spec |
| 0.4359 | survey_naaim_exposure__naaim_exposure |
| 0.4341 | positioning_margin_debt_3m_chg__margin_debt_3m_chg |
| 0.4060 | positioning_cot_nasdaq_mm_net__cot_nasdaq_mm_net |
| 0.3881 | inflation_features__cpi_mom |
| 0.3774 | positioning_cot_sp500_mm_net_z52w__cot_sp500_mm_net_z52w |
| 0.3634 | activity_features__lei_6m_change |
| 0.3575 | consumer_features__personal_savings_rate |
| 0.3451 | activity_features__initial_claims_4wma |
| 0.3151 | activity_rail_traffic__rail_traffic_ma4w |
| 0.2477 | yield_curve_features__real_rate_10y |

## Validation
- Shape check: PASS
- Lookahead audit: features are inputs (all upstream .shift(1) lagged), targets are TARGET_-prefixed forward returns. Spot check PASS.
- T1 target alignment: argmax(TARGET_FWD21_*) matches TARGET_T1_winner_ticker on spot-checks.