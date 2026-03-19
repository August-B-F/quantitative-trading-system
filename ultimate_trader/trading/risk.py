"""Risk management: Kelly sizing, exposure limits, regime filters, earnings blackout."""
import datetime
import numpy as np
from typing import Optional

from ultimate_trader.utils.logging import get_logger

logger = get_logger(__name__)


def apply_regime_filters(
    base_confidence_threshold: float,
    regime: int,
) -> float:
    """
    Adjust confidence threshold based on market regime.

    Regime 0 (bull): relax threshold slightly, we trust signals more
    Regime 1 (mixed): use base threshold
    Regime 2 (bear/crash): tighten threshold significantly

    Args:
        base_confidence_threshold: threshold from config / hyperparam search
        regime: integer 0, 1, or 2

    Returns:
        Adjusted confidence threshold
    """
    adjustments = {0: -0.05, 1: 0.0, 2: +0.15}
    adjusted = base_confidence_threshold + adjustments.get(regime, 0.0)
    return float(np.clip(adjusted, 0.3, 0.99))


def check_earnings_blackout(
    symbol: str,
    today: str,
    earnings_calendar: dict,
    blackout_days: int = 1,
) -> bool:
    """
    Return True if today is within blackout_days of an earnings announcement.
    Trading during earnings is high-risk; we skip new entries.

    Args:
        symbol: ticker string
        today: current date as 'YYYY-MM-DD'
        earnings_calendar: dict of symbol -> list of date strings
        blackout_days: days before earnings to block trades

    Returns:
        True if in blackout period (skip trade), False if safe
    """
    dates = earnings_calendar.get(symbol, [])
    today_dt = datetime.datetime.strptime(today, "%Y-%m-%d").date()
    for d in dates:
        try:
            earnings_dt = datetime.datetime.strptime(d, "%Y-%m-%d").date()
            delta = (earnings_dt - today_dt).days
            if 0 <= delta <= blackout_days:
                return True
        except ValueError:
            continue
    return False


def kelly_fraction(
    confidence: float,
    expected_return: float,
    kelly_multiplier: float = 0.25,
) -> float:
    """
    Fractional Kelly Criterion for position sizing.

    Full Kelly f* = (p*b - q) / b where:
        p = probability of win (confidence)
        q = 1 - p
        b = expected return if correct (expected_return)

    We use fractional Kelly (default 0.25x) for robustness.

    Args:
        confidence: model confidence in [0, 1]
        expected_return: expected return if prediction is correct
        kelly_multiplier: fraction of full Kelly to use (0.25 = quarter-Kelly)

    Returns:
        Fraction of portfolio to allocate in [0, 1]
    """
    if expected_return <= 0:
        return 0.0
    p = confidence
    q = 1.0 - p
    b = expected_return
    full_kelly = (p * b - q) / b
    full_kelly = max(0.0, full_kelly)  # Can't be negative (would mean don't trade)
    return min(kelly_multiplier * full_kelly, 0.4)  # Hard cap at 40% of equity per trade


def compute_kelly_sizes(
    candidates: list[dict],
    equity: float,
    max_single_position: float,
    search_space: dict,
) -> list[dict]:
    """
    Compute dollar amount for each candidate trade using fractional Kelly.

    Args:
        candidates: list of candidate trade dicts (must have 'confidence' and 'expected_return')
        equity: total account equity
        max_single_position: max fraction of equity per position
        search_space: hyperparam search space dict (for kelly_fraction param)

    Returns:
        candidates with 'dollar_amount' field added
    """
    kelly_mult = search_space.get("kelly_fraction", [0.25])
    if isinstance(kelly_mult, list):
        kelly_mult = 0.25  # Default until hyperparams are tuned

    for trade in candidates:
        frac = kelly_fraction(
            confidence=trade["confidence"],
            expected_return=trade["expected_return"],
            kelly_multiplier=kelly_mult,
        )
        frac = min(frac, max_single_position)
        trade["kelly_fraction"] = frac
        trade["dollar_amount"] = frac * equity

    return candidates


def apply_exposure_limits(
    candidates: list[dict],
    equity: float,
    trading_cfg: dict,
) -> list[dict]:
    """
    Ensure total gross exposure doesn't exceed config limits.
    Trims candidate list from lowest-confidence trade first.

    Args:
        candidates: list of trade dicts with 'dollar_amount'
        equity: total account equity
        trading_cfg: trading section of config

    Returns:
        Trimmed candidates list that respects exposure limits
    """
    max_gross = trading_cfg.get("max_gross_exposure", 0.9) * equity
    min_cash = trading_cfg.get("min_cash_buffer", 0.1) * equity
    max_deployable = equity - min_cash

    total = 0.0
    allowed = []
    for trade in sorted(candidates, key=lambda x: x["confidence"], reverse=True):
        amount = trade["dollar_amount"]
        if total + amount <= min(max_gross, max_deployable):
            total += amount
            allowed.append(trade)
        else:
            logger.info(
                f"{trade['symbol']}: skipped — exposure limit reached "
                f"(deployed=${total:.0f}, limit=${max_deployable:.0f})"
            )

    return allowed
