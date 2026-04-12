# ARCHIVED: legacy backtest harness — superseded by scripts/model/* runners
"""Run a full historical backtest.

Steps:
  1. Load market data from cache (run download_data.py first)
  2. Load the trained model checkpoint
  3. Run model inference over all historical dates to generate predictions
  4. Pass predictions to Backtester to simulate trading
  5. Print metrics and save equity_curve.csv + trades.csv

Usage:
    python scripts/backtest.py
    python scripts/backtest.py --checkpoint data/models/fold_2.pt
    python scripts/backtest.py --start 2022-01-01 --end 2024-01-01
    python scripts/backtest.py --equity 50000
"""
import argparse
import os
import sys
import json
import numpy as np
import pandas as pd
import torch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from ultimate_trader.utils.config_loader import load_config
from ultimate_trader.utils.logging import get_logger
from ultimate_trader.data_sources.alpaca_market import MarketDataFetcher
from ultimate_trader.data_sources.alpaca_news import NewsFetcher
from ultimate_trader.data_sources.alt_data import AltDataBuilder
from ultimate_trader.features.feature_builder import FeatureBuilder
from ultimate_trader.features.regimes import RegimeDetector
from ultimate_trader.modeling.model import build_model
from ultimate_trader.evaluation.backtester import Backtester

log = get_logger("backtest")


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--config", default="config")
    p.add_argument("--checkpoint", default=None,
                   help="Path to model checkpoint (default: data/models/best_model.pt)")
    p.add_argument("--start", default=None, help="Backtest start date YYYY-MM-DD")
    p.add_argument("--end", default=None, help="Backtest end date YYYY-MM-DD")
    p.add_argument("--equity", type=float, default=100_000.0, help="Initial equity")
    p.add_argument("--no-news", action="store_true", help="Skip FinBERT, use zero sentiment")
    p.add_argument("--output-dir", default="data/backtest_results")
    p.add_argument("--mc-samples", type=int, default=30,
                   help="MC Dropout samples for uncertainty estimation")
    return p.parse_args()


@torch.no_grad()
def run_inference(model, fb, bars, sentiment, macro_df,
                  symbols, symbol_to_idx, symbol_to_sector,
                  dates, device, mc_samples=30, fundamentals=None):
    """
    Run model inference on each date in `dates`.
    Returns a DataFrame with columns:
        [date, symbol, pred_class, confidence, uncertainty, probs_...]
    """
    records = []

    for date in dates:
        ts = pd.Timestamp(date)
        date_bars = {sym: df[df.index <= ts] for sym, df in bars.items() if sym in symbols}

        valid_syms = [
            s for s, df in date_bars.items()
            if len(df) >= fb.price_window
        ]
        if not valid_syms:
            continue

        features, _ = fb.build_features(
            bars=date_bars,
            sentiment=sentiment,
            macro_df=macro_df,
            symbols=valid_syms,
            symbol_to_idx=symbol_to_idx,
            symbol_to_sector=symbol_to_sector,
            fundamentals=fundamentals,
            fit=False,
        )

        for symbol, feat in features.items():
            tech = torch.tensor(feat["tech"], dtype=torch.float32).unsqueeze(0).to(device)
            sent = torch.tensor(feat["sent"], dtype=torch.float32).unsqueeze(0).to(device)
            macro = torch.tensor(feat["macro"], dtype=torch.float32).unsqueeze(0).to(device)
            fund = torch.tensor(feat.get("fund", [0.0] * 6), dtype=torch.float32).unsqueeze(0).to(device)
            sym_idx = torch.tensor([feat["sym_idx"]], dtype=torch.long).to(device)
            sec_idx = torch.tensor([feat["sec_idx"]], dtype=torch.long).to(device)
            regime_idx = torch.tensor([0], dtype=torch.long).to(device)

            mean_probs, uncertainty = model.predict_with_uncertainty(
                tech, sent, macro, fund, sym_idx, sec_idx, regime_idx,
                n_samples=mc_samples,
            )
            probs = mean_probs.squeeze(0).cpu().numpy()
            pred_class = int(probs.argmax())
            confidence = float(probs.max())
            unc = float(uncertainty.squeeze(0).cpu())

            row = {
                "date": date,
                "symbol": symbol,
                "pred_class": pred_class,
                "confidence": confidence,
                "uncertainty": unc,
            }
            for i, p in enumerate(probs):
                row[f"prob_{i}"] = round(float(p), 5)
            records.append(row)

    return pd.DataFrame(records)


def main():
    args = parse_args()
    cfg = load_config(args.config)
    os.makedirs(args.output_dir, exist_ok=True)

    ckpt_path = args.checkpoint or os.path.join(cfg.paths.models_dir, "best_model.pt")
    if not os.path.exists(ckpt_path):
        log.error(f"Checkpoint not found: {ckpt_path}. Run scripts/train.py first.")
        sys.exit(1)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    log.info(f"Using device: {device}")

    # ---- Load data ----
    log.info("Loading market data from cache...")
    market = MarketDataFetcher(cfg)
    all_syms = (
        list(cfg.universe.symbols)
        + [cfg.universe.benchmark]
        + list(cfg.universe.sector_etfs)
        + list(cfg.universe.macro_tickers)
        + [cfg.universe.vix_ticker]
    )
    bars = market.fetch(list(dict.fromkeys(s for s in all_syms if s)))

    alt = AltDataBuilder(cfg)
    macro_df = alt.build_macro_features(bars)

    if args.no_news or not cfg.news.enabled:
        sentiment = {}
    else:
        news = NewsFetcher(cfg)
        sentiment = news.fetch_and_score(list(cfg.universe.symbols))

    # ---- Load checkpoint ----
    log.info(f"Loading checkpoint: {ckpt_path}")
    ckpt = torch.load(ckpt_path, map_location=device)
    symbol_to_idx = ckpt["symbol_to_idx"]
    symbol_to_sector = ckpt["symbol_to_sector"]
    n_symbols = ckpt["n_symbols"]
    n_sectors = ckpt["n_sectors"]
    tech_dim = ckpt["tech_dim"]
    sent_dim = ckpt["sent_dim"]
    macro_dim = ckpt["macro_dim"]

    fund_dim = ckpt.get("fund_dim", 6)
    model = build_model(cfg, n_symbols, n_sectors, tech_dim, sent_dim, macro_dim, fund_dim).to(device)
    model.load_state_dict(ckpt["model_state"])
    # Restore calibrated temperature if saved
    if "temperature" in ckpt:
        with torch.no_grad():
            model.temperature.fill_(ckpt["temperature"])
    model.eval()
    log.info(f"Model loaded (fold {ckpt.get('fold', '?')}, val_acc={ckpt.get('val_acc', 0):.4f}, "
             f"T={model.temperature.item():.3f})")

    # ---- Load scalers ----
    fb = FeatureBuilder(cfg)
    fb.load_scalers()

    # ---- Fit regime detector ----
    spy_bars = bars.get("SPY")
    regime_detector = RegimeDetector()
    regime_path = os.path.join(cfg.paths.models_dir, "regime_detector.pkl")
    if os.path.exists(regime_path):
        regime_detector.load(regime_path)
    elif spy_bars is not None:
        regime_detector.fit(spy_bars)

    # ---- Date range ----
    symbols = [s for s in cfg.universe.symbols if s in bars]
    if spy_bars is not None:
        all_dates = spy_bars.index
    else:
        all_dates = next(iter(bars.values())).index

    start = pd.Timestamp(args.start) if args.start else all_dates.min()
    end = pd.Timestamp(args.end) if args.end else all_dates.max()
    bt_dates = all_dates[(all_dates >= start) & (all_dates <= end)]

    log.info(f"Backtest range: {bt_dates[0].date()} -> {bt_dates[-1].date()} "
             f"({len(bt_dates)} trading days)")

    # ---- Run inference ----
    log.info("Running model inference over backtest period...")
    predictions_df = run_inference(
        model, fb, bars, sentiment, macro_df,
        symbols, symbol_to_idx, symbol_to_sector,
        bt_dates, device, mc_samples=args.mc_samples,
        fundamentals=None,  # not used in backtest by default
    )
    log.info(f"Generated {len(predictions_df)} predictions across {len(bt_dates)} dates")

    # ---- Regime series ----
    regime_series = regime_detector.predict(spy_bars) if spy_bars is not None else pd.Series()

    # ---- Price data for backtester ----
    price_data = {sym: bars[sym]["close"] for sym in symbols if sym in bars}

    # ---- Run backtest ----
    log.info("Running backtest simulation...")
    backtester = Backtester(cfg)
    results = backtester.run(
        predictions=predictions_df,
        price_data=price_data,
        regime_series=regime_series,
        initial_equity=args.equity,
    )

    # ---- Save results ----
    eq_path = os.path.join(args.output_dir, "equity_curve.csv")
    trades_path = os.path.join(args.output_dir, "trades.csv")
    metrics_path = os.path.join(args.output_dir, "metrics.json")
    preds_path = os.path.join(args.output_dir, "predictions.csv")

    results["equity_curve"].to_csv(eq_path)
    if not results["trades"].empty:
        results["trades"].to_csv(trades_path, index=False)
    with open(metrics_path, "w") as f:
        json.dump(results["metrics"], f, indent=2)
    predictions_df.to_csv(preds_path, index=False)

    # ---- Print summary ----
    m = results["metrics"]
    print("\n" + "=" * 55)
    print(f"  BACKTEST RESULTS  ({bt_dates[0].date()} -> {bt_dates[-1].date()})")
    print("=" * 55)
    print(f"  Total Return : {m['total_return']:+.2%}")
    print(f"  Sharpe Ratio : {m['sharpe']:.3f}")
    print(f"  Sortino Ratio: {m['sortino']:.3f}")
    print(f"  Max Drawdown : {m['max_drawdown']:.2%}")
    print(f"  Win Rate     : {m['win_rate']:.2%}")
    print(f"  # Trades     : {m['n_trades']}")
    print(f"  Final Equity : ${m['final_equity']:,.2f}")
    print("=" * 55)
    print(f"\n  Results saved to: {args.output_dir}/")


if __name__ == "__main__":
    main()
