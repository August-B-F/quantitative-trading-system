"""Market regime detection using Hidden Markov Models on benchmark returns.

Detects N regimes (default 3: bull, bear, sideways/chop).
Used to adapt position sizing and confidence thresholds dynamically.
"""
import numpy as np
import pandas as pd
import pickle
from pathlib import Path
from ultimate_trader.utils.logging import get_logger

logger = get_logger("regimes")


def fit_hmm(
    market_close: pd.Series,
    n_components: int = 3,
    n_iter: int = 200,
) -> tuple:
    """
    Fit a Gaussian HMM on daily log-returns of the market series.
    Returns (fitted_model, states_series).
    States are re-labeled by mean return: 0=bear, 1=neutral, 2=bull.
    """
    from hmmlearn.hmm import GaussianHMM

    log_ret = np.log(market_close / market_close.shift(1)).dropna().values.reshape(-1, 1)

    model = GaussianHMM(
        n_components=n_components,
        covariance_type="full",
        n_iter=n_iter,
        random_state=42,
    )
    model.fit(log_ret)

    raw_states = model.predict(log_ret)

    # relabel states by their mean return (ascending: bear->bull)
    means = [model.means_[i][0] for i in range(n_components)]
    sorted_idx = np.argsort(means)                     # low mean = bear
    remap = {old: new for new, old in enumerate(sorted_idx)}
    relabeled = np.array([remap[s] for s in raw_states])

    index = market_close.dropna().index[1:]            # align with diff'd returns
    states_series = pd.Series(relabeled, index=index, name="regime")

    return model, states_series


def save_hmm(model, path: str = "data/models/hmm_regime.pkl"):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        pickle.dump(model, f)
    logger.info(f"HMM saved to {path}")


def load_hmm(path: str = "data/models/hmm_regime.pkl"):
    with open(path, "rb") as f:
        return pickle.load(f)


def predict_regime(model, market_close: pd.Series, n_components: int = 3) -> pd.Series:
    """
    Predict regime labels for a market_close series using a fitted HMM.
    Returns pd.Series of regime labels.
    """
    log_ret = np.log(market_close / market_close.shift(1)).dropna().values.reshape(-1, 1)
    means = [model.means_[i][0] for i in range(n_components)]
    sorted_idx = np.argsort(means)
    remap = {old: new for new, old in enumerate(sorted_idx)}
    raw = model.predict(log_ret)
    relabeled = np.array([remap[s] for s in raw])
    index = market_close.dropna().index[1:]
    return pd.Series(relabeled, index=index, name="regime")


def get_current_regime(model, market_close: pd.Series, n_components: int = 3) -> int:
    """Return the most recent regime label (0=bear, 1=neutral, 2=bull)."""
    states = predict_regime(model, market_close, n_components)
    return int(states.iloc[-1])


def build_regime_features(
    market_close: pd.Series,
    model=None,
    model_path: str = "data/models/hmm_regime.pkl",
    n_components: int = 3,
) -> pd.DataFrame:
    """
    Build regime one-hot features for the full time series.
    Returns DataFrame with columns: regime_0, regime_1, regime_2.
    """
    if model is None:
        try:
            model = load_hmm(model_path)
            states = predict_regime(model, market_close, n_components)
        except Exception:
            logger.info("Fitting new HMM regime model...")
            model, states = fit_hmm(market_close, n_components)
            save_hmm(model, model_path)
    else:
        states = predict_regime(model, market_close, n_components)

    # one-hot encode
    one_hot = pd.get_dummies(states, prefix="regime")
    for i in range(n_components):
        col = f"regime_{i}"
        if col not in one_hot.columns:
            one_hot[col] = 0

    # also include raw label and VIX-style rolling vol as proxy
    one_hot["regime_raw"] = states

    return one_hot
