# Keep or Delete — adversarial trial verdict (2026-07-02)

The owner asked whether to keep this system or delete and redo everything.
Three independent agents argued it: a prosecutor ordered to win the
delete-everything case, a defender, and an independent rebuild estimator.
A fourth judged. Full briefs in the session record; verdicts verified
against the repo (LOC counts, test collection, live panel reads).

## Ruling: KEEP CORE, DELETE CRUFT

The decisive observation: **the prosecution could not construct
delete-everything.** Its own winning plan was "a fresh repo whose commit
#1 is the ~7.6k-LOC salvage (ledger engine, hardened executor, rotation,
gates, 135 tests, constitution) plus the negative-result ledgers" — i.e.
keep-and-prune with extra migration risk. Nobody in an adversarial trial
defended true deletion.

## What the prosecution proved (conceded, becomes the purge list)

- `MASTER_ARCHITECTURE.md` still calls itself "the single source of truth"
  for numbers the post-mortem voided, and live configs cite it as binding.
- 25 void reports sit in `results/` with production-sounding titles and no
  void banners (`FINAL_STRATEGY_VALIDATED.md`, `WINNING_STRATEGY.md`, ...).
- `README.md` describes a PyTorch/FinBERT bot that never existed.
- ~48% of all Python LOC is literally dead (archive/ + tests/autonomous
  contribute 0 of the 138 collected tests); ~70% serves nothing adopted.
- The 1029-column frozen panel is still on the money path (gated, not
  removed), and the 9 void strategies are still wired to 9 funded accounts.

## What cannot be rebuilt at any price (the reason not to delete)

1. **The kill list** — `results/TRIAL_LEDGER.csv` (896 trials) and the 11
   measured kills (vol targeting -159 bps/yr, vol-adjusted ranks -580,
   bands -129, weekly breadth, calendar, ...). Pre-registration is
   one-shot: you cannot honestly re-run experiments whose outcomes you
   know. Delete it and every future Sharpe becomes un-deflatable and every
   dead idea becomes re-testable.
2. **The live-failure forensics** — `docs/POSTMORTEM_2026H1.md`, the
   file:line record of a 2.5-month real failure. Its 7 bug classes are the
   spec every current fix was built against.
3. **The proof that intentions don't work** — the repo's own git history
   shows the written rule "do NOT run hundreds of experiments" was violated
   within 48 hours by the ~300-trial autonomous suite. A fresh repo with
   the same operator restarts at N=0 trials with no enforcement — the exact
   configuration that produced the disaster.

And one live fact: the master panel is *still* frozen at 2026-04-10, and
the freshness gates in `run_rebalance.py` are actively refusing to trade
it **today**. The old system traded that exact staleness for 2.5 months.
The machinery being asked to justify itself is currently doing its job.

## Rebuild price (independent estimate)

~12±2 focused sessions to code parity, re-exposing the 7 fixed bug classes
along the way — and the estimate is self-contradictory, because the
rebuild's spec documents (post-mortem, ledgers) are the ones deletion
destroys.

## Step zero — before ANY path

**Commit the working tree.** HEAD (`40bd7b7`, 2026-05-13) is the broken
pre-audit system; all value exists only uncommitted (139 untracked files).
One `git clean` today is unrecoverable.

## The purge manifest (execute after commit + decommissioning the 9 slots)

DELETE (~48k LOC, zero collected tests lost):
- `tests/autonomous/`, `archive/`, `scripts/model/`
- `src/backtest/engine.py`, `src/backtest/multi_engine.py`,
  `scripts/run_backtest.py`, `scripts/run_multi_backtest.py`,
  `tests/test_backtest_engine.py` (fold the canary xfail record into the
  post-mortem first)
- `src/strategy/strategies.py` + `configs/strategies/strategy_1..9_*.yaml`
  + `candidate_two_sleeve.yaml` (AFTER decommissioning the 9 account slots)
- `src/features/`, `src/model/`, `scripts/run_retrain.py`,
  `scripts/scheduler/quarterly_retrain.ps1`,
  `data/features/master_panel.parquet` (same sequencing condition)
- 28 dead fetchers in `src/data/fetchers/` (keep yahoo, yahoo_prices,
  fred_macro, fomc_calendar, twelve_data, bls), `scripts/phase1_fred*.py`,
  `phase2_*.py`, `phase3_*.py` (keep `phase1_download.py` — nightly job)
- `scripts/generate_presentation.py`, `generate_pdf_report.py`,
  `debug_zt_client.py`

ARCHIVE WITH VOID BANNERS (do not silently delete — the post-mortem cites
them as evidence): `MASTER_ARCHITECTURE.md` and the 25 void
`results/*.md` reports → `docs/void/`.

EDIT: `configs/accounts.yaml` (remove the 9 void slots),
`configs/strategy.yaml` (re-anchor citations from MASTER_ARCHITECTURE to
CONSTITUTION/EVALUATION), `README.md` (rewrite the fictional front page).

KEEP (load-bearing, ~4.4k LOC + tests): `src/backtest/ledger.py`,
`src/execution/`, `src/strategy/rotation.py` + `sleeves.py`,
`scripts/run_rebalance.py`, `run_health_check.py`, `run_race_report.py`,
`scripts/research/deflated_sharpe.py`, `tests/` (minus autonomous),
`CONSTITUTION.md`, `EVALUATION.md`, `docs/`, `results/TRIAL_LEDGER.csv`,
`results/DROPLET_LEDGER.md`, `results/BASELINES.md`, `research/droplets/`,
`configs/strategies/candidate_blend_rotation.yaml`, the live data layer,
skylark ops UI.
