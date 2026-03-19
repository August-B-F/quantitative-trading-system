"""Evaluation metrics for training and backtesting."""
import numpy as np
from typing import List, Dict


def directional_accuracy(preds: List[int], labels: List[int]) -> float:
    """Fraction of predictions where direction (buy/sell) is correct."""
    correct = sum(1 for p, l in zip(preds, labels) if p == l)
    return correct / max(len(preds), 1)


def sharpe_ratio(returns: List[float], risk_free: float = 0.0,
                 annualize: bool = True) -> float:
    """Annualized Sharpe ratio from daily returns."""
    r = np.array(returns)
    if r.std() < 1e-9:
        return 0.0
    sr = (r.mean() - risk_free / 252) / r.std()
    return float(sr * np.sqrt(252) if annualize else sr)


def sortino_ratio(returns: List[float], risk_free: float = 0.0) -> float:
    """Annualized Sortino ratio (penalizes only downside vol)."""
    r = np.array(returns)
    downside = r[r < 0]
    if len(downside) == 0 or downside.std() < 1e-9:
        return float("inf") if r.mean() > 0 else 0.0
    return float((r.mean() - risk_free / 252) / downside.std() * np.sqrt(252))


def max_drawdown(equity_curve: List[float]) -> float:
    """Maximum peak-to-trough drawdown as a fraction."""
    eq = np.array(equity_curve)
    peak = np.maximum.accumulate(eq)
    dd = (eq - peak) / (peak + 1e-9)
    return float(dd.min())


def win_rate(pnl_per_trade: List[float]) -> float:
    wins = sum(1 for p in pnl_per_trade if p > 0)
    return wins / max(len(pnl_per_trade), 1)


def per_class_precision(preds: List[int], labels: List[int],
                         num_classes: int = 5) -> Dict[int, float]:
    """Precision per class."""
    result = {}
    for c in range(num_classes):
        tp = sum(1 for p, l in zip(preds, labels) if p == c and l == c)
        fp = sum(1 for p, l in zip(preds, labels) if p == c and l != c)
        result[c] = tp / max(tp + fp, 1)
    return result


def summarize(equity: List[float], returns: List[float],
              preds: List[int] = None, labels: List[int] = None) -> dict:
    """Full summary dict of all metrics."""
    s = {
        "sharpe": sharpe_ratio(returns),
        "sortino": sortino_ratio(returns),
        "max_drawdown": max_drawdown(equity),
        "total_return": float((equity[-1] / equity[0] - 1) * 100) if equity else 0.0,
        "win_rate": win_rate(returns),
    }
    if preds and labels:
        s["accuracy"] = directional_accuracy(preds, labels)
        s["per_class_precision"] = per_class_precision(preds, labels)
    return s
