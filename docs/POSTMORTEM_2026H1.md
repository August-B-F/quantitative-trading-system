# POST-MORTEM — 2026 H1 Paper Race (2026-04-14 .. 2026-06-30)

**STATUS: THE ENTIRE 2026-04-14 .. 2026-06-30 TRACK RECORD IS VOID.**

Every rebalance in the race traded a signal computed as of **2026-04-10**.
The master feature panel froze on that date, nothing rebuilt it, no gate
checked it, and the health check reported `ALERTS: 0` for the full 2.5
months. The nine equity curves in `logs/monthly_comparison.csv` measure
which strategy happened to hold the luckiest frozen April portfolio —
they contain zero information about live strategy skill.

---

## 1. Timeline

| Date | Event |
|---|---|
| 2026-04-10 | Last row of `data/features/master_panel.parquet`. All live signals are frozen at this date from here on. |
| 2026-04-11 | `results/MASTER_SUMMARY.md` generated: 316 strategies backtested, best Sharpe 0.962. |
| 2026-04-13/14 | Autonomous suite (~300 trials, 49 phases) crowns ROBUST_VAR (Sharpe 1.989, fwd21 proxy engine). |
| 2026-04-14 | **Go-live.** 9 Alpaca paper accounts funded at $100k. The rebalance ran **twice** (no instance lock). |
| 2026-04-30 | Rebalance #1. `as_of = bundle.dates.max()` = 2026-04-10. The April signal is re-traded with **zero warnings**. |
| 2026-05-29 | Rebalance #2. Same frozen signal. Orders submitted while the **market was closed**; `wait_for_fill` gave up after 120 s; fills landed 06-01 (see the extra 2026-06-01 row in `monthly_comparison.csv`). |
| 2026-06-30 | Rebalance #3. Same frozen signal, third time. **Two concurrent rebalance processes** ran (no instance lock); `insufficient buying power` 403s with no retry. |
| 2026-04-14 .. 06-30 | `scripts/run_health_check.py` reports `ALERTS: 0` every single day. |
| 2026-07-02 | Audit discovers the freeze. This document written; record declared void. |

## 2. Root causes (file:line)

1. **Master panel frozen; live features silently truncated back onto the
   stale index.** `src/data/pipeline.py:47-54` (`load_panel`): the panel
   index is taken from `master_panel.parquet` (`dates = df.index`, last
   row 2026-04-10). The per-feature parquets under `data/features/price/`
   **were current** (nightly `rebuild_features()` kept
   `returns_63d.parquet` fresh through 2026-06-29+), but
   `pipeline.py:66` and `:68` `.reindex(dates)` them **back onto the
   stale panel index**, discarding every row after 2026-04-10. Nothing
   rebuilds the master panel itself.
2. **No freshness gate.** `scripts/run_rebalance.py` sets
   `as_of = bundle.dates.max()` and trades it unconditionally. A signal
   dated 2.5 months in the past produced no warning, no alert, no
   refusal. Exit code was 0 on every run.
3. **`gate_fired(NaN)` returns True — silent risk-off.**
   `src/strategy/sma_gate.py:11-13`:
   `return not (spy_distance > buffer)` — a NaN comparison is False, so
   NaN ⇒ True. `quality_dist_sma200__SPY` is NaN at the stale panel
   tail, so the SMA200 gate "fired" and sent TREND_SIMPLE (S5) 100% into
   SHY **while SPY was +8% above its SMA200**. A NaN input should be a
   hard error, not a position.
4. **Health check watched the wrong layer.**
   `scripts/run_health_check.py:35` monitors `data/clean/prices` — which
   was perfectly fresh. Nothing checked `master_panel.parquet` or the
   feature layer, so the system reported `ALERTS: 0` through 2.5 months
   of frozen signals.
5. **Execution-layer defects** (`src/execution/executor.py`, working
   tree at audit time — fixes in flight in a parallel workstream):
   - Buys sized from a **pre-wait equity snapshot**; the plan could be
     built up to 11 h before market open, so sizes were stale at fill
     time ⇒ `insufficient buying power` 403s with **no retry**
     (`executor.py:136`).
   - `wait_for_fill(timeout_s=120)` **abandons** unfilled orders
     (`executor.py:176,201`) — the 05-29 closed-market submissions.
   - `residual_close` flips `success=False` on otherwise-successful
     rebalances (`executor.py:205`), so the log cried wolf on good runs.
   - **No instance lock** — double-runs on 04-14 and 06-30.
   - `run_rebalance` **exits 0 on total failure**, so the scheduler
     wrapper (`scripts/scheduler/monthly_rebalance.ps1`) never raised a
     FAILED alert.
6. **Scheduler blind spot.** `iStock_MonthlyRebalance` triggers Tue–Sat
   04:15 Stockholm; a month-end falling on a Monday (next: 2026-08-31)
   is silently skipped.
7. **`spy_return` never recorded.** The `monthly_comparison.csv` writer
   is hardcoded to `spy_return=None` (`scripts/run_rebalance.py`,
   `write_monthly_comparison_row` call site), so the benchmark column is
   empty in every row — there was no on-file benchmark to notice the
   divergence against.

## 3. The numbers

Equity per account, `logs/monthly_comparison.csv` (initial $100,000;
final row 2026-06-30):

| Slot | Strategy | 2026-06-30 equity | Return | Verdict |
|---|---|---|---|---|
| S1 | OPTIMIZED | 93,218.96 | -6.8% | void |
| S2 | ROBUST_STACK | 94,118.72 | -5.9% | void |
| S3 | DROPOVERLAP | 94,124.62 | -5.9% | void |
| S4 | T2_BALANCED | 98,402.18 | -1.6% | void |
| S5 | TREND_SIMPLE | 106,023.18 | +6.0% | void (NaN gate forced SHY at some rebalances; see §2.3) |
| S6 | DUAL_MOMENTUM | 137,680.91 | **+37.7%** | **void — frozen lucky draw. MUST NOT BE FUNDED on this evidence.** |
| S7 | ROBUST_VAR | 91,631.81 | -8.4% | void |
| S8 | P59_FULL_STACK | 93,124.52 | -6.9% | void |
| S9 | P57_FRONTLOADED | 93,232.31 | -6.8% | void |

`spy_return` column: empty in all 5 rows (writer hardcodes `None`).
SPY itself returned **~+7.9%** over the window.

**The frozen signal vs reality.** The momentum-family accounts held the
2026-04-10 allocation — **XLE 88% / 6% / 6%** — for the entire window.
By end of June the true 63-day ranking had SOXX at **+107%** while XLE
was **-13.7%**. A correctly refreshed signal would have rotated into
semiconductors; the counterfactual fresh-signal path is roughly **+44%**
against the realized **-6% to -8%** for the momentum accounts. The
strategies did not fail; the plumbing did — and, symmetrically, S6's
+37.7% is plumbing luck, not strategy skill.

## 4. DECLARATION OF VOID

1. The 2026-04-14 .. 2026-06-30 paper record is **void as strategy
   evidence**. It may not be cited in any promotion, funding, or
   kill decision.
2. **S6 (DUAL_MOMENTUM)'s +37.7% is a frozen lucky draw** — its account
   happened to hold the April portfolio that drifted best. It must not
   be funded or promoted on this record.
3. All 9 paper accounts are to be **reset (or archived and reopened) at
   relaunch** per `docs/RELAUNCH_RUNBOOK.md`. The race restarts from
   zero under `EVALUATION.md`.
4. Every head-to-head contrast the race was designed to test
   (`results/STRATEGY_SELECTION.md`) is unanswered. No conclusion about
   ROBUST_STACK vs ROBUST_VAR vs P59 vs P57 may be drawn.

## 5. Research-layer findings (why the relaunch needs a constitution)

The audit also re-examined the research record that produced the lineup:

- **~650 trials, no holdout.** 316 strategies in `MASTER_SUMMARY` plus
  ~300 autonomous-suite experiments (plus assorted tier studies), all
  evaluated on the same sample, best-of reported. Nothing was held out.
- **The best honest Sharpe is 0.962** (FN_abs_mom_optimized,
  daily-ledger engine, `results/MASTER_SUMMARY.md`) — and it sits
  **below the luck envelope for N=316 trials** (E[max SR] ≈ 0.97 at the
  ledger's cross-trial variance; ~1.4–1.7 under wider dispersion
  assumptions). Its Deflated Sharpe is **0.46** at N=316 and **0.26**
  against the full 616-trial ledger
  (`py -3 scripts/research/deflated_sharpe.py --sharpe 0.962 --T 96 --ledger results/TRIAL_LEDGER.csv`).
- **The Sharpe-1.9+ champions come from the fwd21 proxy engine**
  (`src/backtest/engine.py` — "gross, pre-transaction-cost", forward-21d
  overlapping-return approximation), not a daily trade ledger. They are
  not comparable to net, daily-ledger numbers.
- **Macro features carry ~25–35 days of lookahead** (publication-lag
  misalignment), inflating any classifier-conditioned backtest.
- **The regime classifier's 60–66% walk-forward accuracy is below the
  91% of naive persistence** (predict "same regime as today").
- Full trial census: `results/TRIAL_LEDGER.csv` (seeded 2026-07-02).

## 6. Remediation

- **Governance:** `CONSTITUTION.md` (10 rules; freshness rule 10 makes
  this failure class a refusal-to-trade, not a silent re-trade).
- **Relaunch protocol:** `EVALUATION.md` (new race design, fidelity
  gates, tripwires) and `docs/RELAUNCH_RUNBOOK.md` (operator steps).
- **Code fixes** (parallel workstreams, out of scope for this document):
  panel rebuild + freshness gate in the pipeline, NaN-hostile SMA gate,
  feature-layer health checks, executor sizing/retry/lock/exit-codes.
