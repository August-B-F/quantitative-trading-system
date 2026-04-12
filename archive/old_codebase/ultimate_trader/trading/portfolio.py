"""Portfolio state management - always reconciles against Alpaca as source of truth."""
import json
import os
from datetime import datetime
from typing import Dict, List
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import GetAssetsRequest
from alpaca.trading.enums import AssetClass
from ultimate_trader.utils.logging import get_logger
from ultimate_trader.utils.config_loader import Config

logger = get_logger(__name__)


class Portfolio:
    """
    Manages portfolio state by reconciling local cache with Alpaca live positions.
    Alpaca is ALWAYS the source of truth - local state is only a convenience cache.
    """

    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.client = TradingClient(
            cfg.alpaca.key_id, cfg.alpaca.secret_key,
            paper=not cfg.trading.live
        )
        self.positions: Dict = {}   # {symbol: {qty, avg_price, current_price, ...}}
        self.cash: float = 0.0
        self.equity: float = 0.0

    def reconcile(self) -> Dict:
        """
        Pull current positions and account state from Alpaca.
        This is called at the start of every trading run.
        Returns the live positions dict.
        """
        try:
            account = self.client.get_account()
            self.cash = float(account.cash)
            self.equity = float(account.equity)

            raw_positions = self.client.get_all_positions()
            self.positions = {}

            for pos in raw_positions:
                self.positions[pos.symbol] = {
                    "qty": float(pos.qty),
                    "avg_price": float(pos.avg_entry_price),
                    "current_price": float(pos.current_price),
                    "market_value": float(pos.market_value),
                    "unrealized_pnl": float(pos.unrealized_pl),
                    "side": pos.side.value,
                }

            logger.info(
                f"Reconciled: equity=${self.equity:,.2f}, cash=${self.cash:,.2f}, "
                f"{len(self.positions)} open positions"
            )
        except Exception as e:
            logger.error(f"Portfolio reconciliation failed: {e}")
            raise

        return self.positions

    def get_position_value(self, symbol: str) -> float:
        return self.positions.get(symbol, {}).get("market_value", 0.0)

    def get_total_invested(self) -> float:
        return sum(p["market_value"] for p in self.positions.values())

    def get_gross_exposure(self) -> float:
        """Gross exposure as fraction of equity."""
        return self.get_total_invested() / max(self.equity, 1)

    def is_open(self, symbol: str) -> bool:
        return symbol in self.positions

    def summary(self) -> dict:
        return {
            "timestamp": datetime.now().isoformat(),
            "equity": self.equity,
            "cash": self.cash,
            "num_positions": len(self.positions),
            "gross_exposure": self.get_gross_exposure(),
            "positions": self.positions,
        }
