

## Session 4.x - Sentiment + Fundamental features (108 files, builder: src/features/sentiment_features.py)

Builder reads /data/clean/sentiment and /data/clean/fundamental, applies LAG_DAYS shifts, then reindexes onto the NYSE trading calendar from 2003-01-01. AAII/NAAIM weekly +1d, COT +4d (Tue position date publishes Fri), CNN F&G (reconstructed) +1d, CBOE PCR +1d, FRED margin debt +30d, Shiller CAPE +30d, S&P buyback yield (FRED Z.1 quarterly) +60d, SIA semi sales +45d, news sentiment +1d.

Counts: survey 13, positioning 52, news 32, fundamental 11.

Sources skipped (failed in Phase 3 - confirmed zero orphan features):
- investors_intelligence: paid only, no free historical feed (FAILED_SOURCES line 37)
- ETF flow data: not ingested
- Dark pool data: not ingested
- Insider transactions: file exists but only 196 rows (Jun 2025+); openinsider screener permanently failed (FAILED_SOURCES line 1465). Do not build features until backfilled.
- Per-sector P/E (tech, energy): macrotrends search disallowed (FAILED_SOURCES lines 21-22). Only aggregate sp500_pe_ratio used.
- IPO volume: not ingested
- Forward P/E: not ingested
- Book-to-bill ratio: not in SIA file (only sales/yoy/mom)

Fold notes:
- positioning_pcr_* features are built from native CBOE files (cboe_putcall_equity, cboe_putcall_total, cboe_putcall_index), so coverage ends 2019-10-04. For post-2019 folds use VIX-derived sentiment from data/features/macro/vol_features.parquet. Do NOT use the spliced files in Phase 4 features.
- survey_fg_* uses fear_greed_reconstructed.parquet (2000-2026) rather than the 249-row cnn_fear_greed.parquet (2025-04+). The reconstruction is built only from market data (momentum, breadth, vol, safe-haven, junk-bond, strength) so leakage risk is the same as VIX features; +1d shift suffices.
- positioning_short_volume_ratio_* uses FINRA daily short *volume* (Jan-2023+), not aggregate short *interest* of issues. Coverage too short for crisis periods; treat as a recent-regime-only feature.
- Margin-debt-per-SPY-px is a *price-relative* proxy: market cap not available, so we divide FRED margin debt by SPY adj_close. Relative trend only, NOT a true % of market cap.

Validation results (build 2026-04-12):
- AAII extreme pessimism (spread < -20%) Mar 2020 = 5 days, Oct 2022 = 29 days [PASS]
- COT crude managed-money net Jan-Feb 2022 mean = +62,497 contracts (net long, before 2022 oil rally) [PASS]
- News energy sentiment 21d MA: Q1-2021 = -0.112 -> Q4-2021 = -0.048 (improving before XLE outperformance) [PASS]
- Orphan check: 0 features reference failed sources (investors_intel, etf_flow, darkpool, ipo, sector_pe, insider_) [PASS]

## Session 4.x - Interaction features + Phase 5 targets (build 2026-04-12, builder: src/features/interactions_targets.py)

12 interaction feature files combine 63d momentum with macro regimes (VIX extreme zero-out, yield-curve normal/inverted split, CPI hot/cool split), sentiment (AAII spread product, PCR total z product), cross-asset confirmation (energy=XLE×USO, tech=SOXX×SMH, safe-haven=GLD×HY-IG spread chg, bond=TLT×yc-slope chg), and 4 momentum spreads (SOXX-XLE, QQQ-XLV, SPY-GLD, SPY-EEM). All inputs are .shift(1) lagged via the upstream feature builders, so interaction columns inherit no-lookahead.

Targets (data/features/targets/, all columns prefixed TARGET_): T1 8-class winner of 21d forward return across {SOXX,QQQ,XLK,VGT,IGV,XLE,GLD,SHY}; T2 8 forward 21d returns; T4 binary drawdown of the 63d-momentum-top holding at 3/5/7% thresholds; T5 binary "did the systematic strategy pick the actual winner"; T_REGIME forward-21d VIX regime + growth-inflation quadrant labels. Forward return uses prices T+1..T+21 (label only, never join as feature). Strategy holding for T4/T5 = argmax of 63d momentum among PRIMARY_UNIVERSE on day T (computed from T-1 data).

Validation results:
- T1 base rates: SOXX 25.0%, XLE 22.4%, GLD 21.3%, IGV 13.2%, SHY 7.8%, QQQ 4.7%, XLK 3.4%, VGT 2.2%. Every ETF wins at least sometimes (no zero-win classes). [PASS]
- T1 2022 top winners: XLE 47.8%, SOXX 19.9%, GLD 12.4% (energy dominant as expected). [PASS]
- T1 2023-2024 top winners: SOXX 27.7%, XLE 20.3%, GLD 19.7% (tech leads, as expected). [PASS]
- T4 drawdown rates of held ETF: 3% threshold 18.6%, 5% threshold 12.1%, 7% threshold 7.8% (5% within target 10-20% range). [PASS]
- T4 March 2020: 5/19 days flagged at >5% (drawdown trigger fired during the COVID crash). [PASS]
- T5 systematic strategy base accuracy: 19.75% (random 8-class baseline 12.5%). This is the bar the AI must beat.
- Energy confirmation Sep-Dec 2021: mean +0.682 (XLE & USO both rising before the 2022 oil rally). [PASS]

Notes:
- "Crude oil momentum" is proxied with USO; "semiconductor revenue trend" is proxied with SMH ETF momentum because the SIA semi sales feature is monthly with +45d lag and gives a confirmation signal too coarse for daily alignment.
- TLT is in EXTRA_TICKERS and is loaded directly from data/clean/prices/TLT.parquet.
- mom63 inputs use rolling_return(close, 63) which is .shift(1)-lagged; interaction columns are the same length as the price calendar (5351 rows, 2005-01-03..2026-04-10) and the trailing ~21 rows of T-prefixed targets are NaN by construction.

| interaction | mom63_x_vix_regime | 8 | 5351 | 2005-01-03..2026-04-10 | data/features/interaction/mom63_x_vix_regime.parquet | 2026-04-12 |
| interaction | mom63_when_yc_normal | 8 | 5351 | 2005-01-03..2026-04-10 | data/features/interaction/mom63_when_yc_normal.parquet | 2026-04-12 |
| interaction | mom63_when_yc_inverted | 8 | 5351 | 2005-01-03..2026-04-10 | data/features/interaction/mom63_when_yc_inverted.parquet | 2026-04-12 |
| interaction | mom63_when_cpi_hot | 8 | 5351 | 2005-01-03..2026-04-10 | data/features/interaction/mom63_when_cpi_hot.parquet | 2026-04-12 |
| interaction | mom63_when_cpi_cool | 8 | 5351 | 2005-01-03..2026-04-10 | data/features/interaction/mom63_when_cpi_cool.parquet | 2026-04-12 |
| interaction | mom63_x_aaii_spread | 8 | 5351 | 2005-01-03..2026-04-10 | data/features/interaction/mom63_x_aaii_spread.parquet | 2026-04-12 |
| interaction | mom63_x_pcr_total_z | 8 | 5351 | 2005-01-03..2026-04-10 | data/features/interaction/mom63_x_pcr_total_z.parquet | 2026-04-12 |
| interaction | energy_confirmation | 1 | 5351 | 2005-01-03..2026-04-10 | data/features/interaction/energy_confirmation.parquet | 2026-04-12 |
| interaction | tech_confirmation | 1 | 5351 | 2005-01-03..2026-04-10 | data/features/interaction/tech_confirmation.parquet | 2026-04-12 |
| interaction | safe_haven_confirmation | 1 | 5351 | 2005-01-03..2026-04-10 | data/features/interaction/safe_haven_confirmation.parquet | 2026-04-12 |
| interaction | bond_confirmation | 1 | 5351 | 2005-01-03..2026-04-10 | data/features/interaction/bond_confirmation.parquet | 2026-04-12 |
| interaction | momentum_spreads_63d | 4 | 5351 | 2005-01-03..2026-04-10 | data/features/interaction/momentum_spreads_63d.parquet | 2026-04-12 |
| targets | T2_forward_returns_21d | 8 | 5351 | 2005-01-03..2026-04-10 | data/features/targets/T2_forward_returns_21d.parquet | 2026-04-12 |
| targets | T1_winner_8class | 2 | 5351 | 2005-01-03..2026-04-10 | data/features/targets/T1_winner_8class.parquet | 2026-04-12 |
| targets | T4_drawdown | 3 | 5351 | 2005-01-03..2026-04-10 | data/features/targets/T4_drawdown.parquet | 2026-04-12 |
| targets | T5_strategy_correct | 1 | 5351 | 2005-01-03..2026-04-10 | data/features/targets/T5_strategy_correct.parquet | 2026-04-12 |
| targets | T_regime_fwd21 | 2 | 5351 | 2005-01-03..2026-04-10 | data/features/targets/T_regime_fwd21.parquet | 2026-04-12 |

## Session 5.0 - Master panel assembly (build 2026-04-12, src/features/assemble_master_panel.py)

Loaded 1051 raw feature columns across 7 categories, plus 16 target columns. Dropped 165 features via |corr|>=0.95 pairwise dedup (keeping the longer-history member of each pair). Ran ADF stationarity (flagged 184 non-stationary � these must be differenced at training time per-fold, not here). Computed lag-21 autocorrelation per feature. Built CORE (50 feats, 2010+ with <5% NaN, non-experimental, |target_corr|>=0.05), EXTENDED (120 feats, all survivors), and MINIMAL (13 feats, hand-picked for low-param models). Master panel saved to data/features/master_panel.parquet (shape (5351, 902)). Recommended training start: 2006-01-03 00:00:00 (first day where CORE NaN<10%).

NaN by year (master panel):
- 2005: 35.3%
- 2006: 19.8%
- 2007: 18.7%
- 2008: 18.5%
- 2009: 18.6%
- 2010: 10.7%
- 2011: 9.2%
- 2012: 9.1%
- 2013: 9.2%
- 2014: 9.3%
- 2015: 6.8%
- 2016: 3.9%
- 2017: 3.9%
- 2018: 2.9%
- 2019: 3.2%
- 2020: 4.6%
- 2021: 4.6%
- 2022: 4.2%
- 2023: 4.0%
- 2024: 6.5%
- 2025: 6.0%
- 2026: 5.4%

Correlation drops: 165 pairs. First 10:
- DROP `quality_drawdown_252d__QQQ` (kept `quality_52w_high_ratio__QQQ`, |r|=1.0)
- DROP `quality_drawdown_252d__VGT` (kept `quality_52w_high_ratio__VGT`, |r|=1.0)
- DROP `quality_drawdown_252d__XLE` (kept `quality_52w_high_ratio__XLE`, |r|=1.0)
- DROP `quality_drawdown_252d__GLD` (kept `quality_52w_high_ratio__GLD`, |r|=1.0)
- DROP `quality_drawdown_252d__SHY` (kept `quality_52w_high_ratio__SHY`, |r|=1.0)
- DROP `quality_drawdown_252d__SPY` (kept `quality_52w_high_ratio__SPY`, |r|=1.0)
- DROP `quality_drawdown_252d__XLI` (kept `quality_52w_high_ratio__XLI`, |r|=1.0)
- DROP `quality_drawdown_252d__IWM` (kept `quality_52w_high_ratio__IWM`, |r|=1.0)
- DROP `momentum_spreads_63d__spy_minus_gld_63d` (kept `relative_strength_63d__GLD`, |r|=1.0)
- DROP `vol_features__vix_regime_low` (kept `regime_vix__vix_regime_low`, |r|=1.0)

Artifacts:
- data/features/master_panel.parquet
- data/features/master_panel_metadata.json
- configs/feature_sets.yaml
- data/FEATURE_REPORT.md

## Session 5.0 - Master panel assembly (build 2026-04-12, src/features/assemble_master_panel.py)

Loaded 1051 raw feature columns across 7 categories, plus 16 target columns. Dropped 165 features via |corr|>=0.95 pairwise dedup (keeping the longer-history member of each pair). Ran ADF stationarity (flagged 184 non-stationary � these must be differenced at training time per-fold, not here). Computed lag-21 autocorrelation per feature. Built CORE (50 feats, 2010+ with <5% NaN, non-experimental, |target_corr|>=0.05), EXTENDED (120 feats, all survivors), and MINIMAL (13 feats, hand-picked for low-param models). Master panel saved to data/features/master_panel.parquet (shape (5351, 902)). Recommended training start: 2006-01-03 00:00:00 (first day where CORE NaN<10%).

NaN by year (master panel):
- 2005: 35.3%
- 2006: 19.8%
- 2007: 18.7%
- 2008: 18.5%
- 2009: 18.6%
- 2010: 10.7%
- 2011: 9.2%
- 2012: 9.1%
- 2013: 9.2%
- 2014: 9.3%
- 2015: 6.8%
- 2016: 3.9%
- 2017: 3.9%
- 2018: 2.9%
- 2019: 3.2%
- 2020: 4.6%
- 2021: 4.6%
- 2022: 4.2%
- 2023: 4.0%
- 2024: 6.5%
- 2025: 6.0%
- 2026: 5.4%

Correlation drops: 165 pairs. First 10:
- DROP `quality_drawdown_252d__QQQ` (kept `quality_52w_high_ratio__QQQ`, |r|=1.0)
- DROP `quality_drawdown_252d__VGT` (kept `quality_52w_high_ratio__VGT`, |r|=1.0)
- DROP `quality_drawdown_252d__XLE` (kept `quality_52w_high_ratio__XLE`, |r|=1.0)
- DROP `quality_drawdown_252d__GLD` (kept `quality_52w_high_ratio__GLD`, |r|=1.0)
- DROP `quality_drawdown_252d__SHY` (kept `quality_52w_high_ratio__SHY`, |r|=1.0)
- DROP `quality_drawdown_252d__SPY` (kept `quality_52w_high_ratio__SPY`, |r|=1.0)
- DROP `quality_drawdown_252d__XLI` (kept `quality_52w_high_ratio__XLI`, |r|=1.0)
- DROP `quality_drawdown_252d__IWM` (kept `quality_52w_high_ratio__IWM`, |r|=1.0)
- DROP `momentum_spreads_63d__spy_minus_gld_63d` (kept `relative_strength_63d__GLD`, |r|=1.0)
- DROP `vol_features__vix_regime_low` (kept `regime_vix__vix_regime_low`, |r|=1.0)

Artifacts:
- data/features/master_panel.parquet
- data/features/master_panel_metadata.json
- configs/feature_sets.yaml
- data/FEATURE_REPORT.md
| price | returns_5d | 17 | 5351 | 2005-01-03..2026-04-10 | data/features/price/returns_5d.parquet | 2026-04-13 |
| price | returns_10d | 17 | 5351 | 2005-01-03..2026-04-10 | data/features/price/returns_10d.parquet | 2026-04-13 |
| price | returns_21d | 17 | 5351 | 2005-01-03..2026-04-10 | data/features/price/returns_21d.parquet | 2026-04-13 |
| price | returns_42d | 17 | 5351 | 2005-01-03..2026-04-10 | data/features/price/returns_42d.parquet | 2026-04-13 |
| price | returns_63d | 17 | 5351 | 2005-01-03..2026-04-10 | data/features/price/returns_63d.parquet | 2026-04-13 |
| price | returns_126d | 17 | 5351 | 2005-01-03..2026-04-10 | data/features/price/returns_126d.parquet | 2026-04-13 |
| price | returns_252d | 17 | 5351 | 2005-01-03..2026-04-10 | data/features/price/returns_252d.parquet | 2026-04-13 |
| price | returns_12_1_mom | 17 | 5351 | 2005-01-03..2026-04-10 | data/features/price/returns_12_1_mom.parquet | 2026-04-13 |
| price | vol_21d | 17 | 5351 | 2005-01-03..2026-04-10 | data/features/price/vol_21d.parquet | 2026-04-13 |
| price | vol_42d | 17 | 5351 | 2005-01-03..2026-04-10 | data/features/price/vol_42d.parquet | 2026-04-13 |
| price | vol_63d | 17 | 5351 | 2005-01-03..2026-04-10 | data/features/price/vol_63d.parquet | 2026-04-13 |
| price | atr_14d | 17 | 5351 | 2005-01-03..2026-04-10 | data/features/price/atr_14d.parquet | 2026-04-13 |
| price | atr_21d | 17 | 5351 | 2005-01-03..2026-04-10 | data/features/price/atr_21d.parquet | 2026-04-13 |
| price | intraday_range_21d | 17 | 5351 | 2005-01-03..2026-04-10 | data/features/price/intraday_range_21d.parquet | 2026-04-13 |
| price | quality_voladj_mom_21d | 17 | 5351 | 2005-01-03..2026-04-10 | data/features/price/quality_voladj_mom_21d.parquet | 2026-04-13 |
| price | quality_voladj_mom_42d | 17 | 5351 | 2005-01-03..2026-04-10 | data/features/price/quality_voladj_mom_42d.parquet | 2026-04-13 |
| price | quality_voladj_mom_63d | 17 | 5351 | 2005-01-03..2026-04-10 | data/features/price/quality_voladj_mom_63d.parquet | 2026-04-13 |
| price | quality_voladj_mom_126d | 17 | 5351 | 2005-01-03..2026-04-10 | data/features/price/quality_voladj_mom_126d.parquet | 2026-04-13 |
| price | quality_mom_accel | 17 | 5351 | 2005-01-03..2026-04-10 | data/features/price/quality_mom_accel.parquet | 2026-04-13 |
| price | quality_52w_high_ratio | 17 | 5351 | 2005-01-03..2026-04-10 | data/features/price/quality_52w_high_ratio.parquet | 2026-04-13 |
| price | quality_dist_sma200 | 17 | 5351 | 2005-01-03..2026-04-10 | data/features/price/quality_dist_sma200.parquet | 2026-04-13 |
| price | quality_dist_sma50 | 17 | 5351 | 2005-01-03..2026-04-10 | data/features/price/quality_dist_sma50.parquet | 2026-04-13 |
| price | quality_golden_cross | 17 | 5351 | 2005-01-03..2026-04-10 | data/features/price/quality_golden_cross.parquet | 2026-04-13 |
| price | quality_drawdown_252d | 17 | 5351 | 2005-01-03..2026-04-10 | data/features/price/quality_drawdown_252d.parquet | 2026-04-13 |
| price | quality_rsi_14d | 17 | 5351 | 2005-01-03..2026-04-10 | data/features/price/quality_rsi_14d.parquet | 2026-04-13 |
| price | quality_rsi_28d | 17 | 5351 | 2005-01-03..2026-04-10 | data/features/price/quality_rsi_28d.parquet | 2026-04-13 |
| price | quality_bb_position | 17 | 5351 | 2005-01-03..2026-04-10 | data/features/price/quality_bb_position.parquet | 2026-04-13 |
| price | cross_sectional_mom_rank_21d | 8 | 5351 | 2005-01-03..2026-04-10 | data/features/price/cross_sectional_mom_rank_21d.parquet | 2026-04-13 |
| price | cross_sectional_mom_rank_42d | 8 | 5351 | 2005-01-03..2026-04-10 | data/features/price/cross_sectional_mom_rank_42d.parquet | 2026-04-13 |
| price | cross_sectional_mom_rank_63d | 8 | 5351 | 2005-01-03..2026-04-10 | data/features/price/cross_sectional_mom_rank_63d.parquet | 2026-04-13 |
| price | cross_sectional_mom_rank_126d | 8 | 5351 | 2005-01-03..2026-04-10 | data/features/price/cross_sectional_mom_rank_126d.parquet | 2026-04-13 |
| price | cross_sectional_relative_mom_63d | 8 | 5351 | 2005-01-03..2026-04-10 | data/features/price/cross_sectional_relative_mom_63d.parquet | 2026-04-13 |
| price | cross_sectional_mom_zscore_63d | 8 | 5351 | 2005-01-03..2026-04-10 | data/features/price/cross_sectional_mom_zscore_63d.parquet | 2026-04-13 |
| price | cross_sectional_rank_stability_21d | 1 | 5351 | 2005-01-03..2026-04-10 | data/features/price/cross_sectional_rank_stability_21d.parquet | 2026-04-13 |
| price | cross_sectional_top_margin_63d | 1 | 5351 | 2005-01-03..2026-04-10 | data/features/price/cross_sectional_top_margin_63d.parquet | 2026-04-13 |
| price | cross_sectional_dispersion_63d | 1 | 5351 | 2005-01-03..2026-04-10 | data/features/price/cross_sectional_dispersion_63d.parquet | 2026-04-13 |
| price | volume_trend_21_63 | 9 | 5351 | 2005-01-03..2026-04-10 | data/features/price/volume_trend_21_63.parquet | 2026-04-13 |
| price | volume_relative_21d | 9 | 5351 | 2005-01-03..2026-04-10 | data/features/price/volume_relative_21d.parquet | 2026-04-13 |
| price | volume_obv_slope_21d | 9 | 5351 | 2005-01-03..2026-04-10 | data/features/price/volume_obv_slope_21d.parquet | 2026-04-13 |
| price | relative_strength_63d | 8 | 5351 | 2005-01-03..2026-04-10 | data/features/price/relative_strength_63d.parquet | 2026-04-13 |
| price | relative_strength_126d | 8 | 5351 | 2005-01-03..2026-04-10 | data/features/price/relative_strength_126d.parquet | 2026-04-13 |
| price | relative_strength_trend_accel | 8 | 5351 | 2005-01-03..2026-04-10 | data/features/price/relative_strength_trend_accel.parquet | 2026-04-13 |
| price | returns_5d | 17 | 5351 | 2005-01-03..2026-04-10 | data/features/price/returns_5d.parquet | 2026-04-13 |
| price | returns_10d | 17 | 5351 | 2005-01-03..2026-04-10 | data/features/price/returns_10d.parquet | 2026-04-13 |
| price | returns_21d | 17 | 5351 | 2005-01-03..2026-04-10 | data/features/price/returns_21d.parquet | 2026-04-13 |
| price | returns_42d | 17 | 5351 | 2005-01-03..2026-04-10 | data/features/price/returns_42d.parquet | 2026-04-13 |
| price | returns_63d | 17 | 5351 | 2005-01-03..2026-04-10 | data/features/price/returns_63d.parquet | 2026-04-13 |
| price | returns_126d | 17 | 5351 | 2005-01-03..2026-04-10 | data/features/price/returns_126d.parquet | 2026-04-13 |
| price | returns_252d | 17 | 5351 | 2005-01-03..2026-04-10 | data/features/price/returns_252d.parquet | 2026-04-13 |
| price | returns_12_1_mom | 17 | 5351 | 2005-01-03..2026-04-10 | data/features/price/returns_12_1_mom.parquet | 2026-04-13 |
| price | vol_21d | 17 | 5351 | 2005-01-03..2026-04-10 | data/features/price/vol_21d.parquet | 2026-04-13 |
| price | vol_42d | 17 | 5351 | 2005-01-03..2026-04-10 | data/features/price/vol_42d.parquet | 2026-04-13 |
| price | vol_63d | 17 | 5351 | 2005-01-03..2026-04-10 | data/features/price/vol_63d.parquet | 2026-04-13 |
| price | atr_14d | 17 | 5351 | 2005-01-03..2026-04-10 | data/features/price/atr_14d.parquet | 2026-04-13 |
| price | atr_21d | 17 | 5351 | 2005-01-03..2026-04-10 | data/features/price/atr_21d.parquet | 2026-04-13 |
| price | intraday_range_21d | 17 | 5351 | 2005-01-03..2026-04-10 | data/features/price/intraday_range_21d.parquet | 2026-04-13 |
| price | quality_voladj_mom_21d | 17 | 5351 | 2005-01-03..2026-04-10 | data/features/price/quality_voladj_mom_21d.parquet | 2026-04-13 |
| price | quality_voladj_mom_42d | 17 | 5351 | 2005-01-03..2026-04-10 | data/features/price/quality_voladj_mom_42d.parquet | 2026-04-13 |
| price | quality_voladj_mom_63d | 17 | 5351 | 2005-01-03..2026-04-10 | data/features/price/quality_voladj_mom_63d.parquet | 2026-04-13 |
| price | quality_voladj_mom_126d | 17 | 5351 | 2005-01-03..2026-04-10 | data/features/price/quality_voladj_mom_126d.parquet | 2026-04-13 |
| price | quality_mom_accel | 17 | 5351 | 2005-01-03..2026-04-10 | data/features/price/quality_mom_accel.parquet | 2026-04-13 |
| price | quality_52w_high_ratio | 17 | 5351 | 2005-01-03..2026-04-10 | data/features/price/quality_52w_high_ratio.parquet | 2026-04-13 |
| price | quality_dist_sma200 | 17 | 5351 | 2005-01-03..2026-04-10 | data/features/price/quality_dist_sma200.parquet | 2026-04-13 |
| price | quality_dist_sma50 | 17 | 5351 | 2005-01-03..2026-04-10 | data/features/price/quality_dist_sma50.parquet | 2026-04-13 |
| price | quality_golden_cross | 17 | 5351 | 2005-01-03..2026-04-10 | data/features/price/quality_golden_cross.parquet | 2026-04-13 |
| price | quality_drawdown_252d | 17 | 5351 | 2005-01-03..2026-04-10 | data/features/price/quality_drawdown_252d.parquet | 2026-04-13 |
| price | quality_rsi_14d | 17 | 5351 | 2005-01-03..2026-04-10 | data/features/price/quality_rsi_14d.parquet | 2026-04-13 |
| price | quality_rsi_28d | 17 | 5351 | 2005-01-03..2026-04-10 | data/features/price/quality_rsi_28d.parquet | 2026-04-13 |
| price | quality_bb_position | 17 | 5351 | 2005-01-03..2026-04-10 | data/features/price/quality_bb_position.parquet | 2026-04-13 |
| price | cross_sectional_mom_rank_21d | 8 | 5351 | 2005-01-03..2026-04-10 | data/features/price/cross_sectional_mom_rank_21d.parquet | 2026-04-13 |
| price | cross_sectional_mom_rank_42d | 8 | 5351 | 2005-01-03..2026-04-10 | data/features/price/cross_sectional_mom_rank_42d.parquet | 2026-04-13 |
| price | cross_sectional_mom_rank_63d | 8 | 5351 | 2005-01-03..2026-04-10 | data/features/price/cross_sectional_mom_rank_63d.parquet | 2026-04-13 |
| price | cross_sectional_mom_rank_126d | 8 | 5351 | 2005-01-03..2026-04-10 | data/features/price/cross_sectional_mom_rank_126d.parquet | 2026-04-13 |
| price | cross_sectional_relative_mom_63d | 8 | 5351 | 2005-01-03..2026-04-10 | data/features/price/cross_sectional_relative_mom_63d.parquet | 2026-04-13 |
| price | cross_sectional_mom_zscore_63d | 8 | 5351 | 2005-01-03..2026-04-10 | data/features/price/cross_sectional_mom_zscore_63d.parquet | 2026-04-13 |
| price | cross_sectional_rank_stability_21d | 1 | 5351 | 2005-01-03..2026-04-10 | data/features/price/cross_sectional_rank_stability_21d.parquet | 2026-04-13 |
| price | cross_sectional_top_margin_63d | 1 | 5351 | 2005-01-03..2026-04-10 | data/features/price/cross_sectional_top_margin_63d.parquet | 2026-04-13 |
| price | cross_sectional_dispersion_63d | 1 | 5351 | 2005-01-03..2026-04-10 | data/features/price/cross_sectional_dispersion_63d.parquet | 2026-04-13 |
| price | volume_trend_21_63 | 9 | 5351 | 2005-01-03..2026-04-10 | data/features/price/volume_trend_21_63.parquet | 2026-04-13 |
| price | volume_relative_21d | 9 | 5351 | 2005-01-03..2026-04-10 | data/features/price/volume_relative_21d.parquet | 2026-04-13 |
| price | volume_obv_slope_21d | 9 | 5351 | 2005-01-03..2026-04-10 | data/features/price/volume_obv_slope_21d.parquet | 2026-04-13 |
| price | relative_strength_63d | 8 | 5351 | 2005-01-03..2026-04-10 | data/features/price/relative_strength_63d.parquet | 2026-04-13 |
| price | relative_strength_126d | 8 | 5351 | 2005-01-03..2026-04-10 | data/features/price/relative_strength_126d.parquet | 2026-04-13 |
| price | relative_strength_trend_accel | 8 | 5351 | 2005-01-03..2026-04-10 | data/features/price/relative_strength_trend_accel.parquet | 2026-04-13 |
| price | returns_5d | 17 | 5353 | 2005-01-03..2026-04-14 | data/features/price/returns_5d.parquet | 2026-04-14 |
| price | returns_10d | 17 | 5353 | 2005-01-03..2026-04-14 | data/features/price/returns_10d.parquet | 2026-04-14 |
| price | returns_21d | 17 | 5353 | 2005-01-03..2026-04-14 | data/features/price/returns_21d.parquet | 2026-04-14 |
| price | returns_42d | 17 | 5353 | 2005-01-03..2026-04-14 | data/features/price/returns_42d.parquet | 2026-04-14 |
| price | returns_63d | 17 | 5353 | 2005-01-03..2026-04-14 | data/features/price/returns_63d.parquet | 2026-04-14 |
| price | returns_126d | 17 | 5353 | 2005-01-03..2026-04-14 | data/features/price/returns_126d.parquet | 2026-04-14 |
| price | returns_252d | 17 | 5353 | 2005-01-03..2026-04-14 | data/features/price/returns_252d.parquet | 2026-04-14 |
| price | returns_12_1_mom | 17 | 5353 | 2005-01-03..2026-04-14 | data/features/price/returns_12_1_mom.parquet | 2026-04-14 |
| price | vol_21d | 17 | 5353 | 2005-01-03..2026-04-14 | data/features/price/vol_21d.parquet | 2026-04-14 |
| price | vol_42d | 17 | 5353 | 2005-01-03..2026-04-14 | data/features/price/vol_42d.parquet | 2026-04-14 |
| price | vol_63d | 17 | 5353 | 2005-01-03..2026-04-14 | data/features/price/vol_63d.parquet | 2026-04-14 |
| price | atr_14d | 17 | 5353 | 2005-01-03..2026-04-14 | data/features/price/atr_14d.parquet | 2026-04-14 |
| price | atr_21d | 17 | 5353 | 2005-01-03..2026-04-14 | data/features/price/atr_21d.parquet | 2026-04-14 |
| price | intraday_range_21d | 17 | 5353 | 2005-01-03..2026-04-14 | data/features/price/intraday_range_21d.parquet | 2026-04-14 |
| price | quality_voladj_mom_21d | 17 | 5353 | 2005-01-03..2026-04-14 | data/features/price/quality_voladj_mom_21d.parquet | 2026-04-14 |
| price | quality_voladj_mom_42d | 17 | 5353 | 2005-01-03..2026-04-14 | data/features/price/quality_voladj_mom_42d.parquet | 2026-04-14 |
| price | quality_voladj_mom_63d | 17 | 5353 | 2005-01-03..2026-04-14 | data/features/price/quality_voladj_mom_63d.parquet | 2026-04-14 |
| price | quality_voladj_mom_126d | 17 | 5353 | 2005-01-03..2026-04-14 | data/features/price/quality_voladj_mom_126d.parquet | 2026-04-14 |
| price | quality_mom_accel | 17 | 5353 | 2005-01-03..2026-04-14 | data/features/price/quality_mom_accel.parquet | 2026-04-14 |
| price | quality_52w_high_ratio | 17 | 5353 | 2005-01-03..2026-04-14 | data/features/price/quality_52w_high_ratio.parquet | 2026-04-14 |
| price | quality_dist_sma200 | 17 | 5353 | 2005-01-03..2026-04-14 | data/features/price/quality_dist_sma200.parquet | 2026-04-14 |
| price | quality_dist_sma50 | 17 | 5353 | 2005-01-03..2026-04-14 | data/features/price/quality_dist_sma50.parquet | 2026-04-14 |
| price | quality_golden_cross | 17 | 5353 | 2005-01-03..2026-04-14 | data/features/price/quality_golden_cross.parquet | 2026-04-14 |
| price | quality_drawdown_252d | 17 | 5353 | 2005-01-03..2026-04-14 | data/features/price/quality_drawdown_252d.parquet | 2026-04-14 |
| price | quality_rsi_14d | 17 | 5353 | 2005-01-03..2026-04-14 | data/features/price/quality_rsi_14d.parquet | 2026-04-14 |
| price | quality_rsi_28d | 17 | 5353 | 2005-01-03..2026-04-14 | data/features/price/quality_rsi_28d.parquet | 2026-04-14 |
| price | quality_bb_position | 17 | 5353 | 2005-01-03..2026-04-14 | data/features/price/quality_bb_position.parquet | 2026-04-14 |
| price | cross_sectional_mom_rank_21d | 8 | 5353 | 2005-01-03..2026-04-14 | data/features/price/cross_sectional_mom_rank_21d.parquet | 2026-04-14 |
| price | cross_sectional_mom_rank_42d | 8 | 5353 | 2005-01-03..2026-04-14 | data/features/price/cross_sectional_mom_rank_42d.parquet | 2026-04-14 |
| price | cross_sectional_mom_rank_63d | 8 | 5353 | 2005-01-03..2026-04-14 | data/features/price/cross_sectional_mom_rank_63d.parquet | 2026-04-14 |
| price | cross_sectional_mom_rank_126d | 8 | 5353 | 2005-01-03..2026-04-14 | data/features/price/cross_sectional_mom_rank_126d.parquet | 2026-04-14 |
| price | cross_sectional_relative_mom_63d | 8 | 5353 | 2005-01-03..2026-04-14 | data/features/price/cross_sectional_relative_mom_63d.parquet | 2026-04-14 |
| price | cross_sectional_mom_zscore_63d | 8 | 5353 | 2005-01-03..2026-04-14 | data/features/price/cross_sectional_mom_zscore_63d.parquet | 2026-04-14 |
| price | cross_sectional_rank_stability_21d | 1 | 5353 | 2005-01-03..2026-04-14 | data/features/price/cross_sectional_rank_stability_21d.parquet | 2026-04-14 |
| price | cross_sectional_top_margin_63d | 1 | 5353 | 2005-01-03..2026-04-14 | data/features/price/cross_sectional_top_margin_63d.parquet | 2026-04-14 |
| price | cross_sectional_dispersion_63d | 1 | 5353 | 2005-01-03..2026-04-14 | data/features/price/cross_sectional_dispersion_63d.parquet | 2026-04-14 |
| price | volume_trend_21_63 | 9 | 5353 | 2005-01-03..2026-04-14 | data/features/price/volume_trend_21_63.parquet | 2026-04-14 |
| price | volume_relative_21d | 9 | 5353 | 2005-01-03..2026-04-14 | data/features/price/volume_relative_21d.parquet | 2026-04-14 |
| price | volume_obv_slope_21d | 9 | 5353 | 2005-01-03..2026-04-14 | data/features/price/volume_obv_slope_21d.parquet | 2026-04-14 |
| price | relative_strength_63d | 8 | 5353 | 2005-01-03..2026-04-14 | data/features/price/relative_strength_63d.parquet | 2026-04-14 |
| price | relative_strength_126d | 8 | 5353 | 2005-01-03..2026-04-14 | data/features/price/relative_strength_126d.parquet | 2026-04-14 |
| price | relative_strength_trend_accel | 8 | 5353 | 2005-01-03..2026-04-14 | data/features/price/relative_strength_trend_accel.parquet | 2026-04-14 |
