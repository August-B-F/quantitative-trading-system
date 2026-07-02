"""Spec tests: AuctionExecutor cls-auction order flow (whole-share flooring,
cls TIF, buying-power pre-check refusal, dry-run, fill verification) plus the
whole-share validation contract of AlpacaPaperClient.submit_order_qty."""
from __future__ import annotations

import pytest

from execution.alpaca_client import AlpacaPaperClient
from execution.auction_executor import (
    PLAN_EQUITY_HEADROOM,
    AuctionExecutor,
)


# ---- fake client -----------------------------------------------------------

class FakeClient:
    """Scriptable in-memory stand-in for AlpacaPaperClient (auction path).

    ``accounts`` / ``positions`` are consumed as queues (one entry per call,
    last entry repeats), mirroring tests/test_executor.py. ``latest_trades``
    maps ticker -> price for get_latest_trade. All fills resolve immediately.
    """

    def __init__(
        self,
        accounts: list[dict],
        positions: list[dict],
        latest_trades: dict[str, float],
        submit_responses: dict[str, list[dict]] | None = None,
        fill_responses: dict[str, dict] | None = None,
    ):
        self._accounts = list(accounts)
        self._positions = list(positions)
        self.latest_trades = dict(latest_trades)
        self.submit_responses = submit_responses or {}   # ticker -> queued responses
        self.fill_responses = fill_responses or {}       # order_id -> final status
        self.submitted: list[dict] = []
        self.canceled: list[str] = []
        self.trade_lookups: list[str] = []
        self.wait_calls: list[tuple[str, float]] = []
        self._seq: dict[str, int] = {}

    @staticmethod
    def _pop(queue: list) -> dict:
        assert queue, "FakeClient queue exhausted"
        return queue.pop(0) if len(queue) > 1 else queue[0]

    def get_account(self) -> dict:
        return dict(self._pop(self._accounts))

    def get_positions(self) -> dict:
        pos = self._pop(self._positions)
        if "error" in pos:
            return dict(pos)
        return {t: dict(p) for t, p in pos.items()}

    def get_latest_trade(self, ticker: str) -> dict:
        self.trade_lookups.append(ticker)
        if ticker not in self.latest_trades:
            return {"error": f"http 404: no trade for {ticker}"}
        return {"symbol": ticker, "price": self.latest_trades[ticker],
                "size": 100, "timestamp": "2026-07-02T19:45:00Z", "raw": {}}

    def submit_order_qty(self, ticker: str, qty: int, side: str,
                         order_type: str = "market",
                         time_in_force: str = "day",
                         limit_price: float | None = None) -> dict:
        self.submitted.append({
            "ticker": ticker, "qty": qty, "side": side,
            "order_type": order_type, "time_in_force": time_in_force,
        })
        queue = self.submit_responses.get(ticker)
        if queue:
            return dict(queue.pop(0))
        n = self._seq.get(ticker, 0) + 1
        self._seq[ticker] = n
        oid = f"{ticker}-{n}"
        return {"id": oid, "status": "accepted_for_bidding", "symbol": ticker,
                "side": side, "qty": str(qty), "time_in_force": time_in_force}

    def wait_for_fill(self, order_id: str, timeout_s: float = 60.0,
                      poll: float = 1.0) -> dict:
        self.wait_calls.append((order_id, timeout_s))
        default = {"id": order_id, "status": "filled",
                   "filled_qty": "10", "filled_avg_price": "100.0"}
        return dict(self.fill_responses.get(order_id, default))

    def cancel_order(self, order_id: str) -> dict:
        self.canceled.append(order_id)
        return {"id": order_id, "status": "canceled"}


def make_account(equity: float, cash: float, buying_power: float | None = None) -> dict:
    return {
        "equity": equity,
        "cash": cash,
        "buying_power": buying_power if buying_power is not None else cash,
        "status": "ACTIVE",
    }


def make_position(market_value: float, qty: float = 1.0) -> dict:
    return {"qty": qty, "market_value": market_value,
            "avg_entry": 100.0, "pnl": 0.0}


# ---- whole-share sizing ------------------------------------------------------

def test_whole_share_sizing_floors_from_latest_trade_prices() -> None:
    """Target shares = floor(weight * equity * headroom / latest price)."""
    fake = FakeClient(
        accounts=[make_account(100_000, 100_000)],
        positions=[{}],
        latest_trades={"SPY": 333.33, "GLD": 190.10},
    )
    execu = AuctionExecutor("TEST", fake)
    result = execu.execute_rebalance_cls({"SPY": 0.6, "GLD": 0.4}, dry_run=True)

    orders = {o["ticker"]: o for o in result["orders"]}
    # floor(0.6 * 100_000 * 0.998 / 333.33) = floor(179.64) = 179
    assert orders["SPY"]["qty"] == int(0.6 * 100_000 * PLAN_EQUITY_HEADROOM / 333.33)
    assert orders["SPY"]["qty"] == 179
    # floor(0.4 * 100_000 * 0.998 / 190.10) = floor(210.0) = 209 or 210?
    assert orders["GLD"]["qty"] == int(0.4 * 100_000 * PLAN_EQUITY_HEADROOM / 190.10)
    assert all(o["side"] == "buy" for o in result["orders"])
    assert result["success"] is True


def test_sell_qty_is_current_minus_target_whole_shares() -> None:
    """A downsize sells exactly (held_whole - target_shares); fractional
    tails from old notional fills never ride on a cls order."""
    fake = FakeClient(
        accounts=[make_account(100_000, 0.0, 100_000)],
        positions=[{"TLT": make_position(100_000, qty=250.7)}],
        latest_trades={"TLT": 400.0, "SPY": 500.0},
    )
    execu = AuctionExecutor("TEST", fake)
    result = execu.execute_rebalance_cls({"SPY": 1.0}, dry_run=True)

    orders = {o["ticker"]: o for o in result["orders"]}
    # Full exit: sell the 250 whole shares; the 0.7 tail is reported.
    assert orders["TLT"]["side"] == "sell"
    assert orders["TLT"]["qty"] == 250
    assert result["fractional_residuals"] == {"TLT": 0.7}
    # Buy floor(1.0 * 99_800 / 500) = 199 whole shares.
    assert orders["SPY"]["side"] == "buy"
    assert orders["SPY"]["qty"] == 199


# ---- cls TIF -----------------------------------------------------------------

def test_all_orders_submitted_together_as_cls() -> None:
    """Live path submits sells AND buys in one batch, every order market/cls."""
    fake = FakeClient(
        accounts=[make_account(100_000, 0.0, 200_000)],   # 2x margin BP
        positions=[{"TLT": make_position(100_000, qty=250)}],
        latest_trades={"TLT": 400.0, "SPY": 500.0},
    )
    execu = AuctionExecutor("TEST", fake)
    result = execu.execute_rebalance_cls({"SPY": 1.0}, dry_run=False)

    assert len(fake.submitted) == 2
    assert all(s["time_in_force"] == "cls" for s in fake.submitted)
    assert all(s["order_type"] == "market" for s in fake.submitted)
    # Sells listed first, but both hit the wire in the same submission pass.
    assert [s["side"] for s in fake.submitted] == ["sell", "buy"]
    assert result["success"] is True
    assert result["failed_orders"] == []


# ---- buying-power pre-check ----------------------------------------------------

def test_bp_precheck_refuses_when_buys_exceed_buying_power() -> None:
    """Same-auction buys need BP up front (sale proceeds unavailable): the
    executor must refuse, name the margin-multiplier requirement, and submit
    NOTHING — never a partial rebalance."""
    fake = FakeClient(
        accounts=[make_account(100_000, 0.0, 50_000)],    # 1x-ish: BP < buys
        positions=[{"TLT": make_position(100_000, qty=250)}],
        latest_trades={"TLT": 400.0, "SPY": 500.0},
    )
    execu = AuctionExecutor("TEST", fake)
    result = execu.execute_rebalance_cls({"SPY": 1.0}, dry_run=False)

    assert result["success"] is False
    assert "buying power" in result["error"]
    assert "margin" in result["error"]          # names the 2x requirement
    assert "SAME closing auction" in result["error"]
    assert fake.submitted == []                  # refusal happens pre-wire


def test_bp_precheck_passes_with_margin_buying_power() -> None:
    """The identical rebalance goes through when BP covers the buys."""
    fake = FakeClient(
        accounts=[make_account(100_000, 0.0, 200_000)],
        positions=[{"TLT": make_position(100_000, qty=250)}],
        latest_trades={"TLT": 400.0, "SPY": 500.0},
    )
    execu = AuctionExecutor("TEST", fake)
    result = execu.execute_rebalance_cls({"SPY": 1.0}, dry_run=False)
    assert "error" not in result
    assert result["success"] is True


# ---- dry run -------------------------------------------------------------------

def test_dry_run_builds_plan_but_submits_nothing() -> None:
    fake = FakeClient(
        accounts=[make_account(100_000, 100_000)],
        positions=[{}],
        latest_trades={"SPY": 500.0},
    )
    execu = AuctionExecutor("TEST", fake)
    result = execu.execute_rebalance_cls({"SPY": 1.0}, dry_run=True)

    assert result["success"] is True
    assert result["dry_run"] is True
    assert fake.submitted == []
    assert fake.wait_calls == []
    assert len(result["orders"]) == 1
    assert result["orders"][0]["qty"] == 199    # floor(99_800 / 500)


# ---- fill verification -----------------------------------------------------------

def test_unfilled_cls_order_flips_success_false() -> None:
    """Post-close verification: an order that never fills is canceled, lands
    in failed_orders, and flips success=False."""
    fake = FakeClient(
        accounts=[make_account(100_000, 100_000)],
        positions=[{}],
        latest_trades={"SPY": 500.0, "GLD": 200.0},
        fill_responses={
            "GLD-1": {"id": "GLD-1", "status": "new", "timeout": True},
        },
    )
    execu = AuctionExecutor("TEST", fake)
    result = execu.execute_rebalance_cls({"SPY": 0.5, "GLD": 0.5}, dry_run=False)

    assert fake.canceled == ["GLD-1"]
    assert result["success"] is False
    assert len(result["failed_orders"]) == 1
    assert result["failed_orders"][0]["ticker"] == "GLD"
    assert result["failed_orders"][0]["status"] == "timeout"
    # The filled SPY leg is not dragged down with it.
    spy = next(o for o in result["orders"] if o["ticker"] == "SPY")
    assert spy["status"] == "filled"


def test_submit_error_recorded_and_flips_success() -> None:
    fake = FakeClient(
        accounts=[make_account(100_000, 100_000)],
        positions=[{}],
        latest_trades={"SPY": 500.0},
        submit_responses={"SPY": [{"error": "http 422: asset not fractionable"}]},
    )
    execu = AuctionExecutor("TEST", fake)
    result = execu.execute_rebalance_cls({"SPY": 1.0}, dry_run=False)

    assert result["success"] is False
    assert len(result["submit_errors"]) == 1
    assert result["submit_errors"][0]["ticker"] == "SPY"


# ---- result-dict shape parity ----------------------------------------------------

def test_result_shape_matches_strategy_executor() -> None:
    """run_rebalance consumes orders/submit_errors/failed_orders/success —
    the auction path must expose the same keys."""
    fake = FakeClient(
        accounts=[make_account(100_000, 100_000)],
        positions=[{}],
        latest_trades={"SPY": 500.0},
    )
    execu = AuctionExecutor("TEST", fake)
    result = execu.execute_rebalance_cls({"SPY": 1.0}, dry_run=True)
    for key in ("strategy", "dry_run", "target_weights", "orders",
                "submit_errors", "failed_orders", "success",
                "equity", "cash", "current_weights", "deltas"):
        assert key in result, f"missing key: {key}"


# ---- client-level whole-share validation (no network: rejected pre-wire) ---------

def test_submit_order_qty_rejects_fractional_and_bad_auction_combos() -> None:
    client = AlpacaPaperClient("k", "s")
    assert "error" in client.submit_order_qty("SPY", 1.5, "buy")
    assert "error" in client.submit_order_qty("SPY", 0, "buy")
    assert "error" in client.submit_order_qty("SPY", -3, "sell")
    # Auction TIFs are market/limit only.
    err = client.submit_order_qty("SPY", 10, "buy", order_type="stop",
                                  time_in_force="cls")
    assert "error" in err and "market or limit" in err["error"]
    # Limit orders need a price.
    assert "error" in client.submit_order_qty("SPY", 10, "buy",
                                              order_type="limit",
                                              time_in_force="opg")
    # (Accepting an integral-float qty like 10.0 would pass validation and
    # hit the network, so only rejection cases are asserted here; integer
    # qty round-trips are covered by the executor tests above.)


def test_data_url_is_separate_from_trading_base() -> None:
    """get_latest_trade must target the data host, not the trading API."""
    client = AlpacaPaperClient("k", "s")
    assert client.data_url == "https://data.alpaca.markets"
    assert client.base_url != client.data_url
