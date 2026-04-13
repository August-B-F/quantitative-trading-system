"""Risk monitoring — §6.x alert checks.

Scaffold. Each check takes the latest state and returns (severity, message)
tuples. Production uses this on every rebalance day to populate alerts/.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)


@dataclass
class Alert:
    """One alert — severity is IMMEDIATE | WARNING | INFO."""
    severity: str
    code: str
    message: str


def check_drawdown(equity: pd.Series, cfg: dict) -> list[Alert]:
    """Emit alerts on drawdown thresholds (§6.4)."""
    alerts: list[Alert] = []
    if equity.empty:
        return alerts
    peak = equity.cummax()
    dd = float((equity.iloc[-1] / peak.iloc[-1]) - 1.0)
    imm = cfg.get("immediate", {})
    inv_t = float(imm.get("drawdown_investigate_pct", -15.0)) / 100
    kill_t = float(imm.get("drawdown_kill_switch_pct", -25.0)) / 100
    if dd <= kill_t:
        alerts.append(Alert("IMMEDIATE", "DD_KILL", f"drawdown {dd*100:.2f}% <= kill {kill_t*100}%"))
    elif dd <= inv_t:
        alerts.append(Alert("IMMEDIATE", "DD_INVESTIGATE", f"drawdown {dd*100:.2f}% <= investigate {inv_t*100}%"))
    return alerts


def check_feed_staleness(last_update: pd.Timestamp, today: pd.Timestamp, max_days: int, name: str) -> list[Alert]:
    """Emit an alert if a feed has lagged past its staleness window."""
    gap = (today - last_update).days
    if gap > max_days:
        return [Alert("WARNING", "FEED_STALE", f"{name} stale {gap}d > {max_days}d")]
    return []


def check_oecd_age(last_obs: pd.Timestamp, today: pd.Timestamp, cfg: dict) -> list[Alert]:
    """Emit a WARNING if the OECD CLI feature has gone stale.

    OECD CLI (FRED `USALOLITONOSTSAM`) stopped publishing 2023-12.
    Replacements (USSLIND, CFNAI, USPHCI) were evaluated and rejected
    2026-04-12 (max corr 0.72 / 0.36 / 0.64 respectively — all below
    the 0.70 retest floor). Decision: retain oecd_cli with forward-fill
    and monitor staleness as a recurring WARNING — NOT a kill-switch
    or auto-fallback trigger, since oecd_cli is a Tier-C feature (§5.3)
    and the canonical canary (23.61/1.50/-12.94) is computed with the
    forward-filled value. See MASTER_ARCHITECTURE.md §8.1.
    """
    warn_cfg = cfg.get("warning", {})
    warn_days = int(warn_cfg.get("oecd_cli_age_days", 90))
    recur_days = int(warn_cfg.get("oecd_cli_age_recurring_days", 365))
    gap = (today - last_obs).days
    if gap > recur_days:
        return [Alert(
            "WARNING",
            "OECD_CLI_STALE_RECUR",
            f"oecd_cli stale {gap}d > {recur_days}d (recurring, see §8.1 "
            f"— replacements rejected 2026-04-12; re-run "
            f"scripts/test_cfnai_swap.py if FRED resumes publication)",
        )]
    if gap > warn_days:
        return [Alert(
            "WARNING",
            "OECD_CLI_STALE",
            f"oecd_cli stale {gap}d > {warn_days}d (acceptable Tier-C risk, §8.1)",
        )]
    return []


def check_classifier_accuracy(wf_accuracy: float, cfg: dict) -> list[Alert]:
    """Emit alerts on classifier WF accuracy decay."""
    warn = float(cfg.get("warning", {}).get("wf_classifier_accuracy_12m", 0.60))
    disable = float(cfg.get("disable", {}).get("classifier_wf_accuracy_sustained", 0.55))
    if wf_accuracy < disable:
        return [Alert("IMMEDIATE", "CLF_DISABLE", f"WF acc {wf_accuracy:.3f} < {disable}")]
    if wf_accuracy < warn:
        return [Alert("WARNING", "CLF_LOW", f"WF acc {wf_accuracy:.3f} < {warn}")]
    return []
