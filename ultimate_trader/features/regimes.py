"""Market regime detection using a Hidden Markov Model on SPY returns.

Regime labels (0, 1, 2):
  0 = low-volatility bull  (strong trend up, quiet)
  1 = high-volatility / transitional
  2 = bear / crash

The HMM is fitted on SPY log-returns and produces a per-day state label
that is used as a conditioning signal in the model and risk layer.
"""
import numpy as np
import pandas as pd
import joblib
from pathlib import Path
from typing import Optional

from ultimate_trader.utils.logging import get_logger

logger = get_logger(__name__)


def fit_regime_hmm(
    spy_df: pd.DataFrame,
    n_states: int = 3,
    save_path: Optional[str] = "data/scalers/regime_hmm.joblib",
) -> object:
    """
    Fit a Gaussian HMM on SPY daily log-returns.

    Args:
        spy_df: DataFrame with 'close' column
        n_states: number of hidden regime states
        save_path: where to persist the fitted model

    Returns:
        Fitted hmmlearn GaussianHMM object
    """
    try:
        from hmmlearn.hmm import GaussianHMM
    except ImportError:
        raise ImportError("Install hmmlearn: pip install hmmlearn")

    log_ret = np.log(spy_df["close"] / spy_df["close"].shift(1)).dropna().values.reshape(-1, 1)
    model = GaussianHMM(n_components=n_states, covariance_type="full", n_iter=200, random_state=42)
    model.fit(log_ret)
    logger.info(f"HMM fitted. States means: {model.means_.flatten()}")

    if save_path:
        Path(save_path).parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(model, save_path)
        logger.info(f"HMM saved to {save_path}")

    return model


def load_regime_hmm(path: str = "data/scalers/regime_hmm.joblib") -> object:
    """Load a previously fitted HMM from disk."""
    return joblib.load(path)


def predict_regimes(
    spy_df: pd.DataFrame,
    model: object,
) -> pd.Series:
    """
    Predict daily regime labels from a fitted HMM.

    Args:
        spy_df: DataFrame with 'close' column and DatetimeIndex
        model: fitted GaussianHMM

    Returns:
        pd.Series of integer regime labels indexed on spy_df.index[1:]
    """
    log_ret = np.log(spy_df["close"] / spy_df["close"].shift(1)).dropna().values.reshape(-1, 1)
    states = model.predict(log_ret)
    # Re-order states so that 0 = lowest volatility (bull)
    vols = [log_ret[states == s].std() for s in range(model.n_components)]
    order = np.argsort(vols)  # ascending vol -> state 0 is bull
    remap = {old: new for new, old in enumerate(order)}
    remapped = np.array([remap[s] for s in states])
    return pd.Series(remapped, index=spy_df.index[1:], name="regime")


def add_regime_features(
    df: pd.DataFrame,
    regime_series: pd.Series,
) -> pd.DataFrame:
    """
    Merge regime labels into a symbol DataFrame and add one-hot regime columns.

    Args:
        df: symbol DataFrame with DatetimeIndex
        regime_series: pd.Series from predict_regimes

    Returns:
        df with added columns: regime, regime_0, regime_1, regime_2
    """
    out = df.copy()
    out["regime"] = regime_series.reindex(out.index).ffill().fillna(1).astype(int)
    for i in range(3):
        out[f"regime_{i}"] = (out["regime"] == i).astype(float)
    return out
