# iStock

An AI-driven stock trading bot built on PyTorch, Alpaca Markets API, and FinBERT sentiment analysis.

## Start here — governance (read before touching anything)

The 2026 H1 paper race was voided after a signal-freshness failure
(frozen signals were re-traded for 2.5 months with zero alerts). These
four documents now govern all work in this repo:

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
`py -3 scripts/research/deflated_sharpe.py --sharpe <SR> --T <obs> --ledger results/TRIAL_LEDGER.csv`.

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

## Architecture

- **Multi-branch LSTM + Attention model** — separate branches for price/technicals, sentiment, and macro features, fused via attention before classification head
- **FinBERT sentiment** — Alpaca News API feed scored with ProsusAI/FinBERT; no web scraping
- **Regime detection** — Hidden Markov Model on SPY returns classifies market as bull/bear/sideways and adjusts trading behavior
- **Walk-forward training** — models trained and validated on rolling windows to prevent overfitting
- **Bayesian hyperparameter search** — Optuna optimizes all trade filters AND model architecture jointly on out-of-sample Sharpe ratio
- **Kelly Criterion position sizing** — fractional Kelly with per-regime scaling
- **Bracket orders** — stop loss + take profit enforced server-side on Alpaca 24/7
- **Portfolio reconciliation** — Alpaca positions are always source of truth
- **SHAP explainability** — per-feature importance analysis on every model version
- **Performance tracking** — SQLite database logging every trade, daily equity, and Sharpe/drawdown metrics
- **Terminal UI** — full Textual TUI with live charts, signals, positions, and bot control

## Setup

```bash
git clone https://github.com/August-B-F/ultimate-ai-stock-trader
cd ultimate-ai-stock-trader
pip install -r requirements.txt
```

Edit `config/config.yaml` with your Alpaca API keys.

## Usage

```bash
# Terminal UI (recommended)
python scripts/tui.py

# Or run steps manually:

# 1. Download all historical data
python scripts/download_data.py

# 2. Train model with walk-forward + hyperparam search
python scripts/train.py

# 3. Backtest the trained model
python scripts/backtest.py

# 4. Run live/paper trading bot
python scripts/run_live_bot.py
```

## Disclaimer

This is for educational purposes only. Do not trade real money without fully understanding the risks.
