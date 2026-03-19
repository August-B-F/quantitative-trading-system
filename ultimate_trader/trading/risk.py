"""Risk management: position sizing, exposure limits, kill-switch."""
import numpy as np
from typing import Optional
from ultimate_trader.utils.logging import get_logger
from ultimate_trader.features.regimes import get_regime_overrides

log = get_logger(__name__)

# action index mappings (must match model output)
ACTION_NAMES = {0: "strong_sell", 1: "sell", 2: "hold", 3: "buy", 4: "strong_buy"}
BULLISH_ACTIONS  = {3, 4}
BEARISH_ACTIONS  = {0, 1}
NEUTRAL_ACTIONS  = {2}


def kelly_fraction(
    win_prob: float,
    avg_win: float  = 0.03,
    avg_loss: float = 0.015,
    multiplier: float = 0.25,
) -> float:
    """
    Fractional Kelly position sizing.
    f* = (p * b - q) / b  where b = avg_win/avg_loss, q = 1-p
    Clamped to [0, 1] then scaled by multiplier for safety.
    """
    if avg_loss == 0:
        return 0.0
    b = avg_win / avg_loss
    q = 1 - win_prob
    f_star = (win_prob * b - q) / b
    f_star = max(0.0, min(1.0, f_star))
    return f_star * multiplier


def compute_position_size(
    equity: float,
    win_probability: float,
    current_position_fraction: float,
    max_single_position: float = 0.15,
    kelly_multiplier: float    = 0.25,
    min_cash_buffer: float     = 0.05,
    available_cash: float      = None,
    avg_win: float             = 0.03,
    avg_loss: float            = 0.015,
) -> float:
    """
    Compute target dollar allocation for a position.
    Returns dollar amount to invest (may be 0 if limits exceeded).
    """
    kf = kelly_fraction(win_probability, avg_win, avg_loss, kelly_multiplier)
    target_fraction = min(kf, max_single_position)

    # headroom after existing position
    additional_fraction = max(0.0, target_fraction - current_position_fraction)
    dollar_amount = additional_fraction * equity

    # respect cash buffer
    if available_cash is not None:
        max_spendable = available_cash - equity * min_cash_buffer
        dollar_amount = min(dollar_amount, max(0.0, max_spendable))

    return dollar_amount


def apply_regime_filters(
    decisions: dict,
    regime: str,
    base_confidence_threshold: float,
    base_kelly_multiplier: float,
    base_max_gross: float,
) -> tuple:
    """
    Scale trade parameters based on current market regime.
    Returns (confidence_threshold, kelly_multiplier, max_gross_exposure).
    """
    overrides = get_regime_overrides(regime)
    conf_thresh = max(base_confidence_threshold, overrides["confidence_threshold"])
    kelly_mult  = base_kelly_multiplier * overrides["kelly_multiplier"]
    max_gross   = min(base_max_gross, overrides["max_gross_exposure"])
    log.info(f"Regime '{regime}': conf_thresh={conf_thresh:.2f}, "
             f"kelly={kelly_mult:.2f}, max_gross={max_gross:.2f}")
    return conf_thresh, kelly_mult, max_gross


def check_kill_switch(
    equity: float,
    start_equity: float,
    max_daily_loss: float = 0.05,
) -> bool:
    """
    Returns True if trading should be halted (daily loss exceeded).
    max_daily_loss: fraction of starting equity (default 5%).
    """
    loss = (start_equity - equity) / start_equity if start_equity > 0 else 0.0
    if loss > max_daily_loss:
        log.critical(f"KILL SWITCH TRIGGERED: daily loss {loss:.1%} > {max_daily_loss:.1%}")
        return True
    return False
