"""Bayesian hyperparameter search using Optuna.

Objective: maximise walk-forward out-of-sample Sharpe ratio.
All search logic is in suggest_params() — easy to extend.
"""
import optuna
import torch
import numpy as np
from ultimate_trader.utils.logging import get_logger

logger = get_logger("hyperparam_search")

# Suppress Optuna's noisy logs unless debugging
optuna.logging.set_verbosity(optuna.logging.WARNING)


def suggest_params(trial: optuna.Trial, search_space: dict) -> dict:
    """
    Sample a parameter configuration from the search space defined in training.yaml.
    Handles list ranges [min, max] and categorical lists.
    """
    params = {}
    for name, bounds in search_space.items():
        if isinstance(bounds, list) and len(bounds) == 2:
            lo, hi = bounds
            if isinstance(lo, int) and isinstance(hi, int):
                params[name] = trial.suggest_int(name, lo, hi)
            else:
                params[name] = trial.suggest_float(name, lo, hi, log=(lo > 0 and hi / lo > 10))
        elif isinstance(bounds, list):
            params[name] = trial.suggest_categorical(name, bounds)
        else:
            params[name] = bounds
    return params


def run_search(
    train_fn,
    cfg: dict,
    all_features: dict,
    n_trials: int = 80,
):
    """
    Run Optuna hyperparameter search.

    Args:
        train_fn: callable(cfg, all_features, params) -> sharpe_ratio (float)
        cfg:      merged config dict
        all_features: {symbol: pd.DataFrame}
        n_trials: number of Optuna trials

    Returns:
        best_params (dict), study (optuna.Study)
    """
    search_space = cfg.get("hyperparam_search", {}).get("search_space", {})
    sampler_name = cfg.get("hyperparam_search", {}).get("sampler", "tpe")
    pruner_name = cfg.get("hyperparam_search", {}).get("pruner", "median")

    sampler = optuna.samplers.TPESampler(seed=42) if sampler_name == "tpe" \
        else optuna.samplers.RandomSampler(seed=42)
    pruner = optuna.pruners.MedianPruner() if pruner_name == "median" \
        else optuna.pruners.NopPruner()

    study = optuna.create_study(
        direction="maximize",
        sampler=sampler,
        pruner=pruner,
    )

    def objective(trial):
        params = suggest_params(trial, search_space)
        logger.info(f"Trial {trial.number}: {params}")
        try:
            sharpe = train_fn(cfg, all_features, params, trial=trial)
            return sharpe
        except optuna.exceptions.TrialPruned:
            raise
        except Exception as e:
            logger.warning(f"Trial {trial.number} failed: {e}")
            return -999.0

    study.optimize(objective, n_trials=n_trials, show_progress_bar=True)
    logger.info(f"Best Sharpe: {study.best_value:.4f}")
    logger.info(f"Best params: {study.best_params}")
    return study.best_params, study
