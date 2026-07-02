# STUDY 10 — RESULTS (all three specs KILLED)

Run 2026-07-02 per the pre-registered `HYPOTHESIS.md` (written before any
run). Engine daily_ledger_v1; runner `run_study10.py`; raw grid
`results_raw.csv`; every evaluated row in `trials.csv`. Deploy bar
(pre-registered): net Sharpe > 0.4 in BOTH halves (2005-2015, 2016-2026)
at the spec's realistic cost. Deflated Sharpe context: cumulative ledger
741 + 3 new = 744 trials, V[SR]=0.090, E[max SR]=0.95 => DSR=0.0000 for
every number below; none is distinguishable from the best lucky draw.

## Spec 1 — Turn-of-month SPY @ 2 bps/side: **DEAD**

| window | gross CAGR | net CAGR | gross Sh | net Sh | net MaxDD | expo |
|---|---|---|---|---|---|---|
| full | 4.72% | 3.72% | 0.529 | 0.429 | -28.8% | 28.5% |
| 2005-2015 | 3.19% | 2.21% | 0.364 | **0.268** | -28.8% | 28.5% |
| 2016-2026 | 6.48% | 5.46% | 0.733 | 0.627 | -13.9% | 28.5% |

Per-episode gross edge: n=257, +33.4 bps, t=2.21, hit 60.7%. The flow
effect exists but is too small: first half fails the 0.4 bar badly
(0.268). Cost drag ~96 bps/yr at 2 bps/side; at 10/20 bps the spec is
under water outright. Kill per pre-registered bar.

## Spec 2 — Overnight QQQ (close->open, every night): **DEAD** at the
pre-registered primary cost (2 bps/side); lead recorded at 1 bps/side

| cost/side | window | CAGR | Sharpe | MaxDD |
|---|---|---|---|---|
| 0 (gross) | full | 11.61% | 0.944 | -27.4% |
| 0 (gross) | 2005-2015 / 2016-2026 | 10.76% / 12.52% | 0.961 / 0.936 | |
| 1 bps | full | 6.14% | 0.540 | -30.8% |
| 1 bps | 2005-2015 / 2016-2026 | 5.32% / 7.00% | 0.515 / 0.567 | |
| **2 bps** | full | 0.93% | **0.137** | -35.3% |
| **2 bps** | 2005-2015 / 2016-2026 | 0.15% / 1.76% | **0.070 / 0.197** | |

Per-night gross edge: n=5404, +4.67 bps, t=4.36, hit 56.6% — the
strongest statistical effect in this repo's ledger, and cost realism
kills it exactly as feared. Note (arithmetic correction, verdict
unaffected): 2 bps/side = 4 bps/round-trip ~ 1,000 bps/yr of drag, not
the ~500 bps/yr parenthetical in the hypothesis; ~500 bps/yr
corresponds to 1 bps/side, at which the spec passes both halves
(0.515/0.567). Per the pre-registered clause, passing only at 1 bps/side
= DEAD as speced, recorded as a LEAD: a future spec would need measured
MOC/MOO auction slippage on one paper account to justify the 1 bps
assumption, plus the operational reality of 2 orders/day and 100%
short-term-gains tax treatment.

## Spec 3 — Pre-FOMC SPY @ 2 bps/side: **DEAD**

Scheduled meetings only (4 pre-registered emergency-meeting exclusions).

| window | gross CAGR | net CAGR | gross Sh | net Sh | net MaxDD | expo |
|---|---|---|---|---|---|---|
| full | 3.63% | 2.97% | 0.756 | 0.626 | -11.8% | 6.3% |
| 2005-2015 | 5.19% | 4.52% | 0.936 | 0.821 | -11.8% | 6.4% |
| 2016-2026 | 2.03% | 1.38% | 0.520 | **0.362** | -10.9% | 6.3% |

Per-episode gross edge: n=171, +30.3 bps, t=2.21, hit 56.1%. Second
half misses the bar (0.362 < 0.4) — consistent with the published
post-2015 decay of the Lucca-Moench drift. The bar is the bar
(constitution rule 8); no re-litigation. Kill.

## Portfolio deliverable

No spec deploys, so no satellite sizing is proposed. For calibration:
even had pre-FOMC passed, a 10% overlay at its full-window net numbers
would have added ~+30 bps/yr CAGR at ~0.6 standalone Sharpe and near-zero
beta overlap — the ceiling on this whole family is small. Direction
closed at the specs as registered; the only live lead is overnight-QQQ
cost measurement (above).
