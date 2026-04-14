# AUTONOMOUS RESEARCH AGENT — PERSISTENT INSTRUCTIONS

READ ON EVERY RESUME. This file persists the prompt you received so you never forget the rules.

## Hard rules
1. All code/results/notes go in `/tests/autonomous/`. Everything else is read-only.
2. Anti-overfitting: use walk-forward (`src/model/walk_forward.py` ExpandingSplitter). Never eval on train.
3. Apply 50% haircut to every improvement. If haircut kills it, mark FAILED.
4. NON-NEGOTIABLE: `lookback_stable=63`, `rebalance=month_end`, `cpi_yoy` must remain in classifier features. Never replace — only add.
5. Append-only log `LOG.md`. Update `BEST.md` only on haircut-winning beats. Hourly report to `HOURLY.md`. `HANDOFF.md` when stopping.
6. Starting champion: 23.61% CAGR / 1.50 Sharpe / -12.94% MaxDD.
7. Max 5 min per backtest, max 30 min debugging, max 2 params optimized at a time.
8. Check `ALREADY_TESTED.md` before running — don't repeat main-project experiments (M01-M27, E01-E05).

## Phase plan
- Phase 1 (first 2-3h): lookback blends, transition-lb variants, top-N, split ratios, SMA buffer/index, position sizing, M26 window, weekly-check rebal.
- Phase 2 (h3-6): universe mods, classifier experiments, alt gate rules.
- Phase 3 (h6+): multi-timeframe momentum, mom of mom, mean-rev overlay, VIX breakout, correlation regime, adaptive lookback, Kelly, etc.

## Folder
```
tests/autonomous/
  INSTRUCTIONS.md  # this file
  LOG.md           # append-only research log
  BEST.md          # champion + history
  HOURLY.md        # hourly status
  HANDOFF.md       # resume state
  ALREADY_TESTED.md
  experiments/     # one .py per test
  champions/       # only if beats champion post-haircut
  utils/           # base_test.py and helpers
  cache/           # pickled pred_reg, bundle stuff
```

## Workflow each resume
1. Read `HANDOFF.md`, then `LOG.md` tail, then `BEST.md`.
2. Continue queue. Run experiments in batches in single process (cache expensive stuff).
3. Log every result to LOG.md (timestamp / desc / CAGR / Sharpe / MaxDD / pass-fail / takeaway).
4. Hourly: append HOURLY.md summary.
5. On stop: write HANDOFF.md.

## Never stop — only rest when tokens run out.
