<!-- ARCHIVED: stale pre-Phase-3 docs. See PROJECT_SUMMARY.md for canonical docs. -->
# iStock -- AI-Driven Quantitative Trading System

## Complete Technical Documentation for AI Agents

This document is written for AI coding assistants (Claude, GPT, Copilot, etc.) to quickly understand the entire codebase, make safe modifications, and avoid common pitfalls. Every module, function signature, data flow, and architectural decision is documented here.

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Directory Structure](#2-directory-structure)
3. [Configuration System](#3-configuration-system)
4. [Data Pipeline](#4-data-pipeline)
5. [Feature Engineering](#5-feature-engineering)
6. [Model Architecture](#6-model-architecture)
7. [Training Pipeline](#7-training-pipeline)
8. [Backtesting Engine](#8-backtesting-engine)
9. [Live Trading Execution](#9-live-trading-execution)
10. [Risk Management](#10-risk-management)
11. [Terminal UI (TUI)](#11-terminal-ui-tui)
12. [Module Reference](#12-module-reference)
13. [Data Flow Diagrams](#13-data-flow-diagrams)
14. [Critical Invariants and Pitfalls](#14-critical-invariants-and-pitfalls)
15. [Dependencies](#15-dependencies)
16. [Testing](#16-testing)

---

## 1. Project Overview

iStock is a production-grade quantitative stock trading system built in Python. It uses a multi-branch Transformer neural network to predict 5-class stock direction (strong_sell, sell, hold, buy, strong_buy) over a 3-day horizon for a universe of 50 US equities.

### Key Design Principles

- **No lookahead bias**: All data (fundamentals, sentiment, prices) is point-in-time. Fundamentals are delayed 45 days from period end to simulate SEC filing delays.
- **Walk-forward validation**: Rolling train/val/test windows prevent overfitting to any particular market regime.
- **Regime-aware risk management**: A Hidden Markov Model detects bull/bear/sideways/crisis regimes and adjusts position sizing, exposure limits, and confidence thresholds accordingly.
- **Paper trading by default**: Live trading requires explicit opt-in via both CLI flag (`--live`) AND config (`trading.live: true`).
- **Uncertainty-gated execution**: MC Dropout + temperature scaling produce calibrated uncertainty estimates; high-uncertainty predictions are not traded.

### Tech Stack

| Category | Technology |
|---|---|
| Language | Python 3.11+ |
| Deep Learning | PyTorch 2.2+ |
| Data | Pandas 2.1+, NumPy 1.26+, PyArrow |
| ML | scikit-learn 1.4+, Optuna 3.5+ |
| NLP | Transformers 4.38+ (FinBERT) |
| Time Series | hmmlearn 0.3+ (HMM regimes) |
| Broker API | alpaca-py 0.20+, alpaca-trade-api 3.0+ |
| Market Data | yfinance 0.2.36+ |
| UI | Textual 0.60+, Plotext 5.2+ |
| Storage | SQLAlchemy 2.0+ (SQLite) |

---

## 2. Directory Structure

```
quantitative-trading-system/
|-- main.py                          # Entry point: launches TUI
|-- requirements.txt                 # All Python dependencies
|-- test_all.py                      # Comprehensive test suite (15 tests)
|
|-- config/
|   |-- config.yaml                  # API keys, universe, paths, trading params
|   |-- model.yaml                   # Model architecture hyperparameters
|   |-- training.yaml                # Training, walk-forward, augmentation config
|
|-- scripts/
|   |-- tui.py                       # Terminal UI dashboard (Textual app)
|   |-- download_data.py             # Fetch OHLCV bars + news sentiment
|   |-- train.py                     # Walk-forward training + Optuna search
|   |-- backtest.py                  # Historical backtesting
|   |-- run_live_bot.py              # Daily live/paper trading bot
|
|-- ultimate_trader/                 # Core package
|   |-- __init__.py
|   |
|   |-- data_sources/                # External data fetching
|   |   |-- alpaca_market.py         # OHLCV bars from Alpaca API
|   |   |-- alpaca_news.py           # News + FinBERT sentiment
|   |   |-- gdelt_news.py            # GDELT geopolitical sentiment
|   |   |-- alt_data.py              # VIX, yield curve, sector ETFs, earnings
|   |   |-- fundamentals.py          # Quarterly financials via yfinance
|   |
|   |-- features/                    # Feature engineering
|   |   |-- feature_builder.py       # Main feature assembly pipeline
|   |   |-- technicals.py            # 42 technical indicators
|   |   |-- sentiment.py             # Daily sentiment aggregation
|   |   |-- regimes.py               # 4-state HMM regime detection
|   |
|   |-- modeling/                    # Neural network and training
|   |   |-- model.py                 # UltraTradingModel (Transformer)
|   |   |-- losses.py                # FocalLoss, OrdinalReturnLoss
|   |   |-- metrics.py               # Sharpe, Sortino, drawdown, win rate
|   |   |-- calibration.py           # Temperature scaling (L-BFGS)
|   |   |-- hyperparam_search.py     # Optuna Bayesian optimization
|   |
|   |-- evaluation/                  # Backtesting and explainability
|   |   |-- backtester.py            # Walk-forward vectorized backtest
|   |   |-- explainability.py        # SHAP feature importance
|   |
|   |-- trading/                     # Live execution
|   |   |-- execution.py             # Alpaca bracket orders
|   |   |-- risk.py                  # Kelly Criterion position sizing
|   |   |-- portfolio.py             # Alpaca portfolio reconciliation
|   |
|   |-- utils/                       # Shared utilities
|       |-- config_loader.py         # YAML config with dot notation
|       |-- logging.py               # Logger + SQLite performance DB
|       |-- time_utils.py            # Market hours, walk-forward windows
|
|-- data/                            # (gitignored) Runtime data
|   |-- raw/bars/{symbol}.parquet    # Cached OHLCV bars
|   |-- raw/news/{symbol}.json       # Cached news articles
|   |-- models/best_model.pt         # Trained model checkpoint
|   |-- scalers/                     # Fitted RobustScaler pickles
|   |-- performance.db               # SQLite trade/equity log
|
|-- logs/                            # (gitignored) Daily rotating logs
```

---

## 3. Configuration System

### Loading

```python
from ultimate_trader.utils.config_loader import load_config
cfg = load_config("config")  # loads config/, model.yaml, training.yaml
```

`load_config(dir)` reads `config.yaml`, `model.yaml`, and `training.yaml` from the given directory and merges them into a single `Config` object with dot-notation access (e.g., `cfg.model.hidden_dim`).

### config.yaml -- Key Fields

| Path | Type | Description |
|---|---|---|
| `alpaca.key_id` | str | Alpaca API key (paper or live) |
| `alpaca.secret_key` | str | Alpaca API secret |
| `alpaca.base_url` | str | `https://paper-api.alpaca.markets` (paper) or `https://api.alpaca.markets` (live) |
| `universe.symbols` | list[str] | 50 stock tickers |
| `universe.benchmark` | str | `"SPY"` |
| `universe.sector_etfs` | list[str] | 10 sector ETFs (XLK, XLF, XLE, ...) |
| `universe.macro_tickers` | list[str] | `["TLT", "GLD", "UUP", "USO"]` |
| `universe.vix_ticker` | str | `"VIXY"` (VIX ETF proxy) |
| `data.start_date` | str | `"2018-01-01"` |
| `data.bar_timeframe` | str | `"1Day"` |
| `data.min_history_days` | int | `300` |
| `news.enabled` | bool | Whether to fetch/use news sentiment |
| `news.max_articles_per_day` | int | `20` |
| `paths.raw_dir` | str | `"data/raw"` |
| `paths.models_dir` | str | `"data/models"` |
| `paths.scalers_dir` | str | `"data/scalers"` |
| `paths.db_path` | str | `"data/performance.db"` |
| `trading.live` | bool | `false` (MUST be true + `--live` CLI flag for real money) |
| `trading.run_time` | str | `"15:45"` (Eastern, when bot runs daily) |
| `trading.max_gross_exposure` | float | `0.95` |
| `trading.max_single_position` | float | `0.15` |
| `trading.min_cash_buffer` | float | `0.05` |
| `trading.kelly_fraction` | float | `0.3` (fractional Kelly) |
| `trading.min_confidence` | float | `0.60` |
| `trading.base_stop_loss` | float | `0.07` (7%) |
| `trading.base_take_profit` | float | `0.12` (12%) |
| `trading.bracket_orders` | bool | `true` |
| `trading.allow_short` | bool | `false` |

### model.yaml -- Key Fields

| Path | Type | Default | Description |
|---|---|---|---|
| `model.type` | str | `"multi_branch_transformer"` | Architecture type |
| `model.price_window` | int | `40` | Days of price/tech history per sample |
| `model.sentiment_window` | int | `20` | Days of sentiment history |
| `model.macro_window` | int | `20` | Days of macro features |
| `model.hidden_dim` | int | `256` | Transformer d_model for tech branch |
| `model.num_transformer_layers` | int | `4` | Encoder layers per branch |
| `model.num_attn_heads` | int | `8` | Attention heads |
| `model.transformer_ff_dim` | int | `1024` | Feedforward dim in encoder |
| `model.dropout` | float | `0.25` | Used for both training and MC Dropout |
| `model.company_embedding_dim` | int | `16` | Per-symbol embedding |
| `model.sector_embedding_dim` | int | `8` | Per-sector embedding |
| `model.regime_embedding_dim` | int | `8` | Regime state embedding |
| `model.final_hidden_dims` | list[int] | `[512, 256, 128]` | MLP head layer sizes |
| `model.num_classes` | int | `5` | Output classes |
| `targets.horizon_days` | int | `3` | Prediction horizon |
| `targets.r_hi` | float | `0.025` | Threshold for strong signals |
| `targets.r_lo` | float | `0.005` | Threshold for hold zone |
| `uncertainty.mc_dropout_samples` | int | `50` | MC forward passes |

### training.yaml -- Key Fields

| Path | Type | Default | Description |
|---|---|---|---|
| `training.batch_size` | int | `512` | Training batch size |
| `training.num_epochs` | int | `50` | Max epochs |
| `training.lr` | float | `0.0003` | Learning rate |
| `training.weight_decay` | float | `0.0001` | AdamW weight decay |
| `training.lr_scheduler` | str | `"cosine"` | LR schedule type |
| `training.early_stopping_patience` | int | `8` | Epochs without improvement |
| `training.grad_clip` | float | `1.0` | Gradient clipping norm |
| `training.class_weights` | bool | `true` | Use inverse-frequency weights |
| `walk_forward.enabled` | bool | `true` | Walk-forward training |
| `walk_forward.train_months` | int | `18` | Training window length |
| `walk_forward.val_months` | int | `3` | Validation window |
| `walk_forward.test_months` | int | `1` | Test window |
| `walk_forward.step_months` | int | `1` | Slide step |
| `hyperparam_search.n_trials` | int | `80` | Optuna trial count |
| `hyperparam_search.metric` | str | `"sharpe"` | Optimization target |
| `augmentation.gaussian_noise_std` | float | `0.005` | Noise on price features |
| `augmentation.mixup_alpha` | float | `0.2` | Mixup interpolation |

---

## 4. Data Pipeline

### 4.1 OHLCV Bars (`data_sources/alpaca_market.py`)

**Class**: `MarketDataFetcher`

```python
fetcher = MarketDataFetcher(cfg)
bars = fetcher.fetch("AAPL")           # -> pd.DataFrame (date-indexed)
all_bars = fetcher.fetch_all(symbols)  # -> dict[str, pd.DataFrame]
latest = fetcher.get_latest_prices(symbols)  # -> dict[str, float]
```

- Fetches from Alpaca Market Data API v2
- Caches to `data/raw/bars/{symbol}.parquet`
- Columns: `open, high, low, close, volume, vwap`
- Incremental: only fetches new bars after last cached date
- Handles split/dividend adjustments via Alpaca

### 4.2 News Sentiment (`data_sources/alpaca_news.py`)

**Class**: `NewsFetcher`

```python
fetcher = NewsFetcher(cfg)
sentiment = fetcher.fetch_sentiment("AAPL", start, end)  # -> pd.DataFrame
```

- Fetches from Alpaca News API
- Scores each article with FinBERT (`ProsusAI/finbert`)
- Aggregates daily with recency weighting
- Output columns: `num_articles, avg_score, score_std, pos_ratio, neg_ratio, sentiment_momentum_3d, sentiment_momentum_5d, sentiment_vol_5d, news_surge`
- Caches raw articles to `data/raw/news/{symbol}.json`

### 4.3 GDELT Sentiment (`data_sources/gdelt_news.py`)

**Class**: `GDELTFetcher`

```python
fetcher = GDELTFetcher()
gdelt_df = fetcher.fetch(start, end)  # -> pd.DataFrame
```

- Macro-level geopolitical sentiment from GDELT 2.0 API
- 3-month chunked fetching, 1 req/sec rate limit
- Output columns: `gdelt_avg_tone, gdelt_article_count, gdelt_goldstein_scale`
- Cached to `data/raw/gdelt/{cache_key}.parquet`

### 4.4 Alternative Data (`data_sources/alt_data.py`)

**Class**: `AltDataBuilder`

```python
builder = AltDataBuilder(cfg, bars)
macro_df = builder.build(gdelt_df=None)  # -> pd.DataFrame (date-indexed)
```

- Computes macro features from ETF bars (SPY, VIXY, TLT, USO, GLD)
- Features: `vix_level, vix_change_1d, vix_regime_pct, yield_proxy, yield_change_5d, spy_return_1d, spy_return_5d, spy_vol_20d, spy_trend, oil_return_5d, gold_return_5d`
- Sector relative strength vs SPY for each sector ETF
- Merges GDELT sentiment if provided
- Earnings calendar via yfinance

### 4.5 Fundamentals (`data_sources/fundamentals.py`)

**Class**: `FundamentalsFetcher`

```python
fetcher = FundamentalsFetcher(cfg)
fund = fetcher.fetch("AAPL")  # -> pd.DataFrame (date-indexed, forward-filled)
```

- Quarterly financials from yfinance
- Features: `pe_ratio, eps_growth_yoy, revenue_growth_yoy, debt_equity, free_cash_flow_yield, insider_buy_ratio`
- **Critical**: Filing date = `period_end + 45 days` (SEC 10-Q rule) to prevent lookahead bias
- Forward-fills from filing date to daily frequency
- Cache TTL: 7 days

---

## 5. Feature Engineering

### 5.1 Technical Indicators (`features/technicals.py`)

**Function**: `add_technicals(df: pd.DataFrame) -> pd.DataFrame`

Takes a DataFrame with `[open, high, low, close, volume]` columns and adds 42 indicator columns in-place:

| Category | Indicators |
|---|---|
| Returns | `return_1d, return_3d, return_5d, return_10d, return_20d` |
| Volatility | `vol_5d, vol_20d` |
| RSI | `rsi_14, rsi_28` |
| MACD | `macd, macd_signal, macd_hist` |
| Bollinger | `bb_upper, bb_lower, bb_width, bb_pct_b` |
| ATR | `atr_14, atr_pct` |
| Volume | `obv, obv_change_5d, volume_anomaly` |
| SMA | `sma_50_200_ratio, price_vs_sma50, price_vs_sma200` |
| Stochastic | `stoch_k, stoch_d` |
| Williams | `williams_r` |
| Momentum | `momentum_10, momentum_20` |
| Range | `price_range_20d` |
| Log | `log_close, log_volume` |
| VWAP | `vwap_dev` |
| MFI | `mfi_14` |
| Chaikin | `cmf_20` |
| Elder Ray | `elder_bull, elder_bear` |
| Ichimoku | `ichi_tenkan, ichi_kijun, ichi_senkou_a, ichi_senkou_b, ichi_chikou` |

All NaN values are filled with 0 at the end.

### 5.2 Feature Builder (`features/feature_builder.py`)

**Class**: `FeatureBuilder`

This is the central feature assembly pipeline. It combines technicals, sentiment, macro, and fundamentals into windowed arrays ready for the model.

#### Feature Groups (Constants)

```python
TECH_FEATURES       # 42 columns (40 used as model input after filtering)
SENTIMENT_FEATURES  # 8 columns
MACRO_FEATURES      # 14 columns (11 base + 3 GDELT)
FUNDAMENTAL_FEATURES  # 6 columns
```

#### Key Methods

```python
fb = FeatureBuilder(cfg)

# Fit scalers on training data ONLY
fb.fit_scalers(all_tech, all_sent, all_macro, all_fund)

# Load scalers from disk for inference
fb.load_scalers()

# Build inference features (latest window per symbol)
features, labels = fb.build_features(
    bars, sentiment, macro_df, symbols,
    symbol_to_idx, symbol_to_sector,
    earnings_dates=None, fundamentals=None, fit=False
)

# Build training samples (all dates x all symbols)
samples, label_list = fb.build_training_samples(
    bars, sentiment, macro_df, symbols,
    symbol_to_idx, symbol_to_sector,
    date_range, fit_scalers=False,
    earnings_dates=None, fundamentals=None
)
```

#### Sample Format

Each sample is a dict:
```python
{
    "tech":       np.ndarray  # (price_window, 40) float32
    "sent":       np.ndarray  # (sentiment_window, 8) float32
    "macro":      np.ndarray  # (macro_window, 14) float32
    "fund":       np.ndarray  # (6,) float32
    "sym_idx":    int          # symbol index for embedding
    "sec_idx":    int          # sector index for embedding
    "date":       Timestamp    # (training only)
    "regime_idx": int          # 0=unknown, 1=bull, 2=bear, 3=sideways, 4=crisis
}
```

#### Labeling

5-class with volatility-normalized thresholds:
```
Label 4 (strong_buy):  future_return > r_hi * vol_scale
Label 3 (buy):         future_return > r_lo * vol_scale
Label 2 (hold):        -r_lo * vol_scale <= future_return <= r_lo * vol_scale
Label 1 (sell):        future_return < -r_lo * vol_scale
Label 0 (strong_sell): future_return < -r_hi * vol_scale
```

Where `vol_scale = clip(vol_20d / vol_252d, 0.5, 3.0)`.

#### Scaler Safety

- Scalers (RobustScaler) are fitted ONCE on the first training fold
- All subsequent folds and inference use `transform()` only
- Scalers are serialized to `data/scalers/{tech,sent,macro,fund}_scaler.pkl`

#### Additional Feature Helpers

- `_add_earnings_features(df, earnings_dates, symbol)` -- adds `days_to_earnings` (0-1 normalized) and `earnings_flag` (1 if within 3 days)
- `_add_correlation_features(df, symbol, bars, sector_map)` -- adds `corr_spy_20d`, `corr_sector_20d`, `sector_rel_momentum_5d`, `sector_rel_momentum_20d`
- `SECTOR_ETF_MAP` -- hardcoded mapping of each stock to its sector ETF (e.g., `"AAPL": "XLK"`)

### 5.3 Sentiment Aggregation (`features/sentiment.py`)

**Function**: `build_sentiment_features(sentiment_data, symbols, n_days)`

Filters per-symbol sentiment DataFrames to last N days and returns an aligned dict.

### 5.4 Regime Detection (`features/regimes.py`)

**Class**: `RegimeDetector`

```python
rd = RegimeDetector(n_components=4)
rd.fit(spy_bars)                    # fit HMM on SPY log returns
regime = rd.current_regime(spy_bars)  # -> "bull" | "bear" | "sideways" | "crisis"
series = rd.predict(spy_bars)       # -> pd.Series of regime labels
rd.save("path.pkl")                 # serialize
rd.load("path.pkl")                 # deserialize
```

- 4-state Gaussian HMM with full covariance
- Regime assignment by ranking mean returns and variances:
  - Bull: highest mean
  - Sideways: 2nd highest mean
  - Crisis: lowest-mean pair, higher variance
  - Bear: lowest-mean pair, lower variance
- Unfitted fallback: returns `"sideways"` for all dates

---

## 6. Model Architecture

### 6.1 UltraTradingModel (`modeling/model.py`)

**6.07M parameters** with default config.

```
Input Branches:
  tech   (B, 40, 40) -> BranchTransformer(40->256, 4L, 8H, ff=1024) -> SelfAttentionPooling -> concat(mean, last) -> (B, 512)
  sent   (B, 20, 8)  -> BranchTransformer(8->128, 4L, 8H, ff=512)   -> mean pool -> (B, 128)
  cross                  tech_seq queries projected sent_seq via CrossAttention -> (B, 256)
  macro  (B, 20, 14) -> BranchTransformer(14->128, 4L, 8H, ff=512)  -> mean pool -> (B, 128)
  fund   (B, 6)      -> MLP(6->128->64) -> (B, 64)
  sym    (B,)        -> Embedding(51, 16) -> (B, 16)
  sec    (B,)        -> Embedding(12, 8) -> (B, 8)
  regime (B,)        -> Embedding(6, 8) -> (B, 8)

Fusion:
  concat all -> (B, 1120) -> LayerNorm -> MLP(512->256->128) -> Linear(128, 5)
```

#### Forward Signature

```python
model(
    tech: Tensor,         # (B, price_window, tech_dim)  -- 42 tech features
    sent: Tensor,         # (B, sent_window, sent_dim)   -- 8 sentiment features
    macro: Tensor,        # (B, macro_window, macro_dim)  -- 14 macro features
    fund: Tensor,         # (B, fund_dim)                 -- 6 fundamental features
    sym_idx: Tensor,      # (B,) long                     -- symbol embedding index
    sec_idx: Tensor,      # (B,) long                     -- sector embedding index
    regime_idx: Tensor,   # (B,) long                     -- regime: 0=unknown,1=bull,2=bear,3=sideways,4=crisis
) -> Tensor              # (B, 5) raw logits
```

#### MC Dropout Uncertainty

```python
mean_probs, uncertainty = model.predict_with_uncertainty(
    tech, sent, macro, fund, sym_idx, sec_idx, regime_idx,
    n_samples=50
)
# mean_probs: (B, 5) averaged softmax probabilities
# uncertainty: (B,) normalized entropy [0, 1]
```

Keeps `model.train()` active during inference to enable stochastic dropout. Runs N forward passes, averages probabilities, computes predictive entropy.

#### Temperature Scaling

`model.temperature` is a learnable scalar (init=1.0, `requires_grad=False`). Applied at inference: `logits / temperature`. Optimized post-hoc by `TemperatureScaler`.

#### Factory Function

```python
from ultimate_trader.modeling.model import build_model
model = build_model(
    cfg,
    n_symbols=50,    # number of unique symbols
    n_sectors=11,    # number of unique sectors
    tech_dim=40,     # tech feature count
    sent_dim=8,      # sentiment feature count
    macro_dim=14,    # macro feature count
    fund_dim=6,      # fundamental feature count
)
```

### 6.2 Deep Ensemble (`modeling/model.py`)

```python
from ultimate_trader.modeling.model import EnsembleModel
ensemble = EnsembleModel(models=[model1, model2, ...])
mean_probs, uncertainty = ensemble.predict(
    tech, sent, macro, fund, sym_idx, sec_idx, regime_idx,
    mc_samples=10  # per member
)
```

Wraps N independently trained models. Averages MC Dropout predictions across all members.

### 6.3 Loss Functions (`modeling/losses.py`)

```python
from ultimate_trader.modeling.losses import FocalLoss, OrdinalReturnLoss, compute_class_weights

# Inverse-frequency class weights
weights = compute_class_weights(labels_array)  # -> Tensor

# Focal Loss (down-weights easy examples)
fl = FocalLoss(gamma=2.0, weight=weights)
loss = fl(logits, targets)

# Ordinal Return Loss = 70% Focal + 30% ordinal penalty
orl = OrdinalReturnLoss(gamma=2.0, weight=weights)
loss = orl(logits, targets)
```

The ordinal penalty penalizes directional reversals (e.g., predicting strong_buy when truth is strong_sell) more than adjacent misclassifications.

### 6.4 Calibration (`modeling/calibration.py`)

```python
from ultimate_trader.modeling.calibration import TemperatureScaler
ts = TemperatureScaler()
optimal_temp = ts.fit(model, val_loader, device)
# model.temperature is updated in-place
```

Uses L-BFGS to minimize NLL on validation set by optimizing the single temperature scalar.

### 6.5 Metrics (`modeling/metrics.py`)

```python
from ultimate_trader.modeling.metrics import (
    sharpe_ratio,          # annualized Sharpe
    sortino_ratio,         # downside-deviation Sharpe
    max_drawdown,          # peak-to-trough (expects cumulative equity)
    win_rate,              # fraction of positive returns
    directional_accuracy,  # fraction correct direction
    per_class_precision,   # precision per class
    compute_val_sharpe,    # proxy Sharpe from val labels
    summarize,             # full metrics dict
)
```

---

## 7. Training Pipeline

### Script: `scripts/train.py`

```bash
python scripts/train.py [options]
```

**CLI Arguments**:
| Flag | Default | Description |
|---|---|---|
| `--folds` | 4 | Number of walk-forward folds |
| `--epochs` | 50 | Max epochs per fold |
| `--batch-size` | 512 | Batch size |
| `--lr` | 0.0003 | Learning rate |
| `--hparam-search` | false | Run Optuna before training |
| `--no-news` | false | Skip news sentiment features |
| `--no-fundamentals` | false | Skip fundamental features |
| `--no-gdelt` | false | Skip GDELT sentiment |
| `--ensemble N` | 1 | Train N models with different seeds |
| `--compile` | false | torch.compile for ~20% speedup |
| `--device` | auto | cpu/cuda/mps |

### Training Flow

1. **Load data**: bars, sentiment, macro, fundamentals for all symbols
2. **Generate walk-forward windows**: `walk_forward_windows(dates, 18mo, 3mo, 1mo, 1mo)`
3. **For each fold**:
   a. Split into train/val/test date ranges
   b. Build training samples via `FeatureBuilder.build_training_samples()`
   c. Fit scalers on fold 0 training data only (no leakage)
   d. Create DataLoader with `WeightedRandomSampler` for class balance
   e. Train with AdamW + cosine LR schedule + gradient clipping
   f. Loss = `OrdinalReturnLoss` (FocalLoss + ordinal penalty)
   g. Early stopping on validation loss (patience=8)
   h. Temperature calibration via L-BFGS on validation set
   i. Evaluate on test window
4. **Save best model** to `data/models/best_model.pt`
5. **Deep Ensemble mode** (`--ensemble N`): trains N models with different seeds, saves all

### Optuna Hyperparameter Search

When `--hparam-search` is used, runs on fold 0 only:
- 80 trials by default
- Optimizes validation Sharpe ratio
- Search space: lr, hidden_dim, num_layers, dropout, price_window, r_hi, kelly_fraction, min_confidence, stop_loss, take_profit, max_single_position

---

## 8. Backtesting Engine

### Script: `scripts/backtest.py`

```bash
python scripts/backtest.py --checkpoint data/models/best_model.pt [options]
```

**CLI Arguments**:
| Flag | Default | Description |
|---|---|---|
| `--checkpoint` | required | Path to model .pt file |
| `--start` | "2022-01-01" | Backtest start date |
| `--end` | today | Backtest end date |
| `--equity` | 100000 | Starting capital |
| `--no-news` | false | Skip news features |
| `--output-dir` | "data/backtest" | Output directory |
| `--mc-samples` | 50 | MC Dropout samples |

### Backtester Class (`evaluation/backtester.py`)

```python
bt = Backtester(cfg)
result = bt.run(predictions, price_data, regime_series, initial_equity=100_000)
# result = {
#     "equity_curve": pd.DataFrame,  # columns: date, equity
#     "trades": pd.DataFrame,        # columns: symbol, entry_date, exit_date, entry_price, exit_price, pnl, pnl_pct, exit_reason
#     "metrics": dict,               # total_return, sharpe, sortino, max_drawdown, win_rate, n_trades, final_equity
# }
```

**Parameters**:
- `predictions`: DataFrame with columns `[date, symbol, pred_class, confidence, uncertainty]`
- `price_data`: dict of `symbol -> pd.Series` (close prices, date-indexed)
- `regime_series`: pd.Series of regime labels per date

**Backtest Logic Per Day**:
1. Check stop-loss / take-profit on all open positions
2. Update trailing stop ratchet (30% ratchet after 1.5x stop distance in profit)
3. Execute sell signals (pred_class <= 1 OR confidence < min_confidence)
4. Execute buy signals (pred_class >= 3 AND confidence >= min_confidence)
5. Use Kelly Criterion for position sizing, ATR-based dynamic stops

---

## 9. Live Trading Execution

### Script: `scripts/run_live_bot.py`

```bash
python scripts/run_live_bot.py [options]
```

**CLI Arguments**:
| Flag | Default | Description |
|---|---|---|
| `--live` | false | Enable real money trading |
| `--now` | false | Skip timing, run immediately |
| `--no-news` | false | Skip news features |
| `--symbols` | all | Specific symbols to trade |
| `--mc-samples` | 50 | MC Dropout samples |

**Safety**: Requires BOTH `--live` CLI flag AND `trading.live: true` in config for real money.

### Daily Bot Flow

1. Wait for `trading.run_time` (default 15:45 ET) or `--now`
2. Refresh data incrementally (Alpaca bars + news)
3. Build features for all symbols
4. Detect market regime via HMM on SPY
5. Run model inference with MC Dropout uncertainty
6. Execute trades via Alpaca bracket orders
7. Log daily P&L to SQLite PerformanceDB
8. Sleep until next market day

### Executor Class (`trading/execution.py`)

```python
executor = Executor(cfg, api)
executor.run(predictions, prices, regime, model, feature_builder, bars, sentiment, macro, fundamentals)
```

- Executes bracket orders (entry + stop-loss + take-profit) via Alpaca
- Hard uncertainty gating: skips trade if uncertainty > 0.75
- Soft exit: closes position if uncertainty > 0.85
- Earnings calendar: closes positions before earnings date
- Processes exits first, then entries

### Portfolio Class (`trading/portfolio.py`)

```python
portfolio = Portfolio(cfg, api)
portfolio.reconcile()          # sync with Alpaca
is_open = portfolio.is_open("AAPL")
exposure = portfolio.get_gross_exposure()
summary = portfolio.summary()
```

Always uses Alpaca as source of truth for positions.

---

## 10. Risk Management

### RiskManager Class (`trading/risk.py`)

```python
rm = RiskManager(cfg)

# Regime-adjusted confidence threshold
min_conf = rm.min_confidence("bear")  # -> 0.75 (base 0.60 + 0.15 boost)

# Kelly Criterion position sizing
dollar_amount, shares = rm.kelly_size(
    equity=100_000,
    confidence=0.72,
    pred_class=3,         # buy
    current_price=185.50,
    regime="bull",
    stop_loss_pct=0.07,
    take_profit_pct=0.12,
)

# ATR-based stop/take prices
stop_price, take_price = rm.compute_stop_take(
    price=185.50,
    regime="bull",
    base_stop=0.07,
    base_take=0.12,
    atr_value=2.5,  # from ATR indicator
)

# Portfolio limit check
can_open = rm.check_portfolio_limits(current_exposure=0.45, equity=100_000, regime="bull")
```

### Regime Exposure Multipliers

| Regime | Exposure Mult | Confidence Boost | Effect |
|---|---|---|---|
| Bull | 1.0 | 0.0 | Full trading, normal thresholds |
| Sideways | 0.6 | +0.05 | Reduced size, slightly higher bar |
| Bear | 0.25 | +0.15 | Minimal exposure, high confidence only |
| Crisis | 0.0 | +0.25 | NO new positions, exits only |

### Kelly Criterion Sizing

```
f* = (p * b - q) / b
where:
  p = confidence (clipped to [0.01, 0.99])
  q = 1 - p
  b = take_profit_pct / stop_loss_pct

Position size = equity * f* * kelly_fraction * regime_multiplier
Capped at max_single_position (15%)
```

### ATR-Based Dynamic Stops

When ATR is available, stops scale with realized volatility:
- `stop_pct = clip(N_atr * ATR / price, 0.03, 0.12)`
- N_atr varies by regime: bull=2.5, sideways=2.0, bear=2.0, crisis=1.5
- Volatile stocks (TSLA, NVDA) get wider stops; stable stocks (JNJ, KO) get tighter

### Trailing Stop

Activates after position reaches 1.5x the stop distance in profit. Ratchets at 30% of further gains.

---

## 11. Terminal UI (TUI)

### Script: `scripts/tui.py`

```bash
python scripts/tui.py
# or
python main.py
```

Built with Textual framework. 5 tabs:

| Tab | Key | Content |
|---|---|---|
| Dashboard | 1 | Equity sparkline, regime badge, GPU monitor, model info |
| Performance | 2 | Daily P&L chart, trade history, strategy metrics |
| Positions | 3 | Live Alpaca positions with unrealized P&L |
| Signals | 4 | Today's model predictions per symbol |
| Control | 5 | Start/stop download/train/backtest/bot |

**Keybindings**: `1-5` switch tabs, `r` refresh, `q` quit, `F1` help.

---

## 12. Module Reference

### `ultimate_trader.utils.config_loader`

```python
load_config(config_dir: str = "config") -> Config
# Config supports dot notation: cfg.alpaca.key_id
```

### `ultimate_trader.utils.logging`

```python
get_logger(name: str, log_dir: str = "logs") -> logging.Logger
# Daily rotating file handler + console handler

PerformanceDB(db_path: str)
# SQLite ORM for trades, daily P&L, predictions
# Methods: log_trade(), log_daily_pnl(), log_prediction(), get_equity_curve(), get_trades()
```

### `ultimate_trader.utils.time_utils`

```python
market_date_range(start: str, end: str = None) -> pd.DatetimeIndex
# Business day range

walk_forward_windows(
    dates: pd.DatetimeIndex,
    train_months: int = 18,
    val_months: int = 3,
    test_months: int = 1,
    step_months: int = 1,
) -> List[Tuple[DatetimeIndex, DatetimeIndex, DatetimeIndex]]
# Returns (train, val, test) date index tuples

is_market_open() -> bool
# True if 9:30-16:00 ET weekday

next_market_open() -> datetime
# Next 9:30 ET
```

### `ultimate_trader.modeling.model`

```python
# Regime index mapping
REGIME_TO_IDX = {"unknown": 0, "bull": 1, "bear": 2, "sideways": 3, "crisis": 4}

# Build model from config
build_model(cfg, n_symbols, n_sectors, tech_dim, sent_dim, macro_dim, fund_dim=6) -> UltraTradingModel

# Ensemble wrapper
EnsembleModel(models: List[UltraTradingModel])
```

---

## 13. Data Flow Diagrams

### Training Data Flow

```
Alpaca API                yfinance          GDELT API        Alpaca News API
    |                        |                  |                   |
    v                        v                  v                   v
MarketDataFetcher    FundamentalsFetcher    GDELTFetcher       NewsFetcher
    |                        |                  |                   |
    v                        v                  v                   v
data/raw/bars/        fundamentals dict     gdelt_df          sentiment dict
{symbol}.parquet      {symbol: DataFrame}   (date-indexed)    {symbol: DataFrame}
    |                        |                  |                   |
    +----------+-------------+---------+--------+-------------------+
               |                       |
               v                       v
         add_technicals()        AltDataBuilder.build()
               |                       |
               v                       v
         bars + 42 indicators    macro_df (14 features)
               |                       |
               +----------+------------+
                          |
                          v
                  FeatureBuilder.build_training_samples()
                          |
                          v
              samples: List[dict], labels: List[int]
                          |
                          v
                    DataLoader + WeightedRandomSampler
                          |
                          v
                  UltraTradingModel.forward()
                          |
                          v
                  OrdinalReturnLoss (Focal + ordinal)
                          |
                          v
                  AdamW + cosine LR + gradient clipping
                          |
                          v
                  data/models/best_model.pt
```

### Inference Data Flow (Live Bot)

```
Alpaca API (incremental refresh)
    |
    v
bars, sentiment, macro, fundamentals
    |
    v
FeatureBuilder.build_features()     RegimeDetector.current_regime()
    |                                       |
    v                                       v
features dict                          regime: str
    |                                       |
    v                                       v
model.predict_with_uncertainty()    RiskManager.kelly_size()
    |                                       |
    v                                       v
(mean_probs, uncertainty)           (dollar_amount, shares)
    |                                       |
    +-------------------+-------------------+
                        |
                        v
              Executor.run() -> Alpaca bracket orders
                        |
                        v
              PerformanceDB.log_trade()
```

---

## 14. Critical Invariants and Pitfalls

### Must-Obey Rules

1. **Scaler leakage**: Scalers MUST be fitted on training data only. Never call `fit_scalers()` on validation/test data.

2. **Lookahead bias in fundamentals**: The 45-day filing delay in `fundamentals.py` is intentional. Do not remove it.

3. **Regime index mapping**: Use `REGIME_TO_IDX` from `model.py`. The model expects: 0=unknown, 1=bull, 2=bear, 3=sideways, 4=crisis.

4. **Forward signature**: The model's `forward()` uses named args `tech, sent, macro, fund, sym_idx, sec_idx, regime_idx`. NOT `price_seq`, `sent_seq`, etc.

5. **Live trading double-gate**: Both `trading.live: true` in config AND `--live` CLI flag must be set. Never bypass this.

6. **Paper trading default**: `alpaca.base_url` defaults to `https://paper-api.alpaca.markets`. Changing this to the live URL enables real money.

7. **Class ordering**: 0=strong_sell, 1=sell, 2=hold, 3=buy, 4=strong_buy. The backtester and executor depend on this ordering.

8. **Temperature scaling**: `model.temperature` has `requires_grad=False` by default. `TemperatureScaler.fit()` temporarily enables gradient and optimizes via L-BFGS.

9. **MC Dropout**: `model.train()` is called during inference to keep dropout active. `model.eval()` is called when done. This is intentional for uncertainty estimation.

10. **TECH_FEATURES list**: If you add/remove technical indicators, you MUST update `TECH_FEATURES` in `feature_builder.py` AND update `tech_dim` passed to `build_model()`.

### Common Mistakes to Avoid

- **Wrong feature dimensions**: `tech_dim`, `sent_dim`, `macro_dim`, `fund_dim` passed to `build_model()` MUST match the actual feature counts in the data.
- **Missing fillna**: `add_technicals()` fills NaN with 0. If you bypass this, the model will get NaN inputs.
- **Mismatched date indices**: All DataFrames (bars, sentiment, macro) must be date-indexed. The FeatureBuilder aligns them via `.reindex()`.
- **Sector ETF map**: `SECTOR_ETF_MAP` in `feature_builder.py` is hardcoded. New symbols must be added here.
- **HMM instability**: The regime detector can fail with `ValueError: array must not contain infs or NaNs` on very short or synthetic data. Use at least 500+ days of real SPY data.
- **Backtester input format**: `predictions` must be a DataFrame with columns `[date, symbol, pred_class, confidence, uncertainty]`, NOT a dict.

---

## 15. Dependencies

Full list in `requirements.txt`:

### Core ML
- `torch>=2.2.0` -- neural network framework
- `numpy>=1.26.0` -- numerical computing
- `pandas>=2.1.0` -- data manipulation
- `scikit-learn>=1.4.0` -- RobustScaler, preprocessing
- `scipy>=1.12.0` -- L-BFGS optimizer (calibration)
- `pyarrow>=14.0.0` -- Parquet I/O

### Trading
- `alpaca-trade-api>=3.0.0` -- REST API client
- `alpaca-py>=0.20.0` -- official Alpaca SDK

### NLP
- `transformers>=4.38.0` -- FinBERT model
- `sentencepiece` -- tokenizer dependency

### Feature Engineering
- `hmmlearn>=0.3.0` -- Hidden Markov Model for regime detection

### Hyperparameter Search
- `optuna>=3.5.0` -- Bayesian optimization

### Explainability
- `shap>=0.44.0` -- SHAP DeepExplainer

### Data/Storage
- `sqlalchemy>=2.0.0` -- ORM for SQLite
- `pyyaml>=6.0.1` -- config parsing
- `python-dotenv>=1.0.0` -- .env file loading
- `tqdm>=4.66.0` -- progress bars
- `joblib>=1.3.0` -- parallel processing
- `yfinance>=0.2.36` -- fundamental data

### Alternative Data
- `httpx>=0.27.0` -- async HTTP
- `gdeltdoc>=1.0.0` -- GDELT API
- `trafilatura>=1.9.0` -- web scraping
- `curl_cffi>=0.7.0` -- rate-limit handling

### UI
- `textual>=0.60.0` -- terminal UI framework
- `plotext>=5.2.8` -- terminal charts

### Visualization
- `matplotlib>=3.8.0` -- plotting
- `plotly>=5.19.0` -- interactive charts

---

## 16. Testing

### Test Suite: `test_all.py`

Run with: `python test_all.py`

15 tests covering all modules:

| # | Test | What It Validates |
|---|---|---|
| 1 | Config loader | YAML parsing, dot notation, all sections present |
| 2 | Logging/PerformanceDB | Logger creation, SQLite DB initialization |
| 3 | Time utilities | Business day ranges, walk-forward window generation |
| 4 | Technical indicators | 42 indicators computed from synthetic OHLCV |
| 5 | Regime detector | HMM fit/predict, unfitted fallback behavior |
| 6 | Model forward pass | build_model(), 6M param model, (4, 5) output shape |
| 7 | Loss functions | FocalLoss, OrdinalReturnLoss, class weight computation |
| 8 | Evaluation metrics | Sharpe, Sortino, max drawdown, win rate |
| 9 | Temperature scaling | TemperatureScaler init, temperature parameter exists |
| 10 | Backtester | Full backtest with synthetic data, equity curve, trades |
| 11 | Risk manager | Kelly sizing, regime scaling, stop/take computation |
| 12 | Feature builder | Initialization, synthetic data shapes |
| 13 | Import all modules | All 20+ package modules importable |
| 14 | Script imports | All 5 scripts loadable as modules |
| 15 | PyTorch/CUDA | Version detection, device availability |

All tests use synthetic data and require no API keys or external services.
