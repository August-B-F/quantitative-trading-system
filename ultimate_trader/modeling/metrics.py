"""
metrics.py

Evaluation metrics for both ML quality and trading quality.

ML metrics:
  - accuracy, precision, recall per class
  - directional accuracy (did we get up/down right?)

Trading metrics:
  - Sharpe ratio
  - Sortino ratio
  - Max drawdown
  - Hit rate (% profitable trades)
  - Average return per trade
"""

import numpy as np
import pandas as pd
from typing import List, Optional


def directional_accuracy(preds: np.ndarray, labels: np.ndarray) -> float:
    """
    For ordinal 5-class labels:
    Label 0,1 = sell direction; 2 = hold; 3,4 = buy direction.
    Measures whether predicted direction matches true direction.
    """
    pred_dir = np.where(preds > 2, 1, np.where(preds < 2, -1, 0))
    true_dir = np.where(labels > 2, 1, np.where(labels < 2, -1, 0))
    mask = true_dir != 0  # ignore holds
    if mask.sum() == 0:
        return 0.0
    return float((pred_dir[mask] == true_dir[mask]).mean())


def sharpe_ratio(returns: np.ndarray, risk_free: float = 0.0, annualize: bool = True) -> float:
    if len(returns) < 2:
        return 0.0
    excess = returns - risk_free / 252
    mean = excess.mean()
    std = excess.std() + 1e-10
    sr = mean / std
    if annualize:
        sr *= np.sqrt(252)
    return float(sr)


def sortino_ratio(returns: np.ndarray, risk_free: float = 0.0, annualize: bool = True) -> float:
    if len(returns) < 2:
        return 0.0
    excess = returns - risk_free / 252
    downside = excess[excess < 0]
    if len(downside) == 0:
        return float("inf")
    downside_std = downside.std() + 1e-10
    sr = excess.mean() / downside_std
    if annualize:
        sr *= np.sqrt(252)
    return float(sr)


def max_drawdown(equity_curve: np.ndarray) -> float:
    """Maximum peak-to-trough drawdown as a positive fraction."""
    peak = np.maximum.accumulate(equity_curve)
    drawdown = (equity_curve - peak) / (peak + 1e-10)
    return float(-drawdown.min())


def hit_rate(pnl_per_trade: np.ndarray) -> float:
    """Fraction of trades that were profitable."""
    if len(pnl_per_trade) == 0:
        return 0.0
    return float((pnl_per_trade > 0).mean())


def compute_all_metrics(returns: np.ndarray, equity_curve: Optional[np.ndarray] = None) -> dict:
    eq = equity_curve if equity_curve is not None else np.cumprod(1 + returns)
    return {
        "sharpe": sharpe_ratio(returns),
        "sortino": sortino_ratio(returns),
        "max_drawdown": max_drawdown(eq),
        "total_return": float(eq[-1] / eq[0] - 1) if len(eq) > 0 else 0.0,
        "ann_return": float(np.mean(returns) * 252),
        "ann_vol": float(np.std(returns) * np.sqrt(252)),
    }
