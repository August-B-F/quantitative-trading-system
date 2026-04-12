"""Fetch OHLCV bars, sector ETFs, macro tickers from Alpaca Market Data v2.

Falls back to yfinance when Alpaca API keys are not configured (placeholder values).
"""
import os
import time
import pandas as pd
from datetime import datetime
from typing import List, Optional
from ultimate_trader.utils.logging import get_logger
from ultimate_trader.utils.config_loader import Config

logger = get_logger(__name__)


def _alpaca_keys_valid(cfg: Config) -> bool:
    """Check whether Alpaca keys look real (not placeholders)."""
    key = getattr(cfg.alpaca, "key_id", "")
    secret = getattr(cfg.alpaca, "secret_key", "")
    for val in (key, secret):
        if not val or "YOUR" in val.upper() or len(val) < 10:
            return False
    return True


class MarketDataFetcher:
    """
    Fetches and caches OHLCV bar data for any list of symbols.
    Uses Alpaca Market Data v2 when API keys are configured,
    otherwise falls back to yfinance.
    All data is saved as parquet to data/raw/bars/{symbol}.parquet for fast reuse.
    """

    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.raw_dir = os.path.join(cfg.paths.raw_dir, "bars")
        os.makedirs(self.raw_dir, exist_ok=True)
        self._use_alpaca = _alpaca_keys_valid(cfg)

        if self._use_alpaca:
            from alpaca.data.historical import StockHistoricalDataClient
            self.client = StockHistoricalDataClient(
                cfg.alpaca.key_id, cfg.alpaca.secret_key
            )
            logger.info("MarketDataFetcher: using Alpaca API")
        else:
            self.client = None
            logger.info("MarketDataFetcher: Alpaca keys not set, using yfinance fallback")

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
                # Only refetch if we are missing recent data (within 3 days tolerance)
                if len(df) > 0 and (pd.Timestamp(end) - df.index.max()).days <= 3:
                    result[symbol] = df
                    logger.debug(f"Loaded {symbol} from cache ({len(df)} rows)")
                    continue

            try:
                if self._use_alpaca:
                    df = self._fetch_alpaca(symbol, start, end)
                else:
                    df = self._fetch_yfinance(symbol, start, end)

                if df is None or df.empty:
                    logger.warning(f"No data returned for {symbol}")
                    continue

                df.to_parquet(cache_path)
                result[symbol] = df
                logger.info(f"Fetched {symbol}: {len(df)} bars ({start} -> {end})")

            except Exception as e:
                logger.error(f"Failed to fetch {symbol}: {e}")

        return result

    def _fetch_alpaca(self, symbol: str, start: str, end: str) -> Optional[pd.DataFrame]:
        """Fetch from Alpaca Market Data API v2."""
        from alpaca.data.historical import StockHistoricalDataClient
        from alpaca.data.requests import StockBarsRequest
        from alpaca.data.timeframe import TimeFrame

        req = StockBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=TimeFrame.Day,
            start=pd.Timestamp(start, tz="America/New_York"),
            end=pd.Timestamp(end, tz="America/New_York"),
            adjustment="all",
        )
        bars = self.client.get_stock_bars(req).df

        if bars.empty:
            return None

        if isinstance(bars.index, pd.MultiIndex):
            bars = bars.xs(symbol, level="symbol")

        bars.index = pd.to_datetime(bars.index).normalize()
        bars = bars.sort_index()
        return bars

    def _fetch_yfinance(self, symbol: str, start: str, end: str) -> Optional[pd.DataFrame]:
        """Fetch from Yahoo Finance via yfinance library."""
        import yfinance as yf

        # Small delay between requests to be respectful
        time.sleep(0.3)

        ticker = yf.Ticker(symbol)
        df = ticker.history(start=start, end=end, auto_adjust=True)

        if df is None or df.empty:
            return None

        # Normalize column names to match Alpaca format
        df.columns = [c.lower() for c in df.columns]

        # yfinance returns: Open, High, Low, Close, Volume, Dividends, Stock Splits
        # We need: open, high, low, close, volume, vwap
        keep_cols = ["open", "high", "low", "close", "volume"]
        for col in keep_cols:
            if col not in df.columns:
                df[col] = 0.0

        # Compute approximate VWAP (typical price as proxy since we don't have intraday)
        df["vwap"] = (df["high"] + df["low"] + df["close"]) / 3.0

        # Add trade_count placeholder (not available from yfinance)
        df["trade_count"] = 0

        df = df[["open", "high", "low", "close", "volume", "vwap", "trade_count"]]

        # Normalize index to date only (no timezone)
        df.index = pd.to_datetime(df.index).normalize().tz_localize(None)
        df = df.sort_index()

        # Remove any rows with 0 close (bad data)
        df = df[df["close"] > 0]

        return df

    def fetch_all(self, force_refresh: bool = False) -> dict:
        """Fetch all symbols defined in config (stocks + benchmark + sectors + macro)."""
        all_symbols = (
            list(self.cfg.universe.symbols)
            + [self.cfg.universe.benchmark]
            + list(self.cfg.universe.sector_etfs)
            + list(self.cfg.universe.macro_tickers)
            + [self.cfg.universe.vix_ticker]
        )
        all_symbols = [s for s in all_symbols if s]
        return self.fetch(all_symbols, force_refresh=force_refresh)

    def get_latest_prices(self, symbols: List[str]) -> dict:
        """
        Returns {symbol: latest_close_price} from cached data.
        Always use Alpaca live quote in execution, not this.
        """
        bars = self.fetch(symbols)
        return {sym: df["close"].iloc[-1] for sym, df in bars.items()}
