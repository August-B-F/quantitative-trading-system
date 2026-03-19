"""Walk-forward hyperparameter optimisation using Optuna.

The objective function:
  1. Trains a model on the training fold
  2. Runs a simplified backtest on the validation fold
  3. Returns the walk-forward Sharpe ratio as objective
"""
import optuna
import numpy as np
from typing import Callable

from ultimate_trader.utils.logging import get_logger

log = get_logger(__name__)
optuna.logging.set_verbosity(optuna.logging.WARNING)


def run_hyperparam_search(
    train_fn: Callable,      # fn(trial_cfg) -> trained model
    eval_fn: Callable,       # fn(model, trial_cfg) -> sharpe float
    base_cfg: dict,
    n_trials: int = 80,
    objective_metric: str = "sharpe"
) -> dict:
    """
    Run Optuna search over hyperparameter space defined in training.yaml.

    Args:
        train_fn: function that takes a cfg dict, trains a model, returns it
        eval_fn: function that takes (model, cfg) and returns a float metric
        base_cfg: base config dict (will be overridden per trial)
        n_trials: number of Optuna trials
        objective_metric: 'sharpe' | 'sortino' | 'total_return'

    Returns:
        best_params dict
    """
    search_space = base_cfg["hyperparam_search"]["search_space"]

    def objective(trial: optuna.Trial) -> float:
        import copy
        trial_cfg = copy.deepcopy(base_cfg)

        # Sample hyperparameters from defined search space
        lr_range = search_space["lr"]
        trial_cfg["training"]["lr"] = trial.suggest_float("lr", *lr_range, log=True)

        dropout_range = search_space["dropout"]
        trial_cfg["model"]["dropout"] = trial.suggest_float("dropout", *dropout_range)

        hidden_range = search_space["hidden_dim"]
        trial_cfg["model"]["hidden_dim"] = trial.suggest_int("hidden_dim", *hidden_range, step=32)

        window_range = search_space["price_window"]
        trial_cfg["model"]["price_window"] = trial.suggest_int("price_window", *window_range, step=5)

        r_hi_range = search_space["r_hi"]
        trial_cfg["targets"]["r_hi"] = trial.suggest_float("r_hi", *r_hi_range)

        r_lo_range = search_space["r_lo"]
        trial_cfg["targets"]["r_lo"] = trial.suggest_float("r_lo", *r_lo_range)

        kelly_range = search_space["kelly_fraction"]
        trial_cfg["trading"]["kelly_fraction"] = trial.suggest_float("kelly_fraction", *kelly_range)

        conf_range = search_space["confidence_threshold"]
        trial_cfg["trading"]["confidence_threshold"] = trial.suggest_float("confidence_threshold", *conf_range)

        div_range = search_space["diversification"]
        trial_cfg["trading"]["diversification"] = trial.suggest_int("diversification", *div_range)

        try:
            model = train_fn(trial_cfg)
            metric = eval_fn(model, trial_cfg)
            return float(metric)
        except Exception as e:
            log.warning(f"Trial failed: {e}")
            return -999.0

    study = optuna.create_study(direction="maximize",
                                study_name=f"stock_trader_{objective_metric}")
    study.optimize(objective, n_trials=n_trials, show_progress_bar=True)

    log.info(f"Best {objective_metric}: {study.best_value:.4f}")
    log.info(f"Best params: {study.best_params}")

    return study.best_params
