"""Order execution: translates model predictions into Alpaca bracket orders."""
import time
from datetime import datetime, date
from typing import Dict, List, Optional
import pandas as pd
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import (
    MarketOrderRequest, LimitOrderRequest,
    TakeProfitRequest, StopLossRequest,
)
from alpaca.trading.enums import OrderSide, TimeInForce, OrderClass
from ultimate_trader.trading.portfolio import Portfolio
from ultimate_trader.trading.risk import RiskManager
from ultimate_trader.utils.logging import get_logger, PerformanceDB
from ultimate_trader.utils.config_loader import Config

logger = get_logger(__name__)

CLASS_TO_ACTION = {
    0: "strong_sell",
    1: "sell",
    2: "hold",
    3: "buy",
    4: "strong_buy",
}

# Hard gate: trades are SKIPPED (not just logged) when uncertainty exceeds this
UNCERTAINTY_HARD_GATE = 0.75
# Soft gate: exit existing positions when uncertainty exceeds this
UNCERTAINTY_EXIT_GATE = 0.85


class Executor:
    """
    Executes trades based on model predictions.
    - Closes positions that hit exit criteria or have earnings upcoming
    - Opens new positions using Kelly-sized bracket orders
    - Hard uncertainty gating: no trades when model is uncertain
    """

    def __init__(self, cfg: Config, portfolio: Portfolio,
                 risk: RiskManager, db: PerformanceDB):
        self.cfg = cfg
        self.portfolio = portfolio
        self.risk = risk
        self.db = db
        self.client = TradingClient(
            cfg.alpaca.key_id, cfg.alpaca.secret_key,
            paper=not cfg.trading.live
        )

    def get_live_price(self, symbol: str) -> Optional[float]:
        """Get latest trade price from Alpaca."""
        try:
            from alpaca.data.historical import StockHistoricalDataClient
            from alpaca.data.requests import StockLatestTradeRequest
            data_client = StockHistoricalDataClient(
                self.cfg.alpaca.key_id, self.cfg.alpaca.secret_key
            )
            req = StockLatestTradeRequest(symbol_or_symbols=symbol)
            trade = data_client.get_stock_latest_trade(req)
            return float(trade[symbol].price)
        except Exception as e:
            logger.error(f"Could not get live price for {symbol}: {e}")
            return None

    def has_earnings_soon(self, symbol: str,
                           earnings_dates: Dict[str, List[str]],
                           days_ahead: int = 2) -> bool:
        """Returns True if symbol has earnings within `days_ahead` market days."""
        today = date.today()
        for d_str in earnings_dates.get(symbol, []):
            try:
                d = datetime.strptime(d_str, "%Y-%m-%d").date()
                delta = (d - today).days
                if 0 <= delta <= days_ahead:
                    return True
            except Exception:
                pass
        return False

    def close_position(self, symbol: str, reason: str):
        """Close a position via Alpaca market order."""
        try:
            self.client.close_position(symbol)
            logger.info(f"Closed {symbol}: {reason}")
        except Exception as e:
            logger.error(f"Failed to close {symbol}: {e}")

    def run(
        self,
        predictions: Dict[str, Dict],
        regime: str,
        earnings_dates: Dict[str, List[str]] = None,
    ):
        """
        Main execution loop:
        1. Reconcile portfolio
        2. Exit positions: sell signal OR earnings OR uncertainty > EXIT_GATE
        3. Enter positions: buy signal AND confidence >= threshold AND uncertainty < HARD_GATE
        """
        earnings_dates = earnings_dates or {}
        self.portfolio.reconcile()
        equity = self.portfolio.equity
        min_conf = self.risk.min_confidence(regime)

        logger.info(
            f"Execution start | regime={regime} | equity=${equity:,.2f} | "
            f"min_conf={min_conf:.2f} | "
            f"uncertainty_gate={UNCERTAINTY_HARD_GATE}"
        )

        # ── Step 1: Exits ─────────────────────────────────────────────
        for symbol in list(self.portfolio.positions.keys()):
            pred = predictions.get(symbol, {})
            pred_class  = pred.get("pred_class",  2)
            confidence  = pred.get("confidence",  0.0)
            uncertainty = pred.get("uncertainty", 0.0)

            should_exit = False
            exit_reason = ""

            if pred_class in (0, 1) and confidence >= min_conf:
                should_exit = True
                exit_reason = f"Model signal={CLASS_TO_ACTION[pred_class]}, conf={confidence:.2f}"

            if self.has_earnings_soon(symbol, earnings_dates):
                should_exit = True
                exit_reason = "Earnings upcoming"

            # Hard exit when model is too uncertain (actually enforced, not just logged)
            if uncertainty > UNCERTAINTY_EXIT_GATE:
                should_exit = True
                exit_reason = f"High uncertainty={uncertainty:.2f} > {UNCERTAINTY_EXIT_GATE}"

            if should_exit:
                self.close_position(symbol, exit_reason)
                time.sleep(0.3)

        # ── Step 2: Refresh after exits ───────────────────────────────
        self.portfolio.reconcile()
        equity = self.portfolio.equity

        # ── Step 3: Entries ───────────────────────────────────────────
        buy_signals = []
        for sym, pred in predictions.items():
            if pred.get("pred_class", 2) not in (3, 4):
                continue
            if pred.get("confidence", 0) < min_conf:
                logger.debug(f"Skipping {sym}: confidence {pred.get('confidence',0):.2f} < {min_conf:.2f}")
                continue

            uncertainty = pred.get("uncertainty", 1.0)
            if uncertainty >= UNCERTAINTY_HARD_GATE:
                # Hard gate: trade skipped entirely, not just logged
                logger.info(
                    f"Skipping {sym}: uncertainty={uncertainty:.2f} >= hard_gate={UNCERTAINTY_HARD_GATE}"
                )
                continue

            if self.portfolio.is_open(sym):
                continue

            buy_signals.append((sym, pred))

        buy_signals.sort(key=lambda x: x[1]["confidence"], reverse=True)

        for symbol, pred in buy_signals:
            if not self.risk.check_portfolio_limits(
                self.portfolio.get_gross_exposure(), equity, regime
            ):
                logger.info("Portfolio exposure limit reached, stopping entries")
                break

            price = self.get_live_price(symbol)
            if price is None or price <= 0:
                continue

            if self.has_earnings_soon(symbol, earnings_dates):
                logger.info(f"Skipping {symbol}: earnings soon")
                continue

            confidence  = pred["confidence"]
            pred_class  = pred["pred_class"]
            uncertainty = pred.get("uncertainty", 0.0)

            stop_price, take_price = self.risk.compute_stop_take(
                price, regime,
                base_stop=self.cfg.trading.get("base_stop_loss",   0.07),
                base_take=self.cfg.trading.get("base_take_profit", 0.12),
            )
            stop_pct = (price - stop_price) / price
            take_pct = (take_price - price) / price

            dollar_amount, shares = self.risk.kelly_size(
                equity=equity, confidence=confidence,
                pred_class=pred_class, current_price=price,
                regime=regime, stop_loss_pct=stop_pct, take_profit_pct=take_pct,
            )

            shares = round(shares, 2)
            if shares < 0.01 or dollar_amount < 1.0:
                logger.debug(f"Skipping {symbol}: position too small (${dollar_amount:.2f})")
                continue

            if dollar_amount > self.portfolio.cash * 0.9:
                logger.warning(f"Skipping {symbol}: insufficient cash")
                continue

            try:
                if self.cfg.trading.bracket_orders:
                    order = MarketOrderRequest(
                        symbol=symbol, qty=shares,
                        side=OrderSide.BUY,
                        time_in_force=TimeInForce.DAY,
                        order_class=OrderClass.BRACKET,
                        take_profit=TakeProfitRequest(limit_price=take_price),
                        stop_loss=StopLossRequest(stop_price=stop_price),
                    )
                else:
                    order = MarketOrderRequest(
                        symbol=symbol, qty=shares,
                        side=OrderSide.BUY,
                        time_in_force=TimeInForce.DAY,
                    )

                self.client.submit_order(order)
                logger.info(
                    f"BUY {symbol}: {shares} @ ~${price:.2f} "
                    f"stop=${stop_price:.2f} take=${take_price:.2f} "
                    f"conf={confidence:.2f} unc={uncertainty:.2f} regime={regime}"
                )
                self.db.log_trade(
                    symbol=symbol, side="buy", qty=shares, price=price,
                    confidence=confidence, regime=regime,
                    stop_loss=stop_price, take_profit=take_price
                )
                equity -= dollar_amount
                time.sleep(0.3)

            except Exception as e:
                logger.error(f"Order failed for {symbol}: {e}")

        logger.info("Execution complete")
