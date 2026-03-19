"""Assembles per-symbol feature matrices and labels for model training/inference."""
import os
import pickle
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional
from sklearn.preprocessing import RobustScaler
from ultimate_trader.features.technicals import add_technicals
from ultimate_trader.features.sentiment import build_sentiment_features
from ultimate_trader.utils.logging import get_logger
from ultimate_trader.utils.config_loader import Config

logger = get_logger(__name__)

# Technical feature columns fed to model
TECH_FEATURES = [
    "return_1d", "return_3d", "return_5d", "return_10d", "return_20d",
    "vol_5d", "vol_20d",
    "rsi_14", "rsi_28",
    "macd", "macd_signal", "macd_hist",
    "bb_width", "bb_pct_b",
    "atr_pct",
    "obv_change_5d",
    "volume_anomaly",
    "sma_50_200_ratio", "price_vs_sma50", "price_vs_sma200",
    "stoch_k", "stoch_d",
    "williams_r",
    "momentum_10", "momentum_20",
    "price_range_20d",
    # Earnings proximity features (added)
    "days_to_earnings",
    "earnings_flag",
    # Inter-symbol correlation features (added)
    "corr_spy_20d",
    "corr_sector_20d",
]

SENTIMENT_FEATURES = [
    "avg_score", "score_std", "pos_ratio", "neg_ratio",
    "sentiment_momentum_3d", "sentiment_momentum_5d",
    "sentiment_vol_5d", "news_surge",
]

MACRO_FEATURES = [
    "spy_return_1d", "spy_return_5d", "spy_vol_20d", "spy_trend",
    "vix_level", "vix_change_1d", "vix_regime_pct",
    "yield_proxy", "yield_change_5d",
    "oil_return_5d", "gold_return_5d",
]


def _add_earnings_features(
    df: pd.DataFrame,
    earnings_dates: Optional[Dict[str, List[str]]],
    symbol: str,
) -> pd.DataFrame:
    """
    Add days_to_earnings and earnings_flag columns.
    - days_to_earnings: normalised distance to nearest upcoming earnings (0=today, 1=30+days)
    - earnings_flag: 1 if earnings within 3 days, else 0
    """
    df = df.copy()
    df["days_to_earnings"] = 1.0  # default: no upcoming earnings known
    df["earnings_flag"] = 0.0

    if not earnings_dates:
        return df

    dates_list = earnings_dates.get(symbol, [])
    if not dates_list:
        return df

    parsed = []
    for d in dates_list:
        try:
            parsed.append(pd.Timestamp(d))
        except Exception:
            pass
    if not parsed:
        return df

    for ts in df.index:
        future = [e for e in parsed if e >= ts]
        if future:
            nearest = min(future)
            delta = (nearest - ts).days
            df.at[ts, "days_to_earnings"] = min(delta / 30.0, 1.0)  # normalise to [0,1]
            df.at[ts, "earnings_flag"] = 1.0 if delta <= 3 else 0.0
    return df


def _add_correlation_features(
    df: pd.DataFrame,
    symbol: str,
    bars: Dict[str, pd.DataFrame],
    symbol_to_sector_etf: Optional[Dict[str, str]] = None,
    window: int = 20,
) -> pd.DataFrame:
    """
    Add rolling correlation vs SPY and vs the symbol's sector ETF.
    """
    df = df.copy()
    sym_ret = df["close"].pct_change() if "close" in df.columns else None

    # vs SPY
    spy = bars.get("SPY")
    if spy is not None and sym_ret is not None:
        spy_ret = spy["close"].pct_change().reindex(df.index)
        df["corr_spy_20d"] = sym_ret.rolling(window).corr(spy_ret).fillna(0.0)
    else:
        df["corr_spy_20d"] = 0.0

    # vs sector ETF
    sector_etf = (symbol_to_sector_etf or {}).get(symbol)
    if sector_etf and sector_etf in bars and sym_ret is not None:
        sec_ret = bars[sector_etf]["close"].pct_change().reindex(df.index)
        df["corr_sector_20d"] = sym_ret.rolling(window).corr(sec_ret).fillna(0.0)
    else:
        df["corr_sector_20d"] = df.get("corr_spy_20d", pd.Series(0.0, index=df.index))

    return df


SECTOR_ETF_MAP = {
    "AAPL": "XLK", "MSFT": "XLK", "NVDA": "XLK", "AVGO": "XLK",
    "ORCL": "XLK", "CRM": "XLK", "ADBE": "XLK", "AMD": "XLK",
    "INTC": "XLK", "QCOM": "XLK", "TXN": "XLK", "ACN": "XLK",
    "INTU": "XLK", "NOW": "XLK", "CSCO": "XLK",
    "JPM": "XLF", "BAC": "XLF", "GS": "XLF", "V": "XLF", "MA": "XLF", "SPGI": "XLF",
    "UNH": "XLV", "LLY": "XLV", "JNJ": "XLV", "ABT": "XLV", "MRK": "XLV",
    "ABBV": "XLV", "TMO": "XLV", "DHR": "XLV", "AMGN": "XLV",
    "XOM": "XLE", "CVX": "XLE",
    "WMT": "XLP", "KO": "XLP", "PG": "XLP", "COST": "XLP", "PEP": "XLP", "PM": "XLP",
    "AMZN": "XLY", "TSLA": "XLY", "MCD": "XLY", "NKE": "XLY", "HD": "XLY",
    "META": "XLC", "GOOGL": "XLC", "NFLX": "XLC",
    "RTX": "XLI", "UPS": "XLI", "LIN": "XLI", "NEE": "XLI",
}


class FeatureBuilder:
    """
    Builds windowed feature arrays and labels for model training/inference.

    Scaler fit/transform separation:
      - fit_scalers() is called ONCE on training-fold data
      - All subsequent calls use transform() only
      - Scalers are saved to disk and reloaded at inference

    Added features vs v1:
      - Earnings proximity (days_to_earnings, earnings_flag)
      - Inter-symbol correlation (corr_spy_20d, corr_sector_20d)
    """

    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.price_window = cfg.model.price_window
        self.sentiment_window = cfg.model.sentiment_window
        self.macro_window = cfg.model.macro_window
        self.horizon = cfg.targets.horizon_days
        self.r_hi = cfg.targets.r_hi
        self.r_lo = cfg.targets.r_lo
        self.scalers_dir = cfg.paths.scalers_dir
        os.makedirs(self.scalers_dir, exist_ok=True)

        self.tech_scaler = RobustScaler()
        self.sent_scaler = RobustScaler()
        self.macro_scaler = RobustScaler()
        self._fitted = False

    def fit_scalers(self, all_tech: np.ndarray, all_sent: np.ndarray,
                    all_macro: np.ndarray):
        """Fit scalers on TRAINING data only. Call once, then save."""
        self.tech_scaler.fit(all_tech.reshape(-1, all_tech.shape[-1]))
        self.sent_scaler.fit(all_sent.reshape(-1, all_sent.shape[-1]))
        if all_macro.shape[-1] > 0:
            self.macro_scaler.fit(all_macro.reshape(-1, all_macro.shape[-1]))
        self._fitted = True
        self._save_scalers()
        logger.info("Feature scalers fitted and saved")

    def _save_scalers(self):
        for name, scaler in [("tech", self.tech_scaler),
                              ("sent", self.sent_scaler),
                              ("macro", self.macro_scaler)]:
            with open(os.path.join(self.scalers_dir, f"{name}_scaler.pkl"), "wb") as f:
                pickle.dump(scaler, f)

    def load_scalers(self):
        for name, attr in [("tech", "tech_scaler"),
                            ("sent", "sent_scaler"),
                            ("macro", "macro_scaler")]:
            path = os.path.join(self.scalers_dir, f"{name}_scaler.pkl")
            if os.path.exists(path):
                with open(path, "rb") as f:
                    setattr(self, attr, pickle.load(f))
        self._fitted = True
        logger.info("Feature scalers loaded from disk")

    def build_features(
        self,
        bars: Dict[str, pd.DataFrame],
        sentiment: Dict[str, pd.DataFrame],
        macro_df: pd.DataFrame,
        symbols: List[str],
        symbol_to_idx: Dict[str, int],
        symbol_to_sector: Dict[str, int],
        earnings_dates: Optional[Dict[str, List[str]]] = None,
        fit: bool = False,
    ) -> Tuple[dict, Optional[dict]]:
        tech_pool, sent_pool, macro_pool = [], [], []
        raw = {}

        for symbol in symbols:
            if symbol not in bars:
                continue

            df = bars[symbol].copy()
            df = add_technicals(df)
            df = _add_earnings_features(df, earnings_dates, symbol)
            df = _add_correlation_features(df, symbol, bars, SECTOR_ETF_MAP)

            # FIX: use .ffill() not deprecated fillna(method='ffill')
            macro_aligned = macro_df.reindex(df.index).ffill().fillna(0)

            sent_df = sentiment.get(symbol, pd.DataFrame()).reindex(df.index).fillna(0)
            sent_cols = [c for c in SENTIMENT_FEATURES if c in sent_df.columns]
            sent_arr = sent_df[sent_cols].values if sent_cols else np.zeros((len(df), len(SENTIMENT_FEATURES)))

            tech_arr = df[[c for c in TECH_FEATURES if c in df.columns]].values.astype(np.float32)
            macro_arr = macro_aligned[[c for c in MACRO_FEATURES if c in macro_aligned.columns]].values.astype(np.float32)

            raw[symbol] = {
                "tech": tech_arr, "sent": sent_arr, "macro": macro_arr,
                "index": df.index, "close": df["close"].values,
                "sym_idx": symbol_to_idx.get(symbol, 0),
                "sec_idx": symbol_to_sector.get(symbol, 0),
            }
            tech_pool.append(tech_arr)
            sent_pool.append(sent_arr)
            macro_pool.append(macro_arr)

        if fit and tech_pool:
            self.fit_scalers(
                np.concatenate(tech_pool),
                np.concatenate(sent_pool),
                np.concatenate(macro_pool)
            )

        features, labels = {}, {}
        for symbol, data in raw.items():
            tech_s = self.tech_scaler.transform(data["tech"]) if self._fitted else data["tech"]
            sent_s = self.sent_scaler.transform(data["sent"]) if self._fitted else data["sent"]
            macro_s = self.macro_scaler.transform(data["macro"]) if self._fitted and data["macro"].shape[-1] > 0 else data["macro"]

            features[symbol] = {
                "tech":    tech_s[-self.price_window:],
                "sent":    sent_s[-self.sentiment_window:],
                "macro":   macro_s[-self.macro_window:],
                "sym_idx": data["sym_idx"],
                "sec_idx": data["sec_idx"],
            }
            close = data["close"]
            if len(close) > self.horizon:
                future_ret = (close[-1] / close[-(self.horizon + 1)] - 1)
                labels[symbol] = self._label(future_ret)

        return features, labels

    def _label(self, ret: float) -> int:
        """5-class label: 0=strong_sell … 4=strong_buy"""
        if ret > self.r_hi:       return 4
        elif ret > self.r_lo:     return 3
        elif ret >= -self.r_lo:   return 2
        elif ret >= -self.r_hi:   return 1
        else:                     return 0

    def build_training_samples(
        self,
        bars: Dict[str, pd.DataFrame],
        sentiment: Dict[str, pd.DataFrame],
        macro_df: pd.DataFrame,
        symbols: List[str],
        symbol_to_idx: Dict[str, int],
        symbol_to_sector: Dict[str, int],
        date_range: pd.DatetimeIndex,
        fit_scalers: bool = False,
        earnings_dates: Optional[Dict[str, List[str]]] = None,
    ) -> Tuple[List, List[int]]:
        """
        Builds (feature_dict, label) samples over all symbols x all dates.

        Scaler safety:
          fit_scalers=True  -> fit ONLY on this date_range (training fold)
          fit_scalers=False -> transform only (validation / inference)
        """
        samples, label_list = [], []
        tech_pool, sent_pool, macro_pool = [], [], []
        raw_data = {}

        for symbol in symbols:
            if symbol not in bars:
                continue
            df = bars[symbol].copy()
            df = add_technicals(df)
            df = _add_earnings_features(df, earnings_dates, symbol)
            df = _add_correlation_features(df, symbol, bars, SECTOR_ETF_MAP)

            # FIX: .ffill() instead of deprecated fillna(method='ffill')
            macro_aligned = macro_df.reindex(df.index).ffill().fillna(0)
            sent_df = sentiment.get(symbol, pd.DataFrame()).reindex(df.index).fillna(0)
            sent_cols = [c for c in SENTIMENT_FEATURES if c in sent_df.columns]

            tech_arr = df[[c for c in TECH_FEATURES if c in df.columns]].values.astype(np.float32)
            sent_arr = (sent_df[sent_cols].values if sent_cols
                        else np.zeros((len(df), len(SENTIMENT_FEATURES)), dtype=np.float32))
            macro_arr = macro_aligned[[c for c in MACRO_FEATURES
                                        if c in macro_aligned.columns]].values.astype(np.float32)

            # For scaler fitting: only collect rows that fall in date_range (training data)
            date_mask = pd.Series(df.index).isin(date_range).values
            raw_data[symbol] = {
                "tech": tech_arr, "sent": sent_arr, "macro": macro_arr,
                "dates": df.index, "close": df["close"].values,
                "sym_idx": symbol_to_idx.get(symbol, 0),
                "sec_idx": symbol_to_sector.get(symbol, 0),
                "date_mask": date_mask,
            }

            if fit_scalers:
                # Only pool training-fold rows for scaler fitting
                tech_pool.append(tech_arr[date_mask])
                sent_pool.append(sent_arr[date_mask])
                macro_pool.append(macro_arr[date_mask])

        if fit_scalers and tech_pool:
            # Scalers fitted strictly on training data - no leakage
            self.fit_scalers(
                np.concatenate([t for t in tech_pool if len(t) > 0]),
                np.concatenate([s for s in sent_pool if len(s) > 0]),
                np.concatenate([m for m in macro_pool if len(m) > 0]),
            )

        for symbol, data in raw_data.items():
            dates = data["dates"]
            close = data["close"]

            # transform() only - never fit on val data
            tech_s = self.tech_scaler.transform(data["tech"]) if self._fitted else data["tech"]
            sent_s = self.sent_scaler.transform(data["sent"]) if self._fitted else data["sent"]
            macro_s = self.macro_scaler.transform(data["macro"]) if self._fitted else data["macro"]

            for i, date in enumerate(dates):
                if date not in date_range:
                    continue
                if i < max(self.price_window, self.sentiment_window, self.macro_window):
                    continue
                if i + self.horizon >= len(close):
                    continue

                future_ret = close[i + self.horizon] / close[i] - 1
                label = self._label(future_ret)

                sample = {
                    "tech":    tech_s[i - self.price_window:i].astype(np.float32),
                    "sent":    sent_s[i - self.sentiment_window:i].astype(np.float32),
                    "macro":   macro_s[i - self.macro_window:i].astype(np.float32),
                    "sym_idx": data["sym_idx"],
                    "sec_idx": data["sec_idx"],
                }
                samples.append(sample)
                label_list.append(label)

        logger.info(f"Built {len(samples)} training samples")
        return samples, label_list
