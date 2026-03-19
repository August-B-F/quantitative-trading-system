"""Bayesian hyperparameter search using Optuna, maximising walk-forward Sharpe."""
import optuna
import torch
import numpy as np
from typing import Callable

from ultimate_trader.utils.logging import get_logger

log = get_logger(__name__)

optuna.logging.set_verbosity(optuna.logging.WARNING)


def create_objective(
    train_eval_fn: Callable[[dict], float],
    search_space: dict,
) -> Callable:
    """
    Create an Optuna objective function.

    Args:
        train_eval_fn: callable(hyperparams_dict) -> float (score to maximise)
        search_space: dict from training.yaml hyperparam_search.search_space

    Returns:
        objective function for optuna.Study.optimize()
    """
    def objective(trial: optuna.Trial) -> float:
        params = {}
        for name, bounds in search_space.items():
            if isinstance(bounds, list) and len(bounds) == 2:
                lo, hi = bounds
                if isinstance(lo, float) or isinstance(hi, float):
                    params[name] = trial.suggest_float(name, lo, hi)
                else:
                    # treat as integer range
                    params[name] = trial.suggest_int(name, int(lo), int(hi))
            elif isinstance(bounds, list) and len(bounds) > 2:
                # categorical
                params[name] = trial.suggest_categorical(name, bounds)
        try:
            score = train_eval_fn(params)
        except Exception as e:
            log.warning(f"Trial failed: {e}")
            score = -999.0
        return score

    return objective


def run_hyperparam_search(
    train_eval_fn: Callable[[dict], float],
    search_space: dict,
    n_trials: int = 60,
    direction: str = "maximize",
    study_name: str = "stock_trader_search",
    storage: str = None,
) -> dict:
    """
    Run Bayesian hyperparameter search and return best params dict.

    train_eval_fn: your function that takes a params dict,
                   trains a model, runs walk-forward validation,
                   and returns a scalar score (e.g. Sharpe ratio).
    """
    study = optuna.create_study(
        study_name=study_name,
        direction=direction,
        storage=storage,
        load_if_exists=True,
        sampler=optuna.samplers.TPESampler(seed=42),
        pruner=optuna.pruners.MedianPruner(n_startup_trials=10, n_warmup_steps=5),
    )

    objective = create_objective(train_eval_fn, search_space)
    study.optimize(objective, n_trials=n_trials, show_progress_bar=True)

    log.info(f"Best trial score: {study.best_value:.4f}")
    log.info(f"Best params: {study.best_params}")

    return study.best_params
