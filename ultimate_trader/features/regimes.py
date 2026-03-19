"""
regimes.py

Market regime detection using Hidden Markov Model (HMM) on SPY daily returns.

Regimes:
  0 = low_vol_bull     (trending up, low volatility)
  1 = high_vol_bear    (trending down, high volatility)
  2 = sideways_chop    (mean-reverting, medium volatility)

The regime label is a daily feature fed into the model AND
used by risk.py to modulate position sizing / confidence thresholds.

Fix vs old bot:
  Previous bot had zero regime awareness. Position sizing and
  confidence thresholds were static regardless of market environment.
"""

import os
import numpy as np
import pandas as pd
import joblib
from typing import Optional

from ultimate_trader.utils.logging import get_logger

logger = get_logger("regimes")

N_STATES = 3
REGIME_NAMES = {0: "low_vol_bull", 1: "high_vol_bear", 2: "sideways_chop"}


class RegimeDetector:
    """
    Fits a Gaussian HMM on benchmark (SPY) returns + volatility.
    Predicts regime labels for any date range.
    """

    def __init__(self, n_states: int = N_STATES, scalers_dir: str = "data/scalers"):
        self.n_states = n_states
        self.scalers_dir = scalers_dir
        self.model = None
        self._state_map = None  # maps raw HMM state -> semantic regime
        os.makedirs(scalers_dir, exist_ok=True)

    def fit(self, spy_bars: pd.DataFrame) -> "RegimeDetector":
        """
        Fit HMM on SPY. Features: [daily_return, rolling_vol_10d, rolling_vol_20d].
        """
        try:
            from hmmlearn.hmm import GaussianHMM
        except ImportError:
            raise ImportError("Install hmmlearn: pip install hmmlearn")

        close = spy_bars["close"]
        ret = close.pct_change().fillna(0)
        vol10 = ret.rolling(10).std().fillna(0)
        vol20 = ret.rolling(20).std().fillna(0)

        X = np.column_stack([ret.values, vol10.values, vol20.values])
        X = X[20:]  # drop NaN prefix

        self.model = GaussianHMM(
            n_components=self.n_states,
            covariance_type="diag",
            n_iter=200,
            random_state=42,
        )
        self.model.fit(X)

        # Map states to semantic labels by mean return of each state
        mean_returns = self.model.means_[:, 0]  # first feature = daily return
        sorted_states = np.argsort(mean_returns)  # ascending return
        # State with lowest return = high_vol_bear (1)
        # State with highest return = low_vol_bull (0)
        # Middle = sideways (2)
        self._state_map = {
            sorted_states[0]: 1,  # worst returns -> bear
            sorted_states[1]: 2,  # middle -> chop
            sorted_states[2]: 0,  # best returns -> bull
        }

        path = os.path.join(self.scalers_dir, "regime_hmm.joblib")
        joblib.dump((self.model, self._state_map), path)
        logger.info(f"Regime HMM fitted and saved to {path}")
        return self

    def load(self) -> "RegimeDetector":
        path = os.path.join(self.scalers_dir, "regime_hmm.joblib")
        if not os.path.exists(path):
            raise FileNotFoundError("Regime HMM not fitted yet. Call fit() first.")
        self.model, self._state_map = joblib.load(path)
        return self

    def predict(self, spy_bars: pd.DataFrame) -> pd.Series:
        """
        Predict regime for each trading day.
        Returns Series indexed by date with values {0, 1, 2}.
        """
        if self.model is None:
            raise RuntimeError("Model not fitted. Call fit() or load() first.")

        close = spy_bars["close"]
        ret = close.pct_change().fillna(0)
        vol10 = ret.rolling(10).std().fillna(0)
        vol20 = ret.rolling(20).std().fillna(0)

        X = np.column_stack([ret.values, vol10.values, vol20.values])
        raw_states = self.model.predict(X)
        semantic = np.array([self._state_map[s] for s in raw_states])

        regimes = pd.Series(semantic, index=spy_bars.index, name="regime")
        return regimes

    def predict_latest(self, spy_bars: pd.DataFrame) -> int:
        """Returns the regime label for the most recent bar."""
        return int(self.predict(spy_bars).iloc[-1])

    @staticmethod
    def regime_name(regime_id: int) -> str:
        return REGIME_NAMES.get(regime_id, "unknown")
