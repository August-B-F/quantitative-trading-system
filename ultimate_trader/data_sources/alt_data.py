"""Alternative / macro data sources.

Currently fetches:
  - VIX (volatility index) via yfinance fallback
  - US Treasury yield spread (10Y - 2Y)
  - Macro indicators: DXY (dollar index), GLD (gold ETF as proxy)

All sources are optional and degrade gracefully if unavailable.
"""
import pandas as pd
from pathlib import Path

from ultimate_trader.utils.logging import get_logger

log = get_logger(__name__)

# Symbols proxied via Alpaca (traded as ETFs/products)
MACRO_SYMBOLS = {
    "vix": "VIXY",        # ProShares VIX Short-Term Futures ETF as VIX proxy
    "gold": "GLD",
    "dollar": "UUP",      # Invesco DB US Dollar Index
    "oil": "USO",
    "bonds_long": "TLT",  # iShares 20+ Year Treasury Bond
    "bonds_short": "SHY", # iShares 1-3 Year Treasury Bond
    "high_yield": "HYG",  # iShares High Yield Corporate Bond
}


class AltDataFetcher:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.raw_dir = Path(cfg["paths"]["raw_dir"]) / "macro"
        self.raw_dir.mkdir(parents=True, exist_ok=True)

    def fetch_macro(self, market_fetcher) -> dict[str, pd.DataFrame]:
        """
        Fetch macro proxy ETFs using the existing AlpacaMarketFetcher.
        Returns dict name->DataFrame with OHLCV.
        """
        symbols = list(MACRO_SYMBOLS.values())
        log.info(f"Fetching {len(symbols)} macro proxy symbols")

        try:
            bars = market_fetcher.fetch_bars(
                symbols=symbols,
                start=self.cfg["data"]["start_date"],
                end=self.cfg["data"].get("end_date"),
                save=True
            )
            # Rename from ETF ticker to semantic name
            named = {}
            for name, sym in MACRO_SYMBOLS.items():
                if sym in bars:
                    named[name] = bars[sym]
            return named
        except Exception as e:
            log.error(f"Failed to fetch macro data: {e}")
            return {}

    def build_macro_features(self, macro_bars: dict[str, pd.DataFrame]) -> pd.DataFrame:
        """
        Build a single daily macro feature DataFrame with columns:
          vix_close, vix_change, yield_spread_proxy (TLT/SHY ratio),
          gold_return, dollar_return, oil_return, hy_spread_proxy
        """
        features = pd.DataFrame()

        for name, df in macro_bars.items():
            if df is None or df.empty:
                continue
            col = f"{name}_close"
            features[col] = df["close"]
            features[f"{name}_return_1d"] = df["close"].pct_change(1)
            features[f"{name}_return_5d"] = df["close"].pct_change(5)

        # Yield spread proxy: TLT / SHY relative return
        if "bonds_long" in macro_bars and "bonds_short" in macro_bars:
            tlt = macro_bars["bonds_long"]["close"]
            shy = macro_bars["bonds_short"]["close"]
            features["yield_spread_proxy"] = (tlt / shy).pct_change(1)

        # High-yield spread proxy (HYG returns as risk-on signal)
        if "high_yield" in macro_bars:
            features["hy_risk_signal"] = macro_bars["high_yield"]["close"].pct_change(1)

        features = features.sort_index().ffill().dropna(how="all")
        return features
