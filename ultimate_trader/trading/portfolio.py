"""Portfolio state management. Alpaca is always source of truth."""
import json
from pathlib import Path
from typing import Dict
from ultimate_trader.utils.logging import get_logger, PerformanceDB

log = get_logger(__name__)


class Portfolio:
    """
    Manages portfolio state by reconciling with Alpaca live positions.
    Local state is only a cache and supplementary metadata store.
    """

    def __init__(self, api, db: PerformanceDB, cache_path: str = "data/portfolio.json"):
        """
        api: alpaca REST client
        db:  PerformanceDB instance for logging
        """
        self.api = api
        self.db = db
        self.cache_path = Path(cache_path)
        self.positions: Dict[str, dict] = {}
        self.cash: float = 0.0
        self.equity: float = 0.0

    def reconcile(self):
        """
        Fetch live positions and account from Alpaca.
        This MUST be called at the start of every trading run.
        Alpaca is always authoritative. Local cache is overwritten.
        """
        try:
            account = self.api.get_account()
            self.cash   = float(account.cash)
            self.equity = float(account.equity)

            live_positions = self.api.list_positions()
            self.positions = {
                p.symbol: {
                    "qty":         float(p.qty),
                    "avg_price":   float(p.avg_entry_price),
                    "market_val":  float(p.market_value),
                    "side":        p.side,
                }
                for p in live_positions
            }
            self._save_cache()
            log.info(f"Portfolio reconciled: {len(self.positions)} positions, "
                     f"cash=${self.cash:,.0f}, equity=${self.equity:,.0f}")
            self.db.log_equity(self.equity, self.cash, len(self.positions))
        except Exception as e:
            log.error(f"Portfolio reconciliation failed: {e}")
            self._load_cache()

    def get_position_value(self, symbol: str) -> float:
        """Return current market value of a position, or 0."""
        return self.positions.get(symbol, {}).get("market_val", 0.0)

    def get_position_qty(self, symbol: str) -> float:
        """Return current quantity held for a symbol."""
        return self.positions.get(symbol, {}).get("qty", 0.0)

    def position_fraction(self, symbol: str) -> float:
        """Return position size as fraction of total equity."""
        if self.equity == 0:
            return 0.0
        return self.get_position_value(symbol) / self.equity

    def total_invested_fraction(self) -> float:
        """Fraction of equity currently in positions."""
        if self.equity == 0:
            return 0.0
        total_val = sum(p["market_val"] for p in self.positions.values())
        return total_val / self.equity

    def _save_cache(self):
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.cache_path, "w") as f:
            json.dump({
                "positions": self.positions,
                "cash": self.cash,
                "equity": self.equity,
            }, f, indent=2)

    def _load_cache(self):
        if self.cache_path.exists():
            with open(self.cache_path) as f:
                data = json.load(f)
            self.positions = data.get("positions", {})
            self.cash      = data.get("cash", 0.0)
            self.equity    = data.get("equity", 0.0)
            log.warning("Using cached portfolio (Alpaca reconciliation failed)")
