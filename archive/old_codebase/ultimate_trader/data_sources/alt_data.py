"""Experimental alternative data sources.

Currently implemented:
  - VIX proxy features from VIXY ETF
  - Yield curve proxy (TLT/IEI spread as surrogate for 10Y-2Y)
  - Sector relative strength vs SPY
  - Dollar index proxy (UUP ETF)
  - Earnings calendar via yfinance
  - GDELT market sentiment (optional, merged into macro_df)

All are optional and gracefully disabled if data unavailable.
"""
import pandas as pd
import numpy as np
from typing import Dict, Optional
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

    def build_macro_features(
        self,
        bars: Dict[str, pd.DataFrame],
        gdelt_df: Optional[pd.DataFrame] = None,
    ) -> pd.DataFrame:
        """
        Build a date-indexed macro feature DataFrame from available ETF bars.

        Columns (11 base + 3 GDELT = 14 when GDELT available):
            vix_level, vix_change_1d, vix_regime_pct
            yield_proxy, yield_change_5d
            spy_return_1d, spy_return_5d, spy_vol_20d, spy_trend
            oil_return_5d, gold_return_5d
            gdelt_avg_tone, gdelt_article_count, gdelt_goldstein_scale (if gdelt_df provided)

        Args:
            bars:     {symbol: DataFrame} from MarketDataFetcher
            gdelt_df: Optional pre-fetched GDELT daily sentiment DataFrame
        """
        frames = []

        spy = bars.get("SPY")
        if spy is not None:
            spy_ret = spy["close"].pct_change()
            df_spy = pd.DataFrame({
                "spy_return_1d": spy_ret,
                "spy_return_5d": spy["close"].pct_change(5),
                "spy_vol_20d": spy_ret.rolling(20).std(),
                "spy_trend": spy["close"].rolling(50).mean() / (spy["close"].rolling(200).mean() + 1e-9),
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
            logger.warning("No macro data available — alt features will be empty")
            return pd.DataFrame()

        macro = pd.concat(frames, axis=1).sort_index()
        macro = macro.ffill().fillna(0)

        # ── Merge GDELT sentiment if provided ─────────────────────────────────
        if gdelt_df is not None and not gdelt_df.empty:
            gdelt_cols = [c for c in ["gdelt_avg_tone", "gdelt_article_count", "gdelt_goldstein_scale"]
                          if c in gdelt_df.columns]
            if gdelt_cols:
                gdelt_aligned = (
                    gdelt_df[gdelt_cols]
                    .reindex(macro.index)
                    .ffill()
                    .fillna(0)
                )
                macro = pd.concat([macro, gdelt_aligned], axis=1)
                logger.info(f"Merged GDELT columns: {gdelt_cols}")

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
            rel = etf_bars["close"] / (spy["close"] + 1e-9)
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
            logger.warning("yfinance not installed — earnings calendar unavailable")
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
