"""Fetch OHLCV bars, benchmark, and sector ETF data from Alpaca Market Data v2."""
import os
import time
import datetime
import pandas as pd
from pathlib import Path
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from ultimate_trader.utils.logging import get_logger

logger = get_logger("alpaca_market")


def get_client(api_key: str, secret_key: str) -> StockHistoricalDataClient:
    return StockHistoricalDataClient(api_key, secret_key)


def fetch_bars(
    client: StockHistoricalDataClient,
    symbols: list,
    start: str,
    end: str = None,
    timeframe: TimeFrame = TimeFrame.Day,
    raw_dir: str = "data/raw/bars",
) -> dict:
    """
    Fetch daily OHLCV bars for a list of symbols.
    Returns dict: {symbol: pd.DataFrame}
    Saves CSVs to raw_dir.
    """
    Path(raw_dir).mkdir(parents=True, exist_ok=True)
    end = end or datetime.date.today().isoformat()
    results = {}

    for symbol in symbols:
        logger.info(f"Fetching bars: {symbol} from {start} to {end}")
        try:
            request = StockBarsRequest(
                symbol_or_symbols=symbol,
                timeframe=timeframe,
                start=start,
                end=end,
                adjustment="all",  # split and dividend adjusted
            )
            bars = client.get_stock_bars(request).df

            if isinstance(bars.index, pd.MultiIndex):
                bars = bars.xs(symbol, level="symbol")

            bars.index = pd.to_datetime(bars.index).tz_localize(None)
            bars.index.name = "date"
            bars = bars[["open", "high", "low", "close", "volume", "trade_count", "vwap"]]

            out_path = Path(raw_dir) / f"{symbol}.csv"
            bars.to_csv(out_path)
            results[symbol] = bars
            logger.info(f"  Saved {len(bars)} rows for {symbol}")
            time.sleep(0.1)  # rate limit buffer

        except Exception as e:
            logger.error(f"  Failed to fetch bars for {symbol}: {e}")
            continue

    return results


def load_bars(symbol: str, raw_dir: str = "data/raw/bars") -> pd.DataFrame:
    """Load bars for a symbol from disk."""
    path = Path(raw_dir) / f"{symbol}.csv"
    if not path.exists():
        raise FileNotFoundError(f"No bar data found for {symbol} at {path}")
    df = pd.read_csv(path, index_col="date", parse_dates=True)
    df.index = pd.to_datetime(df.index)
    return df


def fetch_all(
    cfg: dict,
    raw_dir: str = "data/raw/bars",
) -> dict:
    """Fetch bars for all symbols + benchmark + sector ETFs in config."""
    client = get_client(cfg["alpaca"]["key_id"], cfg["alpaca"]["secret_key"])
    start = cfg["data"]["start_date"]
    end = cfg["data"].get("end_date") or datetime.date.today().isoformat()

    all_symbols = (
        cfg["universe"]["symbols"]
        + [cfg["universe"]["benchmark"]]
        + cfg["universe"]["sector_etfs"]
    )
    return fetch_bars(client, all_symbols, start, end, raw_dir=raw_dir)
