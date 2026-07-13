# quantitative-trading-system

A regime-conditional ETF momentum rotation strategy. It rotates monthly across a
fixed 8-ETF universe (7 risk ETFs + 1 short-Treasury cash proxy), ranking them by
trailing total return and holding a 50/50 blend of the single best ETF and an
inverse-volatility-weighted basket of the top three. Execution is Alpaca paper
trading, one account per strategy variant.

Everything is rules-based except a single lookback toggle: a HistGradientBoosting
classifier predicts the growth-inflation quadrant 21 days forward and switches the
ranking lookback between 63 and 21 trading days. It does not pick ETFs or size
positions. An SMA200 trend gate parks the top-1 leg in cash when the broad market
breaks down, and a calendar rule defers rebalances that would land right after FOMC
meetings.

## Start here — governance (read before touching anything)

The 2026 H1 paper race was voided after a signal-freshness failure
(frozen signals were re-traded for 2.5 months with zero alerts). These
four documents govern all work in this repo:

- **[CONSTITUTION.md](CONSTITUTION.md)** — the 10 research/trading rules
  (hypothesis-before-backtest, trial ledger, Deflated Sharpe with every
  Sharpe, naive baselines, freshness-or-refuse).
- **[EVALUATION.md](EVALUATION.md)** — the relaunch race protocol
  (arms, gates, monthly checks, promotion/kill table).
- **[docs/POSTMORTEM_2026H1.md](docs/POSTMORTEM_2026H1.md)** — the full
  incident report and void declaration for 2026-04-14 .. 06-30.
- **[docs/RELAUNCH_RUNBOOK.md](docs/RELAUNCH_RUNBOOK.md)** — operator
  steps to reset accounts and relaunch.

Every trial ever run is censused in `results/TRIAL_LEDGER.csv`; compute
selection-bias-corrected significance with
`python3 scripts/research/deflated_sharpe.py --sharpe <SR> --T <obs> --ledger results/TRIAL_LEDGER.csv`.

The full strategy spec is [MASTER_ARCHITECTURE.md](MASTER_ARCHITECTURE.md). Where
it disagrees with code, the code is wrong.

## Two-tier layout

- **Live money path** (held to CONSTITUTION rules 6 and 10):
  `scripts/run_rebalance.py`, `scripts/run_health_check.py`,
  `scripts/scheduler/`, `src/execution/`, `src/data/pipeline.py`,
  `src/strategy/`, `configs/accounts.yaml`, `configs/strategies/`.
- **Research** (never trades; feeds the ledger):
  `src/backtest/`, `scripts/research/`, `scripts/model/`,
  `tests/autonomous/`, `results/`.

Numbers cross from research to live only via the EVALUATION.md gates —
never directly.

## Components

- **Momentum ranking** — trailing total return over the active lookback,
  ranked cross-sectionally across the universe. `src/strategy/momentum.py`.
- **Regime classifier** — sklearn `HistGradientBoostingClassifier`, 4-class
  growth-inflation quadrant, walk-forward retrained. Output toggles the
  63d/21d lookback only. `src/model/classifier.py`.
- **Position sizing** — 50% top-1, 50% inverse-vol top-3. `src/strategy/position_sizing.py`.
- **SMA200 gate** — parks the top-1 leg in cash when SPY is more than 4% below
  its 200-day SMA. `src/strategy/sma_gate.py`.
- **FOMC deferral** — rebalances that would fall in the days after an FOMC
  meeting are pushed out. Calendar in `data/clean/calendar/events.parquet`.
- **Walk-forward backtest** — rolling train/val/test splits with embargo;
  the canonical backtest is gross with a 20bps degradation budget.
  `src/backtest/`, `src/model/walk_forward.py`.
- **Execution** — Alpaca paper, one account per strategy variant, positions
  reconciled against the broker. `src/execution/`.

All strategy parameters live in `configs/strategy.yaml`; nothing affecting
backtest numbers lives in code.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
```

Fill `.env` with FRED and Alpaca paper keys (nine account key/secret pairs, one
per strategy — see `configs/accounts.yaml`). Without a FRED key the macro fetcher
falls through to the public fredgraph.csv endpoint.

## Usage

Refresh data and run the monthly rebalance (dry run by default; `--execute`
submits orders):

```bash
python3 scripts/run_rebalance.py                 # dry run, all 9 strategies
python3 scripts/run_rebalance.py --status        # broker status of all accounts
python3 scripts/run_rebalance.py --strategy 1 --execute
python3 scripts/run_rebalance.py --force --date 2026-07-31   # off-schedule test
```

Daily health check (price/macro/signal freshness, holdings staleness,
performance vs SPY, classifier age, broker drift). Exit code 1 on any
alert-level finding:

```bash
python3 scripts/run_health_check.py
```

Backtests and research live under `scripts/run_backtest.py`,
`scripts/run_multi_backtest.py`, and `scripts/model/`.

Read-only terminal UI:

```bash
python3 scripts/tui.py
```

## Disclaimer

Educational use. Paper trading only; do not point this at a live account without
understanding the risks.
