"""Fetch OHLCV bars, benchmark, and sector ETF data from Alpaca Market Data v2."""
import time
from pathlib import Path
from datetime import datetime, timedelta

import pandas as pd
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

from ultimate_trader.utils.logging import get_logger
from ultimate_trader.utils.time_utils import today_str

log = get_logger(__name__)


class MarketDataFetcher:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.client = StockHistoricalDataClient(
            api_key=cfg["alpaca"]["key_id"],
            secret_key=cfg["alpaca"]["secret_key"]
        )
        self.raw_dir = Path(cfg["paths"]["raw_dir"]) / "market"
        self.raw_dir.mkdir(parents=True, exist_ok=True)

    def fetch_bars(
        self,
        symbols: list[str],
        start: str,
        end: str | None = None,
        timeframe: str = "1Day",
        save: bool = True
    ) -> dict[str, pd.DataFrame]:
        """Fetch OHLCV bars for a list of symbols. Returns dict symbol->DataFrame."""
        end = end or today_str()
        tf = TimeFrame.Day if timeframe == "1Day" else TimeFrame.Hour

        log.info(f"Fetching bars for {len(symbols)} symbols from {start} to {end}")

        request = StockBarsRequest(
            symbol_or_symbols=symbols,
            timeframe=tf,
            start=start,
            end=end,
            adjustment="all",       # split + dividend adjusted
            feed="sip"             # consolidated tape
        )

        bars = self.client.get_stock_bars(request).df

        # Alpaca returns multi-index (symbol, timestamp) — split into per-symbol dfs
        result = {}
        for symbol in symbols:
            try:
                df = bars.loc[symbol].copy()
                df.index = pd.to_datetime(df.index).tz_localize(None)  # naive UTC dates
                df.index.name = "date"
                result[symbol] = df

                if save:
                    out_path = self.raw_dir / f"{symbol}.csv"
                    df.to_csv(out_path)
                    log.debug(f"Saved {symbol} bars to {out_path}")

            except KeyError:
                log.warning(f"No bar data returned for {symbol}")

        log.info(f"Fetched bars for {len(result)}/{len(symbols)} symbols")
        return result

    def load_bars(self, symbol: str) -> pd.DataFrame | None:
        """Load cached bars for a symbol. Returns None if not found."""
        path = self.raw_dir / f"{symbol}.csv"
        if not path.exists():
            return None
        df = pd.read_csv(path, index_col="date", parse_dates=True)
        return df

    def fetch_all(self, save: bool = True) -> dict[str, pd.DataFrame]:
        """Fetch bars for all symbols + benchmark + sector ETFs in config."""
        symbols = (
            self.cfg["universe"]["symbols"]
            + [self.cfg["universe"]["benchmark"]]
            + self.cfg["universe"]["sector_etfs"]
        )
        # Deduplicate
        symbols = list(dict.fromkeys(symbols))
        return self.fetch_bars(
            symbols=symbols,
            start=self.cfg["data"]["start_date"],
            end=self.cfg["data"].get("end_date"),
            save=save
        )
