"""Risk management: regime-aware position limits, kill-switch, exposure checks.

Regime mapping (from HMM):
  0 = bear
  1 = neutral / sideways
  2 = bull
"""
from ultimate_trader.utils.logging import get_logger

logger = get_logger("risk")

# Regime-dependent parameters
REGIME_PARAMS = {
    0: {  # bear
        "max_gross_exposure": 0.4,
        "max_single_position": 0.08,
        "min_confidence": 0.70,
        "allow_long": True,
        "allow_short": True,
        "kelly_fraction": 0.15,
    },
    1: {  # neutral
        "max_gross_exposure": 0.7,
        "max_single_position": 0.12,
        "min_confidence": 0.60,
        "allow_long": True,
        "allow_short": True,
        "kelly_fraction": 0.25,
    },
    2: {  # bull
        "max_gross_exposure": 1.0,
        "max_single_position": 0.15,
        "min_confidence": 0.55,
        "allow_long": True,
        "allow_short": False,
        "kelly_fraction": 0.40,
    },
}


def get_regime_params(regime: int, cfg: dict = None) -> dict:
    """Return risk parameters for the given regime."""
    params = REGIME_PARAMS.get(regime, REGIME_PARAMS[1]).copy()
    # Allow override from config
    if cfg:
        t = cfg.get("trading", {})
        if "max_gross_exposure" in t:
            params["max_gross_exposure"] = min(params["max_gross_exposure"], t["max_gross_exposure"])
        if "max_single_position" in t:
            params["max_single_position"] = min(params["max_single_position"], t["max_single_position"])
    return params


def kelly_position_size(
    confidence: float,
    predicted_class: int,
    current_price: float,
    equity: float,
    kelly_fraction: float = 0.25,
    max_position_fraction: float = 0.15,
) -> float:
    """
    Fractional Kelly position sizing.

    Maps model output to edge estimate:
      - Class 4 (strong buy):  edge = confidence * 0.06
      - Class 3 (weak buy):    edge = confidence * 0.03
      - Class 1 (weak sell):   edge = confidence * 0.03  (short)
      - Class 0 (strong sell): edge = confidence * 0.06  (short)

    Returns dollar value to invest (positive = long, negative = short).
    """
    edge_map = {4: 0.06, 3: 0.03, 2: 0.0, 1: 0.03, 0: 0.06}
    edge = edge_map.get(predicted_class, 0.0) * confidence

    if edge <= 0 or predicted_class == 2:
        return 0.0

    # Kelly formula: f = edge / odds  (simplified with odds=1)
    f = edge * kelly_fraction
    dollar_size = f * equity
    max_dollar = max_position_fraction * equity
    dollar_size = min(dollar_size, max_dollar)

    if predicted_class in (0, 1):   # sell signal
        return -dollar_size
    return dollar_size


def check_earnings_buffer(
    symbol: str,
    earnings_calendar: dict,
    buffer_days: int = 1,
) -> bool:
    """
    Returns True if the symbol has earnings within buffer_days.
    If True, the bot should skip this symbol or close existing position.
    """
    import datetime
    today = datetime.date.today()
    dates = earnings_calendar.get(symbol, [])
    for d_str in dates:
        try:
            d = datetime.date.fromisoformat(d_str[:10])
            if abs((d - today).days) <= buffer_days:
                return True
        except Exception:
            continue
    return False


def check_kill_switch(account: dict, max_daily_loss: float = 0.05) -> bool:
    """
    Emergency kill switch: if unrealised P&L is below -max_daily_loss * equity,
    return True (caller should halt all trading for the day).
    """
    equity = account.get("equity", 0)
    portfolio_value = account.get("portfolio_value", equity)
    if equity <= 0:
        return False
    daily_pnl_pct = (portfolio_value - equity) / equity
    if daily_pnl_pct < -max_daily_loss:
        logger.warning(f"KILL SWITCH TRIGGERED: daily P&L = {daily_pnl_pct:.2%}")
        return True
    return False
