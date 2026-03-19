"""Evaluation metrics for classification and trading performance."""
import numpy as np
import pandas as pd
from sklearn.metrics import classification_report, confusion_matrix
from typing import Optional


def classification_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    """
    Compute precision, recall, F1 per class plus macro-average.

    Returns:
        dict with sklearn classification_report as a nested dict
    """
    return classification_report(
        y_true, y_pred,
        target_names=["strong_sell", "sell", "hold", "buy", "strong_buy"],
        output_dict=True,
        zero_division=0,
    )


def directional_accuracy(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """
    Fraction of samples where the model correctly predicted up vs down direction.
    Ignores 'hold' class (2) predictions and labels.

    Classes 0,1 = bearish; 3,4 = bullish.
    """
    mask = (y_true != 2) & (y_pred != 2)
    if mask.sum() == 0:
        return float('nan')
    true_dir = (y_true[mask] >= 3).astype(int)
    pred_dir = (y_pred[mask] >= 3).astype(int)
    return (true_dir == pred_dir).mean()


def compute_sharpe(
    returns: np.ndarray,
    risk_free_rate: float = 0.0,
    annualise: bool = True,
) -> float:
    """
    Annualised Sharpe ratio of a daily returns array.

    Args:
        returns: 1D array of daily portfolio returns
        risk_free_rate: annualised risk-free rate
        annualise: multiply by sqrt(252)

    Returns:
        Sharpe ratio (float)
    """
    if len(returns) == 0 or returns.std() == 0:
        return 0.0
    daily_rf = risk_free_rate / 252
    excess = returns - daily_rf
    ratio = excess.mean() / (excess.std() + 1e-9)
    return ratio * np.sqrt(252) if annualise else ratio


def compute_sortino(
    returns: np.ndarray,
    risk_free_rate: float = 0.0,
    annualise: bool = True,
) -> float:
    """Sortino ratio using downside deviation only."""
    daily_rf = risk_free_rate / 252
    excess = returns - daily_rf
    downside = excess[excess < 0]
    if len(downside) == 0:
        return float('inf')
    downside_std = np.sqrt((downside ** 2).mean())
    ratio = excess.mean() / (downside_std + 1e-9)
    return ratio * np.sqrt(252) if annualise else ratio


def compute_max_drawdown(equity_curve: np.ndarray) -> float:
    """
    Maximum drawdown from an equity curve (starting at 1.0).

    Returns:
        Max drawdown as a positive fraction (e.g. 0.15 = 15% drawdown)
    """
    peak = np.maximum.accumulate(equity_curve)
    drawdown = (equity_curve - peak) / (peak + 1e-9)
    return float(-drawdown.min())


def trading_metrics(daily_returns: np.ndarray) -> dict:
    """Bundle all trading performance metrics into one dict."""
    equity = np.cumprod(1 + daily_returns)
    return {
        "total_return": float(equity[-1] - 1) if len(equity) > 0 else 0.0,
        "sharpe": compute_sharpe(daily_returns),
        "sortino": compute_sortino(daily_returns),
        "max_drawdown": compute_max_drawdown(equity),
        "win_rate": float((daily_returns > 0).mean()),
        "n_days": len(daily_returns),
    }
