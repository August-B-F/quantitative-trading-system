# PROJECT SUMMARY

End-of-research snapshot for the production strategy build. This file
is the single landing page for the project — read this first, then
drill into the detailed reports it references.

---

## 1. Starting Point

Baseline (Phase 3.1, [BASELINE_REPORT.md](BASELINE_REPORT.md)):

- **Strategy**: 63-day momentum, top-N over 8 ETFs
- **CAGR**: 19.4%
- **Sharpe**: 1.00
- **MaxDD**: -22.3%

This was the bar to beat. Anything proposed had to clear it after a
realistic transaction-cost haircut on the same walk-forward splits.

---

## 2. Final Result

Strategy `E-R1 + M11 + M26_post_3d` ([FINAL_STRATEGY_VALIDATED.md](FINAL_STRATEGY_VALIDATED.md),
[OPTIMIZED_STRATEGY.md](OPTIMIZED_STRATEGY.md)):

- **CAGR**: 23.61%
- **Sharpe**: 1.50
- **MaxDD**: -12.94%

Net of the +4.21pp CAGR / +0.50 Sharpe / +9.36pp MaxDD improvement
over baseline. Results JSON: [experiments/OPTIMIZED.json](experiments/OPTIMIZED.json).

---

## 3. What Improved It

Three additive components, each individually validated and stress
tested. See [REGIME_INTEGRATION_REPORT.md](REGIME_INTEGRATION_REPORT.md)
and [OPTIMIZATION_REPORT.md](OPTIMIZATION_REPORT.md) for the unit-by-unit
attribution.

| Component | ΔCAGR | ΔSharpe | ΔMaxDD |
|---|---|---|---|
| Regime-conditional lookback switch (E-R1) | +1.9pp | +0.34 | — |
| Inverse-vol top-3 weighting (M11) | +1.2pp | +0.06 | -1.6pp |
| FOMC post-3d deferral (M26_post_3d) | +1.4pp | — | -6.5pp |

The components are nearly orthogonal — the regime switch trades
lookback length, M11 trades position sizing, and M26 trades execution
timing around a known calendar event.

---

## 4. What We Tried That Didn't Work

Most things. The signal of this project is what we *stopped* doing.

- **ML ETF rotation** — 16+ experiments across Tier 1 and 5.2B Blocks A–D.
  Every model that tried to predict next-month ETF returns failed the
  haircut. See [TIER1_REPORT.md](TIER1_REPORT.md), [TIER1_VERDICT.md](TIER1_VERDICT.md),
  [TIER1B_REPORT.md](TIER1B_REPORT.md), [TIER1B_VERDICT.md](TIER1B_VERDICT.md).
- **Bigger models** — deeper HistGBs, MLPs, and ensembles all underperformed
  the simple momentum rule. Capacity hurt, not helped.
- **Universe changes** — adding/removing ETFs or sector tilts uniformly
  hurt risk-adjusted return. The 8-ETF universe is load-bearing.
- **Volatility targeting** — Sharpe-neutral, increased turnover.
- **ML drawdown classifiers** — could not catch real drawdowns out-of-sample
  (they fired on calm vol regimes, not the actual crashes).
- **Rules-based modifications** — 26 of 27 candidates in the M-series failed
  the haircut. M11 was the lone survivor before M26 was added.

Documented in [STRATEGY_CANDIDATES.md](STRATEGY_CANDIDATES.md), 
[M26_ANALYSIS.md](M26_ANALYSIS.md), [M26_FOLLOWUP.md](M26_FOLLOWUP.md),
[SIGNAL_ANALYSIS_REPORT.md](SIGNAL_ANALYSIS_REPORT.md).

---

## 5. Key Findings

Things that surprised us, in roughly the order we figured them out:

- **ML can't pick ETFs but CAN time lookback switches.** The classifier
  selecting between 63d and 189d momentum scored at the 99.8th percentile
  vs random switches. See [LOOKBACK_TRIGGER_REPORT.md](LOOKBACK_TRIGGER_REPORT.md).
- **The classifier is a switch timer, not a regime predictor.** Tried to
  use its output as a "regime label" — that interpretation overfit. Used
  as a switch, it generalizes.
- **Three features drive 72.8% of regime accuracy**: `cpi_yoy`, `pmi`,
  and `rail_traffic`. Adding more features barely moves the needle. See
  [FEATURE_IMPORTANCE_REPORT.md](FEATURE_IMPORTANCE_REPORT.md), 
  [experiments/REGIME_3FEAT.json](experiments/REGIME_3FEAT.json).
- **Edge is strongest in low/medium dispersion**, not crisis. The strategy
  is *not* a crash-alpha play — it's a calm-and-trending-market play that
  also avoids the worst of crashes via lookback switching.
- **Month-end rebalancing is structural**, not arbitrary. Mid-month and
  weekly variants consistently underperformed. See [STRESS_TEST_REPORT.md](STRESS_TEST_REPORT.md)
  test 5.

---

## 6. Known Risks

Read this section before sizing positions in production.

- **63d lookback is non-negotiable.** There is a sharp cliff at 42d — shorter
  windows collapse Sharpe. Don't tune this.
- **`cpi_yoy` is load-bearing.** Removing it from the regime feature set
  destroys drawdown containment. If the FRED CPI series ever changes
  definition or is delayed, the strategy degrades silently. Monitor this.
- **Calm-market drag.** Expect 13+ months of SPY underperformance during
  low-vol melt-ups. This is structural — the strategy gives up upside
  in exchange for downside containment.
- **Monte Carlo p05 MaxDD is -28.8%.** The headline -12.94% is the realized
  drawdown, not the worst plausible one. Size position for -28.8%, not -13%.
  See [STRESS_TEST_REPORT.md](STRESS_TEST_REPORT.md).
- **Classifier needs quarterly retraining.** Stale-model stress test
  confirms accuracy degrades after ~90 days.

---

## 7. Production Requirements

What the live system needs to function. See [data/DATA_CATALOG.md](../data/DATA_CATALOG.md)
and [data/DATA_HEALTH.md](../data/DATA_HEALTH.md) for source details.

- **Data feeds**:
  - Yahoo Finance (ETF prices, daily)
  - FRED (macro: CPI, PMI, rates, ~12 series)
  - ~17 alternative sources via fetchers in `src/data/fetchers/`
    (rail traffic, AAII, NAAIM, CFTC, FINRA, CBOE, etc.)
- **Rebalance**: monthly, last trading day, market-on-close.
- **FOMC calendar**: must be maintained — `M26_post_3d` defers entries
  in the 3 trading days after FOMC announcements.
- **Classifier retraining**: quarterly, walk-forward, on rolling window.
- **Transaction cost budget**: ≤20 bps per round-trip. Above this the
  edge starts to compress materially.

---

## 8. Sessions Run

Chronological log of research sessions that produced this project. Each
session has detailed notes in the corresponding report; this is the
table of contents.

- **3.1** — Baseline replication, 8-ETF momentum, [BASELINE_REPORT.md](BASELINE_REPORT.md)
- **3.2** — Splitter comparison and walk-forward design, [SPLITTER_COMPARISON.md](SPLITTER_COMPARISON.md)
- **3.3** — Phase-2 alternative data ingestion and health checks
- **3.4** — Feature engineering pass 1
- **3.5** — Feature engineering pass 2 (retry session for failed sources)
- **4.1** — Tier 1 ML rotation experiments E01-E05, [TIER1_REPORT.md](TIER1_REPORT.md), [TIER1_VERDICT.md](TIER1_VERDICT.md)
- **4.2** — Signal analysis, [SIGNAL_ANALYSIS_REPORT.md](SIGNAL_ANALYSIS_REPORT.md)
- **4.3** — Tier 2 hybrid strategies, [TIER2_REPORT.md](TIER2_REPORT.md), [TIER2_VERDICT.md](TIER2_VERDICT.md)
- **5.1** — Strategy candidate sweep M01-M27, [STRATEGY_CANDIDATES.md](STRATEGY_CANDIDATES.md)
- **5.2A** — Feature importance and 3-feature regime model, [FEATURE_IMPORTANCE_REPORT.md](FEATURE_IMPORTANCE_REPORT.md)
- **5.2B** — Tier 1B blocks A/B/C/D — bigger models, all failed, [TIER1B_REPORT.md](TIER1B_REPORT.md), [TIER1B_VERDICT.md](TIER1B_VERDICT.md)
- **5.3** — Lookback trigger validation, [LOOKBACK_TRIGGER_REPORT.md](LOOKBACK_TRIGGER_REPORT.md)
- **5.4** — Regime integration E-R1 through E-R6, [REGIME_INTEGRATION_REPORT.md](REGIME_INTEGRATION_REPORT.md)
- **6.1** — M26 FOMC analysis, [M26_ANALYSIS.md](M26_ANALYSIS.md), [M26_FOLLOWUP.md](M26_FOLLOWUP.md)
- **6.2** — Optimization block, [OPTIMIZATION_REPORT.md](OPTIMIZATION_REPORT.md), [OPTIMIZED_STRATEGY.md](OPTIMIZED_STRATEGY.md)
- **6.3** — Stress testing, [STRESS_TEST_REPORT.md](STRESS_TEST_REPORT.md), [FINAL_STRATEGY_VALIDATED.md](FINAL_STRATEGY_VALIDATED.md)
- **6.4** — Project cleanup (this session)

---

## File Map

- **Production code**: `src/`, `scripts/model/run_optimization_block.py`
- **Data pipeline**: `scripts/phase1_*`, `scripts/phase2_*`, `scripts/phase3_*`, `src/data/fetchers/`
- **Reference experiments**: `scripts/model/run_tier1.py`, `run_tier2.py`, `run_regime_integration.py`, `run_m26_*.py`
- **Stress tests**: `scripts/model/stress_*.py`
- **Configs**: `configs/feature_sets.yaml`
- **Final strategy artifact**: `results/experiments/OPTIMIZED.json`
- **Archived non-production**: `archive/scripts/`, `archive/experiments/`
