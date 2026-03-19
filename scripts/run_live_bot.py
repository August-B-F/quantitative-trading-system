"""Daily live / paper trading bot.

Full pipeline per run:
  1. Wait until run_time (default 15:45 ET) so most price action is settled
  2. Incremental data refresh (bars + news)
  3. Build features + macro
  4. Detect current market regime via HMM
  5. Load trained model, run MC Dropout inference on all universe symbols
  6. Pass predictions to Executor -> Alpaca bracket orders
  7. Log daily P&L snapshot to SQLite

Usage:
    # Paper trade (default, uses paper-api.alpaca.markets)
    python scripts/run_live_bot.py

    # Live trade (set trading.live=true in config first!)
    python scripts/run_live_bot.py --live

    # Run immediately without waiting for run_time (for testing)
    python scripts/run_live_bot.py --now

    # Override which symbols to trade
    python scripts/run_live_bot.py --symbols AAPL MSFT NVDA

Safety:
    - Defaults to paper trading. You must explicitly pass --live AND
      set trading.live=true in config to trade real money.
    - Model checkpoint must exist (run scripts/train.py first).
    - If Alpaca reconciliation fails, the bot exits without trading.
"""
import argparse
import os
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import torch
import pandas as pd
import pytz

from ultimate_trader.utils.config_loader import load_config
from ultimate_trader.utils.logging import get_logger, PerformanceDB
from ultimate_trader.data_sources.alpaca_market import MarketDataFetcher
from ultimate_trader.data_sources.alpaca_news import NewsFetcher
from ultimate_trader.data_sources.alt_data import AltDataBuilder
from ultimate_trader.features.feature_builder import FeatureBuilder
from ultimate_trader.features.regimes import RegimeDetector
from ultimate_trader.modeling.model import build_model
from ultimate_trader.trading.portfolio import Portfolio
from ultimate_trader.trading.risk import RiskManager
from ultimate_trader.trading.execution import Executor

log = get_logger("run_live_bot")
ET = pytz.timezone("America/New_York")


def parse_args():
    p = argparse.ArgumentParser(description="Daily trading bot")
    p.add_argument("--config", default="config")
    p.add_argument("--checkpoint", default=None)
    p.add_argument("--live", action="store_true",
                   help="Enable live trading (REAL MONEY - use with caution!)")
    p.add_argument("--now", action="store_true",
                   help="Run immediately without waiting for run_time")
    p.add_argument("--no-news", action="store_true",
                   help="Skip FinBERT news scoring (faster, less accurate)")
    p.add_argument("--symbols", nargs="+", default=None,
                   help="Override universe symbol list")
    p.add_argument("--mc-samples", type=int, default=50,
                   help="MC Dropout samples for uncertainty (default: 50)")
    return p.parse_args()


def wait_for_run_time(run_time_str: str):
    """Block until the configured run_time (HH:MM ET) on the current trading day."""
    hh, mm = map(int, run_time_str.split(":"))
    while True:
        now_et = datetime.now(ET)
        target = now_et.replace(hour=hh, minute=mm, second=0, microsecond=0)
        if now_et >= target:
            log.info(f"Run time reached: {now_et.strftime('%H:%M:%S ET')}")
            return
        wait_secs = (target - now_et).total_seconds()
        log.info(f"Waiting {wait_secs/60:.1f} min until {run_time_str} ET...")
        time.sleep(min(wait_secs, 60))  # check every minute max


def is_market_day() -> bool:
    """Returns True if today is a weekday (rough check; Alpaca will reject if holiday)."""
    return datetime.now(ET).weekday() < 5


@torch.no_grad()
def run_inference(model, fb, bars, sentiment, macro_df,
                  symbols, symbol_to_idx, symbol_to_sector,
                  device, mc_samples):
    """
    Run MC Dropout inference on all symbols using TODAY's data.
    Returns dict: {symbol: {pred_class, confidence, uncertainty, probs}}
    """
    features, _ = fb.build_features(
        bars=bars,
        sentiment=sentiment,
        macro_df=macro_df,
        symbols=symbols,
        symbol_to_idx=symbol_to_idx,
        symbol_to_sector=symbol_to_sector,
        fit=False,
    )

    predictions = {}
    for symbol, feat in features.items():
        tech = torch.tensor(feat["tech"], dtype=torch.float32).unsqueeze(0).to(device)
        sent = torch.tensor(feat["sent"], dtype=torch.float32).unsqueeze(0).to(device)
        macro = torch.tensor(feat["macro"], dtype=torch.float32).unsqueeze(0).to(device)
        sym_idx = torch.tensor([feat["sym_idx"]], dtype=torch.long).to(device)
        sec_idx = torch.tensor([feat["sec_idx"]], dtype=torch.long).to(device)

        mean_probs, uncertainty = model.predict_with_uncertainty(
            tech, sent, macro, sym_idx, sec_idx, n_samples=mc_samples
        )
        probs = mean_probs.squeeze(0).cpu().numpy()
        pred_class = int(probs.argmax())
        confidence = float(probs.max())
        unc = float(uncertainty.squeeze(0).cpu())

        predictions[symbol] = {
            "pred_class": pred_class,
            "confidence": confidence,
            "uncertainty": unc,
            "probs": probs.tolist(),
        }

    return predictions


def main():
    args = parse_args()
    cfg = load_config(args.config)

    # ---- Safety check for live trading ----
    if args.live:
        if not cfg.trading.live:
            log.error(
                "--live flag passed but trading.live=false in config. "
                "Set trading.live=true in config/config.yaml to enable live trading."
            )
            sys.exit(1)
        log.warning("=" * 60)
        log.warning("  LIVE TRADING ENABLED - REAL MONEY AT RISK")
        log.warning("=" * 60)
    else:
        # Force paper even if config says live (safer default)
        cfg.trading.live = False
        log.info("Paper trading mode (pass --live to trade real money)")

    if not is_market_day():
        log.info("Today is not a trading day. Exiting.")
        sys.exit(0)

    # ---- Wait for run time ----
    if not args.now:
        wait_for_run_time(cfg.trading.run_time)
    else:
        log.info("--now flag: running immediately without waiting")

    log.info(f"Bot starting | {datetime.now(ET).strftime('%Y-%m-%d %H:%M ET')}")

    # ---- Load checkpoint ----
    ckpt_path = args.checkpoint or os.path.join(cfg.paths.models_dir, "best_model.pt")
    if not os.path.exists(ckpt_path):
        log.error(f"No model checkpoint found at {ckpt_path}. Run scripts/train.py first.")
        sys.exit(1)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    log.info(f"Loading model from {ckpt_path} on {device}")
    ckpt = torch.load(ckpt_path, map_location=device)
    symbol_to_idx = ckpt["symbol_to_idx"]
    symbol_to_sector = ckpt["symbol_to_sector"]

    model = build_model(
        cfg,
        ckpt["n_symbols"], ckpt["n_sectors"],
        ckpt["tech_dim"], ckpt["sent_dim"], ckpt["macro_dim"]
    ).to(device)
    model.load_state_dict(ckpt["model_state"])
    model.eval()
    log.info(f"Model loaded (fold={ckpt.get('fold','?')}, val_acc={ckpt.get('val_acc',0):.4f})")

    # ---- Symbol list ----
    symbols = args.symbols or list(cfg.universe.symbols)
    log.info(f"Trading universe: {len(symbols)} symbols")

    # ---- Refresh data ----
    log.info("Refreshing market data (incremental)...")
    all_tickers = (
        symbols
        + [cfg.universe.benchmark]
        + list(cfg.universe.sector_etfs)
        + list(cfg.universe.macro_tickers)
        + [cfg.universe.vix_ticker]
    )
    all_tickers = list(dict.fromkeys(t for t in all_tickers if t))
    market = MarketDataFetcher(cfg)
    bars = market.fetch(all_tickers, force_refresh=True)  # always get today's bar

    # ---- Macro features ----
    alt = AltDataBuilder(cfg)
    macro_df = alt.build_macro_features(bars)

    # ---- News sentiment ----
    if args.no_news or not cfg.news.enabled:
        sentiment = {}
        log.info("Skipping news (--no-news or news.enabled=false)")
    else:
        log.info("Fetching + scoring news...")
        news_fetcher = NewsFetcher(cfg)
        sentiment = news_fetcher.fetch_and_score(symbols, lookback_days=5)  # just last 5 days

    # ---- Load scalers ----
    fb = FeatureBuilder(cfg)
    fb.load_scalers()

    # ---- Regime ----
    spy_bars = bars.get("SPY")
    regime_detector = RegimeDetector()
    regime_path = os.path.join(cfg.paths.models_dir, "regime_detector.pkl")
    if os.path.exists(regime_path):
        regime_detector.load(regime_path)
    elif spy_bars is not None:
        log.warning("regime_detector.pkl not found, fitting on the fly from SPY...")
        regime_detector.fit(spy_bars)

    regime = regime_detector.current_regime(spy_bars) if spy_bars is not None else "sideways"
    log.info(f"Current market regime: {regime}")

    # ---- Earnings calendar ----
    log.info("Fetching earnings calendar...")
    earnings_dates = alt.get_earnings_dates(symbols)

    # ---- Run inference ----
    log.info("Running model inference...")
    valid_symbols = [s for s in symbols if s in bars]
    predictions = run_inference(
        model, fb, bars, sentiment, macro_df,
        valid_symbols, symbol_to_idx, symbol_to_sector,
        device, mc_samples=args.mc_samples
    )
    log.info(f"Inference complete: {len(predictions)} symbols scored")

    # ---- Log predictions to DB ----
    db = PerformanceDB(cfg.paths.db_path)
    for symbol, pred in predictions.items():
        db.log_prediction(
            symbol=symbol,
            pred_class=pred["pred_class"],
            confidence=pred["confidence"],
            uncertainty=pred["uncertainty"],
            regime=regime,
        )

    # ---- Execute trades ----
    portfolio = Portfolio(cfg)
    risk = RiskManager(cfg)
    executor = Executor(cfg, portfolio, risk, db)

    try:
        equity_before = portfolio.reconcile() and portfolio.equity or 0.0
    except Exception as e:
        log.error(f"Portfolio reconciliation failed: {e}. Aborting without trading.")
        sys.exit(1)

    # Re-read equity after reconcile
    equity_before = portfolio.equity

    log.info("Executing trades...")
    executor.run(
        predictions=predictions,
        regime=regime,
        earnings_dates=earnings_dates,
    )

    # ---- Log daily P&L ----
    try:
        portfolio.reconcile()
        equity_after = portfolio.equity
        pnl = equity_after - equity_before
        today_str = datetime.now(ET).strftime("%Y-%m-%d")
        db.log_daily(
            date=today_str,
            equity=equity_after,
            cash=portfolio.cash,
            pnl=pnl,
            num_trades=len([p for p in predictions.values() if p["pred_class"] in (3, 4)]),
            regime=regime,
        )
        log.info(
            f"Day complete | equity=${equity_after:,.2f} | "
            f"daily P&L=${pnl:+,.2f} | regime={regime}"
        )
    except Exception as e:
        log.warning(f"Could not log daily P&L: {e}")

    log.info("run_live_bot.py complete.")


if __name__ == "__main__":
    main()
