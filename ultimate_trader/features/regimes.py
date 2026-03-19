"""Market regime detection using a Hidden Markov Model on SPY returns."""
import numpy as np
import pandas as pd
import joblib
from pathlib import Path
from hmmlearn.hmm import GaussianHMM

from ultimate_trader.utils.logging import get_logger

log = get_logger(__name__)

N_REGIMES = 3  # 0=bear/high-vol, 1=sideways, 2=bull/low-vol


class RegimeDetector:
    def __init__(self, cfg: dict, n_regimes: int = N_REGIMES):
        self.cfg = cfg
        self.n_regimes = n_regimes
        self.model: GaussianHMM | None = None
        self.model_path = Path(cfg["paths"]["models_dir"]) / "regime_hmm.pkl"
        Path(cfg["paths"]["models_dir"]).mkdir(parents=True, exist_ok=True)

    def fit(self, benchmark_bars: pd.DataFrame) -> "RegimeDetector":
        """
        Fit HMM on benchmark (SPY) daily returns + rolling volatility.
        Features: [return_1d, vol_5d]
        """
        close = benchmark_bars["close"]
        returns = close.pct_change().fillna(0)
        vol5 = returns.rolling(5).std().fillna(method="bfill")

        X = np.column_stack([returns.values, vol5.values])

        log.info(f"Fitting HMM regime model with {self.n_regimes} states on {len(X)} observations")
        self.model = GaussianHMM(
            n_components=self.n_regimes,
            covariance_type="full",
            n_iter=200,
            random_state=42
        )
        self.model.fit(X)

        # Save
        joblib.dump(self.model, self.model_path)
        log.info(f"Regime HMM saved to {self.model_path}")
        return self

    def load(self) -> "RegimeDetector":
        self.model = joblib.load(self.model_path)
        log.info("Regime HMM loaded")
        return self

    def predict(self, benchmark_bars: pd.DataFrame) -> pd.Series:
        """Return a Series of regime labels aligned to benchmark_bars index."""
        if self.model is None:
            try:
                self.load()
            except FileNotFoundError:
                log.warning("No regime model found, defaulting to regime 1 (neutral)")
                return pd.Series(1, index=benchmark_bars.index, name="regime")

        close = benchmark_bars["close"]
        returns = close.pct_change().fillna(0)
        vol5 = returns.rolling(5).std().fillna(method="bfill")
        X = np.column_stack([returns.values, vol5.values])
        labels = self.model.predict(X)

        # Sort regimes by mean return so regime 0 = lowest (bear), 2 = highest (bull)
        means = [self.model.means_[i][0] for i in range(self.n_regimes)]
        order = np.argsort(means)  # ascending mean return
        remap = {old: new for new, old in enumerate(order)}
        relabelled = np.array([remap[l] for l in labels])

        return pd.Series(relabelled, index=benchmark_bars.index, name="regime")

    def get_current_regime(self, benchmark_bars: pd.DataFrame) -> int:
        """Return the most recent regime label as int."""
        regimes = self.predict(benchmark_bars)
        return int(regimes.iloc[-1])
