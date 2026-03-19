"""Assembles all feature streams into a single aligned dataset with labels."""
import numpy as np
import pandas as pd
import joblib
from pathlib import Path
from sklearn.preprocessing import RobustScaler
from typing import Optional

from ultimate_trader.features.technicals import compute_all_technicals
from ultimate_trader.features.sentiment import build_sentiment_features
from ultimate_trader.features.regimes import RegimeDetector
from ultimate_trader.utils.logging import get_logger

log = get_logger(__name__)


class FeatureBuilder:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.price_window = cfg["model"]["price_window"]
        self.sentiment_window = cfg["model"]["sentiment_window"]
        self.macro_window = cfg["model"]["macro_window"]
        self.horizon = cfg["targets"]["horizon_days"]
        self.r_hi = cfg["targets"]["r_hi"]
        self.r_lo = cfg["targets"]["r_lo"]
        self.scalers_dir = Path(cfg["paths"]["scalers_dir"])
        self.scalers_dir.mkdir(parents=True, exist_ok=True)
        self.scalers: dict[str, RobustScaler] = {}

    def build(
        self,
        symbol: str,
        bars: pd.DataFrame,
        sentiment_df: pd.DataFrame,
        macro_df: pd.DataFrame,
        regime_series: pd.Series,
        symbol_idx: int,
        fit_scalers: bool = True
    ) -> Optional[dict]:
        """
        Build windowed feature tensors and labels for one symbol.

        Returns a dict with keys:
          price_seq: np.ndarray (T, price_window, n_price_features)
          sentiment_seq: np.ndarray (T, sentiment_window, n_sent_features)
          macro_seq: np.ndarray (T, macro_window, n_macro_features)
          regime: np.ndarray (T,)  current regime at each step
          symbol_idx: np.ndarray (T,)  integer index for embedding
          labels: np.ndarray (T,)  class label 0-4
          dates: list[str]
        """
        try:
            # --- Technical features
            tech = compute_all_technicals(bars)

            # --- Align all data to the same date index
            idx = tech.index.intersection(sentiment_df.index).intersection(macro_df.index)
            if len(idx) < self.price_window + self.horizon + 30:
                log.warning(f"{symbol}: insufficient data ({len(idx)} rows), skipping")
                return None

            tech = tech.reindex(idx)
            sent = sentiment_df.reindex(idx)
            macro = macro_df.reindex(idx)
            regime = regime_series.reindex(idx).fillna(1).astype(int)
            close = bars["close"].reindex(idx)

            # --- Labels: future N-day return classified into 5 bins
            future_return = close.pct_change(self.horizon).shift(-self.horizon)

            def make_label(r):
                if pd.isna(r):
                    return np.nan
                if r >= self.r_hi:
                    return 4   # strong buy
                elif r >= self.r_lo:
                    return 3   # weak buy
                elif r > -self.r_lo:
                    return 2   # hold
                elif r > -self.r_hi:
                    return 1   # weak sell
                else:
                    return 0   # strong sell

            labels = future_return.map(make_label)

            # --- Scale features
            price_cols = [c for c in tech.columns]
            sent_cols = [c for c in sent.columns]
            macro_cols = [c for c in macro.columns]

            tech_scaled = self._scale(tech, f"{symbol}_price", fit_scalers)
            sent_scaled = self._scale(sent, f"{symbol}_sent", fit_scalers)
            macro_scaled = self._scale(macro, "macro", fit_scalers)  # shared scaler for macro

            # --- Build sliding windows
            price_seqs, sent_seqs, macro_seqs, regime_vals, sym_idxs, label_vals, dates = \
                [], [], [], [], [], [], []

            window = max(self.price_window, self.sentiment_window, self.macro_window)
            for i in range(window, len(idx) - self.horizon):
                if pd.isna(labels.iloc[i]):
                    continue

                p_slice = tech_scaled.iloc[i - self.price_window:i].values
                s_slice = sent_scaled.iloc[i - self.sentiment_window:i].values
                m_slice = macro_scaled.iloc[i - self.macro_window:i].values

                if (p_slice.shape[0] != self.price_window or
                        s_slice.shape[0] != self.sentiment_window or
                        m_slice.shape[0] != self.macro_window):
                    continue

                price_seqs.append(p_slice)
                sent_seqs.append(s_slice)
                macro_seqs.append(m_slice)
                regime_vals.append(int(regime.iloc[i]))
                sym_idxs.append(symbol_idx)
                label_vals.append(int(labels.iloc[i]))
                dates.append(str(idx[i].date()))

            if not price_seqs:
                return None

            return {
                "price_seq": np.array(price_seqs, dtype=np.float32),
                "sentiment_seq": np.array(sent_seqs, dtype=np.float32),
                "macro_seq": np.array(macro_seqs, dtype=np.float32),
                "regime": np.array(regime_vals, dtype=np.int64),
                "symbol_idx": np.array(sym_idxs, dtype=np.int64),
                "labels": np.array(label_vals, dtype=np.int64),
                "dates": dates
            }

        except Exception as e:
            log.error(f"FeatureBuilder failed for {symbol}: {e}")
            return None

    def _scale(self, df: pd.DataFrame, key: str, fit: bool) -> pd.DataFrame:
        """Scale a DataFrame using a RobustScaler, fit if needed."""
        df = df.replace([np.inf, -np.inf], np.nan).fillna(method="ffill").fillna(0)
        values = df.values
        if fit or key not in self.scalers:
            scaler = RobustScaler()
            scaled = scaler.fit_transform(values)
            self.scalers[key] = scaler
            joblib.dump(scaler, self.scalers_dir / f"{key}_scaler.pkl")
        else:
            scaler = self.scalers[key]
            scaled = scaler.transform(values)
        return pd.DataFrame(scaled, index=df.index, columns=df.columns)

    def load_scalers(self, keys: list[str]) -> None:
        """Load pre-fitted scalers from disk."""
        for key in keys:
            path = self.scalers_dir / f"{key}_scaler.pkl"
            if path.exists():
                self.scalers[key] = joblib.load(path)
            else:
                log.warning(f"Scaler not found for key {key}")
