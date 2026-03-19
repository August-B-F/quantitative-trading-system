"""Alternative / macro data sources."""
import time
import pandas as pd
from pathlib import Path
from typing import List, Optional
from ultimate_trader.utils.logging import get_logger

log = get_logger(__name__)


def fetch_macro_bars(
    macro_symbols: List[str],
    start: str,
    end: Optional[str],
    api_key: str,
    secret_key: str,
    raw_dir: str = "data/raw/macro",
) -> dict:
    """
    Fetch macro ETF bars (VIX proxy, TLT, GLD, USO, UUP, sector ETFs).
    Uses the same alpaca_market fetch_bars function.
    Returns dict of symbol -> pd.DataFrame.
    """
    from ultimate_trader.data_sources.alpaca_market import fetch_bars
    return fetch_bars(
        symbols=macro_symbols,
        start=start,
        end=end,
        api_key=api_key,
        secret_key=secret_key,
        raw_dir=raw_dir,
    )


def compute_yield_spread(tlt_df: pd.DataFrame, shy_df: pd.DataFrame) -> pd.Series:
    """
    Approximate 10Y-2Y yield spread proxy from TLT/SHY price ratio.
    Higher TLT/SHY ratio -> steeper curve (bullish macro).
    Returns a daily Series aligned to TLT dates.
    """
    ratio = tlt_df["close"] / shy_df["close"].reindex(tlt_df.index, method="ffill")
    spread = ratio.pct_change(20).rename("yield_spread_proxy")
    return spread


def compute_vix_level(vixy_df: pd.DataFrame) -> pd.Series:
    """
    Return normalised VIX-proxy level from VIXY ETF close.
    Returns z-scored series (252-day rolling).
    """
    s = vixy_df["close"].rename("vix_z")
    rolling_mean = s.rolling(252, min_periods=60).mean()
    rolling_std  = s.rolling(252, min_periods=60).std()
    return ((s - rolling_mean) / rolling_std).rename("vix_z")


def compute_dollar_strength(uup_df: pd.DataFrame) -> pd.Series:
    """Return 20-day return of USD strength ETF (UUP)."""
    return uup_df["close"].pct_change(20).rename("usd_20d_return")


def compute_gold_trend(gld_df: pd.DataFrame) -> pd.Series:
    """Return 20-day return of gold ETF (GLD)."""
    return gld_df["close"].pct_change(20).rename("gold_20d_return")
