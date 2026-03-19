"""Order execution: bracket orders, reconciliation, position management."""
from datetime import datetime
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest, LimitOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce, OrderClass

from ultimate_trader.utils.logging import get_logger, log_trade
from ultimate_trader.trading.portfolio import Portfolio
from ultimate_trader.trading.risk import compute_position_sizes, kill_switch_triggered

log = get_logger(__name__)


class OrderExecutor:
    def __init__(self, cfg: dict, portfolio: Portfolio):
        self.cfg = cfg
        self.portfolio = portfolio
        self.client = portfolio.client

    def execute(
        self,
        signals: list[dict],
        current_prices: dict[str, float],
        current_regime: int = 1
    ) -> dict:
        """
        Main execution loop.
        1. Check kill-switch
        2. Reconcile existing positions
        3. Close positions no longer in signal set or with exit signals
        4. Open new positions with bracket orders

        signals: list of dicts with keys:
          symbol, action ('buy'|'sell'|'hold'), confidence, prob_win,
          expected_win, expected_loss
        current_prices: dict symbol->float (live last trade price)
        """
        account = self.portfolio.get_account()
        equity = account["equity"]
        positions = self.portfolio.get_positions()

        # --- Kill switch
        total_position_value = sum(p["market_value"] for p in positions.values())
        portfolio_start_value = equity  # simplified; ideally track from day start
        daily_pnl_pct = sum(
            p["unrealized_plpc"] * (p["market_value"] / equity)
            for p in positions.values()
        ) if positions else 0.0

        if kill_switch_triggered(daily_pnl_pct, max_daily_loss=-0.05):
            self.portfolio.close_all_positions()
            return {"status": "kill_switch", "closed": list(positions.keys())}

        # --- Build signal lookup
        signal_map = {s["symbol"]: s for s in signals}

        # --- Close positions not in signal set or with sell signal
        closed = []
        for symbol, pos in positions.items():
            signal = signal_map.get(symbol)
            should_close = (
                signal is None or                          # no signal -> exit
                signal["action"] == "hold" or             # model says hold, we exit for safety
                (signal["action"] == "sell" and pos["side"] == "long") or
                (signal["action"] == "buy" and pos["side"] == "short")
            )
            if should_close:
                if self.portfolio.close_position(symbol):
                    closed.append(symbol)

        # Refresh after closes
        account = self.portfolio.get_account()
        equity = account["equity"]

        # --- Size new positions
        new_signals = [
            s for s in signals
            if s["symbol"] not in positions
            and s["action"] in ("buy", "sell")
        ]
        sized = compute_position_sizes(new_signals, equity, self.cfg, current_regime)

        # --- Submit bracket orders
        opened = []
        for sig in sized:
            symbol = sig["symbol"]
            price = current_prices.get(symbol)
            if price is None or price <= 0:
                log.warning(f"No price for {symbol}, skipping")
                continue

            shares = round(sig["dollar_size"] / price, 2)
            if shares < self.cfg["trading"].get("min_shares", 0.01):
                continue

            side = OrderSide.BUY if sig["action"] == "buy" else OrderSide.SELL
            stop_loss_pct = self.cfg["trading"].get("stop_loss", 0.08)
            take_profit_pct = self.cfg["trading"].get("take_profit", 0.12)

            stop_price = round(price * (1 - stop_loss_pct) if side == OrderSide.BUY
                               else price * (1 + stop_loss_pct), 2)
            limit_price = round(price * (1 + take_profit_pct) if side == OrderSide.BUY
                                else price * (1 - take_profit_pct), 2)

            try:
                order = MarketOrderRequest(
                    symbol=symbol,
                    qty=shares,
                    side=side,
                    time_in_force=TimeInForce.DAY,
                    order_class=OrderClass.BRACKET,
                    stop_loss={"stop_price": stop_price},
                    take_profit={"limit_price": limit_price}
                )
                submitted = self.client.submit_order(order)
                log_trade(
                    f"{side.value.upper()} {shares} x {symbol} @ ~${price:.2f} | "
                    f"SL=${stop_price} TP=${limit_price} | "
                    f"confidence={sig['confidence']:.3f} | "
                    f"order_id={submitted.id} | {datetime.now()}"
                )
                opened.append(symbol)

            except Exception as e:
                log.error(f"Order failed for {symbol}: {e}")

        return {
            "status": "ok",
            "closed": closed,
            "opened": opened,
            "equity": equity
        }
