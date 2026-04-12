# OPTIMIZED STRATEGY SPEC

Derived from incremental layering of best-of-block modifications that passed the haircut.

## Final spec

- Universe: `['SOXX', 'QQQ', 'XLK', 'VGT', 'IGV', 'XLE', 'GLD', 'SHY']`
- Lookback (stable regime): 63d
- Lookback (transition regime): 21d
- Sizing: 50% top-1 + 50% top-3 (inv_vol)
- Trend gate: SMA200 −4% on top-1 leg
- Regime classifier: HistGB on CORE features, 4-class growth/inflation, walk-forward
- Macro/exposure gate: none
- Rebalancing variant: monthly + M26 final (M26_post_3d): if rebalance falls within 2 trading days AFTER FOMC decision, defer 3d

## Performance

- CAGR: **23.61%**
- Sharpe: **1.50**
- MaxDD: **-12.94%**
- vs E-R1: ΔCAGR +1.24pp, ΔSharpe +0.06, ΔMaxDD +1.59pp  
- +M26 vs OPTIMIZED: dCAGR -0.23pp, dSharpe -0.04, dMaxDD +5.63pp
## M26 follow-up (final choice)

- Variant: **M26_post_3d**
- vs OPTIMIZED base: dCAGR +1.37pp, dMaxDD +6.49pp
- Ex-2018 DD improvement (3d sym): +0.00pp
- See [M26_FOLLOWUP.md](M26_FOLLOWUP.md)
