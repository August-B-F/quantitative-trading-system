"""Portfolio state management.

Alpaca is ALWAYS the source of truth.
Local state is only used as a cache between API calls within a single run.
At the start of every run, positions are reconciled from Alpaca.
"""
import json
import datetime
from pathlib import Path
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import GetAssetsRequest
from ultimate_trader.utils.logging import get_logger

logger = get_logger("portfolio")


def get_trading_client(api_key: str, secret_key: str, paper: bool = True) -> TradingClient:
    return TradingClient(api_key, secret_key, paper=paper)


def reconcile_positions(client: TradingClient) -> dict:
    """
    Fetch ALL open positions from Alpaca and return as:
    {symbol: {qty, avg_entry_price, market_value, unrealized_plpc}}
    This is called at the start of every run - no local state trusted.
    """
    positions = {}
    try:
        raw = client.get_all_positions()
        for pos in raw:
            positions[pos.symbol] = {
                "qty": float(pos.qty),
                "avg_entry_price": float(pos.avg_entry_price),
                "market_value": float(pos.market_value),
                "unrealized_plpc": float(pos.unrealized_plpc),
                "side": pos.side.value,
            }
        logger.info(f"Reconciled {len(positions)} open positions from Alpaca")
    except Exception as e:
        logger.error(f"Failed to reconcile positions: {e}")
    return positions


def get_account_info(client: TradingClient) -> dict:
    """Return key account metrics."""
    try:
        acct = client.get_account()
        return {
            "cash": float(acct.cash),
            "equity": float(acct.equity),
            "buying_power": float(acct.buying_power),
            "portfolio_value": float(acct.portfolio_value),
            "daytrade_count": int(acct.daytrade_count),
        }
    except Exception as e:
        logger.error(f"Failed to get account info: {e}")
        return {}


def save_run_snapshot(
    positions: dict,
    account: dict,
    path: str = "data/logs/portfolio_snapshot.json",
):
    """Save a timestamped snapshot of the portfolio for audit trail."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    snapshot = {
        "timestamp": datetime.datetime.now().isoformat(),
        "account": account,
        "positions": positions,
    }
    # append to history file
    history_path = path.replace(".json", "_history.jsonl")
    with open(history_path, "a") as f:
        f.write(json.dumps(snapshot) + "\n")
    # overwrite latest
    with open(path, "w") as f:
        json.dump(snapshot, f, indent=2)
