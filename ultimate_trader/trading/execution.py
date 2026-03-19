"""Order execution: translate model decisions into Alpaca bracket orders."""
import time
from typing import Dict, List
from ultimate_trader.utils.logging import get_logger, PerformanceDB
from ultimate_trader.trading.portfolio import Portfolio
from ultimate_trader.trading.risk import (
    compute_position_size, apply_regime_filters,
    BULLISH_ACTIONS, BEARISH_ACTIONS, ACTION_NAMES, check_kill_switch
)

log = get_logger(__name__)


class TradeExecutor:
    """
    Converts model predictions into live/paper trades on Alpaca.
    Uses server-side bracket orders for stop-loss and take-profit.
    """

    def __init__(
        self,
        api,
        portfolio: Portfolio,
        db: PerformanceDB,
        config: dict,
    ):
        self.api       = api
        self.portfolio = portfolio
        self.db        = db
        self.cfg       = config
        self._start_equity = None

    def execute(
        self,
        predictions: Dict[str, dict],  # symbol -> {pred_class, confidence, uncertainty}
        current_prices: Dict[str, float],
        regime: str,
        symbol_to_sector: Dict[str, int] = None,
    ):
        """
        Main entry point. Runs full trade cycle:
          1. Kill-switch check
          2. Close positions that model now rates as sell/short
          3. Apply regime filters to risk params
          4. Open new positions for bullish signals with sufficient confidence
        """
        # reconcile portfolio first
        self.portfolio.reconcile()

        # set starting equity for kill switch on first call of day
        if self._start_equity is None:
            self._start_equity = self.portfolio.equity

        # kill switch
        if check_kill_switch(self.portfolio.equity, self._start_equity,
                              self.cfg.get("max_daily_loss", 0.05)):
            log.critical("Trading halted by kill switch.")
            return

        # regime-adjusted params
        conf_thresh, kelly_mult, max_gross = apply_regime_filters(
            predictions, regime,
            base_confidence_threshold=self.cfg.get("confidence_threshold", 0.55),
            base_kelly_multiplier=self.cfg.get("kelly_fraction", 0.25),
            base_max_gross=self.cfg.get("max_gross_exposure", 0.95),
        )

        # 1. exit stale positions
        self._exit_positions(predictions, current_prices, conf_thresh, regime)

        # 2. enter new positions
        self._enter_positions(
            predictions, current_prices,
            conf_thresh, kelly_mult, max_gross, regime
        )

    def _exit_positions(self, predictions, current_prices, conf_thresh, regime):
        """Close positions the model now rates as sell/strong_sell with high confidence."""
        for symbol, position in list(self.portfolio.positions.items()):
            pred = predictions.get(symbol)
            if pred is None:
                continue
            pred_class  = int(pred["pred_class"])
            confidence  = float(pred["confidence"])

            if pred_class in BEARISH_ACTIONS and confidence > conf_thresh:
                try:
                    self.api.close_position(symbol)
                    price = current_prices.get(symbol, 0.0)
                    qty   = position["qty"]
                    reason = f"model:{ACTION_NAMES[pred_class]} conf:{confidence:.2f} regime:{regime}"
                    log.info(f"Closed {symbol}: {reason}")
                    self.db.log_trade(symbol, "sell", qty, price, reason, confidence, regime)
                except Exception as e:
                    log.error(f"Failed to close {symbol}: {e}")
                time.sleep(0.2)

    def _enter_positions(
        self, predictions, current_prices,
        conf_thresh, kelly_mult, max_gross, regime
    ):
        """Open new long positions for bullish signals above confidence threshold."""
        # sort by confidence descending, enter highest conviction first
        candidates = [
            (sym, pred) for sym, pred in predictions.items()
            if int(pred["pred_class"]) in BULLISH_ACTIONS
            and float(pred["confidence"]) > conf_thresh
            and sym not in self.portfolio.positions
        ]
        candidates.sort(key=lambda x: x[1]["confidence"], reverse=True)

        for symbol, pred in candidates:
            # check gross exposure
            if self.portfolio.total_invested_fraction() >= max_gross:
                log.info("Max gross exposure reached, stopping new entries.")
                break

            price = current_prices.get(symbol)
            if not price or price <= 0:
                continue

            confidence  = float(pred["confidence"])
            uncertainty = float(pred["uncertainty"])

            # skip high-uncertainty signals
            if uncertainty > self.cfg.get("max_uncertainty", 1.5):
                log.info(f"Skipping {symbol}: uncertainty too high ({uncertainty:.3f})")
                continue

            dollar_amount = compute_position_size(
                equity=self.portfolio.equity,
                win_probability=confidence,
                current_position_fraction=self.portfolio.position_fraction(symbol),
                max_single_position=self.cfg.get("max_single_position", 0.15),
                kelly_multiplier=kelly_mult,
                min_cash_buffer=self.cfg.get("min_cash_buffer", 0.05),
                available_cash=self.portfolio.cash,
            )

            shares = round(dollar_amount / price, 2)
            if shares < 1:
                continue

            stop_price  = round(price * (1 - self.cfg.get("stop_loss", 0.07)), 2)
            limit_price = round(price * (1 + self.cfg.get("take_profit", 0.12)), 2)

            try:
                if self.cfg.get("server_side_orders", True):
                    # server-side bracket order -- enforced by Alpaca 24/7
                    self.api.submit_order(
                        symbol=symbol,
                        qty=shares,
                        side="buy",
                        type="market",
                        time_in_force="day",
                        order_class="bracket",
                        stop_loss={"stop_price": stop_price},
                        take_profit={"limit_price": limit_price},
                    )
                else:
                    self.api.submit_order(
                        symbol=symbol,
                        qty=shares,
                        side="buy",
                        type="market",
                        time_in_force="day",
                    )

                reason = (f"model:{ACTION_NAMES[int(pred['pred_class'])]} "
                          f"conf:{confidence:.2f} uncert:{uncertainty:.3f} regime:{regime}")
                log.info(f"Bought {shares} {symbol} @ ~${price:.2f} | {reason}")
                self.db.log_trade(symbol, "buy", shares, price, reason, confidence, regime)

            except Exception as e:
                log.error(f"Order failed for {symbol}: {e}")

            time.sleep(0.3)
