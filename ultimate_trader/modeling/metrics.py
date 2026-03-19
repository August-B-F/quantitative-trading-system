"""Evaluation metrics for both ML and trading performance."""
import numpy as np
import pandas as pd
from typing import List


def accuracy(preds: np.ndarray, labels: np.ndarray) -> float:
    return float((preds == labels).mean())


def directional_accuracy(preds: np.ndarray, labels: np.ndarray) -> float:
    """
    Fraction of predictions where the direction (buy/sell/hold) matches.
    Classes: 0=strong_sell,1=sell,2=hold,3=buy,4=strong_buy
    Direction: <2 = bearish, 2 = neutral, >2 = bullish
    """
    pred_dir  = np.sign(preds  - 2)
    label_dir = np.sign(labels - 2)
    return float((pred_dir == label_dir).mean())


def sharpe_ratio(returns: np.ndarray, risk_free: float = 0.0,
                 periods_per_year: int = 252) -> float:
    """Annualised Sharpe ratio from array of period returns."""
    if len(returns) < 2:
        return 0.0
    excess = returns - risk_free / periods_per_year
    std = np.std(excess, ddof=1)
    if std == 0:
        return 0.0
    return float(np.mean(excess) / std * np.sqrt(periods_per_year))


def sortino_ratio(returns: np.ndarray, risk_free: float = 0.0,
                  periods_per_year: int = 252) -> float:
    """Annualised Sortino ratio (downside deviation only)."""
    excess = returns - risk_free / periods_per_year
    downside = excess[excess < 0]
    if len(downside) < 2:
        return 0.0
    downside_std = np.std(downside, ddof=1)
    if downside_std == 0:
        return 0.0
    return float(np.mean(excess) / downside_std * np.sqrt(periods_per_year))


def max_drawdown(equity_curve: np.ndarray) -> float:
    """Maximum peak-to-trough drawdown as a fraction."""
    peak = np.maximum.accumulate(equity_curve)
    dd = (equity_curve - peak) / peak
    return float(dd.min())


def calmar_ratio(returns: np.ndarray, equity_curve: np.ndarray,
                 periods_per_year: int = 252) -> float:
    """Annualised return / max drawdown."""
    ann_return = float(np.mean(returns) * periods_per_year)
    mdd = abs(max_drawdown(equity_curve))
    return ann_return / mdd if mdd > 0 else 0.0


def trading_metrics(returns: np.ndarray) -> dict:
    """Return a dict of all key trading metrics."""
    equity = np.cumprod(1 + returns)
    return {
        "sharpe":    sharpe_ratio(returns),
        "sortino":   sortino_ratio(returns),
        "max_dd":    max_drawdown(equity),
        "calmar":    calmar_ratio(returns, equity),
        "total_ret": float(equity[-1] - 1) if len(equity) > 0 else 0.0,
        "win_rate":  float((returns > 0).mean()),
        "n_trades":  len(returns),
    }
