"""Bayesian hyperparameter search with Optuna + walk-forward validation."""
import os
import json
import numpy as np
from typing import Callable, Dict
from ultimate_trader.utils.logging import get_logger

logger = get_logger(__name__)


def run_search(
    objective_fn: Callable,
    search_space: dict,
    n_trials: int = 80,
    study_name: str = "trading_hparam_search",
    output_dir: str = "data/models",
) -> Dict:
    """
    Runs Optuna Bayesian optimization to find best hyperparameters.

    objective_fn: function(trial, params) -> float (metric to MAXIMIZE, e.g. Sharpe)
    search_space: dict from training.yaml hyperparam_search.search_space

    Returns best params dict.
    """
    try:
        import optuna
        optuna.logging.set_verbosity(optuna.logging.WARNING)
    except ImportError:
        logger.error("optuna not installed. Run: pip install optuna")
        return {}

    def _objective(trial):
        params = {}
        for name, bounds in search_space.items():
            if isinstance(bounds, list) and len(bounds) == 2:
                lo, hi = bounds
                if isinstance(lo, float) or isinstance(hi, float):
                    params[name] = trial.suggest_float(name, lo, hi)
                else:
                    params[name] = trial.suggest_int(name, lo, hi)
            elif isinstance(bounds, list) and len(bounds) > 2:
                params[name] = trial.suggest_categorical(name, bounds)
        return objective_fn(trial, params)

    storage = f"sqlite:///{os.path.join(output_dir, study_name)}.db"
    os.makedirs(output_dir, exist_ok=True)

    study = optuna.create_study(
        direction="maximize",
        study_name=study_name,
        storage=storage,
        load_if_exists=True,
        sampler=optuna.samplers.TPESampler(seed=42),
        pruner=optuna.pruners.MedianPruner(n_warmup_steps=10),
    )

    study.optimize(_objective, n_trials=n_trials, show_progress_bar=True)

    best = study.best_params
    best_value = study.best_value
    logger.info(f"Best params (Sharpe={best_value:.3f}): {best}")

    # Save best params
    out_path = os.path.join(output_dir, "best_hyperparams.json")
    with open(out_path, "w") as f:
        json.dump({"best_value": best_value, "params": best}, f, indent=2)
    logger.info(f"Best hyperparams saved to {out_path}")

    return best
