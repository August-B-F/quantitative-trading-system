"""Walk-forward vectorised backtester.

Simulates the strategy on historical predictions:
  - For each day t, looks up the model's prediction made on day t
  - Applies the same sizing / regime logic as live execution
  - Tracks equity curve, trades, drawdown
"""
import numpy as np
import pandas as pd
from ultimate_trader.modeling.metrics import sharpe_ratio, sortino_ratio, max_drawdown, win_rate
from ultimate_trader.utils.logging import get_logger

log = get_logger(__name__)


class Backtester:
    def __init__(self, cfg: dict):
        self.cfg = cfg

    def run(
        self,
        predictions: pd.DataFrame,
        price_data: dict[str, pd.Series],
        regime_series: pd.Series,
        initial_equity: float = 100_000.0
    ) -> dict:
        """
        Run a vectorised backtest.

        Args:
            predictions: DataFrame with columns [date, symbol, action, confidence,
                         prob_buy, expected_win, expected_loss]
            price_data: dict symbol -> pd.Series of close prices
            regime_series: pd.Series of regime labels per date
            initial_equity: starting capital

        Returns:
            dict with equity_curve, trades, metrics
        """
        from ultimate_trader.trading.risk import compute_position_sizes

        dates = sorted(predictions["date"].unique())
        equity = initial_equity
        equity_curve = []
        all_trades = []
        positions: dict[str, dict] = {}  # symbol -> {entry_price, shares, side, entry_date}

        for date in dates:
            # --- Check stop/take profit on existing positions
            exits = []
            for symbol, pos in positions.items():
                current_price = self._get_price(price_data, symbol, date)
                if current_price is None:
                    continue

                pnl_pct = (current_price - pos["entry_price"]) / pos["entry_price"]
                if pos["side"] == "sell":
                    pnl_pct = -pnl_pct

                stop = self.cfg["trading"].get("stop_loss", 0.08)
                tp = self.cfg["trading"].get("take_profit", 0.12)

                if pnl_pct <= -stop or pnl_pct >= tp:
                    pnl_dollar = pnl_pct * pos["entry_price"] * pos["shares"]
                    equity += pos["entry_price"] * pos["shares"] + pnl_dollar
                    reason = "stop_loss" if pnl_pct <= -stop else "take_profit"
                    all_trades.append({
                        "symbol": symbol,
                        "entry_date": pos["entry_date"],
                        "exit_date": date,
                        "side": pos["side"],
                        "pnl_pct": pnl_pct,
                        "pnl_dollar": pnl_dollar,
                        "exit_reason": reason
                    })
                    exits.append(symbol)

            for s in exits:
                positions.pop(s, None)

            # --- New signals for this date
            day_preds = predictions[predictions["date"] == date]
            if day_preds.empty:
                equity_curve.append({"date": date, "equity": equity})
                continue

            current_regime = int(regime_series.get(date, 1))
            signals = day_preds.to_dict("records")

            sized = compute_position_sizes(signals, equity, self.cfg, current_regime)

            for sig in sized:
                symbol = sig["symbol"]
                if symbol in positions:
                    continue  # already holding

                price = self._get_price(price_data, symbol, date)
                if price is None or price <= 0:
                    continue

                shares = sig["dollar_size"] / price
                equity -= sig["dollar_size"]
                positions[symbol] = {
                    "entry_price": price,
                    "shares": shares,
                    "side": sig["action"],
                    "entry_date": date
                }

            # Mark-to-market equity
            mtm = sum(
                pos["shares"] * (self._get_price(price_data, sym, date) or pos["entry_price"])
                for sym, pos in positions.items()
            )
            equity_curve.append({"date": date, "equity": equity + mtm})

        eq_df = pd.DataFrame(equity_curve).set_index("date")
        eq_series = eq_df["equity"]
        daily_returns = eq_series.pct_change().dropna()
        trades_df = pd.DataFrame(all_trades)

        metrics = {
            "total_return": float((eq_series.iloc[-1] / initial_equity) - 1),
            "sharpe": sharpe_ratio(daily_returns),
            "sortino": sortino_ratio(daily_returns),
            "max_drawdown": max_drawdown(eq_series),
            "win_rate": win_rate(trades_df["pnl_dollar"].values) if not trades_df.empty else 0.0,
            "n_trades": len(trades_df),
            "final_equity": float(eq_series.iloc[-1])
        }

        log.info(
            f"Backtest | Return: {metrics['total_return']:.2%} | "
            f"Sharpe: {metrics['sharpe']:.2f} | "
            f"MaxDD: {metrics['max_drawdown']:.2%} | "
            f"Trades: {metrics['n_trades']}"
        )

        return {"equity_curve": eq_df, "trades": trades_df, "metrics": metrics}

    def _get_price(self, price_data: dict, symbol: str, date) -> float | None:
        series = price_data.get(symbol)
        if series is None:
            return None
        try:
            return float(series.asof(pd.Timestamp(date)))
        except Exception:
            return None
