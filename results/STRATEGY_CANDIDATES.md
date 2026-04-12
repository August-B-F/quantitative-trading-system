# STRATEGY CANDIDATES — full ranking

All strategies tested across Tier 1, Tier 2, Tier 1B (5.2B), and the regime-integration session. Sourced from `results/experiments/*.json`. Sorted by Sharpe descending.

Target: CAGR > 18%, Sharpe > 1.15, MaxDD better than −20%.

| Rank | Strategy | CAGR | Sharpe | MaxDD | n | Hits target | Description |
|---|---|---|---|---|---|---|---|
| 1 | E-R1 | 21.2% | 1.34 | -21.0% | 189 |  | T2_balanced structure w/ regime-conditional lookback (63d stable, 21d transition) |
| 2 | T2_3legCAGR_softML | 16.9% | 1.24 | -16.7% | 189 |  | T2_3legCAGR base + soft ML EV gate (HistGB regressor on macro features, weight = clip((pred-p10_val)/(p50_val-p10_val),  |
| 3 | E-R2 | 19.5% | 1.23 | -20.2% | 189 |  | T2_balanced w/ regime-tilted top-3 weights (1.5x favored / 0.75x other) |
| 4 | T2_3leg_gated | 18.5% | 1.22 | -19.4% | 189 | yes | Equal blend of [top1+SMA gate] + top3 + rank_avg(63,126,42)_top3 |
| 5 | T2_balanced | 19.3% | 1.22 | -21.0% | 189 |  | 0.5*[top1+SMA200-4% gate] + 0.5*top3 |
| 6 | E-R3 | 15.6% | 1.21 | -16.7% | 189 |  | T2_3legCAGR_softML w/ 0.5x EV weight on recessionary transitions |
| 7 | T2_top3_63d | 17.8% | 1.20 | -21.1% | 189 |  | Top-3 equal-weight by 63d momentum across 8 ETFs |
| 8 | T2_balanced_60_40 | 19.5% | 1.20 | -21.3% | 189 |  | 0.6*[top1+SMA200-4% gate] + 0.4*top3 |
| 9 | E-R6 | 20.8% | 1.20 | -22.2% | 189 |  | Kitchen sink final layer = L4_universe_tilt |
| 10 | T2_3leg | 18.2% | 1.17 | -19.4% | 189 | yes | (top1_63 + top3_63 + rank_avg(63,126,42)_top3) / 3 |
| 11 | T2_3legCAGR | 19.9% | 1.15 | -22.7% | 189 |  | Equal blend of top1_63 + top3_63 + rank_avg(63,126)_top1 |
| 12 | T2_balanced_softML | 14.0% | 1.14 | -14.1% | 189 |  | T2_balanced base + soft ML EV gate |
| 13 | T2_3leg_softML | 13.3% | 1.13 | -15.1% | 189 |  | T2_3leg base + soft ML EV gate |
| 14 | E-R5 | 15.3% | 1.04 | -20.1% | 189 |  | Dispersion×Regime: hi+stable→momentum; hi+trans→0.7*mom+0.3*SHY; lo+stable→QQQ; lo+trans→SHY |
| 15 | B3_top1_63d | 19.4% | 1.00 | -22.3% | 189 |  | Baseline: top-1 by 63d momentum across 8 ETFs (matches B3) |
| 16 | E-R4 | 11.3% | 0.86 | -22.8% | 189 |  | Regime-filtered universe (HG/LI, HG/HI, LG/LI, LG/HI eligible sets incl. TLT/XLV), top-3 by 63d mom within set, SMA200 g |

## Top 5 by Sharpe

- **E-R1** — CAGR 21.2%, Sharpe 1.34, MaxDD -21.0%
- **T2_3legCAGR_softML** — CAGR 16.9%, Sharpe 1.24, MaxDD -16.7%
- **E-R2** — CAGR 19.5%, Sharpe 1.23, MaxDD -20.2%
- **T2_3leg_gated** — CAGR 18.5%, Sharpe 1.22, MaxDD -19.4%
- **T2_balanced** — CAGR 19.3%, Sharpe 1.22, MaxDD -21.0%

## Top 5 by CAGR

- **E-R1** — CAGR 21.2%, Sharpe 1.34, MaxDD -21.0%
- **E-R6** — CAGR 20.8%, Sharpe 1.20, MaxDD -22.2%
- **T2_3legCAGR** — CAGR 19.9%, Sharpe 1.15, MaxDD -22.7%
- **E-R2** — CAGR 19.5%, Sharpe 1.23, MaxDD -20.2%
- **T2_balanced_60_40** — CAGR 19.5%, Sharpe 1.20, MaxDD -21.3%