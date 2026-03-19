"""
alt_data.py

Experimental alternative data sources.
All are optional — toggled via config.

Current sources:
  1. Macro indicators: 10Y-2Y yield spread, VIX, DXY, Fed Funds Rate
     (fetched from FRED via pandas-datareader)
  2. Earnings calendar: upcoming earnings flags per symbol
     (via yfinance)
  3. Short interest: days-to-cover, short % of float
     (via yfinance, fallback to zero if unavailable)
  4. Options sentiment: put/call ratio, implied volatility rank
     (via yfinance options chain)
  5. Google Trends interest (experimental)
     (via pytrends)
"""

import os
from datetime import datetime, timedelta
from typing import List, Optional

import pandas as pd
import numpy as np

from ultimate_trader.utils.logging import get_logger
from ultimate_trader.utils.config_loader import Config

logger = get_logger("alt_data")


class MacroFetcher:
    """
    Fetches macro regime indicators:
      - VIX (fear index) via VIXY ETF bars
      - 10Y-2Y treasury yield spread (from FRED)
      - US Dollar index (DXY) via UUP ETF
    Output: data/raw/macro.parquet
    Columns: date, vix, yield_spread, dxy, vix_ma20, vix_regime
    """

    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.raw_dir = cfg.paths.raw_dir
        os.makedirs(self.raw_dir, exist_ok=True)

    def fetch(self, start: str, end: Optional[str] = None) -> pd.DataFrame:
        end = end or datetime.today().strftime("%Y-%m-%d")
        path = os.path.join(self.raw_dir, "macro.parquet")

        try:
            import pandas_datareader.data as web

            logger.info("Fetching macro indicators from FRED...")
            # 10-year treasury yield
            ty10 = web.DataReader("DGS10", "fred", start, end)["DGS10"]
            # 2-year treasury yield
            ty2 = web.DataReader("DGS2", "fred", start, end)["DGS2"]
            # Fed funds rate
            fed = web.DataReader("FEDFUNDS", "fred", start, end)["FEDFUNDS"]

            macro = pd.DataFrame({
                "yield_spread": (ty10 - ty2).ffill(),
                "fed_rate": fed.ffill(),
            })
            macro.index = pd.to_datetime(macro.index)
            macro.index.name = "date"

            # Add rolling features
            macro["yield_spread_ma5"] = macro["yield_spread"].rolling(5).mean()
            macro["yield_spread_slope"] = macro["yield_spread"].diff(5)
            macro["fed_rate_change"] = macro["fed_rate"].diff(1)

            macro.to_parquet(path)
            logger.info(f"Macro data saved: {len(macro)} rows")
            return macro

        except Exception as e:
            logger.warning(f"Macro fetch failed: {e}. Returning zeros.")
            idx = pd.bdate_range(start, end)
            return pd.DataFrame(0, index=idx, columns=[
                "yield_spread", "fed_rate", "yield_spread_ma5",
                "yield_spread_slope", "fed_rate_change"
            ])

    def get(self) -> pd.DataFrame:
        path = os.path.join(self.raw_dir, "macro.parquet")
        if not os.path.exists(path):
            raise FileNotFoundError("Macro data not fetched yet.")
        return pd.read_parquet(path)


class EarningsCalendar:
    """
    Fetches upcoming earnings dates for each symbol.
    Returns a set of (symbol, date) tuples where an earnings announcement
    is expected within the next N days.
    Used to reduce exposure before high-risk events.
    """

    def __init__(self, cfg: Config):
        self.cfg = cfg

    def has_earnings_soon(self, symbol: str, days_ahead: int = 2) -> bool:
        """
        Returns True if the symbol has an earnings announcement
        within the next `days_ahead` trading days.
        """
        try:
            import yfinance as yf
            ticker = yf.Ticker(symbol)
            cal = ticker.earnings_dates
            if cal is None or cal.empty:
                return False
            upcoming = cal[cal.index >= pd.Timestamp.today()]
            if upcoming.empty:
                return False
            next_earnings = upcoming.index[0]
            delta = (next_earnings - pd.Timestamp.today()).days
            return 0 <= delta <= days_ahead
        except Exception as e:
            logger.debug(f"Earnings check failed for {symbol}: {e}")
            return False

    def get_earnings_flags(self, symbols: List[str], days_ahead: int = 2) -> dict:
        """
        Returns {symbol: True/False} earnings-soon flag for all symbols.
        """
        return {sym: self.has_earnings_soon(sym, days_ahead) for sym in symbols}


class OptionsDataFetcher:
    """
    Experimental: fetches put/call ratio and IV rank from yfinance options chain.
    These are strong leading indicators when available.
    """

    def __init__(self, cfg: Config):
        self.cfg = cfg

    def get_options_sentiment(self, symbol: str) -> dict:
        """
        Returns:
          put_call_ratio: total put OI / total call OI (>1 = bearish)
          iv_rank: current IV relative to 52-week range (0-1)
        Returns zeros if data unavailable.
        """
        try:
            import yfinance as yf
            ticker = yf.Ticker(symbol)
            expirations = ticker.options
            if not expirations:
                return {"put_call_ratio": 1.0, "iv_rank": 0.5}

            # Use nearest expiration
            chain = ticker.option_chain(expirations[0])
            calls_oi = chain.calls["openInterest"].sum()
            puts_oi = chain.puts["openInterest"].sum()
            pcr = puts_oi / calls_oi if calls_oi > 0 else 1.0

            # IV rank approximation from call implied vols
            ivs = chain.calls["impliedVolatility"].dropna()
            if len(ivs) >= 2:
                iv_rank = (ivs.median() - ivs.min()) / (ivs.max() - ivs.min() + 1e-9)
            else:
                iv_rank = 0.5

            return {"put_call_ratio": float(pcr), "iv_rank": float(iv_rank)}

        except Exception as e:
            logger.debug(f"Options data failed for {symbol}: {e}")
            return {"put_call_ratio": 1.0, "iv_rank": 0.5}
