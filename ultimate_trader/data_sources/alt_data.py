"""Alternative and macro data sources.

Currently fetches:
  - VIX daily close (via yfinance fallback)
  - 10Y-2Y treasury yield spread (via yfinance)
  - Fear & Greed index proxy (VIX-based)

Experimental / extend as needed:
  - Reddit WSB mention counts
  - Insider transaction data (SEC EDGAR)
  - Earnings calendar (yfinance)
"""
import datetime
import pandas as pd
from pathlib import Path
from typing import Optional

from ultimate_trader.utils.logging import get_logger

logger = get_logger(__name__)


def fetch_yfinance_ticker(ticker: str, start: str, end: Optional[str] = None) -> pd.DataFrame:
    """
    Download daily OHLCV from yfinance. Used for macro series not on Alpaca.

    Args:
        ticker: yfinance ticker string e.g. '^VIX', '^TNX'
        start: ISO date
        end: ISO date or None

    Returns:
        DataFrame with DatetimeIndex and Close column
    """
    try:
        import yfinance as yf
        end = end or datetime.datetime.now().strftime("%Y-%m-%d")
        df = yf.download(ticker, start=start, end=end, progress=False, auto_adjust=True)
        df.index = pd.to_datetime(df.index).tz_localize(None).normalize()
        return df[["Close"]].rename(columns={"Close": ticker})
    except Exception as e:
        logger.error(f"yfinance fetch failed for {ticker}: {e}")
        return pd.DataFrame()


def fetch_macro_features(
    start: str,
    end: Optional[str] = None,
    save_dir: str = "data/raw/macro",
) -> pd.DataFrame:
    """
    Fetch macro regime features:
      - VIX level and 10d rolling change
      - 10Y treasury yield (proxy via ^TNX)
      - 2Y treasury yield (proxy via ^IRX)
      - 10Y-2Y yield spread (yield curve)
      - DXY dollar index (^DXY)

    Returns:
        DataFrame with DatetimeIndex and one column per macro feature.
        Forward-fills missing dates (weekends / holidays).
    """
    Path(save_dir).mkdir(parents=True, exist_ok=True)
    cache_path = Path(save_dir) / "macro.csv"

    tickers = {
        "vix": "^VIX",
        "yield_10y": "^TNX",
        "yield_2y": "^IRX",
        "dxy": "DX-Y.NYB",
    }

    frames = []
    for name, ticker in tickers.items():
        logger.info(f"Fetching macro: {ticker}")
        df = fetch_yfinance_ticker(ticker, start, end)
        if not df.empty:
            df.columns = [name]
            frames.append(df)

    if not frames:
        logger.warning("No macro data fetched")
        return pd.DataFrame()

    macro = pd.concat(frames, axis=1).ffill()

    # Derived features
    if "yield_10y" in macro.columns and "yield_2y" in macro.columns:
        macro["yield_spread"] = macro["yield_10y"] - macro["yield_2y"]
    if "vix" in macro.columns:
        macro["vix_change_10d"] = macro["vix"].pct_change(10)
        macro["vix_regime"] = pd.cut(
            macro["vix"],
            bins=[0, 15, 20, 30, 100],
            labels=[0, 1, 2, 3],
        ).astype(float)

    macro.to_csv(cache_path)
    return macro


def fetch_earnings_calendar(
    symbols: list[str],
    save_dir: str = "data/raw/earnings",
) -> dict[str, list[str]]:
    """
    Fetch upcoming and historical earnings dates per symbol via yfinance.
    Used to set a blackout window before earnings.

    Returns:
        dict of symbol -> list of date strings 'YYYY-MM-DD'
    """
    try:
        import yfinance as yf
    except ImportError:
        logger.error("yfinance not installed")
        return {}

    Path(save_dir).mkdir(parents=True, exist_ok=True)
    result = {}

    for symbol in symbols:
        try:
            ticker = yf.Ticker(symbol)
            cal = ticker.calendar
            dates = []
            if cal is not None and not cal.empty:
                for col in cal.columns:
                    try:
                        d = pd.Timestamp(cal[col].iloc[0]).strftime("%Y-%m-%d")
                        dates.append(d)
                    except Exception:
                        pass
            result[symbol] = dates
        except Exception as e:
            logger.warning(f"{symbol}: earnings calendar fetch failed — {e}")
            result[symbol] = []

    return result
