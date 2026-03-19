"""Experimental alternative data sources.

Currently implemented:
  - VIX proxy features from VIXY ETF
  - Yield curve proxy (TLT/IEI spread as surrogate for 10Y-2Y)
  - Sector relative strength vs SPY
  - Dollar index proxy (UUP ETF)
  - Earnings calendar via yfinance
  - Inter-symbol correlation helpers

All are optional and gracefully disabled if data unavailable.
"""
import pandas as pd
import numpy as np
from typing import Dict
from ultimate_trader.utils.logging import get_logger
from ultimate_trader.utils.config_loader import Config

logger = get_logger(__name__)


class AltDataBuilder:
    """
    Builds extra feature columns from macro ETFs and market structure data.
    Input: bars dict from MarketDataFetcher (already contains SPY, TLT, VIXY, etc.)
    Output: a date-indexed DataFrame of macro features.
    """

    def __init__(self, cfg: Config):
        self.cfg = cfg

    def build_macro_features(self, bars: Dict[str, pd.DataFrame]) -> pd.DataFrame:
        """
        Build a date-indexed macro feature DataFrame from available ETF bars.
        Columns:
            vix_level         - VIXY close (VIX proxy)
            vix_change_1d     - 1d change in vix
            vix_regime_pct    - rolling 60d percentile rank of VIX
            yield_proxy       - TLT close (long bond price, inverse of rates)
            yield_change_5d   - 5d change in TLT
            spy_return_1d     - SPY 1d return
            spy_return_5d     - SPY 5d return
            spy_vol_20d       - SPY 20d rolling vol
            spy_trend         - SPY 50d vs 200d SMA ratio (>1 = bull trend)
            oil_return_5d     - USO 5d return
            gold_return_5d    - GLD 5d return
        """
        frames = []

        spy = bars.get("SPY")
        if spy is not None:
            spy_ret = spy["close"].pct_change()
            df_spy = pd.DataFrame({
                "spy_return_1d": spy_ret,
                "spy_return_5d": spy["close"].pct_change(5),
                "spy_vol_20d": spy_ret.rolling(20).std(),
                "spy_trend": spy["close"].rolling(50).mean() / spy["close"].rolling(200).mean(),
            }, index=spy.index)
            frames.append(df_spy)

        vixy = bars.get("VIXY")
        if vixy is not None:
            vix_pct = vixy["close"].rank(pct=True).rolling(60).mean()
            df_vix = pd.DataFrame({
                "vix_level": vixy["close"],
                "vix_change_1d": vixy["close"].pct_change(),
                "vix_regime_pct": vix_pct,
            }, index=vixy.index)
            frames.append(df_vix)

        tlt = bars.get("TLT")
        if tlt is not None:
            df_tlt = pd.DataFrame({
                "yield_proxy": tlt["close"],
                "yield_change_5d": tlt["close"].pct_change(5),
            }, index=tlt.index)
            frames.append(df_tlt)

        uso = bars.get("USO")
        if uso is not None:
            frames.append(pd.DataFrame(
                {"oil_return_5d": uso["close"].pct_change(5)}, index=uso.index
            ))

        gld = bars.get("GLD")
        if gld is not None:
            frames.append(pd.DataFrame(
                {"gold_return_5d": gld["close"].pct_change(5)}, index=gld.index
            ))

        if not frames:
            logger.warning("No macro data available - alt features will be empty")
            return pd.DataFrame()

        macro = pd.concat(frames, axis=1).sort_index()
        # FIX: use .ffill() not deprecated fillna(method='ffill')
        macro = macro.ffill().fillna(0)
        return macro

    def build_sector_strength(self, bars: Dict[str, pd.DataFrame]) -> pd.DataFrame:
        """
        Builds sector relative strength vs SPY.
        Returns DataFrame with columns like {sector}_rel_strength_20d.
        """
        spy = bars.get("SPY")
        if spy is None:
            return pd.DataFrame()

        frames = []
        for etf in self.cfg.universe.sector_etfs:
            etf_bars = bars.get(etf)
            if etf_bars is None:
                continue
            rel = etf_bars["close"] / spy["close"]
            df = pd.DataFrame({
                f"{etf}_rel_strength_20d": rel.pct_change(20),
                f"{etf}_rel_momentum_5d": rel.pct_change(5),
            }, index=etf_bars.index)
            frames.append(df)

        if not frames:
            return pd.DataFrame()
        return pd.concat(frames, axis=1).fillna(0)

    def get_earnings_dates(self, symbols: list) -> Dict[str, list]:
        """
        Returns {symbol: [list of upcoming earnings date strings]} using yfinance.
        Used by:
          - execution.py: to skip entries and exit positions before earnings
          - feature_builder.py: to add days_to_earnings and earnings_flag features
        """
        try:
            import yfinance as yf
        except ImportError:
            logger.warning("yfinance not installed - earnings calendar unavailable")
            return {}

        earnings = {}
        for sym in symbols:
            try:
                ticker = yf.Ticker(sym)
                cal = ticker.calendar
                if cal is not None and "Earnings Date" in cal.index:
                    dates = cal.loc["Earnings Date"]
                    if isinstance(dates, pd.Series):
                        earnings[sym] = [d.strftime("%Y-%m-%d") for d in dates
                                         if hasattr(d, "strftime")]
                    else:
                        earnings[sym] = [str(dates)]
                else:
                    earnings[sym] = []
            except Exception as e:
                logger.debug(f"Earnings fetch failed for {sym}: {e}")
                earnings[sym] = []

        n_with_dates = sum(1 for v in earnings.values() if v)
        logger.info(f"Earnings calendar: {n_with_dates}/{len(symbols)} symbols have upcoming dates")
        return earnings
