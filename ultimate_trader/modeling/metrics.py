"""Evaluation metrics for model + strategy performance."""
import numpy as np
import pandas as pd


def sharpe_ratio(returns: pd.Series | np.ndarray, periods_per_year: int = 252) -> float:
    """Annualised Sharpe ratio."""
    r = np.asarray(returns)
    if r.std() == 0:
        return 0.0
    return float((r.mean() / r.std()) * np.sqrt(periods_per_year))


def sortino_ratio(returns: pd.Series | np.ndarray, periods_per_year: int = 252) -> float:
    """Annualised Sortino ratio (downside std only)."""
    r = np.asarray(returns)
    downside = r[r < 0]
    if len(downside) == 0 or downside.std() == 0:
        return 0.0
    return float((r.mean() / downside.std()) * np.sqrt(periods_per_year))


def max_drawdown(equity_curve: pd.Series | np.ndarray) -> float:
    """Maximum drawdown as a positive fraction."""
    eq = np.asarray(equity_curve, dtype=float)
    peak = np.maximum.accumulate(eq)
    dd = (eq - peak) / np.where(peak == 0, 1, peak)
    return float(-dd.min())


def win_rate(pnl_series: pd.Series | np.ndarray) -> float:
    r = np.asarray(pnl_series)
    if len(r) == 0:
        return 0.0
    return float((r > 0).mean())


def classification_report_dict(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    num_classes: int = 5
) -> dict:
    """Per-class precision, recall, F1."""
    from sklearn.metrics import classification_report
    labels = list(range(num_classes))
    names = ["strong_sell", "sell", "hold", "buy", "strong_buy"]
    report = classification_report(y_true, y_pred, labels=labels,
                                   target_names=names, output_dict=True,
                                   zero_division=0)
    return report
