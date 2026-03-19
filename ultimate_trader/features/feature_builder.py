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


class FeatureBuilder:
    """
    Builds windowed feature arrays and labels for each symbol.
    Scalers are fitted ONCE on training data and saved to disk.
    At inference time, saved scalers are loaded and only transform() is called.
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

        # Scalers - one per feature group
        self.tech_scaler = RobustScaler()
        self.sent_scaler = RobustScaler()
        self.macro_scaler = RobustScaler()
        self._fitted = False

    def fit_scalers(self, all_tech: np.ndarray, all_sent: np.ndarray,
                    all_macro: np.ndarray):
        """
        Fit scalers on training data pooled across all symbols.
        Call this ONCE on training set, then save.
        """
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
        fit: bool = False,
    ) -> Tuple[dict, Optional[dict]]:
        """
        Build feature tensors for all symbols.

        Returns:
            features: dict with keys per symbol, each a dict of:
                'tech'     : np.ndarray (price_window, n_tech_features)
                'sent'     : np.ndarray (sentiment_window, n_sent_features)
                'macro'    : np.ndarray (macro_window, n_macro_features)
                'sym_idx'  : int
                'sec_idx'  : int
            labels: dict {symbol: int} or None if no future data
        """
        tech_pool, sent_pool, macro_pool = [], [], []
        raw = {}  # hold unscaled data before pooled fit

        for symbol in symbols:
            if symbol not in bars:
                continue

            df = bars[symbol].copy()
            df = add_technicals(df)

            # Align macro
            macro_aligned = macro_df.reindex(df.index).fillna(method="ffill").fillna(0)

            # Align sentiment
            sent_df = sentiment.get(symbol, pd.DataFrame()).reindex(
                df.index).fillna(0)
            sent_cols = [c for c in SENTIMENT_FEATURES if c in sent_df.columns]
            if not sent_cols:
                sent_arr = np.zeros((len(df), len(SENTIMENT_FEATURES)))
            else:
                sent_arr = sent_df[sent_cols].values

            tech_arr = df[[c for c in TECH_FEATURES if c in df.columns]].values
            macro_arr = macro_aligned[[c for c in MACRO_FEATURES
                                        if c in macro_aligned.columns]].values

            raw[symbol] = {
                "tech": tech_arr, "sent": sent_arr,
                "macro": macro_arr, "index": df.index,
                "close": df["close"].values,
                "sym_idx": symbol_to_idx.get(symbol, 0),
                "sec_idx": symbol_to_sector.get(symbol, 0),
            }
            tech_pool.append(tech_arr)
            sent_pool.append(sent_arr)
            macro_pool.append(macro_arr)

        if fit and tech_pool:
            all_tech = np.concatenate(tech_pool, axis=0)
            all_sent = np.concatenate(sent_pool, axis=0)
            all_macro = np.concatenate(macro_pool, axis=0)
            self.fit_scalers(all_tech, all_sent, all_macro)

        features = {}
        labels = {}

        for symbol, data in raw.items():
            tech_s = self.tech_scaler.transform(data["tech"]) if self._fitted else data["tech"]
            sent_s = self.sent_scaler.transform(data["sent"]) if self._fitted else data["sent"]
            macro_s = self.macro_scaler.transform(data["macro"]) if self._fitted and data["macro"].shape[-1] > 0 else data["macro"]

            # Take most recent windows
            features[symbol] = {
                "tech": tech_s[-self.price_window:],
                "sent": sent_s[-self.sentiment_window:],
                "macro": macro_s[-self.macro_window:],
                "sym_idx": data["sym_idx"],
                "sec_idx": data["sec_idx"],
            }

            # Build label from future return
            close = data["close"]
            if len(close) > self.horizon:
                future_ret = (close[-1] / close[-(self.horizon + 1)] - 1)
                labels[symbol] = self._label(future_ret)

        return features, labels

    def _label(self, ret: float) -> int:
        """Convert return to 5-class label: 0=strong_sell, 1=sell, 2=hold, 3=buy, 4=strong_buy"""
        if ret > self.r_hi:
            return 4  # strong buy
        elif ret > self.r_lo:
            return 3  # buy
        elif ret >= -self.r_lo:
            return 2  # hold
        elif ret >= -self.r_hi:
            return 1  # sell
        else:
            return 0  # strong sell

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
    ) -> Tuple[List, List[int]]:
        """
        Builds a flat list of (feature_dict, label) samples over all symbols
        and all dates in date_range. This is the input to the PyTorch Dataset.
        """
        samples = []
        label_list = []

        # Collect all raw arrays for scaler fitting
        tech_pool, sent_pool, macro_pool = [], [], []
        raw_data = {}

        for symbol in symbols:
            if symbol not in bars:
                continue
            df = bars[symbol].copy()
            df = add_technicals(df)
            macro_aligned = macro_df.reindex(df.index).fillna(method="ffill").fillna(0)
            sent_df = sentiment.get(symbol, pd.DataFrame()).reindex(df.index).fillna(0)
            sent_cols = [c for c in SENTIMENT_FEATURES if c in sent_df.columns]

            tech_arr = df[[c for c in TECH_FEATURES if c in df.columns]].values
            sent_arr = sent_df[sent_cols].values if sent_cols else np.zeros((len(df), len(SENTIMENT_FEATURES)))
            macro_arr = macro_aligned[[c for c in MACRO_FEATURES if c in macro_aligned.columns]].values

            raw_data[symbol] = {
                "tech": tech_arr, "sent": sent_arr, "macro": macro_arr,
                "dates": df.index, "close": df["close"].values,
                "sym_idx": symbol_to_idx.get(symbol, 0),
                "sec_idx": symbol_to_sector.get(symbol, 0),
            }
            tech_pool.append(tech_arr)
            sent_pool.append(sent_arr)
            macro_pool.append(macro_arr)

        if fit_scalers and tech_pool:
            self.fit_scalers(
                np.concatenate(tech_pool),
                np.concatenate(sent_pool),
                np.concatenate(macro_pool)
            )

        for symbol, data in raw_data.items():
            dates = data["dates"]
            close = data["close"]

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
                    "tech": tech_s[i - self.price_window:i].astype(np.float32),
                    "sent": sent_s[i - self.sentiment_window:i].astype(np.float32),
                    "macro": macro_s[i - self.macro_window:i].astype(np.float32),
                    "sym_idx": data["sym_idx"],
                    "sec_idx": data["sec_idx"],
                }
                samples.append(sample)
                label_list.append(label)

        logger.info(f"Built {len(samples)} training samples")
        return samples, label_list
