"""Portfolio state manager. Always reconciles with Alpaca as source of truth."""
import json
from pathlib import Path
from datetime import datetime

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import GetAssetsRequest
from alpaca.trading.enums import AssetClass

from ultimate_trader.utils.logging import get_logger, log_trade

log = get_logger(__name__)


class Portfolio:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.client = TradingClient(
            api_key=cfg["alpaca"]["key_id"],
            secret_key=cfg["alpaca"]["secret_key"],
            paper=not cfg["trading"]["live"]
        )
        self.cache_path = Path(cfg["paths"]["raw_dir"]).parent / "portfolio_cache.json"

    def get_account(self) -> dict:
        """Return account summary: equity, cash, buying_power."""
        acct = self.client.get_account()
        return {
            "equity": float(acct.equity),
            "cash": float(acct.cash),
            "buying_power": float(acct.buying_power),
            "portfolio_value": float(acct.portfolio_value)
        }

    def get_positions(self) -> dict[str, dict]:
        """
        Return current positions from Alpaca (source of truth).
        Dict: symbol -> {qty, avg_entry_price, market_value, side}
        """
        positions = {}
        try:
            for pos in self.client.get_all_positions():
                positions[pos.symbol] = {
                    "qty": float(pos.qty),
                    "avg_entry_price": float(pos.avg_entry_price),
                    "market_value": float(pos.market_value),
                    "side": pos.side.value,
                    "unrealized_pl": float(pos.unrealized_pl),
                    "unrealized_plpc": float(pos.unrealized_plpc)
                }
        except Exception as e:
            log.error(f"Failed to get positions: {e}")

        # Cache to disk for audit
        self._save_cache(positions)
        return positions

    def get_open_orders(self) -> list:
        try:
            return self.client.get_orders()
        except Exception as e:
            log.error(f"Failed to get open orders: {e}")
            return []

    def cancel_all_orders(self) -> None:
        try:
            self.client.cancel_orders()
            log.info("All open orders cancelled")
        except Exception as e:
            log.error(f"Failed to cancel orders: {e}")

    def close_position(self, symbol: str) -> bool:
        try:
            self.client.close_position(symbol)
            log_trade(f"Closed position: {symbol} at {datetime.now()}")
            return True
        except Exception as e:
            log.error(f"Failed to close position {symbol}: {e}")
            return False

    def close_all_positions(self) -> None:
        try:
            self.client.close_all_positions(cancel_orders=True)
            log_trade(f"Closed ALL positions at {datetime.now()}")
        except Exception as e:
            log.error(f"Failed to close all positions: {e}")

    def _save_cache(self, positions: dict) -> None:
        try:
            with open(self.cache_path, "w") as f:
                json.dump({"timestamp": str(datetime.now()), "positions": positions}, f, indent=2)
        except Exception:
            pass
