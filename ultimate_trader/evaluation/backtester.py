"""Walk-forward vectorised backtester.

Simulates the strategy on historical predictions:
  - For each day t, looks up the model's prediction made on day t
  - Applies the same sizing / regime logic as live execution
  - Tracks equity curve, trades, drawdown
"""
import numpy as np
import pandas as pd
from ultimate_trader.modeling.metrics import sharpe_ratio, sortino_ratio, max_drawdown, win_rate
from ultimate_trader.trading.risk import RiskManager
from ultimate_trader.utils.logging import get_logger
from ultimate_trader.utils.config_loader import Config

log = get_logger(__name__)


class Backtester:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.risk = RiskManager(cfg)

    def run(
        self,
        predictions: pd.DataFrame,
        price_data: dict,
        regime_series: pd.Series,
        initial_equity: float = 100_000.0
    ) -> dict:
        """
        Run a vectorised backtest.

        Args:
            predictions: DataFrame with columns:
                [date, symbol, pred_class, confidence, uncertainty]
            price_data: dict symbol -> pd.Series of close prices (date-indexed)
            regime_series: pd.Series of regime label strings per date
            initial_equity: starting capital

        Returns:
            dict with equity_curve (DataFrame), trades (DataFrame), metrics (dict)
        """
        dates = sorted(predictions["date"].unique())
        equity = initial_equity
        equity_curve = []
        all_trades = []
        # symbol -> {entry_price, shares, entry_date, stop_pct, take_pct, regime}
        positions: dict = {}

        stop_base = self.cfg.trading.get("base_stop_loss", 0.07)
        take_base = self.cfg.trading.get("base_take_profit", 0.12)

        for date in dates:
            ts = pd.Timestamp(date)
            # Regime is always a string: "bull" / "bear" / "sideways"
            if hasattr(regime_series, "asof"):
                regime = regime_series.asof(ts)
            else:
                regime = regime_series.get(date, "sideways")
            if not isinstance(regime, str):
                regime = "sideways"

            # ----------------------------------------------------------------
            # 1. Check stop-loss / take-profit on all open positions
            # ----------------------------------------------------------------
            exits = []
            for symbol, pos in positions.items():
                current_price = self._get_price(price_data, symbol, ts)
                if current_price is None:
                    continue
                pnl_pct = (current_price - pos["entry_price"]) / pos["entry_price"]
                if pnl_pct <= -pos["stop_pct"] or pnl_pct >= pos["take_pct"]:
                    pnl_dollar = pnl_pct * pos["entry_price"] * pos["shares"]
                    equity += pos["entry_price"] * pos["shares"] + pnl_dollar
                    reason = "stop_loss" if pnl_pct <= -pos["stop_pct"] else "take_profit"
                    all_trades.append({
                        "symbol": symbol,
                        "entry_date": pos["entry_date"],
                        "exit_date": date,
                        "pnl_pct": round(pnl_pct, 5),
                        "pnl_dollar": round(pnl_dollar, 2),
                        "exit_reason": reason,
                        "regime": pos["regime"],
                    })
                    exits.append(symbol)
            for s in exits:
                positions.pop(s, None)

            day_preds = predictions[predictions["date"] == date]
            if day_preds.empty:
                equity_curve.append({"date": date, "equity": equity})
                continue

            min_conf = self.risk.min_confidence(regime)

            # ----------------------------------------------------------------
            # 2. Model sell signals -> close positions
            # ----------------------------------------------------------------
            sell_mask = (
                day_preds["pred_class"].isin([0, 1]) &
                (day_preds["confidence"] >= min_conf)
            )
            for _, row in day_preds[sell_mask].iterrows():
                symbol = row["symbol"]
                if symbol not in positions:
                    continue
                pos = positions.pop(symbol)
                current_price = self._get_price(price_data, symbol, ts) or pos["entry_price"]
                pnl_pct = (current_price - pos["entry_price"]) / pos["entry_price"]
                pnl_dollar = pnl_pct * pos["entry_price"] * pos["shares"]
                equity += pos["entry_price"] * pos["shares"] + pnl_dollar
                all_trades.append({
                    "symbol": symbol,
                    "entry_date": pos["entry_date"],
                    "exit_date": date,
                    "pnl_pct": round(pnl_pct, 5),
                    "pnl_dollar": round(pnl_dollar, 2),
                    "exit_reason": "model_sell",
                    "regime": pos["regime"],
                })

            # ----------------------------------------------------------------
            # 3. Model buy signals -> open new positions
            # ----------------------------------------------------------------
            uncertainty_col = "uncertainty" if "uncertainty" in day_preds.columns else None
            buy_mask = (
                day_preds["pred_class"].isin([3, 4]) &
                (day_preds["confidence"] >= min_conf)
            )
            if uncertainty_col:
                buy_mask &= day_preds[uncertainty_col] < 0.75

            buy_signals = day_preds[buy_mask].sort_values("confidence", ascending=False)

            for _, row in buy_signals.iterrows():
                symbol = row["symbol"]
                if symbol in positions:
                    continue

                gross_exposure = (
                    sum(p["shares"] * p["entry_price"] for p in positions.values()) /
                    max(equity, 1)
                )
                if not self.risk.check_portfolio_limits(gross_exposure, equity, regime):
                    break

                price = self._get_price(price_data, symbol, ts)
                if price is None or price <= 0:
                    continue

                stop_price, take_price = self.risk.compute_stop_take(
                    price, regime, stop_base, take_base
                )
                stop_pct = (price - stop_price) / price
                take_pct = (take_price - price) / price

                dollar_amount, shares = self.risk.kelly_size(
                    equity=equity,
                    confidence=float(row["confidence"]),
                    pred_class=int(row["pred_class"]),
                    current_price=price,
                    regime=regime,
                    stop_loss_pct=stop_pct,
                    take_profit_pct=take_pct,
                )

                if shares < 0.01 or dollar_amount > equity * 0.95 or dollar_amount < 1.0:
                    continue

                equity -= dollar_amount
                positions[symbol] = {
                    "entry_price": price,
                    "shares": shares,
                    "entry_date": date,
                    "stop_pct": stop_pct,
                    "take_pct": take_pct,
                    "regime": regime,
                }

            # ----------------------------------------------------------------
            # 4. Mark-to-market equity
            # ----------------------------------------------------------------
            mtm = sum(
                pos["shares"] * (self._get_price(price_data, sym, ts) or pos["entry_price"])
                for sym, pos in positions.items()
            )
            equity_curve.append({"date": date, "equity": equity + mtm})

        # Close any remaining open positions at last available price
        last_ts = pd.Timestamp(dates[-1])
        for symbol, pos in positions.items():
            last_price = self._get_price(price_data, symbol, last_ts)
            if last_price:
                pnl_pct = (last_price - pos["entry_price"]) / pos["entry_price"]
                pnl_dollar = pnl_pct * pos["entry_price"] * pos["shares"]
                all_trades.append({
                    "symbol": symbol,
                    "entry_date": pos["entry_date"],
                    "exit_date": dates[-1],
                    "pnl_pct": round(pnl_pct, 5),
                    "pnl_dollar": round(pnl_dollar, 2),
                    "exit_reason": "end_of_backtest",
                    "regime": pos["regime"],
                })

        eq_df = pd.DataFrame(equity_curve).set_index("date")
        eq_series = eq_df["equity"]
        daily_returns = eq_series.pct_change().dropna()
        trades_df = pd.DataFrame(all_trades) if all_trades else pd.DataFrame()

        metrics = {
            "total_return": float((eq_series.iloc[-1] / initial_equity) - 1),
            "sharpe": sharpe_ratio(daily_returns),
            "sortino": sortino_ratio(daily_returns),
            "max_drawdown": max_drawdown(eq_series),
            "win_rate": win_rate(trades_df["pnl_dollar"].values) if not trades_df.empty else 0.0,
            "n_trades": len(trades_df),
            "final_equity": float(eq_series.iloc[-1]),
        }

        log.info(
            f"Backtest | Return: {metrics['total_return']:.2%} | "
            f"Sharpe: {metrics['sharpe']:.2f} | "
            f"MaxDD: {metrics['max_drawdown']:.2%} | "
            f"Trades: {metrics['n_trades']}"
        )

        return {"equity_curve": eq_df, "trades": trades_df, "metrics": metrics}

    def _get_price(self, price_data: dict, symbol: str, ts: pd.Timestamp):
        series = price_data.get(symbol)
        if series is None:
            return None
        try:
            return float(series.asof(ts))
        except Exception:
            return None
