"""
alpaca_market.py

Fetches OHLCV bars, benchmark/sector ETF data, and options sentiment
from the Alpaca Market Data v2 API.
All data is saved as Parquet files for fast loading.
"""

import os
import time
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Optional

from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest, StockLatestTradeRequest
from alpaca.data.timeframe import TimeFrame
from alpaca.trading.client import TradingClient

from ultimate_trader.utils.logging import get_logger
from ultimate_trader.utils.config_loader import Config

logger = get_logger("alpaca_market")


class MarketDataFetcher:
    """
    Wraps Alpaca Data v2 to download and cache daily OHLCV bars
    for every symbol in the universe, plus benchmark and sector ETFs.
    """

    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.client = StockHistoricalDataClient(
            api_key=cfg.alpaca.key_id,
            secret_key=cfg.alpaca.secret_key,
        )
        self.trading_client = TradingClient(
            api_key=cfg.alpaca.key_id,
            secret_key=cfg.alpaca.secret_key,
            paper=not cfg.trading.live,
        )
        self.raw_dir = cfg.paths.raw_dir
        os.makedirs(self.raw_dir, exist_ok=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fetch_all(self, symbols: List[str], start: str, end: Optional[str] = None) -> None:
        """
        Download daily bars for all symbols + benchmark + sector ETFs.
        Saves each symbol as data/raw/bars_{SYMBOL}.parquet.
        Only downloads missing/new dates (incremental).
        """
        end = end or datetime.today().strftime("%Y-%m-%d")
        all_symbols = list(set(symbols
                                + [self.cfg.universe.benchmark]
                                + self.cfg.universe.sector_etfs))

        for sym in all_symbols:
            self._fetch_symbol(sym, start, end)

    def get_bars(self, symbol: str) -> pd.DataFrame:
        """
        Load cached bars for a symbol. Returns DataFrame with
        columns: [open, high, low, close, volume, vwap, trade_count]
        indexed by date string YYYY-MM-DD.
        """
        path = self._bar_path(symbol)
        if not os.path.exists(path):
            raise FileNotFoundError(f"No bar data for {symbol}. Run fetch_all first.")
        df = pd.read_parquet(path)
        df.index = pd.to_datetime(df.index)
        return df.sort_index()

    def get_latest_price(self, symbol: str) -> float:
        """
        Get real-time last trade price via Alpaca API.
        Uses this instead of reading CSV (avoids stale data bug from old bot).
        """
        req = StockLatestTradeRequest(symbol_or_symbols=symbol)
        trade = self.client.get_stock_latest_trade(req)
        return float(trade[symbol].price)

    def get_account(self):
        return self.trading_client.get_account()

    def get_positions(self) -> dict:
        """
        Returns dict: {symbol: {qty, avg_entry_price, current_price, market_value}}
        Always uses Alpaca as source of truth — never a local file.
        """
        positions = self.trading_client.get_all_positions()
        return {
            p.symbol: {
                "qty": float(p.qty),
                "avg_entry_price": float(p.avg_entry_price),
                "current_price": float(p.current_price),
                "market_value": float(p.market_value),
                "side": p.side,
            }
            for p in positions
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _fetch_symbol(self, symbol: str, start: str, end: str) -> None:
        path = self._bar_path(symbol)
        existing = None

        if os.path.exists(path):
            existing = pd.read_parquet(path)
            existing.index = pd.to_datetime(existing.index)
            last_date = existing.index.max()
            # Only fetch the gap
            new_start = (last_date + timedelta(days=1)).strftime("%Y-%m-%d")
            if new_start > end:
                logger.debug(f"{symbol}: already up to date.")
                return
            start = new_start

        logger.info(f"Fetching bars for {symbol} from {start} to {end}")
        try:
            req = StockBarsRequest(
                symbol_or_symbols=symbol,
                timeframe=TimeFrame.Day,
                start=datetime.strptime(start, "%Y-%m-%d"),
                end=datetime.strptime(end, "%Y-%m-%d"),
            )
            bars = self.client.get_stock_bars(req).df

            if bars.empty:
                logger.warning(f"{symbol}: empty response for {start}–{end}")
                return

            # Flatten multi-index if present
            if isinstance(bars.index, pd.MultiIndex):
                bars = bars.xs(symbol, level="symbol")

            bars.index = bars.index.tz_localize(None).normalize()
            bars.index.name = "date"
            bars = bars[["open", "high", "low", "close", "volume", "vwap", "trade_count"]]

            if existing is not None:
                bars = pd.concat([existing, bars]).drop_duplicates()

            bars.sort_index(inplace=True)
            bars.to_parquet(path)
            logger.info(f"{symbol}: saved {len(bars)} rows.")
            time.sleep(0.12)  # respect rate limits

        except Exception as e:
            logger.error(f"Failed to fetch {symbol}: {e}")

    def _bar_path(self, symbol: str) -> str:
        return os.path.join(self.raw_dir, f"bars_{symbol}.parquet")
