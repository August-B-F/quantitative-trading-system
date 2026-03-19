"""Bayesian hyperparameter search using Optuna.

Objective: maximise walk-forward Sharpe ratio.
Search space is defined in config/training.yaml under hyperparam_search.search_space.

Usage:
    from ultimate_trader.modeling.hyperparam_search import run_search
    best_params = run_search(dataset, cfg, n_trials=80)
"""
import json
import optuna
import numpy as np
from pathlib import Path
from typing import Callable

from ultimate_trader.utils.logging import get_logger

logger = get_logger(__name__)
optuna.logging.set_verbosity(optuna.logging.WARNING)


def _suggest_params(trial: optuna.Trial, search_space: dict) -> dict:
    """
    Map search_space config entries to Optuna suggest calls.

    search_space entries can be:
        [min, max]      -> suggest_float (log scale if both > 0 and ratio > 100)
        [a, b, step]    -> suggest_int
        [opt1, opt2, ..]  (len > 2 or strings) -> suggest_categorical
    """
    params = {}
    for name, bounds in search_space.items():
        if isinstance(bounds[0], str) or len(bounds) > 2:
            params[name] = trial.suggest_categorical(name, bounds)
        elif all(isinstance(b, int) for b in bounds):
            params[name] = trial.suggest_int(name, bounds[0], bounds[1])
        else:
            lo, hi = bounds[0], bounds[1]
            log = (hi / lo > 100) if lo > 0 else False
            params[name] = trial.suggest_float(name, lo, hi, log=log)
    return params


def run_search(
    build_and_evaluate_fn: Callable[[dict], float],
    cfg: dict,
    n_trials: int = 80,
    save_dir: str = "data/models",
) -> dict:
    """
    Run Optuna hyperparameter search.

    Args:
        build_and_evaluate_fn:
            A callable that accepts a params dict and returns a float score
            (e.g. walk-forward Sharpe). This function is responsible for
            training and evaluating one set of hyperparameters.
        cfg: full config dict
        n_trials: number of Optuna trials
        save_dir: where to save best params JSON

    Returns:
        dict of best hyperparameters
    """
    search_space = cfg.get("hyperparam_search", {}).get("search_space", {})
    sampler = optuna.samplers.TPESampler(seed=42)
    study = optuna.create_study(direction="maximize", sampler=sampler)

    def objective(trial: optuna.Trial) -> float:
        params = _suggest_params(trial, search_space)
        try:
            score = build_and_evaluate_fn(params)
        except Exception as e:
            logger.warning(f"Trial failed: {e}")
            return -np.inf
        return score

    logger.info(f"Starting Optuna search with {n_trials} trials")
    study.optimize(objective, n_trials=n_trials, show_progress_bar=True)

    best = study.best_params
    logger.info(f"Best params: {best}  |  Best score: {study.best_value:.4f}")

    Path(save_dir).mkdir(parents=True, exist_ok=True)
    out_path = Path(save_dir) / "best_hyperparams.json"
    with open(out_path, "w") as f:
        json.dump({"params": best, "score": study.best_value}, f, indent=2)
    logger.info(f"Best params saved to {out_path}")

    return best
