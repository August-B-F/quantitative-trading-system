# CONSTITUTION — Research & Trading Rules

Adopted 2026-07-02 after the H1 void (see `docs/POSTMORTEM_2026H1.md`).
These rules bind every experiment, backtest, and deployment in this
repository. Amendments require a dated entry at the bottom of this file
made **before** the work the amendment enables.

1. **Hypothesis before backtest.** No backtest may be run until a dated
   hypothesis file is committed containing: the exact spec, the
   universe **fixed ex-ante**, the cost assumption, and the numeric
   deploy and kill thresholds. Results may not be used to edit that file.
2. **Hard budget: 3 specs per quarter.** Every trial — including
   discarded ones — is appended to `results/TRIAL_LEDGER.csv` before its
   result is discussed anywhere.
3. **Every reported Sharpe ships with its Deflated Sharpe**, computed by
   `scripts/research/deflated_sharpe.py --ledger results/TRIAL_LEDGER.csv`
   using the **cumulative** ledger trial count. A Sharpe without a DSR
   is not a result.
4. **Beat the named naive baseline net of costs, or be dropped.**
   Classifiers must beat regime persistence (~91%); strategies must beat
   their declared baseline (GEM dual momentum, SPY/SMA200, or 60/40 —
   named in the hypothesis file). No excuses tier.
5. **Numbers come only from the daily-ledger engine**
   (`src/backtest/ledger.py`). The fwd21 proxy harness
   (`src/backtest/engine.py`, gross of costs) is a screening tool; its
   output may never be quoted as performance.
6. **Minimum 3 months of paper trading at natural cadence**, plus a
   passing implementation-fidelity gate (live vs simulated same-signal,
   per `EVALUATION.md`), before any real capital.
7. **Negative results are kept.** Failed trials stay in the ledger and
   in the repo; deleting or rewording them is falsification.
8. **Criteria are never rewritten after seeing results.** Deploy/kill
   thresholds are those in the committed hypothesis file, verbatim.
9. **Universe by ex-ante rule only.** No ticker enters or leaves a
   universe because of how it performed in the sample under study.
10. **A system that cannot prove its signal is fresh must refuse to
    trade.** If the panel's max date, the feature layer's max date, and
    the wall clock disagree beyond the declared tolerance, the rebalance
    exits non-zero and alerts — it never trades the last available row.
