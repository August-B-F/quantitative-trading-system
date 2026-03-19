"""Fetch OHLCV bars, fundamentals proxy, and index/sector data from Alpaca Market Data v2."""
import time
import pandas as pd
from pathlib import Path
from typing import Optional
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

from ultimate_trader.utils.logging import get_logger
from ultimate_trader.utils.config_loader import get_full_config

logger = get_logger(__name__)


def _get_client(cfg: dict) -> StockHistoricalDataClient:
    return StockHistoricalDataClient(
        api_key=cfg["alpaca"]["key_id"],
        secret_key=cfg["alpaca"]["secret_key"],
    )


def fetch_bars(
    symbols: list[str],
    start: str,
    end: Optional[str] = None,
    timeframe: str = "1Day",
    save_dir: str = "data/raw/bars",
) -> dict[str, pd.DataFrame]:
    """
    Download daily OHLCV bars for a list of symbols.
    Caches to CSV in save_dir. Only fetches missing/new data on re-runs.

    Args:
        symbols: list of ticker strings e.g. ['AAPL', 'MSFT']
        start: ISO date string '2018-01-01'
        end: ISO date string or None (today)
        timeframe: Alpaca timeframe string
        save_dir: directory to cache raw bar CSVs

    Returns:
        dict mapping symbol -> DataFrame with columns
        [open, high, low, close, volume, vwap, trade_count]
    """
    cfg = get_full_config()
    client = _get_client(cfg)
    Path(save_dir).mkdir(parents=True, exist_ok=True)
    tf_map = {"1Day": TimeFrame.Day, "1Hour": TimeFrame.Hour}
    tf = tf_map.get(timeframe, TimeFrame.Day)
    end_str = end or pd.Timestamp.now().strftime("%Y-%m-%d")
    result = {}

    for symbol in symbols:
        cache_path = Path(save_dir) / f"{symbol}.csv"
        existing = None

        if cache_path.exists():
            existing = pd.read_csv(cache_path, index_col=0, parse_dates=True)
            # Only fetch from the day after last cached date
            fetch_start = (existing.index.max() + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
            if fetch_start >= end_str:
                logger.info(f"{symbol}: cache up-to-date, skipping fetch")
                result[symbol] = existing
                continue
        else:
            fetch_start = start

        logger.info(f"Fetching bars for {symbol} from {fetch_start} to {end_str}")
        try:
            req = StockBarsRequest(
                symbol_or_symbols=symbol,
                timeframe=tf,
                start=fetch_start,
                end=end_str,
            )
            bars = client.get_stock_bars(req).df

            if bars.empty:
                logger.warning(f"{symbol}: no bars returned")
                if existing is not None:
                    result[symbol] = existing
                continue

            # Flatten multi-index if needed
            if isinstance(bars.index, pd.MultiIndex):
                bars = bars.xs(symbol, level="symbol")
            bars.index = pd.to_datetime(bars.index).tz_localize(None).normalize()

            # Merge with cache
            if existing is not None:
                bars = pd.concat([existing, bars]).drop_duplicates().sort_index()

            bars.to_csv(cache_path)
            result[symbol] = bars
            time.sleep(0.2)  # Avoid rate limits

        except Exception as e:
            logger.error(f"{symbol}: fetch_bars failed — {e}")
            if existing is not None:
                result[symbol] = existing

    return result


def fetch_all_universe(
    cfg: Optional[dict] = None,
) -> dict[str, pd.DataFrame]:
    """
    Convenience wrapper — fetches all symbols in config (universe + benchmark + sectors).

    Returns:
        dict of symbol -> OHLCV DataFrame
    """
    if cfg is None:
        cfg = get_full_config()
    all_symbols = (
        cfg["universe"]["symbols"]
        + [cfg["universe"]["benchmark"]]
        + cfg["universe"]["sector_etfs"]
    )
    return fetch_bars(
        symbols=all_symbols,
        start=cfg["data"]["start_date"],
        end=cfg["data"].get("end_date"),
        timeframe=cfg["data"]["bar_timeframe"],
    )
