"""
feature_builder.py

Builds the final feature tensors for model training and inference.

Key fixes vs old bot:
  - Scalers are FIT on training data ONLY, saved to disk, then
    only TRANSFORM is applied during inference (no leakage)
  - News sentiment aligned to bars by date, not forced into a time-series
  - Company encoded via integer index (for learned embedding), not char-sum
  - All features normalized per-scaler-group, saved as joblib

Output feature groups (all windows = price_window length unless noted):
  1. price_features   : returns, vol, rsi, macd, obv, atr, bb, volume_z
  2. sentiment_features: avg_score, score_std, pos_ratio, neg_ratio,
                          sentiment_momentum_3d, sentiment_momentum_5d
  3. macro_features   : yield_spread, fed_rate, vix (from SPY vol proxy)
  4. regime_feature   : one-hot of regime {0,1,2}
  5. company_idx      : integer index for embedding lookup
  6. sector_idx       : integer index for sector embedding
  7. label            : target class {0..4} (strong_sell..strong_buy)
"""

import os
import numpy as np
import pandas as pd
import joblib
from typing import List, Tuple, Optional, Dict
from sklearn.preprocessing import StandardScaler

from ultimate_trader.features.technicals import compute_all
from ultimate_trader.features.sentiment import compute_sentiment_features
from ultimate_trader.utils.logging import get_logger

logger = get_logger("feature_builder")

SECTOR_MAP = {
    "AAPL": 0, "MSFT": 0, "AMZN": 0, "GOOGL": 0, "META": 0,
    "NVDA": 0, "AMD": 0, "INTC": 0, "QCOM": 0, "TXN": 0,
    "AVGO": 0, "MU": 0, "AMAT": 0, "ADBE": 0, "CRM": 0,
    "JPM": 1, "BAC": 1, "GS": 1, "V": 1, "MA": 1,
    "PYPL": 1, "SQ": 1, "COIN": 1, "HOOD": 1, "BRK.B": 1,
    "XOM": 2, "CVX": 2,
    "JNJ": 3, "UNH": 3, "PFE": 3, "ABBV": 3, "MRNA": 3, "AMGN": 3, "GILD": 3,
    "HD": 4, "MCD": 4, "NKE": 4, "DIS": 4, "NFLX": 4,
    "WMT": 4, "COST": 4, "TGT": 4, "KO": 4, "PEP": 4,
    "BA": 5, "CAT": 5, "GE": 5, "MMM": 5, "LMT": 5,
}


class FeatureBuilder:
    """
    Builds windowed feature tensors for all symbols.
    Call fit_scalers() on training data, then build() for any split.
    """

    def __init__(self, cfg, symbols: List[str]):
        self.cfg = cfg
        self.symbols = symbols
        self.price_window = cfg.model.price_window
        self.sentiment_window = cfg.model.sentiment_window
        self.macro_window = cfg.model.macro_window
        self.horizon = cfg.targets.horizon_days
        self.r_hi = cfg.targets.r_hi
        self.r_lo = cfg.targets.r_lo
        self.scalers_dir = cfg.paths.scalers_dir
        self.raw_dir = cfg.paths.raw_dir
        os.makedirs(self.scalers_dir, exist_ok=True)

        # Scalers per group
        self._price_scaler = StandardScaler()
        self._sentiment_scaler = StandardScaler()
        self._macro_scaler = StandardScaler()
        self._scalers_fitted = False

        # Symbol / sector index maps
        self.symbol_to_idx = {s: i for i, s in enumerate(symbols)}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fit_scalers(self, all_price_features: np.ndarray,
                    all_sentiment_features: np.ndarray,
                    all_macro_features: np.ndarray) -> None:
        """
        Fit scalers on TRAINING data only.
        Pass flattened 2D arrays (n_samples * window, n_features).
        """
        self._price_scaler.fit(all_price_features)
        self._sentiment_scaler.fit(all_sentiment_features)
        self._macro_scaler.fit(all_macro_features)
        self._scalers_fitted = True

        joblib.dump(self._price_scaler, os.path.join(self.scalers_dir, "price_scaler.joblib"))
        joblib.dump(self._sentiment_scaler, os.path.join(self.scalers_dir, "sentiment_scaler.joblib"))
        joblib.dump(self._macro_scaler, os.path.join(self.scalers_dir, "macro_scaler.joblib"))
        logger.info("Scalers fitted and saved.")

    def load_scalers(self) -> None:
        """Load previously fitted scalers for inference (transform only)."""
        self._price_scaler = joblib.load(os.path.join(self.scalers_dir, "price_scaler.joblib"))
        self._sentiment_scaler = joblib.load(os.path.join(self.scalers_dir, "sentiment_scaler.joblib"))
        self._macro_scaler = joblib.load(os.path.join(self.scalers_dir, "macro_scaler.joblib"))
        self._scalers_fitted = True
        logger.info("Scalers loaded.")

    def build_dataset(
        self,
        bars_dict: Dict[str, pd.DataFrame],
        macro_df: pd.DataFrame,
        spy_bars: pd.DataFrame,
        regimes: pd.Series,
        start_date: str,
        end_date: str,
        fit_scalers: bool = False,
    ) -> Tuple:
        """
        Builds the full dataset for a date range.
        Returns:
          price_X      : (N, window, n_price_features)
          sentiment_X  : (N, window, n_sent_features)
          macro_X      : (N, window, n_macro_features)
          regime_X     : (N, 3)  one-hot
          company_idx  : (N,)    int
          sector_idx   : (N,)    int
          labels       : (N,)    int  class 0-4
          meta         : list of (symbol, date) for each sample
        """
        if not self._scalers_fitted and not fit_scalers:
            self.load_scalers()

        spy_returns = spy_bars["close"].pct_change()

        all_price_raw, all_sent_raw, all_macro_raw = [], [], []
        all_labels, all_regimes, all_company, all_sector, all_meta = [], [], [], [], []

        for sym in self.symbols:
            if sym not in bars_dict:
                continue
            bars = bars_dict[sym]
            bars = bars[(bars.index >= start_date) & (bars.index <= end_date)]
            if len(bars) < self.price_window + self.horizon + 5:
                continue

            # Technical features
            bench_ret = spy_returns.reindex(bars.index).fillna(0)
            tech = compute_all(bars, benchmark_returns=bench_ret)

            # Sentiment features
            sent = compute_sentiment_features(sym, self.raw_dir, bars.index)

            # Macro features (aligned)
            macro_aligned = macro_df.reindex(bars.index).ffill().fillna(0)

            # Regimes
            regime_aligned = regimes.reindex(bars.index).ffill().fillna(2).astype(int)

            close = bars["close"]
            company_idx = self.symbol_to_idx.get(sym, 0)
            sector_idx = SECTOR_MAP.get(sym, 6)  # 6 = unknown

            # Build windowed samples
            pw = self.price_window
            sw = self.sentiment_window
            mw = self.macro_window
            max_w = max(pw, sw, mw)

            price_cols = [c for c in tech.columns]
            sent_cols = [c for c in sent.columns]
            macro_cols = [c for c in macro_aligned.columns]

            tech_arr = tech.values
            sent_arr = sent.values
            macro_arr = macro_aligned.values
            close_arr = close.values
            regime_arr = regime_aligned.values

            for i in range(max_w, len(bars) - self.horizon):
                # Label: forward return class
                future_ret = (close_arr[i + self.horizon] - close_arr[i]) / (close_arr[i] + 1e-10)
                label = self._classify(future_ret)

                p_window = tech_arr[i - pw: i]
                s_window = sent_arr[i - sw: i] if len(sent_arr) > 0 else np.zeros((sw, len(sent_cols)))
                m_window = macro_arr[i - mw: i]

                if p_window.shape[0] < pw or m_window.shape[0] < mw:
                    continue

                all_price_raw.append(p_window)
                all_sent_raw.append(s_window)
                all_macro_raw.append(m_window)
                all_labels.append(label)
                all_regimes.append(regime_arr[i])
                all_company.append(company_idx)
                all_sector.append(sector_idx)
                all_meta.append((sym, bars.index[i].strftime("%Y-%m-%d")))

        if not all_price_raw:
            raise ValueError("No samples built. Check date ranges and data availability.")

        price_X = np.array(all_price_raw, dtype=np.float32)   # (N, pw, F_price)
        sent_X = np.array(all_sent_raw, dtype=np.float32)     # (N, sw, F_sent)
        macro_X = np.array(all_macro_raw, dtype=np.float32)   # (N, mw, F_macro)
        labels = np.array(all_labels, dtype=np.int64)
        regimes_arr = np.array(all_regimes, dtype=np.int64)
        company_arr = np.array(all_company, dtype=np.int64)
        sector_arr = np.array(all_sector, dtype=np.int64)

        # Fit or transform scalers
        N, pw, fp = price_X.shape
        _, sw2, fs = sent_X.shape
        _, mw2, fm = macro_X.shape

        if fit_scalers:
            self.fit_scalers(
                price_X.reshape(-1, fp),
                sent_X.reshape(-1, fs),
                macro_X.reshape(-1, fm),
            )

        price_X = self._price_scaler.transform(price_X.reshape(-1, fp)).reshape(N, pw, fp)
        sent_X = self._sentiment_scaler.transform(sent_X.reshape(-1, fs)).reshape(N, sw2, fs)
        macro_X = self._macro_scaler.transform(macro_X.reshape(-1, fm)).reshape(N, mw2, fm)

        # One-hot regimes
        regime_onehot = np.eye(3, dtype=np.float32)[regimes_arr]

        return (
            price_X.astype(np.float32),
            sent_X.astype(np.float32),
            macro_X.astype(np.float32),
            regime_onehot,
            company_arr,
            sector_arr,
            labels,
            all_meta,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _classify(self, ret: float) -> int:
        """
        Maps a forward return to a class label:
          4 = strong buy    (ret >  r_hi)
          3 = weak buy      (r_lo < ret <= r_hi)
          2 = hold          (-r_lo <= ret <= r_lo)
          1 = weak sell     (-r_hi <= ret < -r_lo)
          0 = strong sell   (ret < -r_hi)
        """
        if ret > self.r_hi:
            return 4
        elif ret > self.r_lo:
            return 3
        elif ret >= -self.r_lo:
            return 2
        elif ret >= -self.r_hi:
            return 1
        else:
            return 0
