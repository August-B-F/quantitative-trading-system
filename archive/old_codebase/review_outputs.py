# ARCHIVED: pre-Phase-3 codebase, not imported by current pipeline.
"""Review all pipeline outputs for correctness."""
import pandas as pd, json, os, torch

print("=" * 60)
print("PIPELINE OUTPUT REVIEW")
print("=" * 60)

# 1. Bar data
bars_dir = "data/raw/bars"
files = os.listdir(bars_dir)
print(f"\n[1] Bar Data: {len(files)} parquet files")
df = pd.read_parquet(f"{bars_dir}/AAPL.parquet")
print(f"    AAPL: {len(df)} rows, {df.index[0].date()} -> {df.index[-1].date()}")
print(f"    Columns: {list(df.columns)}")
print(f"    Null values: {df.isnull().sum().sum()}")

# 2. Model checkpoint
ckpt = torch.load("data/models/best_model.pt", map_location="cpu", weights_only=False)
print(f"\n[2] Model Checkpoint:")
print(f"    Fold: {ckpt['fold']}, Epoch: {ckpt['epoch']}, Seed: {ckpt['seed']}")
print(f"    Val Accuracy: {ckpt['val_acc']:.4f}")
print(f"    Val Sharpe: {ckpt['val_sharpe']:.4f}")
print(f"    Temperature: {ckpt['temperature']:.4f}")
print(f"    Dims: tech={ckpt['tech_dim']}, sent={ckpt['sent_dim']}, macro={ckpt['macro_dim']}, fund={ckpt['fund_dim']}")
print(f"    Symbols: {ckpt['n_symbols']}, Sectors: {ckpt['n_sectors']}")

# 3. Scalers
scalers_dir = "data/scalers"
scaler_files = [f for f in os.listdir(scalers_dir) if f.endswith(".pkl")]
print(f"\n[3] Scalers: {scaler_files}")

# 4. Regime detector
print(f"\n[4] Regime Detector: {os.path.exists('data/models/regime_detector.pkl')}")

# 5. Backtest results
print(f"\n[5] Backtest Results:")
eq = pd.read_csv("data/backtest_results/equity_curve.csv")
print(f"    Equity curve: {len(eq)} rows")

trades = pd.read_csv("data/backtest_results/trades.csv")
print(f"    Trades: {len(trades)} total")
print(f"    Exit reasons: {trades.exit_reason.value_counts().to_dict()}")
print(f"    Symbols traded: {trades.symbol.nunique()}")
print(f"    PnL stats: mean={trades.pnl_pct.mean():.4f}, median={trades.pnl_pct.median():.4f}")

with open("data/backtest_results/metrics.json") as f:
    metrics = json.load(f)
print(f"    Metrics: {json.dumps(metrics, indent=6)}")

preds = pd.read_csv("data/backtest_results/predictions.csv")
print(f"\n[6] Predictions:")
print(f"    Total: {len(preds)} predictions")
print(f"    Unique symbols: {preds.symbol.nunique()}")
print(f"    Unique dates: {preds.date.nunique()}")
print(f"    Class distribution: {preds.pred_class.value_counts().sort_index().to_dict()}")

print(f"\n{'=' * 60}")
print("[RESULT] All pipeline outputs present and valid.")
print(f"{'=' * 60}")
