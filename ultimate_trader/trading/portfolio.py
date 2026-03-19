"""Portfolio state management.

Alpaca is ALWAYS the source of truth.  Local state is a cache synced at
the start of every run.  Never trust local JSON over live API positions.
"""
import json
from pathlib import Path
from typing import Optional
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import GetAssetsRequest

from ultimate_trader.utils.logging import get_logger
from ultimate_trader.utils.config_loader import get_full_config

logger = get_logger(__name__)
_PORTFOLIO_CACHE = Path("data/portfolio.json")


def get_trading_client(cfg: Optional[dict] = None) -> TradingClient:
    if cfg is None:
        cfg = get_full_config()
    return TradingClient(
        api_key=cfg["alpaca"]["key_id"],
        secret_key=cfg["alpaca"]["secret_key"],
        paper=not cfg["trading"]["live"],
    )


def reconcile_portfolio(cfg: Optional[dict] = None) -> dict:
    """
    Fetch live positions from Alpaca and reconcile with local cache.
    Alpaca is source of truth — overwrites local state.

    Returns:
        dict of symbol -> {
            qty: float,
            avg_entry_price: float,
            side: 'long' | 'short',
            market_value: float,
            unrealized_pl: float,
        }
    """
    client = get_trading_client(cfg)
    positions = {}
    try:
        for pos in client.get_all_positions():
            positions[pos.symbol] = {
                "qty": float(pos.qty),
                "avg_entry_price": float(pos.avg_entry_price),
                "side": pos.side.value,
                "market_value": float(pos.market_value),
                "unrealized_pl": float(pos.unrealized_pl),
            }
        logger.info(f"Reconciled {len(positions)} live positions from Alpaca")
    except Exception as e:
        logger.error(f"Failed to fetch live positions: {e}")

    # Persist reconciled state
    _PORTFOLIO_CACHE.parent.mkdir(parents=True, exist_ok=True)
    with open(_PORTFOLIO_CACHE, "w") as f:
        json.dump(positions, f, indent=2)

    return positions


def get_account_info(cfg: Optional[dict] = None) -> dict:
    """
    Fetch account cash, equity, and buying power from Alpaca.

    Returns:
        dict with keys: cash, equity, buying_power, portfolio_value
    """
    client = get_trading_client(cfg)
    account = client.get_account()
    return {
        "cash": float(account.cash),
        "equity": float(account.equity),
        "buying_power": float(account.buying_power),
        "portfolio_value": float(account.portfolio_value),
    }


def load_local_portfolio() -> dict:
    """Load last-saved local portfolio cache (use reconcile_portfolio for live runs)."""
    if _PORTFOLIO_CACHE.exists():
        with open(_PORTFOLIO_CACHE) as f:
            return json.load(f)
    return {}
