"""Market regime detection using Hidden Markov Model on SPY returns."""
import numpy as np
import pandas as pd
from typing import Optional
from ultimate_trader.utils.logging import get_logger

logger = get_logger(__name__)

# Regime labels
REGIME_BULL = "bull"
REGIME_BEAR = "bear"
REGIME_SIDEWAYS = "sideways"
REGIME_CRISIS = "crisis"


class RegimeDetector:
    """
    Fits a 4-state Gaussian HMM on SPY daily returns to identify market regimes:
      - Bull    (high positive drift, medium vol)
      - Bear    (negative drift, elevated vol)
      - Sideways (near-zero drift, low vol)
      - Crisis  (most negative drift, highest vol — extreme drawdown periods)

    The current regime is used by the risk module to adjust position sizes,
    confidence thresholds, and exposure limits.
    """

    def __init__(self, n_components: int = 4):
        self.n_components = n_components
        self.model = None
        self._regime_map = {}  # hidden state index -> label

    def fit(self, spy_bars: pd.DataFrame) -> "RegimeDetector":
        """
        Fit HMM on SPY log returns.
        spy_bars must have a 'close' column.
        """
        try:
            from hmmlearn.hmm import GaussianHMM
        except ImportError:
            logger.error("hmmlearn not installed. Run: pip install hmmlearn")
            return self

        returns = np.log(spy_bars["close"]).diff().dropna().values.reshape(-1, 1)
        self.model = GaussianHMM(
            n_components=self.n_components,
            covariance_type="full",
            n_iter=300,
            random_state=42,
        )
        self.model.fit(returns)

        # Assign labels based on mean return and variance
        means = self.model.means_.flatten()
        # Extract per-state variance from covariance matrix
        variances = np.array([
            self.model.covars_[i].flatten()[0]
            for i in range(self.n_components)
        ])
        ranked = np.argsort(means)  # ascending: ranked[0] = most negative mean

        # Bull = highest mean; Sideways = 2nd highest mean
        bull_state = int(ranked[3])
        sideways_state = int(ranked[2])

        # Among the two lowest-mean states, crisis = higher variance, bear = lower variance
        low_pair = ranked[:2]
        crisis_idx = int(low_pair[np.argmax(variances[low_pair])])
        bear_idx = int(low_pair[1 - np.argmax(variances[low_pair])])

        self._regime_map = {
            bull_state:     REGIME_BULL,
            sideways_state: REGIME_SIDEWAYS,
            bear_idx:       REGIME_BEAR,
            crisis_idx:     REGIME_CRISIS,
        }

        logger.info(
            f"Regime HMM fitted (4-state). Means: {dict(zip(range(self.n_components), means.round(5)))} "
            f"| Map: {self._regime_map}"
        )
        return self

    def predict(self, spy_bars: pd.DataFrame) -> pd.Series:
        """Returns a pd.Series of regime labels indexed by date."""
        if self.model is None:
            logger.warning("RegimeDetector not fitted. Returning 'sideways' for all dates.")
            return pd.Series(REGIME_SIDEWAYS, index=spy_bars.index)

        returns = np.log(spy_bars["close"]).diff().fillna(0).values.reshape(-1, 1)
        hidden_states = self.model.predict(returns)
        labels = [self._regime_map.get(int(s), REGIME_SIDEWAYS) for s in hidden_states]
        return pd.Series(labels, index=spy_bars.index, name="regime")

    def current_regime(self, spy_bars: pd.DataFrame) -> str:
        """Returns the regime label for the most recent date."""
        series = self.predict(spy_bars)
        return series.iloc[-1]

    def save(self, path: str):
        import pickle
        with open(path, "wb") as f:
            pickle.dump({"model": self.model, "regime_map": self._regime_map,
                         "n_components": self.n_components}, f)
        logger.info(f"RegimeDetector saved to {path}")

    def load(self, path: str) -> "RegimeDetector":
        import pickle
        with open(path, "rb") as f:
            data = pickle.load(f)
        self.model = data["model"]
        self._regime_map = data["regime_map"]
        self.n_components = data.get("n_components", 4)
        logger.info(f"RegimeDetector loaded from {path}")
        return self
