"""Download all historical market data and score news sentiment.

Runs two things:
  1. Fetches OHLCV bars for all symbols + macro/sector ETFs from Alpaca
     and saves to data/raw/bars/{symbol}.parquet
  2. Fetches Alpaca news for all symbols, scores each article with
     FinBERT, and saves to data/raw/news/{symbol}.json

Usage:
    python scripts/download_data.py                   # incremental update
    python scripts/download_data.py --refresh         # force re-download all bars
    python scripts/download_data.py --no-news         # skip news / FinBERT
    python scripts/download_data.py --symbols AAPL MSFT  # specific symbols only
"""
import argparse
import sys
import os

# Make sure the repo root is on the path when running from scripts/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from ultimate_trader.utils.config_loader import load_config
from ultimate_trader.utils.logging import get_logger
from ultimate_trader.data_sources.alpaca_market import MarketDataFetcher
from ultimate_trader.data_sources.alpaca_news import NewsFetcher

log = get_logger("download_data")


def parse_args():
    p = argparse.ArgumentParser(description="Download market data + score news")
    p.add_argument("--config", default="config", help="Config directory (default: config)")
    p.add_argument("--refresh", action="store_true", help="Force re-download all bar data")
    p.add_argument("--no-news", action="store_true", help="Skip news fetching / FinBERT scoring")
    p.add_argument("--symbols", nargs="+", default=None,
                   help="Override universe - only download these symbols")
    p.add_argument("--lookback-days", type=int, default=None,
                   help="Override news lookback window in days")
    return p.parse_args()


def main():
    args = parse_args()
    cfg = load_config(args.config)

    # Determine symbol list
    if args.symbols:
        symbols = args.symbols
        log.info(f"Overriding universe with {len(symbols)} symbols: {symbols}")
    else:
        symbols = list(cfg.universe.symbols)

    # All tickers we need bars for (stocks + benchmark + macro + sectors)
    all_bar_tickers = (
        symbols
        + [cfg.universe.benchmark]
        + list(cfg.universe.sector_etfs)
        + list(cfg.universe.macro_tickers)
        + [cfg.universe.vix_ticker]
    )
    all_bar_tickers = list(dict.fromkeys(t for t in all_bar_tickers if t))  # dedup, preserve order

    # 1. Market bars
    log.info(f"Fetching bars for {len(all_bar_tickers)} tickers (force_refresh={args.refresh})...")
    market = MarketDataFetcher(cfg)
    bars = market.fetch(all_bar_tickers, force_refresh=args.refresh)
    log.info(f"Bars done: {len(bars)}/{len(all_bar_tickers)} symbols fetched successfully")

    # Quick summary
    if bars:
        sample = next(iter(bars.values()))
        log.info(f"Date range in data: {sample.index.min().date()} -> {sample.index.max().date()}")

    # 2. News + FinBERT sentiment
    if not args.no_news and cfg.news.enabled:
        lookback = args.lookback_days or cfg.news.lookback_days
        log.info(f"Fetching + scoring news for {len(symbols)} symbols "
                 f"(lookback={lookback} days)...")
        news_fetcher = NewsFetcher(cfg)
        sentiment = news_fetcher.fetch_and_score(symbols, lookback_days=lookback)
        scored = sum(1 for df in sentiment.values() if df is not None and not df.empty)
        log.info(f"News scoring done: {scored}/{len(symbols)} symbols have sentiment data")
    else:
        log.info("Skipping news (--no-news or news.enabled=false in config)")

    log.info("download_data.py complete.")


if __name__ == "__main__":
    main()
