"""Alternative / experimental data sources.

Currently implemented:
  - VIX daily close (via yfinance fallback)
  - 10Y-2Y yield spread (via yfinance: ^TNX, ^IRX)
  - Earnings calendar (via yfinance)

These are intentionally simple and robust — no scraping, no fragile APIs.
Expand this module to add options flow, Reddit sentiment, etc.
"""
import datetime
import pandas as pd
from pathlib import Path
from ultimate_trader.utils.logging import get_logger

logger = get_logger("alt_data")


def fetch_yfinance_series(
    tickers: list,
    start: str,
    end: str = None,
    raw_dir: str = "data/raw/alt",
) -> dict:
    """
    Download daily close prices for given tickers using yfinance.
    Returns {ticker: pd.Series}.
    """
    import yfinance as yf
    Path(raw_dir).mkdir(parents=True, exist_ok=True)
    end = end or datetime.date.today().isoformat()
    results = {}
    for ticker in tickers:
        logger.info(f"  Downloading alt series: {ticker}")
        try:
            df = yf.download(ticker, start=start, end=end, progress=False, auto_adjust=True)
            series = df["Close"].squeeze()
            series.name = ticker
            series.index = pd.to_datetime(series.index).tz_localize(None)
            out = Path(raw_dir) / f"{ticker.replace('^','')}.csv"
            series.to_csv(out, header=True)
            results[ticker] = series
        except Exception as e:
            logger.error(f"  Failed to fetch {ticker}: {e}")
    return results


def fetch_macro_data(cfg: dict, raw_dir: str = "data/raw/alt") -> dict:
    """
    Fetch macro indicators:
      - ^VIX  : CBOE Volatility Index
      - ^TNX  : 10-Year Treasury Yield
      - ^IRX  : 13-Week Treasury Bill Yield (proxy for 2Y)
      - GC=F  : Gold futures (macro risk-off signal)
      - CL=F  : Crude oil futures (macro risk signal)
      - DX-Y.NYB : USD index
    """
    start = cfg["data"]["start_date"]
    end = cfg["data"].get("end_date") or datetime.date.today().isoformat()
    tickers = ["^VIX", "^TNX", "^IRX", "GC=F", "CL=F", "DX-Y.NYB"]
    return fetch_yfinance_series(tickers, start, end, raw_dir=raw_dir)


def fetch_earnings_calendar(symbols: list, raw_dir: str = "data/raw/alt") -> dict:
    """
    Fetch upcoming and past earnings dates per symbol using yfinance.
    Returns {symbol: [date_str, ...]}
    """
    import yfinance as yf
    Path(raw_dir).mkdir(parents=True, exist_ok=True)
    calendar = {}
    for symbol in symbols:
        try:
            ticker = yf.Ticker(symbol)
            cal = ticker.earnings_dates
            if cal is not None and not cal.empty:
                dates = [d.isoformat()[:10] for d in cal.index.tz_localize(None)]
                calendar[symbol] = dates
            else:
                calendar[symbol] = []
        except Exception as e:
            logger.warning(f"  Could not fetch earnings for {symbol}: {e}")
            calendar[symbol] = []
    import json
    out = Path(raw_dir) / "earnings_calendar.json"
    with open(out, "w") as f:
        json.dump(calendar, f, indent=2)
    return calendar


def load_earnings_calendar(raw_dir: str = "data/raw/alt") -> dict:
    import json
    path = Path(raw_dir) / "earnings_calendar.json"
    if not path.exists():
        return {}
    with open(path, "r") as f:
        return json.load(f)
