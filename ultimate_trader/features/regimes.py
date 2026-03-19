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


class RegimeDetector:
    """
    Fits a Gaussian HMM on SPY daily returns to identify 3 market regimes:
      - Bull (high positive drift, medium vol)
      - Bear (negative drift, high vol)
      - Sideways (near-zero drift, low vol)

    The current regime is used by the risk module to adjust position sizes,
    confidence thresholds, and exposure limits.
    """

    def __init__(self, n_components: int = 3):
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
            n_iter=200,
            random_state=42,
        )
        self.model.fit(returns)

        # Assign labels based on mean return of each hidden state
        means = self.model.means_.flatten()
        ranked = np.argsort(means)  # lowest mean -> highest mean
        labels = [REGIME_BEAR, REGIME_SIDEWAYS, REGIME_BULL]
        self._regime_map = {int(ranked[i]): labels[i] for i in range(len(labels))}

        logger.info(f"Regime HMM fitted. State means: {dict(zip(self._regime_map.values(), sorted(means)))}")
        return self

    def predict(self, spy_bars: pd.DataFrame) -> pd.Series:
        """
        Returns a pd.Series of regime labels indexed by date.
        """
        if self.model is None:
            logger.warning("RegimeDetector not fitted. Returning 'sideways' for all dates.")
            return pd.Series(REGIME_SIDEWAYS, index=spy_bars.index)

        returns = np.log(spy_bars["close"]).diff().fillna(0).values.reshape(-1, 1)
        hidden_states = self.model.predict(returns)
        labels = [self._regime_map.get(int(s), REGIME_SIDEWAYS) for s in hidden_states]
        return pd.Series(labels, index=spy_bars.index, name="regime")

    def current_regime(self, spy_bars: pd.DataFrame) -> str:
        """
        Returns the regime label for the most recent date.
        """
        series = self.predict(spy_bars)
        return series.iloc[-1]

    def save(self, path: str):
        import pickle
        with open(path, "wb") as f:
            pickle.dump({"model": self.model, "regime_map": self._regime_map}, f)
        logger.info(f"RegimeDetector saved to {path}")

    def load(self, path: str) -> "RegimeDetector":
        import pickle
        with open(path, "rb") as f:
            data = pickle.load(f)
        self.model = data["model"]
        self._regime_map = data["regime_map"]
        logger.info(f"RegimeDetector loaded from {path}")
        return self
