"""Risk management: position sizing, exposure limits, regime-based adjustments."""
import numpy as np
from typing import Dict, Tuple
from ultimate_trader.features.regimes import REGIME_BULL, REGIME_BEAR, REGIME_SIDEWAYS
from ultimate_trader.utils.logging import get_logger
from ultimate_trader.utils.config_loader import Config

logger = get_logger(__name__)

# Regime multipliers: how aggressively to deploy capital per regime
REGIME_EXPOSURE_MULTIPLIER = {
    REGIME_BULL:     1.0,   # full exposure allowed
    REGIME_SIDEWAYS: 0.6,   # reduce exposure in choppy markets
    REGIME_BEAR:     0.25,  # minimal exposure in bear regime
}

REGIME_CONFIDENCE_BOOST = {
    REGIME_BULL:     0.0,    # keep normal confidence threshold
    REGIME_SIDEWAYS: 0.05,   # require slightly higher confidence
    REGIME_BEAR:     0.15,   # require much higher confidence
}


class RiskManager:
    """
    Computes per-trade position sizes and enforces portfolio-level risk limits.
    Uses fractional Kelly Criterion for optimal sizing.
    """

    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.kelly_fraction = cfg.trading.kelly_fraction
        self.max_single = cfg.trading.max_single_position
        self.max_exposure = cfg.trading.max_gross_exposure
        self.min_cash = cfg.trading.min_cash_buffer
        self.base_min_confidence = cfg.trading.min_confidence

    def min_confidence(self, regime: str) -> float:
        """Returns regime-adjusted minimum confidence threshold."""
        boost = REGIME_CONFIDENCE_BOOST.get(regime, 0.0)
        return min(self.base_min_confidence + boost, 0.95)

    def max_deployable_equity(self, equity: float, regime: str) -> float:
        """Max capital that can be deployed given regime."""
        regime_mult = REGIME_EXPOSURE_MULTIPLIER.get(regime, 0.5)
        return equity * self.max_exposure * regime_mult * (1 - self.min_cash)

    def kelly_size(
        self,
        equity: float,
        confidence: float,
        pred_class: int,
        current_price: float,
        regime: str,
        stop_loss_pct: float,
        take_profit_pct: float,
    ) -> Tuple[float, float]:
        """
        Compute optimal position size using fractional Kelly Criterion.

        f* = (p * b - q) / b  where:
          p = probability of win (confidence)
          q = 1 - p
          b = expected win/loss ratio (take_profit / stop_loss)

        Returns (dollar_amount, num_shares).
        """
        p = float(np.clip(confidence, 0.01, 0.99))
        q = 1.0 - p
        b = take_profit_pct / max(stop_loss_pct, 1e-4)

        kelly_f = (p * b - q) / max(b, 1e-4)
        kelly_f = max(kelly_f, 0.0)  # no negative sizing
        fractional_f = kelly_f * self.kelly_fraction

        # Cap at per-position limit
        fractional_f = min(fractional_f, self.max_single)

        # Scale by regime
        regime_mult = REGIME_EXPOSURE_MULTIPLIER.get(regime, 0.5)
        fractional_f *= regime_mult

        dollar_amount = equity * fractional_f
        shares = dollar_amount / max(current_price, 0.01)

        return dollar_amount, shares

    def compute_stop_take(
        self, price: float, regime: str,
        base_stop: float = 0.07, base_take: float = 0.12
    ) -> Tuple[float, float]:
        """
        Compute stop loss and take profit prices.
        In bear regimes, tighten stops; in bull regimes, widen takes.
        """
        if regime == REGIME_BEAR:
            stop_pct = base_stop * 0.7   # tighter stop
            take_pct = base_take * 0.8
        elif regime == REGIME_BULL:
            stop_pct = base_stop * 1.1
            take_pct = base_take * 1.3   # let winners run more
        else:
            stop_pct = base_stop
            take_pct = base_take

        return round(price * (1 - stop_pct), 2), round(price * (1 + take_pct), 2)

    def check_portfolio_limits(
        self, current_exposure: float, equity: float, regime: str
    ) -> bool:
        """Returns True if there is room to open more positions."""
        max_dep = self.max_deployable_equity(equity, regime)
        current_invested = current_exposure * equity
        return current_invested < max_dep
