# Already tested in main project — do NOT repeat

From `results/OPTIMIZATION_REPORT.md`, `results/STRATEGY_CANDIDATES.md`, `results/M26_*`, etc. Populated on first session start.

## Confirmed NON-NEGOTIABLES (cliff-tested; don't re-sweep)
- `lookback_stable=63` (dropping to 42d collapses Sharpe 1.50→1.13)
- `rebalance_day=month_end` (mid/start/random all drop Sharpe to ~1.17)
- `inflation_features__cpi_yoy` in CORE feature set (removal widens MaxDD -12.94→-18.68)

## Already-tested modules (M01–M27, E-series)
- M11: top-3 inverse-volatility weighting (ADOPTED, +1.2pp CAGR)
- M14-M18: universe modifications (all hurt risk-adj return — treat as negative prior but still worth fresh creative tests)
- M26: FOMC deferral variants. post-3d is optimal vs pre-only (22.69/1.38/-15.28) and symmetric (23.41/1.43/-12.94)
- E-R1: regime-conditional 63/21 lookback switch (ADOPTED, +1.9pp CAGR)
- 10 rule-based lookback-trigger alternatives (VIX>25 best at Sharpe 1.39 — all lost to classifier)
- 16+ ML-based ETF-selection variants (all failed walk-forward)

## Implication
- Fine-grain sweeps of lookback_stable, rebalance day, and CORE feature set are dead ends.
- Universe-edit experiments have a strong negative prior but new structural ideas (factor/international adds) still worth one-shot tests.
- Lookback-trigger rules have been exhausted for rule-based variants — only classifier-side innovations can help.
- FOMC window/defer days minor sweeps already done at M26 level.
