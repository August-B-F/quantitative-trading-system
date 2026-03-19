"""Fetch OHLCV bars, sector ETFs, macro tickers from Alpaca Market Data v2."""
import os
import pandas as pd
from datetime import datetime
from typing import List, Optional
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from ultimate_trader.utils.logging import get_logger
from ultimate_trader.utils.config_loader import Config

logger = get_logger(__name__)


class MarketDataFetcher:
    """
    Fetches and caches OHLCV bar data for any list of symbols from Alpaca.
    All data is saved as parquet to data/raw/bars/{symbol}.parquet for fast reuse.
    """

    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.client = StockHistoricalDataClient(
            cfg.alpaca.key_id, cfg.alpaca.secret_key
        )
        self.raw_dir = os.path.join(cfg.paths.raw_dir, "bars")
        os.makedirs(self.raw_dir, exist_ok=True)

    def fetch(self, symbols: List[str], start: str = None, end: str = None,
              force_refresh: bool = False) -> dict:
        """
        Returns a dict of {symbol: pd.DataFrame} with columns:
            open, high, low, close, volume, vwap, trade_count
        Indexed by date.
        """
        start = start or self.cfg.data.start_date
        end = end or datetime.today().strftime("%Y-%m-%d")

        result = {}
        for symbol in symbols:
            cache_path = os.path.join(self.raw_dir, f"{symbol}.parquet")

            # Use cache unless force_refresh or cache missing
            if os.path.exists(cache_path) and not force_refresh:
                df = pd.read_parquet(cache_path)
                # Only refetch if we are missing recent data
                if pd.Timestamp(end) <= df.index.max():
                    result[symbol] = df
                    logger.debug(f"Loaded {symbol} from cache ({len(df)} rows)")
                    continue

            try:
                req = StockBarsRequest(
                    symbol_or_symbols=symbol,
                    timeframe=TimeFrame.Day,
                    start=pd.Timestamp(start, tz="America/New_York"),
                    end=pd.Timestamp(end, tz="America/New_York"),
                    adjustment="all",  # split + dividend adjusted
                )
                bars = self.client.get_stock_bars(req).df

                if bars.empty:
                    logger.warning(f"No data returned for {symbol}")
                    continue

                # Flatten multi-index if needed
                if isinstance(bars.index, pd.MultiIndex):
                    bars = bars.xs(symbol, level="symbol")

                bars.index = pd.to_datetime(bars.index).normalize()
                bars = bars.sort_index()
                bars.to_parquet(cache_path)
                result[symbol] = bars
                logger.info(f"Fetched {symbol}: {len(bars)} bars ({start} -> {end})")

            except Exception as e:
                logger.error(f"Failed to fetch {symbol}: {e}")

        return result

    def fetch_all(self, force_refresh: bool = False) -> dict:
        """Fetch all symbols defined in config (stocks + benchmark + sectors + macro)."""
        all_symbols = (
            list(self.cfg.universe.symbols)
            + [self.cfg.universe.benchmark]
            + list(self.cfg.universe.sector_etfs)
            + list(self.cfg.universe.macro_tickers)
            + [self.cfg.universe.vix_ticker]
        )
        # Remove any None or empty
        all_symbols = [s for s in all_symbols if s]
        return self.fetch(all_symbols, force_refresh=force_refresh)

    def get_latest_prices(self, symbols: List[str]) -> dict:
        """
        Returns {symbol: latest_close_price} from cached data.
        Always use Alpaca live quote in execution, not this.
        """
        bars = self.fetch(symbols)
        return {sym: df["close"].iloc[-1] for sym, df in bars.items()}
