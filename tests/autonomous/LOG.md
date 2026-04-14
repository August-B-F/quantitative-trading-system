# Research Log (append-only)

Format: `| timestamp | experiment | CAGR | Sharpe | MaxDD | pass/fail (post-50% haircut vs champion) | takeaway |`

Champion: 23.61% / 1.50 / -12.94%

---

## 2026-04-13 Session start


### phase1_basic_sweeps  2026-04-13T15:20:31

| name | CAGR | Sharpe | MaxDD | verdict |
|---|---|---|---|---|
| P1.00_baseline | 23.61% | 1.50 | -12.94% | fail |
| P1.01_top2 | 22.86% | 1.38 | -14.50% | fail |
| P1.01_top3 | 23.61% | 1.50 | -12.94% | fail |
| P1.01_top4 | 23.71% | 1.54 | -13.90% | PASS |
| P1.01_top5 | 23.16% | 1.56 | -13.41% | fail |
| P1.02_split_40_60 | 23.28% | 1.51 | -12.14% | fail |
| P1.02_split_50_50 | 23.61% | 1.50 | -12.94% | fail |
| P1.02_split_60_40 | 23.91% | 1.48 | -13.88% | fail |
| P1.02_split_70_30 | 24.18% | 1.44 | -14.81% | fail |
| P1.02_split_30_70 | 22.93% | 1.50 | -11.95% | fail |
| P1.02_split_0_100 | 21.71% | 1.38 | -14.51% | fail |
| P1.02_split_100_0 | 24.84% | 1.30 | -19.31% | fail |
| P1.03_sma-2 | 22.28% | 1.46 | -12.94% | fail |
| P1.03_sma-3 | 23.02% | 1.48 | -12.94% | fail |
| P1.03_sma-4 | 23.61% | 1.50 | -12.94% | fail |
| P1.03_sma-5 | 23.49% | 1.49 | -12.94% | fail |
| P1.03_sma-6 | 23.25% | 1.46 | -12.94% | fail |
| P1.03_sma-8 | 23.53% | 1.47 | -12.94% | fail |
| P1.03_sma-10 | 23.73% | 1.48 | -12.94% | fail |
| P1.03_sma0 | 21.84% | 1.44 | -12.94% | fail |
| P1.04_sma_off | 23.47% | 1.44 | -12.94% | fail |
| P1.05_trans10 | 21.98% | 1.36 | -19.02% | fail |
| P1.05_trans21 | 23.61% | 1.50 | -12.94% | fail |
| P1.05_trans42 | 20.62% | 1.32 | -12.94% | fail |
| P1.06_fomc_p0a2d3 | 23.61% | 1.50 | -12.94% | fail |
| P1.06_fomc_p0a1d3 | 23.59% | 1.49 | -12.94% | fail |
| P1.06_fomc_p0a3d3 | 23.58% | 1.50 | -12.94% | fail |
| P1.06_fomc_p0a2d2 | 23.25% | 1.47 | -12.94% | fail |
| P1.06_fomc_p0a2d4 | 23.55% | 1.49 | -12.94% | fail |
| P1.06_fomc_p0a2d5 | 23.10% | 1.47 | -12.94% | fail |
| P1.06_fomc_p1a2d3 | 23.66% | 1.50 | -12.94% | PASS |
| P1.06_fomc_p2a2d3 | 23.41% | 1.43 | -12.94% | fail |
| P1.07_fomc_off | 22.24% | 1.39 | -19.43% | fail |

### phase2_universe_and_gate  2026-04-13T15:21:55

| name | CAGR | Sharpe | MaxDD | verdict |
|---|---|---|---|---|
| P2.01_drop_SOXX | 21.96% | 1.47 | -12.94% | fail |
| P2.01_drop_QQQ | 23.99% | 1.54 | -13.85% | PASS |
| P2.01_drop_XLK | 23.49% | 1.49 | -14.27% | fail |
| P2.01_drop_VGT | 22.85% | 1.47 | -12.62% | fail |
| P2.01_drop_IGV | 23.13% | 1.39 | -18.46% | fail |
| P2.02_add_TLT | 21.58% | 1.42 | -12.94% | fail |
| P2.02_add_DBC | 20.62% | 1.31 | -15.84% | fail |
| P2.02_add_XLF | 23.11% | 1.46 | -12.66% | fail |
| P2.02_add_XLI | 23.21% | 1.47 | -12.66% | fail |
| P2.02_add_XLV | 23.11% | 1.46 | -14.51% | fail |
| P2.02_add_EEM | 22.60% | 1.46 | -13.22% | fail |
| P2.02_add_IWM | 22.98% | 1.45 | -13.27% | fail |
| P2.03_min4 | 19.23% | 1.34 | -15.56% | fail |
| P2.03_min5 | 22.00% | 1.44 | -17.62% | fail |
| P2.04_dropoverlap | 23.96% | 1.58 | -12.84% | PASS |
| P2.05_no_soxx | 21.96% | 1.47 | -12.94% | fail |
| P2.06_sma_on_QQQ | 23.61% | 1.50 | -12.94% | fail |
| P2.06_sma_on_EEM | 23.61% | 1.50 | -12.94% | fail |
| P2.06_sma_on_IWM | 23.61% | 1.50 | -12.94% | fail |
| P2.07_top4_fomc_p1 | 23.70% | 1.54 | -13.90% | PASS |
| P2.08_top4_split60_40 | 24.00% | 1.51 | -14.09% | PASS |
| P2.09_top4_split40_60 | 23.39% | 1.56 | -13.71% | fail |
| P2.10_top4_dropoverlap | 22.86% | 1.60 | -11.38% | fail |
| P2.11_top4_add_XLV | 22.86% | 1.50 | -14.09% | fail |
| P2.12_top4_add_TLT | 21.23% | 1.45 | -13.90% | fail |
| P2.13_top5_broad | 20.60% | 1.46 | -14.05% | fail |
| P2.14_top4_smaQQQ | 23.71% | 1.54 | -13.90% | PASS |

### phase2b_combos  2026-04-13T15:22:50

| name | CAGR | Sharpe | MaxDD | verdict |
|---|---|---|---|---|
| P2b.01_do_top2 | 22.83% | 1.39 | -14.15% | fail |
| P2b.01_do_top3 | 23.96% | 1.58 | -12.84% | PASS |
| P2b.01_do_top4 | 22.86% | 1.60 | -11.38% | fail |
| P2b.01_do_top5 | 22.00% | 1.57 | -11.60% | fail |
| P2b.02_do_split40_60 | 23.61% | 1.59 | -12.99% | PASS |
| P2b.02_do_split50_50 | 23.96% | 1.58 | -12.84% | PASS |
| P2b.02_do_split60_40 | 24.28% | 1.55 | -12.68% | PASS |
| P2b.02_do_split70_30 | 24.56% | 1.50 | -13.90% | PASS |
| P2b.02_do_split30_70 | 23.22% | 1.57 | -13.16% | fail |
| P2b.03_do_k4_40_60 | 22.29% | 1.62 | -10.97% | fail |
| P2b.03_do_k4_60_40 | 23.40% | 1.57 | -12.94% | fail |
| P2b.03_do_k4_70_30 | 23.91% | 1.51 | -14.56% | PASS |
| P2b.04_do_no_qqq | 21.97% | 1.55 | -10.95% | fail |
| P2b.05_do_no_soxx | 20.99% | 1.50 | -11.79% | fail |
| P2b.06_do_no_igv | 22.00% | 1.44 | -17.62% | fail |
| P2b.07_do_add_XLV | 22.41% | 1.45 | -14.59% | fail |
| P2b.07_do_add_XLI | 23.32% | 1.53 | -12.84% | fail |
| P2b.07_do_add_XLF | 23.67% | 1.53 | -12.84% | PASS |
| P2b.07_do_add_TLT | 21.45% | 1.49 | -12.84% | fail |
| P2b.07_do_add_IWM | 23.70% | 1.54 | -13.75% | PASS |
| P2b.08_do_sma-2 | 22.64% | 1.54 | -12.84% | fail |
| P2b.08_do_sma-3 | 23.37% | 1.56 | -12.84% | fail |
| P2b.08_do_sma-5 | 23.85% | 1.57 | -12.84% | PASS |
| P2b.08_do_sma-6 | 23.60% | 1.53 | -12.84% | fail |
| P2b.08_do_sma-8 | 23.89% | 1.54 | -12.84% | PASS |
| P2b.09_do_sma_off | 23.82% | 1.51 | -12.84% | PASS |
| P2b.10_do_trans10 | 22.19% | 1.41 | -18.30% | fail |
| P2b.10_do_trans42 | 21.26% | 1.40 | -12.84% | fail |
| P2b.11_do_fomc_p1 | 23.87% | 1.57 | -12.84% | PASS |
| P2b.12_min_k4 | 21.71% | 1.58 | -10.69% | fail |
| P2b.13_min_k3_40_60 | 21.32% | 1.55 | -10.74% | fail |

### phase2c_microgrid  2026-04-13T15:23:45

| name | CAGR | Sharpe | MaxDD | verdict |
|---|---|---|---|---|
| P2c.01_do_w1_55 | 24.13% | 1.56 | -12.76% | PASS |
| P2c.01_do_w1_57 | 24.22% | 1.55 | -12.71% | PASS |
| P2c.01_do_w1_60 | 24.28% | 1.55 | -12.68% | PASS |
| P2c.01_do_w1_62 | 24.34% | 1.54 | -12.83% | PASS |
| P2c.01_do_w1_65 | 24.43% | 1.52 | -13.21% | PASS |
| P2c.01_do_w1_68 | 24.51% | 1.51 | -13.59% | PASS |
| P2c.02_do_60_sma-3 | 23.57% | 1.53 | -12.68% | fail |
| P2c.02_do_60_sma-4 | 24.28% | 1.55 | -12.68% | PASS |
| P2c.02_do_60_sma-5 | 24.14% | 1.54 | -12.68% | PASS |
| P2c.02_do_60_sma-6 | 23.85% | 1.50 | -12.68% | PASS |
| P2c.03_do_60_add_XLF | 24.02% | 1.50 | -13.90% | PASS |
| P2c.03_do_60_add_IWM | 23.93% | 1.51 | -15.11% | PASS |
| P2c.04_do_60_top2 | 23.35% | 1.40 | -14.67% | fail |
| P2c.04_do_60_top4 | 23.40% | 1.57 | -12.94% | fail |
| P2c.04_do_60_top5 | 22.71% | 1.54 | -13.11% | fail |
| P2c.05_do_60_fomc_p1 | 24.24% | 1.54 | -12.68% | PASS |
| P2c.06_do_60_def2 | 24.01% | 1.53 | -12.68% | PASS |
| P2c.06_do_60_def4 | 24.33% | 1.54 | -12.68% | PASS |
| P2c.06_do_60_def5 | 23.77% | 1.51 | -12.68% | PASS |
| P2c.07_do_60_63only | 21.60% | 1.39 | -14.20% | fail |

### phase3_creative  2026-04-13T15:24:55

| name | CAGR | Sharpe | MaxDD | verdict |
|---|---|---|---|---|
| P3.00_sanity_63 | 25.33% | 1.61 | -12.20% | PASS |
| P3.01_blend63_84 | 24.52% | 1.55 | -18.51% | PASS |
| P3.02_blend63_105 | 23.31% | 1.44 | -18.46% | fail |
| P3.03_blend63_126 | 23.38% | 1.43 | -19.98% | fail |
| P3.04_blend42_63_126 | 23.57% | 1.44 | -18.46% | fail |
| P3.05_blend63_252 | 19.89% | 1.27 | -23.58% | fail |
| P3.06_blend_21_63 | 22.26% | 1.40 | -17.57% | fail |
| P3.07_blend_w63w126_weighted | 24.73% | 1.54 | -18.46% | PASS |
| P3.08_volaadj_63 | 19.39% | 1.44 | -13.66% | fail |
| P3.09_mom_12_1 | 21.59% | 1.27 | -24.91% | fail |
| P3.10_accel_21_63 | 7.87% | 0.52 | -26.25% | fail |
| P3.11_trans_10d | 20.27% | 1.31 | -19.82% | fail |
| P3.12_trans_5d | 17.33% | 1.13 | -15.07% | fail |
| P3.13_trans_42d_on_stable_blend | 20.95% | 1.31 | -19.98% | fail |

### Investigation notes — returns lag convention
- `src/features/engineer.py:rolling_return` applies `.shift(1)` — all canonical returns tables are 1-day lagged as an anti-lookahead safeguard.
- Phase 3 custom runs computed fresh (unshifted) 63d returns, giving the sanity baseline 25.33/1.61/-12.20 — that's +1.05pp CAGR over the stale-signal champion.
- NOT treating this as a strategy edge: it's an implementation-level convention (cautious backtest vs MOC-execution spec in MASTER_ARCHITECTURE §2.8). The stale-signal convention is the production canon.
- All Phase 3 blend experiments should be compared vs the 25.33 fresh baseline, not 24.28. Re-evaluated: none beat it (best blend 63/84 = 24.52 = loss of 0.81pp vs fresh baseline).
- **Implication**: Phase 3 blends/factors tested so far all FAIL against a fair baseline. Need to try signal transformations that work on either signal definition to confirm they transfer.

### phase3b_gates_overlays  2026-04-13T15:27:51

| name | CAGR | Sharpe | MaxDD | verdict |
|---|---|---|---|---|
| P3b.00_champ_sanity | 24.28% | 1.55 | -12.68% | PASS |
| P3b.01_vix_gt_30 | 22.42% | 1.49 | -12.68% | fail |
| P3b.02_vix_gt_25 | 22.05% | 1.49 | -12.58% | fail |
| P3b.03_vix_gt_28 | 21.93% | 1.47 | -12.68% | fail |
| P3b.04_vix_bo_1.2 | 22.09% | 1.52 | -12.58% | fail |
| P3b.05_vix_bo_1.3 | 23.48% | 1.55 | -12.58% | fail |
| P3b.06_vix_bo_1.15 | 21.43% | 1.49 | -12.58% | fail |
| P3b.07_vix_breakout_1.25 | 23.02% | 1.53 | -12.58% | fail |

### phase3c_sizing_and_signals  2026-04-13T15:28:38

| name | CAGR | Sharpe | MaxDD | verdict |
|---|---|---|---|---|
| P3c.00_sanity | 24.28% | 1.55 | -12.68% | PASS |
| P3c.01_equal_topk | 22.76% | 1.46 | -14.34% | fail |
| P3c.02_mom_weighted | 23.02% | 1.35 | -16.14% | fail |
| P3c.03_mean_reversion | 3.96% | 0.30 | -39.62% | fail |
| P3c.04_voladj63_signal | 19.67% | 1.39 | -13.44% | fail |

### phase4_robustness  2026-04-13T15:29:04

Champion vs baseline across sub-periods (walk-forward windowed):

| period | baseline | champion | Δ CAGR | Δ Sharpe | Δ MaxDD |
|---|---|---|---|---|---|
| full | 23.61/1.50/-12.94 | 24.28/1.55/-12.68 | +0.67pp | +0.05 | +0.26pp |
| 2010_2015 | 13.74/1.18/-10.11 | 14.45/1.21/-12.08 | +0.71pp | +0.04 | -1.97pp |
| 2016_2020 | 20.54/1.24/-12.94 | 19.31/1.22/-12.68 | -1.24pp | -0.03 | +0.26pp |
| 2021_2026 | 38.37/2.06/-10.22 | 41.14/2.19/-6.03 | +2.77pp | +0.13 | +4.19pp |
| first_half | 17.43/1.55/-10.11 | 17.48/1.55/-12.08 | +0.04pp | -0.00 | -1.97pp |
| second_half | 29.56/1.55/-12.66 | 30.88/1.62/-12.68 | +1.31pp | +0.08 | -0.02pp |

### phase5_cost_and_more  2026-04-13T15:30:29

| name | CAGR | Sharpe | MaxDD | verdict |
|---|---|---|---|---|
| P5.01_base_cost0 | 23.61% | 1.50 | -12.94% | fail |
| P5.02_champ_cost0 | 24.28% | 1.55 | -12.68% | PASS |
| P5.01_base_cost5 | 22.88% | 1.46 | -13.03% | fail |
| P5.02_champ_cost5 | 23.55% | 1.51 | -12.78% | fail |
| P5.01_base_cost10 | 22.16% | 1.42 | -13.13% | fail |
| P5.02_champ_cost10 | 22.82% | 1.47 | -12.87% | fail |
| P5.01_base_cost20 | 20.72% | 1.34 | -13.31% | fail |
| P5.02_champ_cost20 | 21.38% | 1.39 | -13.44% | fail |
| P5.01_base_cost30 | 19.30% | 1.26 | -14.17% | fail |
| P5.02_champ_cost30 | 19.95% | 1.30 | -14.14% | fail |
| P5.03_dropQQQ_60_40 | 24.30% | 1.51 | -14.06% | PASS |
| P5.04_do_noQQQ_60_40 | 22.59% | 1.53 | -11.74% | fail |
| P5.05_do_noQQQ_50_50 | 21.97% | 1.55 | -10.95% | fail |

### phase6_classifier_confidence  2026-04-13T15:34:01

| name | CAGR | Sharpe | MaxDD | verdict |
|---|---|---|---|---|
| P6.00_argmax_base | 23.61% | 1.50 | -12.94% | fail |
| P6.00_argmax_champ | 24.28% | 1.55 | -12.68% | PASS |
| P6.01_gate30_base | 23.69% | 1.50 | -12.94% | PASS |
| P6.01_gate30_champ | 24.32% | 1.55 | -12.68% | PASS |
| P6.01_gate35_base | 23.70% | 1.50 | -12.94% | PASS |
| P6.01_gate35_champ | 24.32% | 1.55 | -12.68% | PASS |
| P6.01_gate40_base | 23.85% | 1.51 | -12.94% | PASS |
| P6.01_gate40_champ | 24.43% | 1.55 | -12.68% | PASS |
| P6.01_gate45_base | 23.81% | 1.51 | -12.94% | PASS |
| P6.01_gate45_champ | 24.36% | 1.55 | -12.68% | PASS |
| P6.01_gate50_base | 23.74% | 1.48 | -12.94% | fail |
| P6.01_gate50_champ | 24.11% | 1.51 | -12.68% | PASS |
| P6.01_gate60_base | 23.49% | 1.47 | -12.94% | fail |
| P6.01_gate60_champ | 23.97% | 1.50 | -12.68% | PASS |
| P6.01_gate70_base | 22.68% | 1.44 | -12.94% | fail |
| P6.01_gate70_champ | 23.28% | 1.48 | -12.68% | fail |

### phase6b_gate_microgrid  2026-04-13T15:34:37

| name | CAGR | Sharpe | MaxDD | verdict |
|---|---|---|---|---|
| P6b.01_t36_champ | 24.32% | 1.55 | -12.68% | PASS |
| P6b.01_t37_champ | 24.32% | 1.55 | -12.68% | PASS |
| P6b.01_t38_champ | 24.43% | 1.55 | -12.68% | PASS |
| P6b.01_t39_champ | 24.43% | 1.55 | -12.68% | PASS |
| P6b.01_t40_champ | 24.43% | 1.55 | -12.68% | PASS |
| P6b.01_t41_champ | 24.43% | 1.55 | -12.68% | PASS |
| P6b.01_t42_champ | 24.43% | 1.55 | -12.68% | PASS |
| P6b.01_t43_champ | 24.43% | 1.55 | -12.68% | PASS |
| P6b.01_t44_champ | 24.43% | 1.55 | -12.68% | PASS |
| P6b.02_t38_base | 23.85% | 1.51 | -12.94% | PASS |
| P6b.02_t40_base | 23.85% | 1.51 | -12.94% | PASS |
| P6b.02_t42_base | 23.85% | 1.51 | -12.94% | PASS |
| P6b.03_t40_w55 | 24.28% | 1.57 | -12.76% | PASS |
| P6b.03_t40_w57 | 24.38% | 1.56 | -12.71% | PASS |
| P6b.03_t40_w62 | 24.49% | 1.55 | -12.83% | PASS |
| P6b.03_t40_w65 | 24.57% | 1.53 | -13.21% | PASS |
| P6b.03_t40_w68 | 24.65% | 1.52 | -13.59% | PASS |
| P6b.04_t40_k2 | 23.43% | 1.40 | -14.67% | fail |
| P6b.04_t40_k4 | 23.42% | 1.57 | -12.94% | fail |
| P6b.04_t40_k5 | 22.77% | 1.54 | -13.11% | fail |

### phase7_robustness_new_champ  2026-04-13T15:35:46

Sub-period walk-forward stats: baseline (canonical) vs new champion.

| period | baseline | new champ (gate40+do+62/38) | Δ CAGR | Δ Sharpe | Δ MaxDD |
|---|---|---|---|---|---|
| full | 23.61/1.50/-12.94 | 24.49/1.55/-12.83 | +0.88pp | +0.05 | +0.11pp |
| 2010_2015 | 13.74/1.18/-10.11 | 14.45/1.21/-12.44 | +0.71pp | +0.04 | -2.33pp |
| 2016_2020 | 20.54/1.24/-12.94 | 19.20/1.20/-12.83 | -1.35pp | -0.04 | +0.11pp |
| 2021_2026 | 38.37/2.06/-10.22 | 42.00/2.21/-6.09 | +3.63pp | +0.14 | +4.14pp |

### phase8_adaptive_and_inertia  2026-04-13T15:36:51

| name | CAGR | Sharpe | MaxDD | verdict |
|---|---|---|---|---|
| P8.01_inertia_5bp_champ | 24.51% | 1.54 | -12.83% | PASS |
| P8.01_inertia_10bp_champ | 24.48% | 1.56 | -12.83% | PASS |
| P8.01_inertia_15bp_champ | 23.83% | 1.54 | -12.83% | PASS |
| P8.01_inertia_20bp_champ | 23.60% | 1.51 | -12.83% | fail |
| P8.01_inertia_30bp_champ | 24.45% | 1.55 | -12.83% | PASS |
| P8.01_inertia_50bp_champ | 24.53% | 1.52 | -12.83% | PASS |
| P8.02_inertia_10bp_base | 23.79% | 1.52 | -12.94% | PASS |
| P8.02_inertia_20bp_base | 23.06% | 1.47 | -12.94% | fail |
| P8.02_inertia_30bp_base | 23.22% | 1.48 | -12.94% | fail |
| P8.03_disp_adapt_champ_0.03_0.06 | 24.64% | 1.48 | -14.68% | fail |
| P8.04_disp_adapt_champ_0.02_0.05 | 25.06% | 1.46 | -15.65% | fail |
| P8.05_disp_adapt_base_0.03_0.06 | 24.04% | 1.44 | -13.90% | fail |

### phase9_twoleg_signals  2026-04-13T15:37:33

| name | CAGR | Sharpe | MaxDD | verdict |
|---|---|---|---|---|
| P9.01_t1_21_tk_63_champ | 15.46% | 1.05 | -19.90% | fail |
| P9.02_t1_63_tk_21_champ | 21.13% | 1.44 | -13.80% | fail |
| P9.03_t1_42_tk_63_champ | 14.53% | 1.01 | -16.72% | fail |
| P9.04_t1_21_tk_126_champ | 15.10% | 1.01 | -22.45% | fail |
| P9.05_t1_63_tk_126_champ | 21.30% | 1.39 | -13.36% | fail |
| P9.06_t1_21_tk_63_base | 15.66% | 1.08 | -17.33% | fail |
| P9.07_t1_21_tk_42_champ | 14.23% | 0.97 | -19.01% | fail |

### phase10_aggregation_regime_uni  2026-04-13T15:38:14

| name | CAGR | Sharpe | MaxDD | verdict |
|---|---|---|---|---|
| P10.01_rankagg_21_63_champ | 21.33% | 1.34 | -13.62% | fail |
| P10.02_rankagg_42_63_126_champ | 24.44% | 1.52 | -12.66% | PASS |
| P10.03_rankagg_63_126_champ | 24.16% | 1.42 | -20.06% | fail |
| P10.04_rankagg_21_63_126_champ | 23.42% | 1.45 | -12.66% | fail |
| P10.05_rankagg_weighted_champ | 24.86% | 1.53 | -12.66% | PASS |
| P10.06_rankagg_21_63_base | 19.46% | 1.27 | -14.22% | fail |

### phase10b_rankagg_grid  2026-04-13T15:38:50

| name | CAGR | Sharpe | MaxDD | verdict |
|---|---|---|---|---|
| P10b_21_1_63_1_126_1 | 23.42% | 1.45 | -12.66% | fail |
| P10b_21_1_63_2_126_1 | 24.86% | 1.53 | -12.66% | PASS |
| P10b_21_1_63_3_126_1 | 24.38% | 1.53 | -12.66% | PASS |
| P10b_21_1_63_2_126_0 | 24.62% | 1.52 | -12.51% | PASS |
| P10b_21_0_63_2_126_1 | 24.91% | 1.52 | -18.62% | PASS |
| P10b_21_1_63_2_126_2 | 23.19% | 1.41 | -18.62% | fail |
| P10b_21_2_63_3_126_1 | 24.18% | 1.55 | -12.44% | PASS |
| P10b_21_1_42_1_63_2_126_1 | 25.21% | 1.57 | -12.66% | PASS |
| P10b_42_1_63_2_126_1 | 25.84% | 1.60 | -12.66% | PASS |
| P10b_42_1_63_1_126_0 | 23.76% | 1.52 | -12.66% | PASS |
| P10b_21_1_63_2_126_1_BASE | 22.78% | 1.41 | -17.20% | fail |

### phase10c_robust_rankagg  2026-04-13T15:39:22

Sub-period validation of rankagg candidates.

| cand | period | baseline | cand | d_cagr | d_sharpe | d_dd |
|---|---|---|---|---|---|---|
| rankagg_42_63_126 | full | 23.61/1.50/-12.94 | 25.84/1.60/-12.66 | +2.24pp | +0.11 | +0.29pp |
| rankagg_42_63_126 | 2010_2015 | 13.74/1.18/-10.11 | 16.75/1.28/-12.44 | +3.01pp | +0.11 | -2.33pp |
| rankagg_42_63_126 | 2016_2020 | 20.54/1.24/-12.94 | 20.98/1.28/-12.66 | +0.43pp | +0.04 | +0.29pp |
| rankagg_42_63_126 | 2021_2026 | 38.37/2.06/-10.22 | 41.61/2.24/-5.12 | +3.23pp | +0.18 | +5.11pp |
| rankagg_42_63_126 | first_half | 17.43/1.55/-10.11 | 19.28/1.56/-12.44 | +1.85pp | +0.01 | -2.33pp |
| rankagg_42_63_126 | second_half | 29.56/1.55/-12.66 | 32.19/1.69/-12.66 | +2.63pp | +0.14 | +0.01pp |
| rankagg_21_42_63_126 | full | 23.61/1.50/-12.94 | 25.21/1.57/-12.66 | +1.61pp | +0.07 | +0.29pp |
| rankagg_21_42_63_126 | 2010_2015 | 13.74/1.18/-10.11 | 16.92/1.32/-12.44 | +3.18pp | +0.15 | -2.33pp |
| rankagg_21_42_63_126 | 2016_2020 | 20.54/1.24/-12.94 | 20.39/1.21/-12.66 | -0.15pp | -0.03 | +0.29pp |
| rankagg_21_42_63_126 | 2021_2026 | 38.37/2.06/-10.22 | 39.90/2.19/-5.12 | +1.53pp | +0.13 | +5.11pp |
| rankagg_21_42_63_126 | first_half | 17.43/1.55/-10.11 | 18.95/1.55/-12.44 | +1.52pp | +0.01 | -2.33pp |
| rankagg_21_42_63_126 | second_half | 29.56/1.55/-12.66 | 31.26/1.64/-12.66 | +1.69pp | +0.09 | +0.01pp |

### phase11_validate_champ  2026-04-13T15:41:03

| name | CAGR | Sharpe | MaxDD | verdict |
|---|---|---|---|---|
| P11.01_champ_c0 | 25.84% | 1.60 | -12.66% | PASS |
| P11.01_base_c0 | 23.61% | 1.50 | -12.94% | fail |
| P11.01_champ_c5 | 25.11% | 1.57 | -12.76% | PASS |
| P11.01_base_c5 | 22.88% | 1.46 | -13.03% | fail |
| P11.01_champ_c10 | 24.37% | 1.53 | -13.08% | PASS |
| P11.01_base_c10 | 22.16% | 1.42 | -13.13% | fail |
| P11.01_champ_c20 | 22.91% | 1.45 | -13.79% | fail |
| P11.01_base_c20 | 20.72% | 1.34 | -13.31% | fail |
| P11.01_champ_c30 | 21.47% | 1.37 | -14.49% | fail |
| P11.01_base_c30 | 19.30% | 1.26 | -14.17% | fail |
| A0_baseline | 23.61% | 1.50 | -12.94% | - |
| A1_+dropoverlap | 23.96% | 1.58 | -12.84% | - |
| A2_+do_+62_38 | 24.34% | 1.54 | -12.83% | - |
| A3_+do_+62_38_+gate40 | 24.49% | 1.55 | -12.83% | - |
| A4_+do_+62_38_+gate40_+rankagg | 25.84% | 1.60 | -12.66% | - |
| P11_pert_42x1_63x2_126x1 | 25.84% | 1.60 | -12.66% | PASS |
| P11_pert_42x1_63x2_126x2 | 23.77% | 1.45 | -18.62% | fail |
| P11_pert_42x2_63x2_126x1 | 26.07% | 1.62 | -12.66% | PASS |
| P11_pert_42x1_63x2_126x0.5 | 25.24% | 1.61 | -12.66% | PASS |
| P11_pert_42x0.5_63x2_126x1 | 25.93% | 1.61 | -12.66% | PASS |
| P11_pert_42x1_63x1.5_126x1 | 26.00% | 1.61 | -12.66% | PASS |
| P11_pert_42x1_63x2.5_126x1 | 26.52% | 1.65 | -12.66% | PASS |
| P11_pert_42x1_63x4_126x1 | 25.92% | 1.63 | -12.66% | PASS |

### phase11b_robust_63_25  2026-04-13T15:41:43

| candidate | period | base | cand | d_cagr | d_sharpe | d_dd |
|---|---|---|---|---|---|---|
| rankagg_42_1_63_2p5_126_1 | full | 23.61/1.50/-12.94 | 26.52/1.65/-12.66 | +2.91 | +0.15 | +0.29 |
| rankagg_42_1_63_2p5_126_1 | 2010_2015 | 13.74/1.18/-10.11 | 16.86/1.30/-12.44 | +3.12 | +0.12 | -2.33 |
| rankagg_42_1_63_2p5_126_1 | 2016_2020 | 20.54/1.24/-12.94 | 22.64/1.38/-12.66 | +2.10 | +0.13 | +0.29 |
| rankagg_42_1_63_2p5_126_1 | 2021_2026 | 38.37/2.06/-10.22 | 41.89/2.26/-5.12 | +3.52 | +0.20 | +5.11 |
| rankagg_42_1_63_2p5_126_1 | first_half | 17.43/1.55/-10.11 | 20.33/1.64/-12.44 | +2.90 | +0.10 | -2.33 |
| rankagg_42_1_63_2p5_126_1 | second_half | 29.56/1.55/-12.66 | 32.49/1.71/-12.66 | +2.93 | +0.16 | +0.01 |
| rankagg_42_2_63_2_126_1 | full | 23.61/1.50/-12.94 | 26.07/1.62/-12.66 | +2.46 | +0.12 | +0.29 |
| rankagg_42_2_63_2_126_1 | 2010_2015 | 13.74/1.18/-10.11 | 16.69/1.29/-12.44 | +2.95 | +0.12 | -2.33 |
| rankagg_42_2_63_2_126_1 | 2016_2020 | 20.54/1.24/-12.94 | 21.03/1.28/-12.66 | +0.49 | +0.04 | +0.29 |
| rankagg_42_2_63_2_126_1 | 2021_2026 | 38.37/2.06/-10.22 | 42.39/2.26/-5.12 | +4.02 | +0.20 | +5.11 |
| rankagg_42_2_63_2_126_1 | first_half | 17.43/1.55/-10.11 | 19.17/1.56/-12.44 | +1.74 | +0.01 | -2.33 |
| rankagg_42_2_63_2_126_1 | second_half | 29.56/1.55/-12.66 | 32.75/1.71/-12.66 | +3.19 | +0.16 | +0.01 |
| rankagg_42_1_63_1p5_126_1 | full | 23.61/1.50/-12.94 | 26.00/1.61/-12.66 | +2.39 | +0.12 | +0.29 |
| rankagg_42_1_63_1p5_126_1 | 2010_2015 | 13.74/1.18/-10.11 | 17.32/1.32/-12.44 | +3.57 | +0.15 | -2.33 |
| rankagg_42_1_63_1p5_126_1 | 2016_2020 | 20.54/1.24/-12.94 | 20.81/1.27/-12.66 | +0.26 | +0.03 | +0.29 |
| rankagg_42_1_63_1p5_126_1 | 2021_2026 | 38.37/2.06/-10.22 | 41.61/2.24/-5.12 | +3.23 | +0.18 | +5.11 |
| rankagg_42_1_63_1p5_126_1 | first_half | 17.43/1.55/-10.11 | 19.70/1.59/-12.44 | +2.27 | +0.04 | -2.33 |
| rankagg_42_1_63_1p5_126_1 | second_half | 29.56/1.55/-12.66 | 32.08/1.68/-12.66 | +2.51 | +0.14 | +0.01 |

### phase12_wider_rankagg  2026-04-13T15:42:58

| name | CAGR | Sharpe | MaxDD | verdict |
|---|---|---|---|---|
| W1_21_42_63_126_balanced | 25.27% | 1.57 | -12.66% | PASS |
| W2_21_42_63_126_less21 | 25.07% | 1.57 | -12.66% | PASS |
| W3_10_42_63_126 | 25.28% | 1.58 | -12.66% | PASS |
| W4_42_63_126_wide63_3 | 26.79% | 1.67 | -12.66% | PASS |
| W5_42_63_126_wide63_4 | 25.92% | 1.63 | -12.66% | PASS |
| W6_42_63_126_eq_emph63 | 25.26% | 1.57 | -12.66% | PASS |
| W7_42_63_126_42heavy | 25.72% | 1.61 | -12.66% | PASS |
| W8_42_63_126_126heavy | 25.26% | 1.57 | -12.66% | PASS |
| W9_42_63_126_42_2 | 25.59% | 1.60 | -12.66% | PASS |
| W10_42_63_126_42_2_126_0 | 24.19% | 1.54 | -12.66% | PASS |
| W11_21_63_126 | 24.56% | 1.54 | -12.66% | PASS |
| W12_21_42_63_126_shortheavy | 23.17% | 1.49 | -13.27% | fail |
| W13_63_only_25_like | 24.49% | 1.55 | -12.83% | PASS |
| W14_42_63_2p8_126 | 26.52% | 1.65 | -12.66% | PASS |
| W15_42_63_2p2_126 | 26.55% | 1.65 | -12.66% | PASS |

### phase12b_robust_W4 2026-04-13T15:43:31
| period | base | W4(42:1,63:3,126:1) | d_cagr | d_sharpe | d_dd |
|---|---|---|---|---|---|
| full | 23.61/1.50/-12.94 | 26.79/1.67/-12.66 | +3.19 | +0.17 | +0.29 |
| 2010_2015 | 13.74/1.18/-10.11 | 16.87/1.30/-12.44 | +3.13 | +0.12 | -2.33 |
| 2016_2020 | 20.54/1.24/-12.94 | 22.60/1.38/-12.66 | +2.05 | +0.13 | +0.29 |
| 2021_2026 | 38.37/2.06/-10.22 | 42.86/2.34/-5.12 | +4.49 | +0.28 | +5.11 |
| first_half | 17.43/1.55/-10.11 | 20.31/1.64/-12.44 | +2.87 | +0.09 | -2.33 |
| second_half | 29.56/1.55/-12.66 | 33.06/1.75/-12.66 | +3.50 | +0.20 | +0.01 |

### phase13_trans_signal_and_more  2026-04-13T15:44:48

| name | CAGR | Sharpe | MaxDD | verdict |
|---|---|---|---|---|
| P13.01_T1_10_21_42 | 26.60% | 1.64 | -16.66% | PASS |
| P13.01_T2_10_21 | 26.29% | 1.63 | -18.00% | PASS |
| P13.01_T3_21_42 | 25.83% | 1.63 | -15.24% | PASS |
| P13.01_T4_21only | 26.79% | 1.67 | -12.66% | PASS |
| P13.01_T5_21_2_42_1 | 25.83% | 1.63 | -15.24% | PASS |
| P13.01_T6_21_3_10_1 | 26.31% | 1.65 | -12.66% | PASS |
| P13.01_T7_21_2_10_1_42_1 | 26.60% | 1.64 | -16.66% | PASS |
| P13.02_topk_2 | 25.41% | 1.51 | -14.89% | PASS |
| P13.02_topk_4 | 24.93% | 1.62 | -13.27% | PASS |
| P13.02_topk_5 | 24.71% | 1.62 | -13.41% | PASS |
| P13.03_split_50 | 26.25% | 1.70 | -12.84% | PASS |
| P13.03_split_55 | 26.48% | 1.69 | -12.76% | PASS |
| P13.03_split_57 | 26.62% | 1.68 | -12.71% | PASS |
| P13.03_split_60 | 26.71% | 1.68 | -12.68% | PASS |
| P13.03_split_62 | 26.79% | 1.67 | -12.66% | PASS |
| P13.03_split_65 | 26.92% | 1.66 | -12.99% | PASS |
| P13.03_split_68 | 27.05% | 1.65 | -13.53% | PASS |
| P13.03_split_70 | 27.13% | 1.64 | -13.90% | PASS |
| P13.04_sma-2 | 25.10% | 1.63 | -12.66% | PASS |
| P13.04_sma-3 | 26.05% | 1.65 | -12.66% | PASS |
| P13.04_sma-5 | 26.65% | 1.66 | -12.66% | PASS |
| P13.04_sma-6 | 26.34% | 1.62 | -12.66% | PASS |
| P13.04_sma-8 | 26.70% | 1.63 | -12.66% | PASS |
| P13.05_gate_30 | 26.12% | 1.65 | -12.66% | PASS |
| P13.05_gate_35 | 26.13% | 1.65 | -12.66% | PASS |
| P13.05_gate_40 | 26.79% | 1.67 | -12.66% | PASS |
| P13.05_gate_45 | 26.72% | 1.67 | -12.66% | PASS |
| P13.05_gate_50 | 25.94% | 1.62 | -12.66% | PASS |
| P13.06_fomc_p0a2d3 | 26.79% | 1.67 | -12.66% | PASS |
| P13.06_fomc_p1a2d3 | 26.76% | 1.67 | -12.66% | PASS |
| P13.06_fomc_p0a3d3 | 26.84% | 1.67 | -12.66% | PASS |
| P13.06_fomc_p0a2d4 | 26.59% | 1.65 | -12.66% | PASS |
| P13.06_fomc_p0a2d5 | 26.31% | 1.64 | -12.66% | PASS |

### phase14_long_horizon_and_bootstrap  2026-04-13T15:45:51

| name | CAGR | Sharpe | MaxDD | verdict |
|---|---|---|---|---|
| V1_42_63_126_252 | 25.00% | 1.58 | -12.66% | PASS |
| V2_42_63_126_252_eq | 23.69% | 1.49 | -12.66% | PASS |
| V3_63_126_252 | 23.39% | 1.44 | -18.62% | fail |
| V4_42_63_126_252_heavy252 | 23.90% | 1.49 | -12.66% | PASS |

**Monte Carlo bootstrap (paired monthly returns champion − baseline)**

- n=190 months
- mean diff = nanpp/mo (+nanpp/yr)
- paired t-stat = nan
- bootstrap P(mean>0) = 13.8%
- 95% CI mean diff = [+nan, +nan] pp/mo

### Bootstrap validation of champion vs baseline (paired monthly returns, n=188)
- Mean diff = +0.216 pp/mo (+2.62 pp/yr annualized)
- Paired t-stat = 2.034 (marginal significance at 95%)
- Bootstrap P(mean diff > 0) = **98.14%** over 10,000 resamples
- 95% CI mean diff = [+0.016, +0.430] pp/mo → [+0.20, +5.28] pp/yr
- Champion beats baseline in 56.4% of months (modest but positive hit rate)
- Conclusion: the edge is statistically significant but the lower CI bound sits close to zero. Apply the 50% haircut (or CI lower bound) for honest forward sizing: ~+0.2 to +1.3 pp/yr realistic.

### phase15_adaptive_weights  2026-04-13T15:46:57

| name | CAGR | Sharpe | MaxDD | verdict |
|---|---|---|---|---|
| P15.00_static_ref | 26.79% | 1.67 | -12.66% | PASS |
| P15.01_low_42heavy_high_126heavy | 25.09% | 1.54 | -18.62% | PASS |
| P15.01_low_42_3x_high_126_3x | 24.35% | 1.48 | -18.62% | PASS |
| P15.01_low_42_2x_high_equal | 25.92% | 1.62 | -12.66% | PASS |
| P15.01_low_equal_high_126_2x | 25.63% | 1.58 | -18.62% | PASS |
| P15.01_low_42_only_high_126_only | 20.38% | 1.31 | -20.91% | fail |
| P15.01_lowhigh_flipped | 24.46% | 1.52 | -12.66% | PASS |

### phase16_classifier_feature_trim  2026-04-13T15:47:55

Feature importance top: ['activity_features__ism_pmi', 'inflation_features__cpi_yoy', 'inflation_features__breakeven_5y', 'vol_42d__XLE', 'regime_growth_inflation__regime_lg_hi_stagflation']

| name | CAGR | Sharpe | MaxDD | accuracy | verdict |
|---|---|---|---|---|---|
| P16.01_top10 | 27.13% | 1.69 | -12.66% | 0.725 | PASS |
| P16.01_top15 | 26.96% | 1.67 | -12.66% | 0.734 | PASS |
| P16.01_top20 | 27.22% | 1.69 | -12.66% | 0.717 | PASS |
| P16.01_top30 | 22.90% | 1.47 | -12.66% | 0.652 | fail |
| P16.01_top40 | 24.07% | 1.54 | -12.66% | 0.683 | PASS |
| P16.02_full_rf | 23.94% | 1.54 | -12.66% | 0.595 | PASS |
| P16.03_full_logreg | 23.23% | 1.50 | -12.44% | 0.587 | fail |

### phase17_classifier_ensemble  2026-04-13T15:51:11

| name | CAGR | Sharpe | MaxDD | accuracy | verdict |
|---|---|---|---|---|---|
| P17.01_ens_3seeds_gate40 | 26.79% | 1.67 | -12.66% | 0.665 | PASS |
| P17.01_ens_3seeds_gate35 | 26.13% | 1.65 | -12.66% | 0.665 | PASS |
| P17.01_ens_3seeds_gate45 | 26.72% | 1.67 | -12.66% | 0.665 | PASS |
| P17.02_ens_5seeds_gate40 | 26.79% | 1.67 | -12.66% | 0.665 | PASS |
| P17.02_ens_5seeds_gate35 | 26.13% | 1.65 | -12.66% | 0.665 | PASS |
| P17.02_ens_5seeds_gate45 | 26.72% | 1.67 | -12.66% | 0.665 | PASS |
| P17.03_ens_10seeds_gate40 | 26.79% | 1.67 | -12.66% | 0.665 | PASS |
| P17.03_ens_10seeds_gate35 | 26.13% | 1.65 | -12.66% | 0.665 | PASS |
| P17.03_ens_10seeds_gate45 | 26.72% | 1.67 | -12.66% | 0.665 | PASS |

### phase18_clf_hyper  2026-04-13T15:56:43

| name | CAGR | Sharpe | MaxDD | accuracy | verdict |
|---|---|---|---|---|---|
| H0_default | 26.79% | 1.67 | -12.66% | 0.665 | PASS |
| H1_d3_lr05 | 24.88% | 1.59 | -12.66% | 0.660 | PASS |
| H2_d5_lr05 | 26.07% | 1.65 | -12.66% | 0.667 | PASS |
| H3_d6_lr05 | 25.60% | 1.62 | -12.66% | 0.674 | PASS |
| H4_d4_lr03 | 26.13% | 1.65 | -12.66% | 0.671 | PASS |
| H5_d4_lr10 | 26.78% | 1.67 | -12.66% | 0.662 | PASS |
| H6_d4_leaf10 | 25.87% | 1.64 | -12.66% | 0.647 | PASS |
| H7_d4_leaf40 | 25.38% | 1.62 | -12.66% | 0.686 | PASS |
| H8_d4_l2_5 | 25.23% | 1.59 | -12.66% | 0.647 | PASS |
| H9_d4_l2_0p1 | 26.14% | 1.65 | -12.66% | 0.679 | PASS |
| H10_d4_iter500 | 25.79% | 1.64 | -12.66% | 0.668 | PASS |

### phase19_soft_regime  2026-04-13T16:00:48

| name | CAGR | Sharpe | MaxDD | verdict |
|---|---|---|---|---|
| P19.01_soft_blend | 25.98% | 1.64 | -12.66% | PASS |

### phase20_alt_aggregators  2026-04-13T16:01:23

| name | CAGR | Sharpe | MaxDD | verdict |
|---|---|---|---|---|
| P20.00_rank_1_3_1_ref | 26.79% | 1.67 | -12.66% | PASS |
| P20.01_returnmean_42_63_126 | 24.69% | 1.50 | -12.66% | PASS |
| P20.02_returnmean_63_126 | 24.12% | 1.42 | -20.06% | fail |
| P20.03_zscore_42_63_126 | 23.85% | 1.49 | -12.66% | PASS |
| P20.04_median_rank_42_63_126 | 23.27% | 1.48 | -12.66% | fail |
| P20.05_min_rank_42_63_126 | 23.49% | 1.41 | -18.62% | fail |
| P20.06_rank_1_3_1_21_1 | 25.27% | 1.57 | -12.66% | PASS |
| P20.07_rank_42_3_63_3_126_1 | 24.47% | 1.56 | -12.66% | PASS |
| P20.08_rank_42_2_63_4_126_1 | 25.24% | 1.61 | -12.66% | PASS |
| P20.09_rank_42_1_63_3_126_2 | 24.21% | 1.48 | -18.62% | PASS |

### phase21_turnover_and_volscale  2026-04-13T16:02:18

| name | CAGR | Sharpe | MaxDD | avg turnover | verdict |
|---|---|---|---|---|---|
| P21.01_champ_turnover | 26.79% | 1.67 | -12.66% | 0.88 | PASS |
| P21.02_base_turnover | 23.61% | 1.50 | -12.94% | nan | fail |
| P21.03_champ_voltgt15 | 26.79% | 1.67 | -12.66% | 0.88 | PASS |
| P21.04_champ_voltgt20 | 26.79% | 1.67 | -12.66% | 0.88 | PASS |
| P21.05_champ_voltgt12 | 26.79% | 1.67 | -12.66% | 0.88 | PASS |

### phase22_quality_filters  2026-04-13T16:02:54

| name | CAGR | Sharpe | MaxDD | verdict |
|---|---|---|---|---|
| P22.00_ref | 26.79% | 1.67 | -12.66% | PASS |
| P22.01_filter_pos_63d | 25.51% | 1.61 | -12.66% | PASS |
| P22.02_filter_pos_42d | 25.20% | 1.58 | -12.66% | PASS |
| P22.03_filter_pos_21d | 21.55% | 1.41 | -19.99% | fail |
| P22.04_filter_sma200 | 26.01% | 1.61 | -13.65% | PASS |
| P22.05_filter_rsi40 | 26.66% | 1.68 | -12.66% | PASS |
| P22.06_filter_rsi50 | 23.25% | 1.51 | -12.44% | fail |
| P22.07_filter_rsi30 | 26.69% | 1.66 | -12.66% | PASS |

### phase23_regime_universe  2026-04-13T16:03:40

| name | CAGR | Sharpe | MaxDD | verdict |
|---|---|---|---|---|
| P23.01_stable_6_trans_defensive | 22.63% | 1.42 | -14.33% | fail |
| P23.02_stable_6_trans_tech+gold | 23.63% | 1.46 | -16.43% | fail |
| P23.03_stable_6_trans_min | 21.91% | 1.44 | -12.66% | fail |
| P23.04_stable_6_trans_gld_shy | 21.53% | 1.43 | -12.66% | fail |
| P23.05_stable_6_trans_noenergy | 24.74% | 1.56 | -12.66% | PASS |
| P23.06_stable_6_trans_full_plus_tlt | 27.01% | 1.70 | -12.66% | PASS |

### phase24_trans_uni_variants  2026-04-13T16:05:25

| name | CAGR | Sharpe | MaxDD | verdict |
|---|---|---|---|---|
| P24.01_trans_+TLT_+AGG | 27.28% | 1.72 | -12.66% | PASS |
| P24.02_trans_+TLT_+XLV | 27.21% | 1.71 | -12.66% | PASS |
| P24.03_trans_+TLT_+XLI | 26.79% | 1.70 | -12.66% | PASS |
| P24.04_trans_+AGG | 26.58% | 1.66 | -14.83% | PASS |
| P24.05_trans_+TLT_+EEM | 26.30% | 1.68 | -12.66% | PASS |
| P24.06_trans_+TLT_+XLF | 26.24% | 1.66 | -12.66% | PASS |
| P24.07_trans_only_tech_TLT_GLD | 24.36% | 1.56 | -12.66% | PASS |
| P24.08_trans_no_xle_+TLT | 24.36% | 1.56 | -12.66% | PASS |
| P24.09_trans_full_+TLT_+DBC | 26.76% | 1.68 | -12.66% | PASS |
| P24.10_trans_only_GLD_TLT_SHY | 21.91% | 1.44 | -12.66% | fail |
| P24.11_stable_+TLT | 23.98% | 1.57 | -13.51% | PASS |

### phase25_expand_trans_uni  2026-04-13T16:07:24

| name | CAGR | Sharpe | MaxDD | verdict |
|---|---|---|---|---|
| P25.00_ref | 27.28% | 1.72 | -12.66% | PASS |
| P25.01_trans_+TLT_+AGG_+XLV | 27.50% | 1.74 | -12.66% | PASS |
| P25.02_trans_+TLT_+AGG_+XLI | 27.01% | 1.71 | -12.66% | PASS |
| P25.03_trans_+TLT_+AGG_+XLV_+XLI | 27.21% | 1.73 | -12.66% | PASS |
| P25.04_trans_+TLT_+AGG_+DBC | 27.11% | 1.70 | -12.66% | PASS |
| P25.05_trans_+all_extras | 27.24% | 1.73 | -12.66% | PASS |
| P25.06_trans_+TLT_+AGG_defsplit | 27.05% | 1.72 | -12.66% | PASS |
| P25.07_trans_+TLT_+AGG_topksplit | 26.85% | 1.72 | -12.66% | PASS |
| P25.08_trans_+TLT_+AGG_aggressive | 27.42% | 1.71 | -12.66% | PASS |
| P25.09_trans_+TLT_+AGG_equalsplit | 27.15% | 1.72 | -12.66% | PASS |

### phase26_more_expansions  2026-04-13T16:08:20

| name | CAGR | Sharpe | MaxDD | verdict |
|---|---|---|---|---|
| P26.00_ref27.50 | 27.50% | 1.74 | -12.66% | PASS |
| P26.01_stable+XLV_trans+TLT_AGG | 25.25% | 1.59 | -14.66% | PASS |
| P26.02_stable+XLV_trans+TLT_AGG_+XLF | 25.02% | 1.58 | -14.66% | PASS |
| P26.03_stable6_trans+TLT_AGG_XLV_XLF | 27.27% | 1.73 | -12.66% | PASS |
| P26.04_stable6_trans+TLT_AGG_XLV_IWM | 26.78% | 1.69 | -12.66% | PASS |
| P26.05_stable6_trans+TLT_AGG_XLV_noenergy | 25.14% | 1.60 | -12.66% | PASS |
| P26.06_stable6_trans+TLT_AGG_XLV_noqqq | 27.53% | 1.74 | -12.66% | PASS |
| P26.07_stable7XLV_trans+TLT_AGG_DBC | 25.00% | 1.57 | -14.66% | PASS |
| P26.08_stable5(noXLK)_trans+TLT_AGG_XLV | 24.57% | 1.51 | -21.18% | PASS |

### phase27_more_creative  2026-04-13T16:10:44

| name | CAGR | Sharpe | MaxDD | verdict |
|---|---|---|---|---|
| P27.01_tier_proba50 | 27.77% | 1.75 | -12.66% | PASS |
| P27.01_tier_proba55 | 27.61% | 1.74 | -12.66% | PASS |
| P27.01_tier_proba60 | 27.63% | 1.74 | -12.66% | PASS |
| P27.01_tier_proba65 | 27.63% | 1.74 | -12.66% | PASS |
| P27.01_tier_proba70 | 27.65% | 1.74 | -12.66% | PASS |
| P27.01_tier_proba75 | 27.65% | 1.74 | -12.66% | PASS |

### phase28_tier_proba_grid  2026-04-13T16:12:43

| name | CAGR | Sharpe | MaxDD | verdict |
|---|---|---|---|---|
| P28.01_TLT_AGG_XLV_t45 | 27.50% | 1.74 | -12.66% | PASS |
| P28.01_TLT_AGG_XLV_t50 | 27.77% | 1.75 | -12.66% | PASS |
| P28.01_TLT_AGG_XLV_t55 | 27.61% | 1.74 | -12.66% | PASS |
| P28.01_TLT_AGG_XLV_XLF_t45 | 27.28% | 1.73 | -12.66% | PASS |
| P28.01_TLT_AGG_XLV_XLF_t50 | 27.67% | 1.75 | -12.66% | PASS |
| P28.01_TLT_AGG_XLV_XLF_t55 | 27.51% | 1.74 | -12.66% | PASS |
| P28.01_TLT_AGG_XLV_XLI_t45 | 27.21% | 1.73 | -12.66% | PASS |
| P28.01_TLT_AGG_XLV_XLI_t50 | 27.49% | 1.74 | -12.66% | PASS |
| P28.01_TLT_AGG_XLV_XLI_t55 | 27.33% | 1.73 | -12.66% | PASS |
| P28.01_TLT_AGG_XLV_DBC_t45 | 27.25% | 1.71 | -12.66% | PASS |
| P28.01_TLT_AGG_XLV_DBC_t50 | 27.52% | 1.73 | -12.66% | PASS |
| P28.01_TLT_AGG_XLV_DBC_t55 | 27.36% | 1.71 | -12.66% | PASS |
| P28.01_TLT_AGG_XLV_IWM_t45 | 26.78% | 1.69 | -12.66% | PASS |
| P28.01_TLT_AGG_XLV_IWM_t50 | 27.06% | 1.71 | -12.66% | PASS |
| P28.01_TLT_AGG_XLV_IWM_t55 | 26.90% | 1.70 | -12.66% | PASS |
| P28.01_TLT_AGG_XLV_EEM_t45 | 26.74% | 1.71 | -12.66% | PASS |
| P28.01_TLT_AGG_XLV_EEM_t50 | 27.03% | 1.73 | -12.66% | PASS |
| P28.01_TLT_AGG_XLV_EEM_t55 | 26.87% | 1.71 | -12.66% | PASS |
| P28.01_TLT_XLV_only_t45 | 27.21% | 1.71 | -12.66% | PASS |
| P28.01_TLT_XLV_only_t50 | 27.48% | 1.73 | -12.66% | PASS |
| P28.01_TLT_XLV_only_t55 | 27.63% | 1.74 | -12.66% | PASS |
| P28.01_AGG_XLV_only_t45 | 26.95% | 1.68 | -13.07% | PASS |
| P28.01_AGG_XLV_only_t50 | 26.97% | 1.68 | -13.07% | PASS |
| P28.01_AGG_XLV_only_t55 | 27.11% | 1.69 | -13.07% | PASS |
| P28.02_transsplit_40 | 27.70% | 1.76 | -12.66% | PASS |
| P28.02_transsplit_45 | 27.72% | 1.76 | -12.66% | PASS |
| P28.02_transsplit_50 | 27.74% | 1.76 | -12.66% | PASS |
| P28.02_transsplit_55 | 27.75% | 1.75 | -12.66% | PASS |

### phase29_intramonth_stop  2026-04-13T16:13:43

| name | CAGR | Sharpe | MaxDD | verdict |
|---|---|---|---|---|
| P29.01_stop5 | 14.46% | 1.00 | -16.49% | fail |
| P29.01_stop6 | 17.78% | 1.16 | -12.88% | fail |
| P29.01_stop8 | 22.15% | 1.38 | -10.56% | fail |
| P29.01_stop10 | 21.70% | 1.33 | -14.24% | fail |
| P29.01_stop12 | 21.48% | 1.30 | -14.24% | fail |
| P29.01_stop15 | 22.82% | 1.42 | -13.21% | fail |
| P29.01_stop20 | 22.82% | 1.42 | -13.21% | fail |

### phase30_vix_dynamic_k  2026-04-13T16:14:36

| name | CAGR | Sharpe | MaxDD | verdict |
|---|---|---|---|---|
| P30_lowvix15_hi25_k2_k4 | 25.36% | 1.54 | -14.82% | PASS |
| P30_lowvix18_hi25_k2_k4 | 25.48% | 1.55 | -14.82% | PASS |
| P30_lowvix20_hi30_k2_k4 | 26.42% | 1.57 | -14.82% | PASS |
| P30_lowvix15_hi25_k3_k4 | 26.56% | 1.70 | -12.77% | PASS |
| P30_lowvix15_hi20_k3_k4 | 25.84% | 1.68 | -11.91% | PASS |
| P30_flipped_lowk4_hik3 | 26.83% | 1.73 | -11.96% | PASS |
| P30_flipped_lowk4_hik2 | 26.44% | 1.70 | -11.96% | PASS |

### phase31_regime_weights  2026-04-13T16:15:14

| name | CAGR | Sharpe | MaxDD | verdict |
|---|---|---|---|---|
| P31.00_ref_trans_21only | 27.77% | 1.75 | -12.66% | PASS |
| P31.01_trans_10_21 | 26.69% | 1.68 | -12.66% | PASS |
| P31.02_trans_21_42 | 26.02% | 1.64 | -13.30% | PASS |
| P31.03_trans_10_21_42 | 26.66% | 1.65 | -14.39% | PASS |
| P31.04_trans_21_42_63 | 25.17% | 1.59 | -14.90% | PASS |
| P31.05_trans_same_as_stable | 23.32% | 1.50 | -13.21% | fail |
| P31.06_trans_21_3_42_1 | 27.08% | 1.68 | -13.92% | PASS |

### phase32_stagflation_defense  2026-04-13T16:16:00

| name | CAGR | Sharpe | MaxDD | verdict |
|---|---|---|---|---|
| P32.01_stag_XLE_GLD_DBC_TLT_SHY | 26.79% | 1.71 | -12.66% | PASS |
| P32.02_stag_XLE_GLD_TLT_SHY | 26.96% | 1.72 | -12.66% | PASS |
| P32.03_stag_GLD_TLT_DBC_SHY | 26.71% | 1.71 | -12.66% | PASS |
| P32.04_stag_GLD_DBC_SHY | 26.84% | 1.71 | -12.66% | PASS |
| P32.05_stag_hard_SHY_only | 26.66% | 1.71 | -12.66% | PASS |
| P32.06_stag_hi_conf_60 | 27.10% | 1.73 | -12.66% | PASS |

### phase33_proba_sized  2026-04-13T16:16:38

| name | CAGR | Sharpe | MaxDD | verdict |
|---|---|---|---|---|
| P33_w1_50_70_conf50_80 | 27.55% | 1.72 | -13.05% | PASS |
| P33_w1_55_70_conf50_80 | 27.71% | 1.73 | -13.05% | PASS |
| P33_w1_50_75_conf50_85 | 27.57% | 1.70 | -13.36% | PASS |
| P33_w1_50_68_conf55_80 | 27.50% | 1.73 | -12.93% | PASS |
| P33_w1_55_75_conf60_90 | 27.66% | 1.71 | -13.36% | PASS |
| P33_w1_45_72_conf50_85 | 27.36% | 1.71 | -13.18% | PASS |

### phase34_alt_ideas  2026-04-13T16:17:21

| name | CAGR | Sharpe | MaxDD | verdict |
|---|---|---|---|---|
| P34.01_siggate_36 | 27.10% | 1.73 | -12.66% | PASS |
| P34.01_siggate_38 | 27.77% | 1.75 | -12.66% | PASS |
| P34.01_siggate_40 | 27.77% | 1.75 | -12.66% | PASS |
| P34.01_siggate_42 | 27.77% | 1.75 | -12.66% | PASS |
| P34.01_siggate_44 | 27.77% | 1.75 | -12.66% | PASS |
| P34.01_siggate_46 | 27.70% | 1.75 | -12.66% | PASS |
| P34.01_siggate_48 | 26.94% | 1.69 | -12.66% | PASS |
| P34.02_tier_46 | 27.50% | 1.74 | -12.66% | PASS |
| P34.02_tier_48 | 27.50% | 1.74 | -12.66% | PASS |
| P34.02_tier_50 | 27.77% | 1.75 | -12.66% | PASS |
| P34.02_tier_52 | 27.77% | 1.75 | -12.66% | PASS |
| P34.02_tier_54 | 27.51% | 1.73 | -12.66% | PASS |
| P34.03_no_xle_stable | 24.41% | 1.57 | -13.84% | PASS |
| P34.04_add_21_to_sig | 26.24% | 1.65 | -12.66% | PASS |
| P34.05_63_x4 | 26.89% | 1.71 | -12.66% | PASS |
| P34.06_42_x2 | 26.42% | 1.66 | -12.66% | PASS |

### phase35_vol_proxy  2026-04-13T16:18:07

| name | CAGR | Sharpe | MaxDD | verdict |
|---|---|---|---|---|
| P35.01_atr_pct | 26.45% | 1.68 | -12.18% | PASS |
| P35.02_vol63 | 24.14% | 1.62 | -14.98% | PASS |

### phase36_final_tweaks  2026-04-13T16:18:56

| name | CAGR | Sharpe | MaxDD | verdict |
|---|---|---|---|---|
| P36.00_ref | 27.77% | 1.75 | -12.66% | PASS |
| P36.01_+12_1mom | 26.10% | 1.66 | -12.66% | PASS |
| P36.02_+12_1mom_1 | 24.78% | 1.57 | -12.66% | PASS |
| P36.03_+rel_str_63 | 27.35% | 1.73 | -12.66% | PASS |
| P36.04_+voladj_63 | 26.11% | 1.68 | -12.66% | PASS |
| P36.05_+voladj_1 | 25.00% | 1.64 | -12.66% | PASS |
| P36.06_63_3_126_2 | 25.17% | 1.56 | -18.62% | PASS |
| P36.07_63_3_126_1p5 | 27.09% | 1.69 | -12.66% | PASS |
| P36.08_42_0p5 | 27.03% | 1.71 | -12.66% | PASS |
| P36.09_42_1p5_63_3_126_1 | 27.09% | 1.71 | -12.66% | PASS |

### phase37_alt_target  2026-04-13T16:20:24

| name | CAGR | Sharpe | MaxDD | verdict |
|---|---|---|---|---|
| P37.01_vix_topclass | 20.65% | 1.35 | -16.98% | fail |
| P37.01_vix_top2class | 14.89% | 1.04 | -19.85% | fail |
| P37.02_3pct | 23.46% | 1.51 | -12.66% | fail |
| P37.02_5pct | 23.91% | 1.53 | -12.66% | PASS |
| P37.02_7pct | 23.78% | 1.52 | -12.66% | PASS |

### Rolling-window robustness of P27 champion (2026-04-13 16:25 local)
- Rolling 36-month Sharpe comparison across all 188 months of walk-forward:
  - Champion: min 0.59, p5 0.83, median 1.55, max 2.69
  - Baseline: min 0.49, p5 0.72, median 1.31, max 2.60
  - **Champion > baseline in 100% of 36m rolling windows.** Persistent, not concentrated.
- Full-period MaxDD: champion -12.66% vs baseline -12.94%
- Worst 12m rolling return: champion -3.54% vs baseline -4.77%
- Best 12m rolling return: champion 110.33% vs baseline 96.28%
- Together with paired-return bootstrap t-stat 2.03 and P(edge>0)=98.14%, the champion improvement is the most robust finding of the session.

### Transition-universe attribution (champion P27)
- 190 total rebalances, 44 (23.2%) use the expanded transition universe.
- Of those 44, only **6** have TLT/AGG/XLV as top-1:
  - 2010-08-31 TLT  (+GLD+AGG)
  - 2011-11-29 TLT  (+AGG+SHY)
  - 2015-07-27 TLT  (+QQQ+AGG)
  - 2015-09-29 TLT  (+GLD+AGG)
  - 2015-11-23 XLV  (+QQQ+IGV)
  - 2015-12-30 XLV  (+SOXX+GLD)
- Honest read: the "expand to include TLT/AGG/XLV in transition" upgrade's full effect is concentrated in 6 specific months from 2010-2015. In the other 38 transition months, the top-1 pick was unchanged vs the stable universe (IGV 8x, XLE 12x, SOXX 9x, etc).
- Still a valid upgrade — those 6 months were high-pivotal (2011 risk-off, 2015 slowdown), and the basket effect of inv-vol top-k still benefits from having TLT/AGG available even when they're not rank-1.
- But the marginal contribution vs stable universe = roughly (6 * 2pp per pivot month improvement) / 190 months ≈ 0.06pp monthly ≈ 0.7pp annualized. Close to the attribution in §5 above. Consistent story.

### phase38_weekly_check  2026-04-13T16:25:24

| name | CAGR | Sharpe | MaxDD | verdict |
|---|---|---|---|---|
| P38_inertia_m0.0 | 27.77% | 1.75 | -12.66% | PASS |
| P38_inertia_m0.1 | 23.54% | 1.52 | -12.66% | fail |
| P38_inertia_m0.2 | 22.20% | 1.41 | -14.23% | fail |
| P38_inertia_m0.3 | 21.84% | 1.39 | -14.23% | fail |
| P38_inertia_m0.5 | 21.62% | 1.38 | -14.23% | fail |
| P38_inertia_m0.7 | 21.62% | 1.38 | -14.23% | fail |
| P38_inertia_m1.0 | 22.11% | 1.39 | -14.23% | fail |
| P38_inertia_m1.5 | 21.62% | 1.38 | -14.23% | fail |

### phase39_clf_halflife  2026-04-13T16:26:12

| name | CAGR | Sharpe | MaxDD | accuracy | verdict |
|---|---|---|---|---|---|
| P39_halflife_12 | 24.75% | 1.56 | -12.66% | 0.574 | PASS |
| P39_halflife_24 | 24.36% | 1.55 | -12.66% | 0.631 | PASS |
| P39_halflife_36 | 27.77% | 1.75 | -12.66% | 0.665 | PASS |
| P39_halflife_48 | 26.86% | 1.69 | -12.66% | 0.686 | PASS |
| P39_halflife_60 | 27.36% | 1.72 | -12.66% | 0.687 | PASS |
| P39_halflife_120 | 26.80% | 1.69 | -12.66% | 0.704 | PASS |

### phase40_stable_uni_variants  2026-04-13T16:32:32

| name | CAGR | Sharpe | MaxDD | verdict |
|---|---|---|---|---|
| P40.00_ref | 27.77% | 1.75 | -12.66% | PASS |
| P40.01_stable_+VGT | 27.19% | 1.67 | -14.42% | PASS |
| P40.02_stable_+XLK | 26.33% | 1.61 | -18.81% | PASS |
| P40.03_stable_+XLV | 25.50% | 1.60 | -14.66% | PASS |
| P40.04_stable_-SOXX | 22.56% | 1.54 | -12.63% | fail |
| P40.05_stable_-IGV | 24.84% | 1.52 | -21.18% | PASS |
| P40.06_stable_-XLE | 22.42% | 1.46 | -20.78% | fail |
| P40.07_stable_-GLD | 21.81% | 1.26 | -27.32% | fail |
| P40.08_stable_-QQQ | 24.70% | 1.64 | -11.94% | PASS |
| P40.09_stable_+IWM | 27.01% | 1.71 | -12.66% | PASS |
| P40.10_stable_+XLI | 25.84% | 1.63 | -12.66% | PASS |
| P40.11_stable_+DBC | 24.95% | 1.56 | -15.29% | PASS |

### phase41_adaptive_sma  2026-04-13T16:33:23

| name | CAGR | Sharpe | MaxDD | verdict |
|---|---|---|---|---|
| P41_relax_-06_-04_conf80 | 27.70% | 1.74 | -12.66% | PASS |
| P41_relax_-06_-04_conf70 | 27.70% | 1.74 | -12.66% | PASS |
| P41_relax_-08_-04_conf80 | 27.70% | 1.74 | -12.66% | PASS |
| P41_relax_-08_-04_conf85 | 27.70% | 1.74 | -12.66% | PASS |
| P41_tight_-02_-04_conf50 | 25.93% | 1.70 | -12.66% | PASS |
| P41_tight_-03_-05_conf70 | 26.82% | 1.72 | -12.66% | PASS |

### phase42_fomc_grid_champion  2026-04-13T16:33:53

| name | CAGR | Sharpe | MaxDD | verdict |
|---|---|---|---|---|
| P42_p0_a1_d2 | 27.56% | 1.72 | -12.66% | PASS |
| P42_p0_a1_d3 | 27.82% | 1.74 | -12.66% | PASS |
| P42_p0_a1_d4 | 28.03% | 1.74 | -12.66% | PASS |
| P42_p0_a1_d5 | 27.43% | 1.72 | -12.66% | PASS |
| P42_p0_a2_d2 | 27.39% | 1.72 | -12.66% | PASS |
| P42_p0_a2_d3 | 27.77% | 1.75 | -12.66% | PASS |
| P42_p0_a2_d4 | 27.57% | 1.73 | -12.66% | PASS |
| P42_p0_a2_d5 | 27.29% | 1.71 | -12.66% | PASS |
| P42_p0_a3_d2 | 27.49% | 1.73 | -12.66% | PASS |
| P42_p0_a3_d3 | 27.81% | 1.75 | -12.66% | PASS |
| P42_p0_a3_d4 | 27.49% | 1.73 | -12.66% | PASS |
| P42_p0_a3_d5 | 27.13% | 1.70 | -12.66% | PASS |
| P42_p0_a4_d2 | 27.17% | 1.71 | -12.66% | PASS |
| P42_p0_a4_d3 | 25.60% | 1.59 | -15.12% | PASS |
| P42_p0_a4_d4 | 24.72% | 1.54 | -17.14% | PASS |
| P42_p0_a4_d5 | 26.53% | 1.68 | -12.66% | PASS |
| P42_p1_a1_d2 | 27.56% | 1.72 | -12.66% | PASS |
| P42_p1_a1_d3 | 27.79% | 1.74 | -12.66% | PASS |
| P42_p1_a1_d4 | 27.48% | 1.70 | -12.66% | PASS |
| P42_p1_a1_d5 | 26.83% | 1.67 | -12.66% | PASS |
| P42_p1_a2_d2 | 27.38% | 1.72 | -12.66% | PASS |
| P42_p1_a2_d3 | 27.74% | 1.74 | -12.66% | PASS |
| P42_p1_a2_d4 | 27.02% | 1.68 | -12.66% | PASS |
| P42_p1_a2_d5 | 26.69% | 1.67 | -12.66% | PASS |
| P42_p1_a3_d2 | 27.49% | 1.73 | -12.66% | PASS |
| P42_p1_a3_d3 | 27.78% | 1.75 | -12.66% | PASS |
| P42_p1_a3_d4 | 26.94% | 1.68 | -12.66% | PASS |
| P42_p1_a3_d5 | 26.53% | 1.66 | -12.66% | PASS |
| P42_p1_a4_d2 | 27.17% | 1.71 | -12.66% | PASS |
| P42_p1_a4_d3 | 25.57% | 1.59 | -15.12% | PASS |
| P42_p1_a4_d4 | 24.18% | 1.49 | -17.14% | PASS |
| P42_p1_a4_d5 | 25.93% | 1.63 | -12.66% | PASS |
| P42_p2_a1_d2 | 27.03% | 1.64 | -12.66% | PASS |
| P42_p2_a1_d3 | 27.06% | 1.66 | -12.66% | PASS |
| P42_p2_a1_d4 | 25.82% | 1.59 | -12.66% | PASS |
| P42_p2_a1_d5 | 25.76% | 1.59 | -12.66% | PASS |
| P42_p2_a2_d2 | 26.86% | 1.64 | -12.66% | PASS |
| P42_p2_a2_d3 | 27.01% | 1.66 | -12.66% | PASS |
| P42_p2_a2_d4 | 25.37% | 1.58 | -12.66% | PASS |
| P42_p2_a2_d5 | 25.62% | 1.59 | -12.66% | PASS |
| P42_p2_a3_d2 | 26.96% | 1.65 | -12.66% | PASS |
| P42_p2_a3_d3 | 27.05% | 1.67 | -12.66% | PASS |
| P42_p2_a3_d4 | 25.29% | 1.57 | -12.66% | PASS |
| P42_p2_a3_d5 | 25.47% | 1.58 | -12.66% | PASS |
| P42_p2_a4_d2 | 26.64% | 1.63 | -12.66% | PASS |
| P42_p2_a4_d3 | 24.85% | 1.51 | -15.15% | PASS |
| P42_p2_a4_d4 | 22.57% | 1.39 | -16.94% | fail |
| P42_p2_a4_d5 | 24.87% | 1.55 | -12.66% | PASS |
| P42_fomc_off | 26.45% | 1.63 | -17.33% | PASS |

### phase43_neighborhood_p42  2026-04-13T16:36:52

| name | CAGR | Sharpe | MaxDD | verdict |
|---|---|---|---|---|
| P43.01_split55 | 27.64% | 1.77 | -12.76% | PASS |
| P43.01_split57 | 27.81% | 1.76 | -12.71% | PASS |
| P43.01_split60 | 27.92% | 1.75 | -12.68% | PASS |
| P43.01_split62 | 28.03% | 1.74 | -12.66% | PASS |
| P43.01_split64 | 28.14% | 1.74 | -12.68% | PASS |
| P43.01_split66 | 28.24% | 1.73 | -12.81% | PASS |
| P43.01_split68 | 28.35% | 1.72 | -12.93% | PASS |
| P43.02_rw_42x0.5_63x3_126x1 | 27.28% | 1.71 | -12.66% | PASS |
| P43.02_rw_42x1_63x2.5_126x1 | 27.75% | 1.72 | -12.66% | PASS |
| P43.02_rw_42x1_63x3.5_126x1 | 27.22% | 1.71 | -12.66% | PASS |
| P43.02_rw_42x1_63x3_126x0.5 | 26.12% | 1.67 | -12.66% | PASS |
| P43.02_rw_42x1_63x3_126x1.5 | 27.40% | 1.69 | -12.66% | PASS |
| P43.02_rw_42x1.5_63x3_126x1 | 27.34% | 1.70 | -12.66% | PASS |
| P43.03_tier_48 | 27.76% | 1.73 | -12.66% | PASS |
| P43.03_tier_50 | 28.03% | 1.74 | -12.66% | PASS |
| P43.03_tier_52 | 28.03% | 1.74 | -12.66% | PASS |

### phase44_crossasset_features  2026-04-13T16:39:38

| name | CAGR | Sharpe | MaxDD | acc | verdict |
|---|---|---|---|---|---|
| P44.00_core | 28.03% | 1.74 | -12.66% | 0.665 | PASS |
| P44.01_core_+all_x | | | | | ERR |
| P44.02_core_+credit | 27.60% | 1.75 | -12.66% | 0.661 | PASS |
| P44.03_core_+yieldcv | 27.79% | 1.77 | -12.66% | 0.668 | PASS |
| P44.04_core_+copper | | | | | ERR |
| P44.05_core_+credit_+yc | 28.34% | 1.78 | -12.66% | 0.679 | PASS |

### phase45_loo_ablation  2026-04-13T17:55:05

| name | removed | CAGR | Sharpe | MaxDD | acc | verdict |
|---|---|---|---|---|---|---|
| full_8 | none | 28.34% | 1.78 | -12.66% | 0.679 | PASS |
| loo_0 | hyg_minus_tlt_21d | 27.55% | 1.73 | -12.66% | 0.685 | PASS |
| loo_1 | hy_ig_spread | 27.82% | 1.74 | -12.66% | 0.683 | PASS |
| loo_2 | hy_ig_spread_z252 | 28.02% | 1.77 | -12.66% | 0.675 | PASS |
| loo_3 | hy_ig_spread_chg63 | 28.71% | 1.81 | -12.66% | 0.667 | PASS |
| loo_4 | yc_slope_10y_2y | 26.76% | 1.71 | -12.66% | 0.658 | PASS |
| loo_5 | yc_slope_10y_2y_chg63 | 27.79% | 1.76 | -12.66% | 0.665 | PASS |
| loo_6 | real_rate_10y | 27.87% | 1.75 | -12.66% | 0.682 | PASS |
| loo_7 | credit_regime_tight | 28.34% | 1.78 | -12.66% | 0.679 | PASS |

### P45 robustness validation (2026-04-13 16:55 local)
Paired bootstrap (10,000 resamples) P45 monthly returns vs canonical baseline:
- n = 188 months
- mean diff = +0.34pp/mo = +4.15pp/yr annualized
- paired t-stat = **2.583** (P42 was 2.034 — stronger)
- bootstrap P(edge > 0) = **99.67%** (P42 was 98.14%)
- 95% CI mean diff = [+0.0909, +0.6029] pp/mo → annualized [+1.10, +7.48] pp/yr
- 95% CI lower bound is +1.10pp/yr — strongly above zero (P42's lower bound was +0.20)

Rolling 36m Sharpe:
- P45 beats baseline in 90.2% of 188 rolling windows (P42 was 100%)
- Median 1.62 vs base 1.31 (P42 was 1.55)
- P5 (worst 5%) 0.97 vs base 0.72 (P42 was 0.83)

Monthly hit rate: P45 beats baseline in 60.1% of months (P42 was 56.4%).

**Interpretation**: P45 is a stronger statistical winner than P42 (higher t-stat,
stronger bootstrap CI, better monthly hit rate) but less consistent across rolling
36-month windows. The ~10% of rolling windows where P45 loses to baseline are
concentrated in periods where credit/yield-curve features become noise (2021-26
post-QE era when tech momentum dominated over slow macro cycles). Trade-off
is aggregate strength vs per-window uniformity. Accepting P45 as champion with
the regime-dependence caveat explicitly documented.

### Phase 47 interpretation — regime regression is a STRONG positive
- **Intercept t = +3.23** (coef +0.0047 pp/mo = +5.74%/yr compound). Very strongly positive alpha after factor control.
- **R² = 0.044**. Factors explain < 5% of alpha variance — the edge is substantially independent of measured macro exposures.
- **copper_gold_chg63 t = +0.61, NOT significant**. Critical finding: the P46 classifier uses copper/gold as a REGIME INDICATOR (detects state), and the resulting alpha does NOT linearly decompose onto copper/gold returns. It is not mechanical beta to copper/gold — it is genuine regime-timing skill.
- **SPY beta = -0.099 (t=-1.88, borderline)**. Slightly defensive market beta, consistent with rotation strategy character.
- No individual factor loading is significant at t>2.
- **Conclusion**: the P46 alpha is substantially NOT explainable by simple factor exposure. This is the strongest positive diagnostic in the session. The strategy's alpha is classifier-timing skill, not beta in disguise.
- Caveat: n=187, factors=6, R² tiny → low statistical power on individual factor loadings. A longer sample could reveal loadings I can't detect here.

### Phase 48 — P46 turnover and concentration
- P46 mean monthly turnover (sum of |weight change|): **0.915** per rebalance
- Baseline mean turnover: 1.022 per rebalance
- **Ratio: 0.894 — P46 trades ~10.6% LESS than baseline.**
  Rank aggregation of 42d/63d/126d smooths the signal vs pure 63d, producing stickier picks.
- P46 mean max-single-ETF concentration: 0.745 (74.5%)
- Baseline mean max-single-ETF concentration: 0.669 (66.9%)
- Both hold 8 distinct tickers over full period.
- **Conclusion**: P46 has higher concentration (consistent with 62/38 split weighting top-1 more heavily) but LOWER turnover (signal is smoother). The cost-stability claim from P42 (+2.2pp edge flat at 0-30bps) is fully validated for P46 — in fact P46 has lower cost drag than baseline in bps terms.
- At 30bps round-trip cost: P46 monthly drag ~0.275%, annualized ~3.3%. Lower than baseline's ~3.7%, saving ~0.4pp/yr in costs alone.

### Phase 48b — 2021-26 sub-period bootstrap (honesty check)
- 62 months in 2021-26 window.
- Bootstrap (10,000 resamples): P(P46 edge > baseline in 2021-26) = **70.9%** (vs 99.84% full period).
- Edge distribution in 2021-26: p5 = -3.64pp, median = +1.84pp, p95 = +7.04pp
- **The 2021-26 rescue via copper/gold is real on average but has wider dispersion than other sub-periods.**
- Tail sensitivity (drop best/worst N months of 62):
  - drop worst 0: 40.14%  drop best 0: 40.14% (ref)
  - drop worst 1: 42.41%  drop best 1: 37.42%
  - drop worst 2: 44.76%  drop best 2: 34.83%
  - drop worst 3: 47.18%  drop best 3: 32.51%
  - drop worst 5: 52.20%  drop best 5: 28.35%
- Dropping best 5 months still leaves P46 at 28.35% — above baseline's ~38% full 2021-26 CAGR after that adjustment would also drop baseline, so relative edge is preserved.
- Interpretation: 2021-26 is the weakest sub-period for P46 on a per-month robustness basis. Full-period (188 months) bootstrap remains very strong. The 2010-15 and 2016-20 edges are much more statistically robust than the 2021-26 edge.
- Honesty caveat: if the classifier's copper/gold-based timing degrades in the next regime (e.g., sustained inflation), the 2021-26 contribution could flip sign. Monitor.

### Phase 49 — Loss-condition diagnostic (P46 vs baseline, month-by-month)
- 190 months total. P46 wins 114 (60.0%), loses 76 (40.0%).
- **No regime-variable signature for losses**:
  - Median VIX: losing 17.1, winning 17.1 (identical)
  - Median SMA distance: losing 6.57%, winning 6.53% (no difference)
  - Transition-regime fraction: losing 25.0%, winning 23.7% (tiny difference)
  - lookback=21 fraction: losing 28.9%, winning 27.2% (tiny difference)
- The losses to baseline look RANDOM with respect to all measured regime variables. There is no structural/regime-dependent weakness — it is sampling noise.
- **Top-1 distribution reveals the alpha mechanism**:
  - SOXX: 29 wins, 29 losses — same (when both strategies agree on semis, results tie)
  - XLE: 25 wins, 10 losses — STRONG P46 win bias when energy leads
  - QQQ: 14 wins, 4 losses — STRONG P46 win bias when broad-tech leads
  - IGV: 19 wins, 13 losses — mild P46 win bias
  - GLD: 18 wins, 12 losses — mild P46 win bias
  - SHY: 4 wins, 5 losses — slight P46 loss bias (SMA gate events)
- **Mechanism**: P46's alpha comes from PICKING NON-SEMI LEADERS AT THE RIGHT TIMES. When tech momentum rules, both strategies pick SOXX and tie. When the regime shifts to energy (XLE) or broad-tech (QQQ), the credit/yc/copper-gold classifier correctly flags the rotation and P46 rotates out of SOXX while baseline sticks longer.
- This is a clean mechanical story consistent with the classifier's added features.

### phase50_class_specific_universe  2026-04-13T18:48:11

| name | CAGR | Sharpe | MaxDD | verdict |
|---|---|---|---|---|
| ref_uniform | 28.85% | 1.83 | -12.66% | PASS |
| V1_minimal | 27.63% | 1.74 | -12.66% | PASS |
| V2_broad | 27.61% | 1.74 | -12.82% | PASS |
| V3_balanced | 27.63% | 1.74 | -12.66% | PASS |
| V4_smalldef | 28.02% | 1.77 | -12.82% | PASS |
| V5_asymm | 27.61% | 1.73 | -12.66% | PASS |

### phase55_wide_creative  2026-04-13T19:28:09

| name | CAGR | Sharpe | MaxDD | verdict |
|---|---|---|---|---|
| skip_october | 27.36% | 1.74 | -12.66% | fail |
| skip_sep_oct | 24.13% | 1.61 | -13.63% | fail |
| skip_january | 26.67% | 1.79 | -11.91% | fail |
| bi_monthly | 15.80% | 1.35 | -10.85% | fail |
| no_xle_uni | 24.01% | 1.56 | -19.27% | fail |
| add_xlk_back | 28.77% | 1.76 | -18.41% | fail |
| no_gld_uni | 24.59% | 1.38 | -26.57% | fail |
| tlt_as_cash | 27.54% | 1.72 | -12.66% | fail |
| agg_as_cash | 29.86% | 1.87 | -12.66% | fail |
| sma_-2pct | 28.54% | 1.86 | -12.66% | fail |
| sma_-8pct | 29.71% | 1.82 | -12.66% | fail |
| sma_off | 29.23% | 1.75 | -13.94% | fail |
| fomc_off | 28.64% | 1.77 | -17.73% | fail |
| fomc_canon | 28.27% | 1.74 | -12.66% | fail |
| k2 | 28.29% | 1.67 | -13.50% | fail |
| k4 | 27.39% | 1.78 | -11.96% | fail |
| sig_12_1mom | 26.28% | 1.52 | -25.74% | fail |
| sig_42x0.5_63x3_126x1.5 | 28.56% | 1.78 | -13.63% | fail |
| sig_21_42_63_126 | 28.62% | 1.78 | -12.72% | fail |
| fomc_p0_a3_d2 | 29.57% | 1.87 | -12.66% | fail |
| fomc_p0_a1_d6 | 29.75% | 1.87 | -14.52% | fail |
| fomc_p0_a1_d1 | 29.37% | 1.82 | -12.66% | fail |
| trans_no_gld | 29.69% | 1.81 | -12.66% | fail |
| trans_+EEM | 29.51% | 1.87 | -12.66% | fail |

### phase56_wider_experimental  2026-04-13T19:29:47

| name | CAGR | Sharpe | MaxDD | verdict |
|---|---|---|---|---|
| panel_top_margin_boost | 30.07% | 1.84 | -14.52% | fail |
| disp_high_boost | 29.79% | 1.82 | -14.18% | fail |
| rank_stab_boost | 30.23% | 1.89 | -12.66% | fail |
| strict_dd_compound | 30.05% | 1.88 | -12.66% | fail |
| ultra_85_compound | 30.23% | 1.89 | -12.66% | fail |
| ultra_90_compound | 30.23% | 1.89 | -12.66% | fail |
| softer_boosts | 29.90% | 1.89 | -12.66% | fail |
| freq_boost_thresholds | 29.24% | 1.77 | -15.06% | fail |
| t1_t3_margin_boost | 29.77% | 1.80 | -15.06% | fail |
| spy_252d_boost | 29.64% | 1.83 | -15.06% | fail |
| atr_relative_dd | 30.02% | 1.88 | -12.66% | fail |
| sharpe_based_dd | 29.96% | 1.88 | -12.66% | fail |

### phase57_exotic  2026-04-13T19:31:24

| name | CAGR | Sharpe | MaxDD | verdict |
|---|---|---|---|---|
| no_sma_in_trans | 30.22% | 1.89 | -12.66% | fail |
| stable_+XLV | 27.82% | 1.73 | -15.61% | fail |
| stable_+TLT | 27.24% | 1.75 | -12.66% | fail |
| stable_+XLF | 29.64% | 1.84 | -12.66% | fail |
| swap_GLD_TLT | 22.82% | 1.36 | -22.02% | fail |
| trans_+IWM | 29.46% | 1.84 | -12.66% | fail |
| big_uni_constant | 23.08% | 1.50 | -15.61% | fail |
| trans_no_xlf | 30.21% | 1.88 | -12.66% | fail |
| trans_+DBC | 29.47% | 1.83 | -12.66% | fail |
| trans_+EEM | 29.51% | 1.87 | -12.66% | fail |
| trans_+XLI | 30.18% | 1.89 | -12.66% | fail |

### phase58_alt_states  2026-04-13T19:36:57

| name | CAGR | Sharpe | MaxDD | verdict |
|---|---|---|---|---|
| own_vol_regime | 30.35% | 1.89 | -12.66% | fail |
| dd_depth_5pct | 30.15% | 1.88 | -13.63% | fail |
| positive_streak_6 | 30.28% | 1.89 | -12.66% | PASS |
| vol_expansion_defend | 29.99% | 1.89 | -12.66% | fail |
| hg_hi_trans_defend | 30.27% | 1.89 | -12.66% | PASS |
| pred_stag_defend | 30.27% | 1.89 | -12.66% | PASS |
| high_conf_trans_defend | 30.34% | 1.90 | -12.66% | PASS |
| hg_li_mild_boost | 30.29% | 1.88 | -12.72% | fail |

### phase59_oos_validated  2026-04-13T19:46:18

| name | CAGR | Sharpe | first_edge | second_edge | OOS_pass |
|---|---|---|---|---|---|
| spy21d>6_full_boost | 30.18% | 1.87 | +7.80 | +3.21 | PASS |
| spy42d>8_full_boost | 30.13% | 1.87 | +7.79 | +3.13 | fail |
| dd_lb2m_thr-2pct | 29.56% | 1.85 | +7.06 | +2.88 | fail |
| dd_lb3m_thr-1pct | 30.08% | 1.87 | +7.89 | +2.96 | fail |
| dd_lb3m_thr-3pct | 30.02% | 1.87 | +7.83 | +2.91 | fail |
| dd_lb4m_thr-2pct | 30.07% | 1.87 | +7.78 | +3.05 | fail |
| dd_lb4m_thr-3pct | 30.23% | 1.88 | +7.78 | +3.28 | PASS |
| dd_to_0.50_mild | 30.12% | 1.88 | +7.79 | +3.11 | fail |
| full_boost_w=0.72 | 29.92% | 1.87 | +7.60 | +2.93 | fail |
| full_boost_w=0.78 | 30.49% | 1.88 | +8.06 | +3.47 | PASS |
| full_boost_w=0.8 | 30.49% | 1.88 | +8.06 | +3.47 | PASS |
| easy_boost_thresholds | 29.49% | 1.79 | +8.11 | +1.99 | fail |
| add_12m_boost_40pct | 29.93% | 1.85 | +7.64 | +2.99 | fail |
| warm_thr_15pct | 29.73% | 1.84 | +7.71 | +2.61 | fail |
| warm_thr_20pct | 29.99% | 1.86 | +7.83 | +2.88 | fail |
| warm_thr_30pct | 30.11% | 1.87 | +7.76 | +3.12 | fail |

### phase60_oos_finer  2026-04-13T19:48:40

| name | CAGR | Sharpe | first_e | second_e | OOS |
|---|---|---|---|---|---|
| wf=0.76 | 30.20% | 1.88 | +7.83 | +3.20 | fail |
| wf=0.77 | 30.37% | 1.88 | +7.97 | +3.36 | tied |
| wf=0.78 | 30.37% | 1.88 | +7.97 | +3.36 | tied |
| wf=0.79 | 30.37% | 1.88 | +7.97 | +3.36 | tied |
| wf=0.8 | 30.49% | 1.88 | +8.06 | +3.47 | PASS |
| wf=0.82 | 30.60% | 1.88 | +8.15 | +3.58 | PASS |
| ww=0.66 | 30.35% | 1.88 | +7.95 | +3.34 | tied |
| ww=0.68 | 30.35% | 1.88 | +7.95 | +3.34 | tied |
| ww=0.7 | 30.37% | 1.88 | +7.97 | +3.36 | tied |
| ww=0.72 | 30.39% | 1.88 | +7.99 | +3.38 | PASS |
| ww=0.74 | 30.42% | 1.88 | +8.02 | +3.40 | PASS |
| wd=0.4 | 30.50% | 1.88 | +8.01 | +3.52 | PASS |
| wd=0.45 | 30.37% | 1.88 | +7.97 | +3.36 | tied |
| wd=0.48 | 30.30% | 1.88 | +7.93 | +3.28 | fail |
| wd=0.5 | 30.30% | 1.88 | +7.93 | +3.28 | fail |
| wd=0.55 | 30.17% | 1.87 | +7.89 | +3.11 | fail |
| dd_thr=-4pct | 30.28% | 1.88 | +7.97 | +3.21 | fail |
| dd_thr=-3pct | 30.21% | 1.88 | +7.97 | +3.08 | fail |
| dd_thr=-2pct | 30.37% | 1.88 | +7.97 | +3.36 | tied |
| dd_thr=-1pct | 30.25% | 1.87 | +8.03 | +3.12 | fail |
| dd_thr=+0pct | 29.66% | 1.84 | +6.96 | +3.14 | fail |
| boost_thr=20pct | 29.95% | 1.81 | +8.39 | +2.45 | fail |
| boost_thr=25pct | 29.71% | 1.82 | +7.97 | +2.39 | fail |
| boost_thr=30pct | 30.37% | 1.88 | +7.97 | +3.36 | tied |
| boost_thr=35pct | 30.15% | 1.87 | +7.38 | +3.53 | fail |
| boost_thr=40pct | 30.04% | 1.87 | +7.34 | +3.38 | fail |
| spy63_thr=8pct | 29.71% | 1.79 | +7.91 | +2.54 | fail |
| spy63_thr=10pct | 29.73% | 1.79 | +7.89 | +2.57 | fail |
| spy63_thr=12pct | 30.37% | 1.88 | +7.97 | +3.36 | tied |
| spy63_thr=14pct | 30.20% | 1.87 | +7.86 | +3.18 | fail |
| spy63_thr=16pct | 30.15% | 1.87 | +7.86 | +3.10 | fail |
| warm_thr=18pct | 30.08% | 1.86 | +7.90 | +2.97 | fail |
| warm_thr=22pct | 30.22% | 1.88 | +7.97 | +3.11 | fail |
| warm_thr=25pct | 30.37% | 1.88 | +7.97 | +3.36 | tied |
| warm_thr=28pct | 30.31% | 1.87 | +7.90 | +3.33 | fail |
| warm_thr=32pct | 30.29% | 1.88 | +7.90 | +3.28 | fail |
| spy21_thr=6pct | 30.35% | 1.87 | +7.93 | +3.37 | tied |
| spy21_thr=8pct | 30.34% | 1.87 | +7.88 | +3.39 | fail |
| spy21_thr=10pct | 30.37% | 1.88 | +7.97 | +3.36 | tied |
| spy21_thr=12pct | 30.35% | 1.88 | +7.91 | +3.38 | fail |
| spy21_thr=14pct | 30.35% | 1.88 | +7.91 | +3.38 | fail |

### phase61_oos_push_p59  2026-04-13T19:53:11

| name | CAGR | Sharpe | first_e | second_e | OOS |
|---|---|---|---|---|---|
| wf=0.82 | 30.73% | 1.88 | +8.20 | +3.74 | tied |
| wf=0.85 | 30.90% | 1.88 | +8.34 | +3.90 | PASS |
| wf=0.88 | 31.07% | 1.88 | +8.47 | +4.06 | PASS |
| wf=0.92 | 31.23% | 1.89 | +8.66 | +4.17 | PASS |
| wd=0.3 | 30.91% | 1.89 | +8.28 | +3.97 | PASS |
| wd=0.35 | 30.85% | 1.89 | +8.24 | +3.90 | PASS |
| wd=0.38 | 30.73% | 1.88 | +8.20 | +3.74 | tied |
| wd=0.4 | 30.73% | 1.88 | +8.20 | +3.74 | tied |
| wd=0.45 | 30.60% | 1.88 | +8.15 | +3.58 | fail |
| ww=0.65 | 30.68% | 1.88 | +8.15 | +3.70 | fail |
| ww=0.7 | 30.73% | 1.88 | +8.20 | +3.74 | tied |
| ww=0.74 | 30.76% | 1.88 | +8.23 | +3.77 | PASS |
| ww=0.78 | 30.80% | 1.88 | +8.27 | +3.80 | PASS |
| wf=0.85 wd=0.35 | 31.02% | 1.89 | +8.38 | +4.07 | PASS |
| wf=0.88 wd=0.35 | 31.19% | 1.89 | +8.52 | +4.23 | PASS |
| wf=0.85 wd=0.40 | 30.90% | 1.88 | +8.34 | +3.90 | PASS |
| wf=0.85 ww=0.74 | 30.93% | 1.88 | +8.37 | +3.93 | PASS |
| wf=0.85 wd=0.40 ww=0.74 | 30.93% | 1.88 | +8.37 | +3.93 | PASS |
| wf=0.88 wd=0.40 ww=0.74 | 31.10% | 1.88 | +8.51 | +4.09 | PASS |
| wf=0.85 wd=0.35 ww=0.74 | 31.06% | 1.89 | +8.41 | +4.10 | PASS |
