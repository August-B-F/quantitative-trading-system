"""
hyperparam_search.py

Optuna-based hyperparameter search over walk-forward windows.

Objective: maximize walk-forward Sharpe ratio.
Search space covers: model architecture, training params, AND trading filters.
This is the correct way to optimize trading filters — walk-forward prevents
the curve-fitting problem that pure historical optimization (like the 1B-sim
approach) has.
"""

import os
import json
import optuna
import numpy as np
from typing import Callable, Dict

from ultimate_trader.utils.logging import get_logger

logger = get_logger("hyperparam_search")

optuna.logging.set_verbosity(optuna.logging.WARNING)


def build_search_space(trial: optuna.Trial, search_cfg: dict) -> dict:
    """
    Builds a hyperparameter dict from an Optuna trial.
    Supports float ranges (2-element list) and categorical (list of >2 discrete values).
    """
    params = {}
    for key, spec in search_cfg.items():
        if isinstance(spec, list) and len(spec) == 2 and all(isinstance(v, (int, float)) for v in spec):
            lo, hi = spec
            if isinstance(lo, int) and isinstance(hi, int):
                params[key] = trial.suggest_int(key, lo, hi)
            else:
                params[key] = trial.suggest_float(key, lo, hi, log=(lo > 0 and hi / lo > 10))
        elif isinstance(spec, list):
            params[key] = trial.suggest_categorical(key, spec)
        else:
            params[key] = spec
    return params


class WalkForwardSearch:
    """
    Runs Optuna hyperparameter search where each trial:
      1. Builds model with candidate params
      2. Trains on train window
      3. Evaluates on val window using a backtester
      4. Returns objective metric (Sharpe by default)

    Usage:
      searcher = WalkForwardSearch(train_fn, eval_fn, search_cfg)
      best_params = searcher.run(n_trials=60)
    """

    def __init__(
        self,
        train_fn: Callable,    # fn(params) -> trained model
        eval_fn: Callable,     # fn(model, params) -> float (metric)
        search_cfg: dict,
        study_name: str = "wf_search",
        results_dir: str = "data/models",
    ):
        self.train_fn = train_fn
        self.eval_fn = eval_fn
        self.search_cfg = search_cfg
        self.study_name = study_name
        self.results_dir = results_dir
        os.makedirs(results_dir, exist_ok=True)

    def _objective(self, trial: optuna.Trial) -> float:
        params = build_search_space(trial, self.search_cfg)
        try:
            model = self.train_fn(params)
            score = self.eval_fn(model, params)
            return score if np.isfinite(score) else -999.0
        except Exception as e:
            logger.warning(f"Trial failed: {e}")
            return -999.0

    def run(self, n_trials: int = 60, objective: str = "sharpe") -> Dict:
        direction = "maximize"
        study = optuna.create_study(
            study_name=self.study_name,
            direction=direction,
            sampler=optuna.samplers.TPESampler(seed=42),
        )
        study.optimize(self._objective, n_trials=n_trials, show_progress_bar=True)

        best = study.best_params
        logger.info(f"Best params ({objective}={study.best_value:.4f}): {best}")

        # Save results
        out_path = os.path.join(self.results_dir, f"{self.study_name}_best_params.json")
        with open(out_path, "w") as f:
            json.dump({"best_params": best, "best_value": study.best_value}, f, indent=2)
        logger.info(f"Best params saved to {out_path}")

        return best
