"""Smoke tests: risk monitoring + fallback hierarchy."""
from __future__ import annotations

import numpy as np
import pandas as pd

from risk.monitoring import check_drawdown, check_classifier_accuracy
from risk.fallback import classifier_fallback_pred, exclude_missing_etf, full_cash_fallback


def test_fallback_classifier_pred_all_minus_one() -> None:
    """Fallback pred vector triggers 63d-always in regime_switch."""
    p = classifier_fallback_pred(5)
    assert (p == -1).all() and len(p) == 5


def test_fallback_exclude_missing_etf() -> None:
    """Missing tickers are dropped, order preserved."""
    u = ["SOXX", "QQQ", "SHY"]
    assert exclude_missing_etf(u, ["QQQ"]) == ["SOXX", "SHY"]


def test_full_cash_fallback_all_in_cash() -> None:
    """SHY 100%."""
    w = full_cash_fallback("SHY")
    assert w == {"SHY": 1.0}


def test_drawdown_alert_immediate() -> None:
    """-26% drawdown trips the kill switch."""
    eq = pd.Series(np.linspace(1.0, 0.74, 100))
    cfg = {"immediate": {"drawdown_investigate_pct": -15.0, "drawdown_kill_switch_pct": -25.0}}
    alerts = check_drawdown(eq, cfg)
    assert any(a.code == "DD_KILL" for a in alerts)


def test_classifier_accuracy_alerts() -> None:
    """WF accuracy < 0.55 disables; < 0.60 warns."""
    cfg = {"warning": {"wf_classifier_accuracy_12m": 0.60},
           "disable": {"classifier_wf_accuracy_sustained": 0.55}}
    assert any(a.code == "CLF_DISABLE" for a in check_classifier_accuracy(0.50, cfg))
    assert any(a.code == "CLF_LOW" for a in check_classifier_accuracy(0.58, cfg))
    assert check_classifier_accuracy(0.70, cfg) == []
