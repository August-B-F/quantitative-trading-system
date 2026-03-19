"""Fetch OHLCV bars and account info from Alpaca Markets Data API v2."""
import os
import time
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Optional

from ultimate_trader.utils.logging import get_logger

log = get_logger(__name__)

try:
    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.data.requests import StockBarsRequest
    from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
    _USE_ALPACA_PY = True
except ImportError:
    import alpaca_trade_api as tradeapi
    _USE_ALPACA_PY = False


def _get_client(api_key: str, secret_key: str):
    if _USE_ALPACA_PY:
        return StockHistoricalDataClient(api_key, secret_key)
    return tradeapi.REST(api_key, secret_key, base_url="https://data.alpaca.markets", api_version="v2")


def fetch_bars(
    symbols: List[str],
    start: str,
    end: Optional[str],
    api_key: str,
    secret_key: str,
    timeframe: str = "1Day",
    raw_dir: str = "data/raw/bars",
    force_refresh: bool = False,
) -> dict:
    """
    Download OHLCV bars for each symbol from Alpaca.
    Saves per-symbol CSV to raw_dir.
    Returns dict of symbol -> pd.DataFrame with columns:
        date, open, high, low, close, volume, vwap, trade_count
    """
    Path(raw_dir).mkdir(parents=True, exist_ok=True)
    end = end or datetime.now().strftime("%Y-%m-%d")
    result = {}

    client = _get_client(api_key, secret_key)

    for symbol in symbols:
        fpath = Path(raw_dir) / f"{symbol}.csv"

        if fpath.exists() and not force_refresh:
            df = pd.read_csv(fpath, parse_dates=["date"], index_col="date")
            # only refresh data after the last saved date
            last_saved = str(df.index.max().date())
            if last_saved >= end:
                result[symbol] = df
                continue
            fetch_start = str((pd.Timestamp(last_saved) + timedelta(days=1)).date())
        else:
            fetch_start = start

        try:
            log.info(f"Fetching bars for {symbol} from {fetch_start} to {end}")

            if _USE_ALPACA_PY:
                req = StockBarsRequest(
                    symbol_or_symbols=symbol,
                    timeframe=TimeFrame.Day,
                    start=fetch_start,
                    end=end,
                )
                bars = client.get_stock_bars(req).df
                if isinstance(bars.index, pd.MultiIndex):
                    bars = bars.loc[symbol]
                bars.index = pd.to_datetime(bars.index).normalize()
                bars.index.name = "date"
                bars = bars.rename(columns={
                    "open": "open", "high": "high", "low": "low",
                    "close": "close", "volume": "volume",
                    "vwap": "vwap", "trade_count": "trade_count"
                })
            else:
                raw = client.get_bars(symbol, "1Day", start=fetch_start, end=end).df
                raw.index = pd.to_datetime(raw.index).normalize()
                raw.index.name = "date"
                bars = raw

            if fpath.exists():
                old = pd.read_csv(fpath, parse_dates=["date"], index_col="date")
                bars = pd.concat([old, bars]).loc[~pd.concat([old, bars]).index.duplicated(keep="last")]

            bars.sort_index(inplace=True)
            bars.to_csv(fpath)
            result[symbol] = bars

        except Exception as e:
            log.error(f"Failed to fetch bars for {symbol}: {e}")
            if fpath.exists():
                result[symbol] = pd.read_csv(fpath, parse_dates=["date"], index_col="date")

        time.sleep(0.2)

    return result


def get_latest_prices(symbols: List[str], api_key: str, secret_key: str) -> dict:
    """
    Fetch real-time last trade price for each symbol from Alpaca.
    Returns dict of symbol -> float price.
    Always use this for live order sizing, NOT CSV data.
    """
    prices = {}
    try:
        if _USE_ALPACA_PY:
            from alpaca.data.historical import StockHistoricalDataClient
            from alpaca.data.requests import StockLatestTradeRequest
            client = StockHistoricalDataClient(api_key, secret_key)
            req = StockLatestTradeRequest(symbol_or_symbols=symbols)
            trades = client.get_stock_latest_trade(req)
            for sym, trade in trades.items():
                prices[sym] = float(trade.price)
        else:
            client = _get_client(api_key, secret_key)
            for sym in symbols:
                prices[sym] = float(client.get_latest_trade(sym).price)
                time.sleep(0.1)
    except Exception as e:
        log.error(f"Failed to get latest prices: {e}")
    return prices
