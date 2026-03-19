"""Vectorised backtester: simulate strategy on historical model predictions."""
import numpy as np
import pandas as pd
from typing import Dict, List, Optional
from ultimate_trader.modeling.metrics import trading_metrics, sharpe_ratio
from ultimate_trader.utils.logging import get_logger

log = get_logger(__name__)

# action class mappings
BUYS  = {3, 4}   # buy, strong_buy
SELLS = {0, 1}   # strong_sell, sell


class Backtester:
    """
    Vectorised backtester for multi-symbol strategy.

    For each day:
      - Opens positions in top-N bullish signals above confidence threshold
      - Closes positions when model shifts to bearish or stop/take-profit hit
      - Applies transaction costs (slippage + commission)

    Returns a performance summary dict and equity curve.
    """

    def __init__(
        self,
        commission: float = 0.001,   # 0.1% per trade (round-trip)
        slippage: float   = 0.001,   # 0.1% per trade
        initial_equity: float = 100_000.0,
    ):
        self.commission     = commission
        self.slippage       = slippage
        self.initial_equity = initial_equity

    def run(
        self,
        predictions: Dict[str, pd.DataFrame],
        prices: Dict[str, pd.Series],
        confidence_threshold: float = 0.55,
        max_positions: int          = 10,
        max_single_frac: float      = 0.15,
        stop_loss: float            = 0.07,
        take_profit: float          = 0.12,
        kelly_fraction: float       = 0.25,
        regime_series: pd.Series    = None,
    ) -> dict:
        """
        predictions: dict of symbol -> DataFrame with columns:
            date (index), pred_class (int), confidence (float), uncertainty (float)
        prices: dict of symbol -> Series of close prices indexed by date
        regime_series: optional Series of regime labels indexed by date

        Returns dict with:
            equity_curve, daily_returns, metrics, trade_log
        """
        # align all dates
        all_dates = sorted(set(
            d for df in predictions.values() for d in df.index
        ))

        equity    = self.initial_equity
        cash      = equity
        positions = {}  # symbol -> {qty, entry_price, stop, take_profit}
        equity_curve = []
        daily_returns = []
        trade_log    = []

        for date in all_dates:
            day_prices = {s: float(prices[s].loc[date])
                          for s in prices if date in prices[s].index}

            # check stop/take-profit on open positions
            to_close = []
            for sym, pos in positions.items():
                if sym not in day_prices:
                    continue
                price = day_prices[sym]
                if price <= pos["stop"] or price >= pos["take_profit"]:
                    reason = "stop_loss" if price <= pos["stop"] else "take_profit"
                    to_close.append((sym, price, reason))

            for sym, price, reason in to_close:
                pos   = positions.pop(sym)
                fill  = price * (1 - self.slippage)
                pnl   = (fill - pos["entry_price"]) * pos["qty"]
                pnl  -= price * pos["qty"] * self.commission
                cash += fill * pos["qty"]
                trade_log.append({"date": date, "symbol": sym, "side": "sell",
                                   "price": fill, "reason": reason, "pnl": pnl})

            # collect today's signals
            todays_preds = {}
            for sym, df in predictions.items():
                if date in df.index:
                    row = df.loc[date]
                    todays_preds[sym] = {
                        "pred_class":  int(row["pred_class"]),
                        "confidence":  float(row["confidence"]),
                        "uncertainty": float(row.get("uncertainty", 0)),
                    }

            # close existing positions if model now says sell
            for sym in list(positions.keys()):
                pred = todays_preds.get(sym)
                if pred and int(pred["pred_class"]) in SELLS and pred["confidence"] > confidence_threshold:
                    if sym in day_prices:
                        price = day_prices[sym]
                        pos   = positions.pop(sym)
                        fill  = price * (1 - self.slippage)
                        pnl   = (fill - pos["entry_price"]) * pos["qty"]
                        pnl  -= price * pos["qty"] * self.commission
                        cash += fill * pos["qty"]
                        trade_log.append({"date": date, "symbol": sym, "side": "sell",
                                           "price": fill, "reason": "model_signal", "pnl": pnl})

            # enter new positions
            candidates = [
                (sym, p) for sym, p in todays_preds.items()
                if p["pred_class"] in BUYS
                and p["confidence"] > confidence_threshold
                and sym not in positions
                and sym in day_prices
            ]
            candidates.sort(key=lambda x: x[1]["confidence"], reverse=True)
            candidates = candidates[:max_positions - len(positions)]

            total_invested = sum(
                positions[s]["qty"] * day_prices.get(s, 0)
                for s in positions if s in day_prices
            )
            current_frac = total_invested / equity if equity > 0 else 0

            for sym, pred in candidates:
                price = day_prices[sym]
                frac = min(max_single_frac, kelly_fraction * pred["confidence"])
                dollar = frac * equity
                dollar = min(dollar, cash * 0.95)
                qty = dollar / price
                if qty < 0.01 or dollar < 1:
                    continue
                fill = price * (1 + self.slippage)
                cost = fill * qty * (1 + self.commission)
                if cost > cash:
                    continue
                cash -= cost
                positions[sym] = {
                    "qty":         qty,
                    "entry_price": fill,
                    "stop":        fill * (1 - stop_loss),
                    "take_profit": fill * (1 + take_profit),
                }
                trade_log.append({"date": date, "symbol": sym, "side": "buy",
                                   "price": fill, "reason": "model_signal", "pnl": 0})

            # daily equity
            pos_value = sum(
                positions[s]["qty"] * day_prices.get(s, positions[s]["entry_price"])
                for s in positions
            )
            prev_equity = equity
            equity = cash + pos_value
            daily_ret = (equity - prev_equity) / prev_equity if prev_equity > 0 else 0
            equity_curve.append(equity)
            daily_returns.append(daily_ret)

        equity_arr = np.array(equity_curve)
        ret_arr    = np.array(daily_returns)
        metrics    = trading_metrics(ret_arr)
        metrics["dates"] = all_dates[:len(equity_arr)]

        log.info(f"Backtest complete: Sharpe={metrics['sharpe']:.2f}, "
                 f"MaxDD={metrics['max_dd']:.1%}, TotalRet={metrics['total_ret']:.1%}")

        return {
            "equity_curve":  equity_arr,
            "daily_returns": ret_arr,
            "metrics":       metrics,
            "trade_log":     pd.DataFrame(trade_log),
        }
