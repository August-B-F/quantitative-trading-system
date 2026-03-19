"""Risk management: position sizing with Kelly Criterion, exposure limits, kill-switch."""
import numpy as np
from ultimate_trader.utils.logging import get_logger

log = get_logger(__name__)

REGIME_PARAMS = {
    # regime_id: {max_gross_exposure, confidence_boost, position_scale}
    0: {"exposure_multiplier": 0.4, "conf_add": 0.10, "size_scale": 0.5},   # bear / high-vol
    1: {"exposure_multiplier": 0.75, "conf_add": 0.05, "size_scale": 0.75}, # sideways
    2: {"exposure_multiplier": 1.0, "conf_add": 0.0,  "size_scale": 1.0},   # bull / low-vol
}


def kelly_fraction(
    prob_win: float,
    expected_win: float,
    expected_loss: float,
    kelly_multiplier: float = 0.25
) -> float:
    """
    Fractional Kelly Criterion.
    f* = (p * b - q) / b  where b = expected_win / expected_loss

    Args:
        prob_win: probability of winning (from model)
        expected_win: expected fractional gain if correct (e.g. 0.03)
        expected_loss: expected fractional loss if wrong (e.g. 0.02)
        kelly_multiplier: fraction of full Kelly to use (0.25 = quarter Kelly)

    Returns:
        Fraction of portfolio to deploy (0 to 1, clipped)
    """
    if expected_loss <= 0:
        return 0.0
    b = expected_win / expected_loss
    q = 1.0 - prob_win
    full_kelly = (prob_win * b - q) / b
    fractional = full_kelly * kelly_multiplier
    return float(np.clip(fractional, 0.0, 1.0))


def compute_position_sizes(
    signals: list[dict],      # [{symbol, action, confidence, prob_win, regime}, ...]
    equity: float,
    cfg: dict,
    current_regime: int = 1
) -> list[dict]:
    """
    Compute dollar position sizes for each signal.

    Each signal dict must have:
      symbol, action ('buy'|'sell'|'hold'), confidence (0-1),
      prob_win (0-1), expected_win (float), expected_loss (float)

    Returns signals enriched with 'dollar_size' and 'shares' (needs current price).
    """
    if not signals:
        return []

    regime_params = REGIME_PARAMS.get(current_regime, REGIME_PARAMS[1])
    max_exposure = cfg["trading"]["max_gross_exposure"] * regime_params["exposure_multiplier"]
    max_single = cfg["trading"]["max_single_position"]
    kelly_mult = cfg["trading"].get("kelly_fraction", 0.25)
    conf_threshold = cfg["trading"].get("confidence_threshold", 0.55)
    conf_threshold += regime_params["conf_add"]  # tighten in bear regime

    actionable = [
        s for s in signals
        if s["action"] in ("buy", "sell")
        and s["confidence"] >= conf_threshold
    ]

    # Sort by confidence descending, take top N
    max_positions = cfg["trading"].get("diversification", 10)
    actionable = sorted(actionable, key=lambda x: x["confidence"], reverse=True)[:max_positions]

    total_allocated = 0.0
    sized_signals = []

    for sig in actionable:
        kf = kelly_fraction(
            sig["prob_win"],
            sig.get("expected_win", cfg["targets"]["r_hi"]),
            sig.get("expected_loss", cfg["targets"]["r_hi"]),
            kelly_mult
        )
        kf *= regime_params["size_scale"]

        dollar_size = min(equity * kf, equity * max_single)

        if total_allocated + dollar_size > equity * max_exposure:
            dollar_size = max(0, equity * max_exposure - total_allocated)

        if dollar_size < 1.0:
            continue

        total_allocated += dollar_size
        sig = {**sig, "dollar_size": dollar_size}
        sized_signals.append(sig)

    log.info(
        f"Regime {current_regime}: {len(sized_signals)} positions, "
        f"total allocated ${total_allocated:,.0f} / ${equity:,.0f} equity"
    )
    return sized_signals


def kill_switch_triggered(
    portfolio_pnl_today: float,
    max_daily_loss: float = -0.05
) -> bool:
    """Return True if today's portfolio PnL exceeds max daily loss threshold."""
    if portfolio_pnl_today < max_daily_loss:
        log.critical(
            f"KILL SWITCH: daily PnL {portfolio_pnl_today:.2%} exceeds limit {max_daily_loss:.2%}. "
            "All trading halted."
        )
        return True
    return False
