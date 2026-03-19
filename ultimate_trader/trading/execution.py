"""Order execution layer.

Key design principles:
  - All stops and take-profits are SERVER-SIDE bracket orders on Alpaca.
  - No local stop-loss checking loop.
  - Portfolio state reconciled from Alpaca before every decision.
  - Earnings calendar checked before entry.
  - Regime-aware sizing via risk.py.
"""
import datetime
import time
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import (
    MarketOrderRequest, LimitOrderRequest,
    TakeProfitRequest, StopLossRequest,
)
from alpaca.trading.enums import OrderSide, TimeInForce, OrderClass
from ultimate_trader.utils.logging import get_logger
from ultimate_trader.trading.risk import (
    kelly_position_size, get_regime_params, check_earnings_buffer, check_kill_switch
)

logger = get_logger("execution")


def place_bracket_order(
    client: TradingClient,
    symbol: str,
    dollar_size: float,
    current_price: float,
    side: OrderSide,
    stop_loss_pct: float = 0.07,
    take_profit_pct: float = 0.12,
) -> bool:
    """
    Place a bracket market order with server-side stop-loss and take-profit.
    Returns True if successful.
    """
    qty = round(abs(dollar_size) / current_price, 2)
    if qty < 1:
        logger.info(f"  {symbol}: qty {qty} < 1, skipping")
        return False

    if side == OrderSide.BUY:
        sl_price = round(current_price * (1 - stop_loss_pct), 2)
        tp_price = round(current_price * (1 + take_profit_pct), 2)
    else:
        sl_price = round(current_price * (1 + stop_loss_pct), 2)
        tp_price = round(current_price * (1 - take_profit_pct), 2)

    try:
        req = MarketOrderRequest(
            symbol=symbol,
            qty=qty,
            side=side,
            time_in_force=TimeInForce.DAY,
            order_class=OrderClass.BRACKET,
            take_profit=TakeProfitRequest(limit_price=tp_price),
            stop_loss=StopLossRequest(stop_price=sl_price),
        )
        order = client.submit_order(req)
        logger.info(
            f"  BRACKET ORDER: {side.value} {qty} {symbol} "
            f"@ ~{current_price:.2f} | SL={sl_price} | TP={tp_price} | id={order.id}"
        )
        return True
    except Exception as e:
        logger.error(f"  Order failed for {symbol}: {e}")
        return False


def close_position(client: TradingClient, symbol: str):
    """Close an open position entirely."""
    try:
        client.close_position(symbol)
        logger.info(f"  Closed position: {symbol}")
    except Exception as e:
        logger.warning(f"  Could not close {symbol}: {e}")


def run_trading_session(
    predictions: dict,
    current_prices: dict,
    positions: dict,
    account: dict,
    client: TradingClient,
    current_regime: int,
    earnings_calendar: dict,
    cfg: dict,
):
    """
    Main execution loop for a single trading session.

    Args:
        predictions:       {symbol: {mean_probs, confidence, predicted_class}}
        current_prices:    {symbol: float}
        positions:         current open positions from reconcile_positions()
        account:           account info from get_account_info()
        client:            TradingClient
        current_regime:    int (0/1/2)
        earnings_calendar: {symbol: [date_str]}
        cfg:               merged config dict
    """
    # Kill switch check
    if check_kill_switch(account):
        logger.warning("Kill switch active. No trades will be placed.")
        return

    regime_params = get_regime_params(current_regime, cfg)
    equity = account.get("equity", 0)
    earnings_buffer = cfg.get("trading", {}).get("earnings_buffer_days", 1)
    allow_short = cfg.get("trading", {}).get("allow_short", True) and regime_params["allow_short"]

    actions = []

    for symbol, pred in predictions.items():
        price = current_prices.get(symbol)
        if not price or price <= 0:
            logger.warning(f"  No price for {symbol}, skipping")
            continue

        confidence = float(pred["confidence"])
        predicted_class = int(pred["predicted_class"])

        # Skip hold predictions
        if predicted_class == 2:
            continue

        # Skip if below confidence threshold
        if confidence < regime_params["min_confidence"]:
            logger.info(f"  {symbol}: confidence {confidence:.3f} below threshold, skip")
            continue

        # Skip if earnings are imminent
        if check_earnings_buffer(symbol, earnings_calendar, earnings_buffer):
            logger.info(f"  {symbol}: earnings buffer active, skip")
            # also close any open position
            if symbol in positions:
                close_position(client, symbol)
            continue

        # Determine side
        is_long = predicted_class in (3, 4)
        is_short = predicted_class in (0, 1)

        if is_short and not allow_short:
            continue

        side = OrderSide.BUY if is_long else OrderSide.SELL

        # Kelly sizing
        dollar_size = kelly_position_size(
            confidence=confidence,
            predicted_class=predicted_class,
            current_price=price,
            equity=equity,
            kelly_fraction=regime_params["kelly_fraction"],
            max_position_fraction=regime_params["max_single_position"],
        )

        if abs(dollar_size) < price:  # less than 1 share worth
            continue

        # Check gross exposure
        current_exposure = sum(
            abs(p["market_value"]) for p in positions.values()
        ) / equity if equity > 0 else 0
        if current_exposure >= regime_params["max_gross_exposure"]:
            logger.info(f"  Max gross exposure reached ({current_exposure:.1%}), skipping new trades")
            break

        actions.append((symbol, side, dollar_size, price, confidence, predicted_class))

    # Sort by confidence descending
    actions.sort(key=lambda x: -x[4])

    placed = 0
    for symbol, side, dollar_size, price, confidence, pred_class in actions:
        logger.info(f"  Placing: {side.value} {symbol} ${dollar_size:.0f} conf={confidence:.3f} class={pred_class}")
        success = place_bracket_order(
            client=client,
            symbol=symbol,
            dollar_size=dollar_size,
            current_price=price,
            side=side,
        )
        if success:
            placed += 1
        time.sleep(0.2)  # rate limit buffer

    logger.info(f"Trading session complete: {placed}/{len(actions)} orders placed | regime={current_regime}")
