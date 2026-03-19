"""Evaluation metrics for model and strategy performance."""
import numpy as np
import pandas as pd
from sklearn.metrics import classification_report, confusion_matrix


def classification_metrics(y_true, y_pred) -> dict:
    """Compute per-class precision/recall/F1 + accuracy."""
    report = classification_report(
        y_true, y_pred,
        labels=[0, 1, 2, 3, 4],
        target_names=["strong_sell", "weak_sell", "hold", "weak_buy", "strong_buy"],
        output_dict=True,
        zero_division=0,
    )
    return report


def sharpe_ratio(returns: pd.Series, risk_free: float = 0.0, periods: int = 252) -> float:
    """Annualised Sharpe ratio."""
    excess = returns - risk_free / periods
    if excess.std() == 0:
        return 0.0
    return float(excess.mean() / excess.std() * np.sqrt(periods))


def sortino_ratio(returns: pd.Series, risk_free: float = 0.0, periods: int = 252) -> float:
    """Annualised Sortino ratio."""
    excess = returns - risk_free / periods
    downside = excess[excess < 0]
    if downside.std() == 0:
        return 0.0
    return float(excess.mean() / downside.std() * np.sqrt(periods))


def max_drawdown(returns: pd.Series) -> float:
    """Maximum drawdown from a returns series."""
    cumulative = (1 + returns).cumprod()
    rolling_max = cumulative.cummax()
    drawdown = (cumulative - rolling_max) / rolling_max
    return float(drawdown.min())


def win_rate(returns: pd.Series) -> float:
    return float((returns > 0).mean())


def calmar_ratio(returns: pd.Series, periods: int = 252) -> float:
    ann_return = (1 + returns).prod() ** (periods / len(returns)) - 1
    mdd = abs(max_drawdown(returns))
    return float(ann_return / mdd) if mdd > 0 else 0.0
