"""Market regime detection using Hidden Markov Models on benchmark returns."""
import numpy as np
import pandas as pd
from typing import Tuple
from pathlib import Path
import joblib

from ultimate_trader.utils.logging import get_logger

log = get_logger(__name__)

try:
    from hmmlearn.hmm import GaussianHMM
    _HMM_AVAILABLE = True
except ImportError:
    _HMM_AVAILABLE = False
    log.warning("hmmlearn not installed. Regime detection will use simple volatility-based method.")


REGIME_LABELS = {0: "bear", 1: "sideways", 2: "bull"}


class RegimeDetector:
    """
    Detects market regime (bull / sideways / bear) from SPY daily returns.

    HMM approach (preferred):
        - 3-state Gaussian HMM fitted on (daily_return, rolling_vol) features
        - States are post-hoc labelled by mean return: lowest=bear, highest=bull

    Fallback (if hmmlearn not available):
        - Rolling 20d return + rolling volatility thresholds
    """

    def __init__(self, n_states: int = 3, random_state: int = 42):
        self.n_states = n_states
        self.random_state = random_state
        self.model = None
        self._state_map: dict = {}

    def fit(self, benchmark_bars: pd.DataFrame) -> "RegimeDetector":
        """
        Fit HMM on benchmark OHLCV bars.
        benchmark_bars: DataFrame with 'close' column.
        """
        close = benchmark_bars["close"]
        ret   = close.pct_change().dropna()
        vol   = ret.rolling(20, min_periods=5).std().dropna()
        ret   = ret.loc[vol.index]

        X = np.column_stack([ret.values, vol.values])

        if _HMM_AVAILABLE:
            self.model = GaussianHMM(
                n_components=self.n_states,
                covariance_type="full",
                n_iter=200,
                random_state=self.random_state,
            )
            self.model.fit(X)

            # label states by mean return: lowest = bear, highest = bull
            means = self.model.means_[:, 0]
            order = np.argsort(means)
            self._state_map = {int(order[i]): REGIME_LABELS[i] for i in range(self.n_states)}
        else:
            # fallback: fit thresholds from percentiles
            self._ret_p33 = float(np.percentile(ret.values, 33))
            self._ret_p66 = float(np.percentile(ret.values, 66))

        log.info(f"RegimeDetector fitted. State map: {self._state_map}")
        return self

    def predict(self, benchmark_bars: pd.DataFrame) -> pd.Series:
        """
        Predict regime for each date in benchmark_bars.
        Returns pd.Series of regime labels indexed by date.
        """
        close = benchmark_bars["close"]
        ret   = close.pct_change().dropna()
        vol   = ret.rolling(20, min_periods=5).std().dropna()
        ret   = ret.loc[vol.index]

        if _HMM_AVAILABLE and self.model is not None:
            X = np.column_stack([ret.values, vol.values])
            raw_states = self.model.predict(X)
            labels = [self._state_map.get(int(s), "sideways") for s in raw_states]
            return pd.Series(labels, index=ret.index, name="regime")
        else:
            rolling_ret = ret.rolling(20, min_periods=5).mean()
            labels = pd.cut(
                rolling_ret,
                bins=[-np.inf, self._ret_p33, self._ret_p66, np.inf],
                labels=["bear", "sideways", "bull"]
            ).rename("regime")
            return labels

    def current_regime(self, benchmark_bars: pd.DataFrame) -> str:
        """Return the most recent regime label."""
        regimes = self.predict(benchmark_bars)
        return str(regimes.dropna().iloc[-1])

    def save(self, path: str):
        joblib.dump({"model": self.model, "state_map": self._state_map}, path)

    def load(self, path: str) -> "RegimeDetector":
        data = joblib.load(path)
        self.model = data["model"]
        self._state_map = data["state_map"]
        return self


REGIME_PARAMS = {
    "bull":     {"confidence_threshold": 0.50, "kelly_multiplier": 1.0,  "max_gross_exposure": 0.95},
    "sideways": {"confidence_threshold": 0.60, "kelly_multiplier": 0.6,  "max_gross_exposure": 0.60},
    "bear":     {"confidence_threshold": 0.70, "kelly_multiplier": 0.3,  "max_gross_exposure": 0.30},
}


def get_regime_overrides(regime: str) -> dict:
    """Return risk parameter overrides for the current regime."""
    return REGIME_PARAMS.get(regime, REGIME_PARAMS["sideways"])
