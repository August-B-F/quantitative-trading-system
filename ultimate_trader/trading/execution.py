"""Trade execution with bracket orders, Kelly sizing, and regime-aware filters.

Key design principles:
  - Server-side bracket orders (stop loss + take profit on Alpaca servers)
    so limits fire even when the bot is not running.
  - Fractional Kelly position sizing based on model confidence.
  - Earnings blackout: never enter a new position within N days of earnings.
  - Both long AND short supported.
  - All executions logged to structured logs.
"""
import datetime
from typing import Optional
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest, LimitOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce, OrderClass
from alpaca.trading.requests import TakeProfitRequest, StopLossRequest

from ultimate_trader.trading.portfolio import get_trading_client, get_account_info
from ultimate_trader.trading.risk import (
    apply_regime_filters,
    check_earnings_blackout,
    compute_kelly_sizes,
    apply_exposure_limits,
)
from ultimate_trader.utils.logging import get_logger
from ultimate_trader.utils.config_loader import get_full_config

logger = get_logger(__name__)


def run_trading_session(
    predictions: dict,
    current_portfolio: dict,
    earnings_calendar: dict,
    current_regime: int,
    cfg: Optional[dict] = None,
) -> dict:
    """
    Main trade execution function. Runs once per day.

    Args:
        predictions: dict of symbol -> {
            pred_class: int (0-4),
            confidence: float (0-1),
            mean_probs: list of 5 floats,
        }
        current_portfolio: live positions dict from reconcile_portfolio()
        earnings_calendar: dict of symbol -> list of earnings date strings
        current_regime: integer regime (0=bull, 1=mixed, 2=bear)
        cfg: full config dict

    Returns:
        dict summarising orders placed
    """
    if cfg is None:
        cfg = get_full_config()

    client = get_trading_client(cfg)
    account = get_account_info(cfg)
    equity = account["equity"]
    today = datetime.datetime.now().strftime("%Y-%m-%d")

    trading_cfg = cfg["trading"]
    blackout_days = trading_cfg.get("earnings_blackout_days", 1)
    allow_short = trading_cfg.get("allow_short", True)
    max_single = trading_cfg.get("max_single_position", 0.15)

    orders_placed = []

    # --- 1. Close positions that no longer have a buy/hold signal ---
    for symbol, pos in current_portfolio.items():
        pred = predictions.get(symbol, {})
        pred_class = pred.get("pred_class", 2)
        side = pos["side"]

        should_close = False
        if side == "long" and pred_class in [0, 1]:  # Was long, now bearish
            should_close = True
        elif side == "short" and pred_class in [3, 4]:  # Was short, now bullish
            should_close = True
        elif pred.get("confidence", 1.0) < 0.3:  # Very uncertain
            should_close = True

        if should_close:
            try:
                client.close_position(symbol)
                logger.info(f"Closed position in {symbol} (pred_class={pred_class}, side={side})")
                orders_placed.append({"action": "close", "symbol": symbol})
            except Exception as e:
                logger.error(f"Failed to close {symbol}: {e}")

    # --- 2. Filter predictions to actionable signals ---
    # Regime-adjusted confidence threshold
    base_conf = cfg.get("hyperparam_search", {}).get("search_space", {}).get("confidence_threshold", [0.6])
    conf_threshold = apply_regime_filters(base_conf if isinstance(base_conf, float) else 0.6, current_regime)

    candidates = []
    for symbol, pred in predictions.items():
        pred_class = pred.get("pred_class", 2)
        confidence = pred.get("confidence", 0.0)
        mean_probs = pred.get("mean_probs", [0.2] * 5)

        if pred_class == 2:  # hold
            continue
        if confidence < conf_threshold:
            continue
        if check_earnings_blackout(symbol, today, earnings_calendar, blackout_days):
            logger.info(f"{symbol}: skipped — earnings blackout")
            continue
        if not allow_short and pred_class in [0, 1]:
            continue

        side = "buy" if pred_class >= 3 else "sell"
        # Edge estimate: expected value from probability distribution
        # Classes: 0=-2r, 1=-r, 2=0, 3=r, 4=2r where r = r_hi
        r = cfg["targets"]["r_hi"]
        class_returns = [-2 * r, -r, 0, r, 2 * r]
        expected_return = sum(p * ret for p, ret in zip(mean_probs, class_returns))

        candidates.append({
            "symbol": symbol,
            "side": side,
            "confidence": confidence,
            "expected_return": abs(expected_return),
            "pred_class": pred_class,
        })

    # Sort by expected return descending, take top N
    max_positions = cfg.get("hyperparam_search", {}).get("search_space", {}).get("diversification", [8])
    if isinstance(max_positions, list):
        max_positions = 8
    candidates = sorted(candidates, key=lambda x: x["expected_return"], reverse=True)[:max_positions]

    # --- 3. Kelly sizing ---
    candidates = compute_kelly_sizes(
        candidates, equity, max_single, cfg.get("hyperparam_search", {}).get("search_space", {})
    )

    # --- 4. Exposure limit check ---
    candidates = apply_exposure_limits(candidates, equity, trading_cfg)

    # --- 5. Submit bracket orders ---
    stop_loss_pct = 0.05   # These will be tuned by hyperparam search
    take_profit_pct = 0.10

    for trade in candidates:
        symbol = trade["symbol"]
        side = trade["side"]
        dollar_amount = trade.get("dollar_amount", 0)

        if dollar_amount < 1:
            continue

        try:
            # Get current price from Alpaca
            from alpaca.data.historical import StockHistoricalDataClient
            from alpaca.data.requests import StockLatestTradeRequest
            data_client = StockHistoricalDataClient(
                api_key=cfg["alpaca"]["key_id"],
                secret_key=cfg["alpaca"]["secret_key"],
            )
            latest = data_client.get_stock_latest_trade(StockLatestTradeRequest(symbol_or_symbols=symbol))
            price = float(latest[symbol].price)
            qty = round(dollar_amount / price, 4)

            if qty < 0.01:
                continue

            order_side = OrderSide.BUY if side == "buy" else OrderSide.SELL

            # Bracket: server-side stop loss and take profit
            if side == "buy":
                sl_price = round(price * (1 - stop_loss_pct), 4)
                tp_price = round(price * (1 + take_profit_pct), 4)
            else:  # short
                sl_price = round(price * (1 + stop_loss_pct), 4)
                tp_price = round(price * (1 - take_profit_pct), 4)

            order_req = MarketOrderRequest(
                symbol=symbol,
                qty=qty,
                side=order_side,
                time_in_force=TimeInForce.DAY,
                order_class=OrderClass.BRACKET,
                stop_loss=StopLossRequest(stop_price=sl_price),
                take_profit=TakeProfitRequest(limit_price=tp_price),
            )

            order = client.submit_order(order_req)
            logger.info(
                f"Order submitted: {side.upper()} {qty} {symbol} @ ~${price:.2f} "
                f"| SL=${sl_price} TP=${tp_price} | conf={trade['confidence']:.3f}"
            )
            orders_placed.append({
                "action": side,
                "symbol": symbol,
                "qty": qty,
                "price": price,
                "confidence": trade["confidence"],
                "order_id": str(order.id),
            })

        except Exception as e:
            logger.error(f"Order failed for {symbol}: {e}")

    logger.info(f"Trading session complete. {len(orders_placed)} actions taken.")
    return {"orders": orders_placed, "equity": equity}
