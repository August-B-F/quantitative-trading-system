# P59 Layer Inventory

Canonical baseline: 23.61 CAGR / 1.50 Sharpe / -12.94 MaxDD
Full P59 stack:     30.73 CAGR / 1.88 Sharpe / -12.66 MaxDD

## The 10 layers (ordered structural → feedback)

**Structural layers (canonical deltas, no state feedback):**

| # | Layer | Change |
|---|---|---|
| L1 | Universe drop-overlap | Drop VGT and XLK from canonical 8-ETF universe → 6 ETF stable universe [SOXX, QQQ, IGV, XLE, GLD, SHY] |
| L2 | Split 62/38 | Shift top1/top3 weights from canonical 50/50 to 62/38 |
| L3 | Classifier proba gate 0.40 | Only honor a regime-switch prediction (→21d) if argmax proba ≥ 0.40; else fall back to stable regime |
| L4 | Rank aggregation signal | Replace pure 63d momentum with weighted rank aggregation across 42d, 63d, 126d with weights (1, 3, 1) |
| L5 | Regime-conditional trans universe | When classifier proba ≥ 0.50 and predicted ≠ current, expand to transition universe [..., TLT, AGG, XLV, XLF] |
| L6 | Classifier credit/yc/copper extras | CORE-50 feature set + 7 extras (hyg_minus_tlt, hy_ig_spread, hy_ig_z252, yc_slope, yc_slope_chg63, real_rate_10y, copper_gold_ratio) |
| L7 | Tightened FOMC window | Change FOMC deferral window from canonical (pre=0, post=2, defer=3) to (pre=0, post=1, defer=4) |

**State-feedback layers (Kelly-style):**

| # | Layer | Change |
|---|---|---|
| L8 | DD-mode trigger | When trail3m return < -2%, force top1 weight = 0.40 (aggressive defense) |
| L9 | FULL boost trigger | When trail9m > +30% OR SPY 63d return > +12%, set top1 weight = 0.82 |
| L10 | WARM boost trigger | When trail6m > +25% OR SPY 21d return > +10%, set top1 weight = 0.70 |

## Toggle semantics (what "removing" each layer means)

- **L1 OFF**: use canonical 8-ETF universe [SOXX, QQQ, XLK, VGT, IGV, XLE, GLD, SHY].
- **L2 OFF**: use 50/50 top1/top3 split.
- **L3 OFF**: use raw argmax predictions (no proba gate); regime switch fires whenever argmax disagrees with current regime.
- **L4 OFF**: use pure `bundle.returns[63]` 63-day momentum (canonical).
- **L5 OFF**: use the stable universe in both regimes (no expansion).
- **L6 OFF**: use pred_proba.pkl (CORE-50 classifier) instead of pred_proba_p46.pkl.
- **L7 OFF**: use canonical FOMC window (pre=0, post=2, defer=3).
- **L8 OFF**: DD trigger does not fire (skip the DD check).
- **L9 OFF**: FULL boost does not fire.
- **L10 OFF**: WARM boost does not fire.

When all L8, L9, L10 are off, sizing reverts to the static top1 weight (controlled by L2).

## Protocol references P59 as "full stack target"

P59 monthly returns (computed during purge) are the baseline for the 6-test evaluation. Everything is compared against P59 and canonical simultaneously.
