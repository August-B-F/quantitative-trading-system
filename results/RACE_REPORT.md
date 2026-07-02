# RACE REPORT — paper-trading relaunch race (EVALUATION.md)

Generated 2026-07-02 19:14 by `scripts/run_race_report.py` (offline, logs only).
Data: 6 snapshot rows, 2026-04-14..2026-07-02.

## Data era

**PRE-RELAUNCH / VOIDED ERA.** No `--race-start` was supplied, so every
number below comes from the voided 2026 H1 record
(`docs/POSTMORTEM_2026H1.md`) and the pre-relaunch account lineup in
`configs/accounts.yaml`. This is plumbing verification output — it is
NOT race evidence and must not be quoted as performance.

## Per-arm equity vs SPY

SPY benchmark equity: 107,885.29 (+7.89% vs initial 100,000).

| Arm | Slot | Equity | Return | vs SPY (pp) |
|---|---|---|---|---|
| OPTIMIZED | 1 | 92,852.41 | -7.15% | -15.0 |
| ROBUST_STACK | 2 | 92,719.67 | -7.28% | -15.2 |
| DROPOVERLAP | 3 | 92,745.71 | -7.25% | -15.1 |
| T2_BALANCED | 4 | 96,836.55 | -3.16% | -11.0 |
| TREND_SIMPLE | 5 | 105,773.91 | +5.77% | -2.1 |
| DUAL_MOMENTUM | 6 | 126,350.84 | +26.35% | +18.5 |
| ROBUST_VAR | 7 | 90,980.63 | -9.02% | -16.9 |
| P59_FULL_STACK | 8 | 92,238.53 | -7.76% | -15.6 |
| P57_FRONTLOADED | 9 | 92,278.18 | -7.72% | -15.6 |

## Implementation fidelity

**PLACEHOLDER — not yet implemented.** TODO: for each arm, re-run the
daily-ledger engine (`src/backtest/ledger.py::run_ledger_backtest`) on the
`target_weights` recorded in `logs/rebalance_log.json` (the signals the live
system claims it traded) and compare the simulated month return with the
realized account return from `logs/monthly_comparison.csv`. Alert when the
divergence exceeds 50 bps/month (EVALUATION.md §3); >2 unexplained failing
months voids the arm's record (§4). Requires the relaunch accounts to map
1:1 to race arms in `configs/accounts.yaml`.

## Drawdown vs tripwires

Tripwires per EVALUATION.md §3: -20% de-risk 50% / -25% halt the arm. High-water mark seeded at initial capital 100,000.

| Arm | Slot | Max DD | Current DD | Tripwire |
|---|---|---|---|---|
| OPTIMIZED | 1 | -7.15% | -7.15% | OK |
| ROBUST_STACK | 2 | -7.28% | -7.28% | OK |
| DROPOVERLAP | 3 | -7.25% | -7.25% | OK |
| T2_BALANCED | 4 | -4.77% | -4.77% | OK |
| TREND_SIMPLE | 5 | -0.26% | -0.26% | OK |
| DUAL_MOMENTUM | 6 | -8.23% | -8.23% | OK |
| ROBUST_VAR | 7 | -9.02% | -9.02% | OK |
| P59_FULL_STACK | 8 | -7.76% | -7.76% | OK |
| P57_FRONTLOADED | 9 | -7.72% | -7.72% | OK |

Tripwire action required: none.

## Execution errors

Total execution errors in `logs/rebalance_log.json`: **45** (target 0 per EVALUATION.md §3). Entries with data warnings: 3.

| Strategy | Errors | Submit errors | Total |
|---|---|---|---|
| strategy_1_optimized | 5 | 1 | 6 |
| strategy_2_robust_stack | 5 | 1 | 6 |
| strategy_3_dropoverlap | 5 | 1 | 6 |
| strategy_4_t2_balanced | 5 | 2 | 7 |
| strategy_5_trend_simple | 4 | 1 | 5 |
| strategy_6_dual_momentum | 2 | 0 | 2 |
| strategy_7_robust_var | 4 | 0 | 4 |
| strategy_8_p59_full_stack | 3 | 1 | 4 |
| strategy_9_p57_frontloaded | 4 | 1 | 5 |

Any error must be fixed before the next rebalance (§3).

## Race clock

Months elapsed: 4 / 12. Months remaining: 8. (Pre-relaunch data — the race clock has NOT started.)

## Power-corrected verdict language (Study 13)

The EVALUATION.md §4 rule — promote on a >= 0.20 Sharpe edge over
both controls after 12 months — is **not statistically decisive** at this
window (block-bootstrap of the actual arm returns, `research/droplets/study13_race_power/`):

- 12-month Sharpe-edge sampling SD: 0.81 vs GEM, 0.57 vs SPY/SMA200 — several times the 0.20 bar itself.
- False-positive rate of the rule (true edge 0): 34% vs GEM, 35% vs SPY/SMA200; worst-case 20% for the promote-over-BOTH rule.
- False-negative rate (true edge exactly 0.20): 57% vs GEM, 50% vs SPY/SMA200 — a coin flip by construction.
- Window for 80% power against a true 0.20 edge: > 240 months for every statistic tested, including the paired daily-difference test.

**Verdict rule this report applies (per Study 13):** the month-12 decision is
judged on (1) implementation fidelity (<= 50 bps/month divergence), (2) drawdown
discipline (tripwire section above), and (3) process compliance (execution
errors, signal freshness). The 12-month Sharpe ordering is a TIEBREAK only and
is quoted with its bootstrap SD; no promotion claim may rest on a 12-month
Sharpe edge. The candidate's long-window statistical case is the SPA test on
the full common history (p = 0.059 vs GEM, p = 0.008 vs SPY/SMA200 at 10 bps), which the
race verifies for implementability rather than re-litigates.
