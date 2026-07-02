"""Spec tests: StrategyExecutor live-path order flow (fresh snapshot sizing,
sell-then-buy phasing, buying-power retry, timeouts, residual closes)."""
from __future__ import annotations

import pytest

from execution.executor import (
    BUY_CASH_HEADROOM,
    PLAN_EQUITY_HEADROOM,
    StrategyExecutor,
)


# ---- fake client -----------------------------------------------------------

class FakeClient:
    """Scriptable in-memory stand-in for AlpacaPaperClient.

    ``accounts`` / ``positions`` are consumed as queues (one entry per call,
    last entry repeats) so tests can script different snapshots for the
    pre-wait fetch, the post-open re-fetch, the post-sell re-fetch, etc.
    All fills resolve immediately — no sleeps, no network.
    """

    def __init__(
        self,
        accounts: list[dict],
        positions: list[dict],
        submit_responses: dict[str, list[dict]] | None = None,
        fill_responses: dict[str, dict] | None = None,
        clock: dict | None = None,
    ):
        self._accounts = list(accounts)
        self._positions = list(positions)
        self.submit_responses = submit_responses or {}   # ticker -> queued responses
        self.fill_responses = fill_responses or {}       # order_id -> final status
        self.clock = clock or {"is_open": True}
        self.submitted: list[dict] = []
        self.canceled: list[str] = []
        self.closed: list[str] = []
        self.wait_calls: list[tuple[str, float]] = []
        self.market_open_calls = 0
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

    def wait_for_market_open(self, poll: float = 30.0) -> dict:
        self.market_open_calls += 1
        return dict(self.clock)

    def submit_order(self, ticker: str, notional: float, side: str, **kwargs) -> dict:
        self.submitted.append({"ticker": ticker, "notional": notional, "side": side})
        queue = self.submit_responses.get(ticker)
        if queue:
            return dict(queue.pop(0))
        n = self._seq.get(ticker, 0) + 1
        self._seq[ticker] = n
        oid = f"{ticker}-{n}"
        return {"id": oid, "status": "accepted", "symbol": ticker,
                "side": side, "notional": notional}

    def get_order_status(self, order_id: str) -> dict:
        return self.wait_for_fill(order_id)

    def wait_for_fill(self, order_id: str, timeout_s: float = 60.0,
                      poll: float = 1.0) -> dict:
        self.wait_calls.append((order_id, timeout_s))
        default = {"id": order_id, "status": "filled",
                   "filled_qty": "10", "filled_avg_price": "100.0"}
        return dict(self.fill_responses.get(order_id, default))

    def cancel_order(self, order_id: str) -> dict:
        self.canceled.append(order_id)
        return {"id": order_id, "status": "canceled"}

    def close_position(self, ticker: str) -> dict:
        self.closed.append(ticker)
        return {"status": "submitted", "symbol": ticker,
                "raw": {"id": f"close-{ticker}"}}

    def close_all_positions(self) -> list:
        return []


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


# ---- tests -----------------------------------------------------------------

def test_buys_sized_from_post_sell_cash_not_stale_snapshot() -> None:
    """The plan is rebuilt after market open; buys use post-sell cash.

    Pre-wait snapshot says equity=$200k (11h stale); by open the account is
    only $100k. Orders must be sized from the fresh snapshot, and the buy
    from actual post-sell cash — never from the stale plan.
    """
    fake = FakeClient(
        accounts=[
            make_account(200_000, 0.0, 200_000),   # pre-wait (stale)
            make_account(100_000, 0.0, 100_000),   # post-open re-fetch
            make_account(100_000, 99_000, 99_000),  # post-sell (buys sized here)
            make_account(100_000, 505.0, 505.0),    # reconcile
        ],
        positions=[
            {"TLT": make_position(200_000, qty=500)},  # pre-wait (stale)
            {"TLT": make_position(100_000, qty=250)},  # post-open re-fetch
            {},                                        # residual check: TLT gone
            {"SPY": make_position(100_000)},           # reconcile
        ],
    )
    execu = StrategyExecutor("TEST", fake)
    result = execu.execute_rebalance({"SPY": 1.0}, dry_run=False)

    sells = [s for s in fake.submitted if s["side"] == "sell"]
    buys = [s for s in fake.submitted if s["side"] == "buy"]
    # Sell sized from the FRESH $100k snapshot (stale plan would say ~$198k).
    assert sells == [
        {"ticker": "TLT",
         "notional": round(100_000 * PLAN_EQUITY_HEADROOM, 2),
         "side": "sell"}
    ]
    # Buy sized from post-sell cash * BUY_CASH_HEADROOM, never the stale plan.
    # The residual sweep then tops the (single) buy leg up to exactly that cap.
    assert buys == [
        {"ticker": "SPY",
         "notional": round(99_000 * BUY_CASH_HEADROOM, 2),
         "side": "buy"}
    ]
    assert result["equity"] == 100_000  # result reflects the fresh snapshot
    assert result["success"] is True
    assert result["failed_orders"] == []


def test_insufficient_buying_power_403_retries_exactly_once() -> None:
    """A 403 'insufficient buying power' rescales that order to
    remaining_cash * 0.98 and retries exactly once."""
    fake = FakeClient(
        accounts=[
            make_account(100_000, 100_000),  # pre-wait
            make_account(100_000, 100_000),  # post-open re-fetch
            make_account(100_000, 100_000),  # post-sell (buy sizing)
            make_account(100_000, 40_000),   # re-fetch after 403
            make_account(100_000, 0.0),      # reconcile
        ],
        positions=[
            {},  # pre-wait
            {},  # post-open
            {"SPY": make_position(60_000), "QQQ": make_position(40_000)},  # reconcile
        ],
        submit_responses={
            "SPY": [{"error": "http 403: insufficient buying power"}],
        },
    )
    execu = StrategyExecutor("TEST", fake)
    result = execu.execute_rebalance({"SPY": 0.6, "QQQ": 0.4}, dry_run=False)

    spy_submits = [s for s in fake.submitted if s["ticker"] == "SPY"]
    assert len(spy_submits) == 2  # original + exactly one retry
    # Original: 0.6 * 100k * plan headroom (+$100 residual sweep into the
    # largest leg: available 99_900 - planned 99_800).
    assert spy_submits[0]["notional"] == pytest.approx(
        0.6 * 100_000 * PLAN_EQUITY_HEADROOM + 100.0
    )
    # Retry: capped at min(original, remaining 40k * 0.98) = 39_200.
    assert spy_submits[1]["notional"] == pytest.approx(39_200.0)
    assert result["submit_errors"] == []  # resolved by the retry
    assert result["success"] is True
    spy_order = next(o for o in result["orders"] if o["ticker"] == "SPY")
    assert spy_order["retried"] is True
    assert spy_order["status"] == "filled"


def test_residual_close_does_not_flip_success() -> None:
    """Orders appended by the residual-close pass carry status
    'residual_close' and count as success — not as failures."""
    fake = FakeClient(
        accounts=[
            make_account(100_000, 0.0, 100_000),    # pre-wait
            make_account(100_000, 0.0, 100_000),    # post-open re-fetch
            make_account(100_000, 99_000, 99_000),  # post-sell
            make_account(100_000, 0.0),             # reconcile
        ],
        positions=[
            {"TLT": make_position(100_000, qty=250)},  # pre-wait
            {"TLT": make_position(100_000, qty=250)},  # post-open
            {"TLT": make_position(50.0, qty=0.5)},     # residual left after sell
            {"SPY": make_position(100_000)},           # reconcile
        ],
    )
    execu = StrategyExecutor("TEST", fake)
    result = execu.execute_rebalance({"SPY": 1.0}, dry_run=False)

    assert fake.closed == ["TLT"]
    residuals = [o for o in result["orders"] if o.get("status") == "residual_close"]
    assert len(residuals) == 1
    assert residuals[0]["ticker"] == "TLT"
    assert residuals[0]["side"] == "sell"
    assert result["failed_orders"] == []
    assert result["success"] is True
    assert result["reconciled"] is True


def test_order_stuck_new_is_canceled_and_fails_run() -> None:
    """An order that never reaches a terminal state gets canceled, is marked
    status='timeout' and flips success=False via failed_orders."""
    fake = FakeClient(
        accounts=[make_account(100_000, 100_000)],
        positions=[{}],
        fill_responses={
            "SPY-1": {"id": "SPY-1", "status": "new", "timeout": True},
        },
    )
    execu = StrategyExecutor("TEST", fake)
    result = execu.execute_rebalance({"SPY": 1.0}, dry_run=False)

    assert fake.canceled == ["SPY-1"]
    assert result["success"] is False
    assert len(result["failed_orders"]) == 1
    assert result["failed_orders"][0]["ticker"] == "SPY"
    assert result["failed_orders"][0]["status"] == "timeout"


def test_buys_scaled_proportionally_when_cash_short() -> None:
    """When planned buys exceed post-sell cash * headroom every buy notional
    is scaled by the same factor."""
    fake = FakeClient(
        accounts=[
            make_account(100_000, 100_000),  # pre-wait
            make_account(100_000, 100_000),  # post-open re-fetch
            make_account(100_000, 50_000),   # post-sell: only 50k cash
            make_account(100_000, 0.0),      # reconcile
        ],
        positions=[{}, {}, {}],
    )
    execu = StrategyExecutor("TEST", fake)
    result = execu.execute_rebalance({"SPY": 0.6, "QQQ": 0.4}, dry_run=False)

    available = 50_000 * BUY_CASH_HEADROOM
    planned = 100_000 * PLAN_EQUITY_HEADROOM
    buys = {s["ticker"]: s["notional"] for s in fake.submitted if s["side"] == "buy"}
    assert buys["SPY"] == pytest.approx(0.6 * available, abs=0.02)
    assert buys["QQQ"] == pytest.approx(0.4 * available, abs=0.02)
    assert sum(buys.values()) == pytest.approx(available, abs=0.05)
    assert buys["SPY"] / buys["QQQ"] == pytest.approx(1.5)  # proportions kept
    assert result["buy_scale_factor"] == pytest.approx(available / planned, abs=1e-4)


def test_residual_cash_swept_into_largest_buy() -> None:
    """Cash the plan doesn't spend gets swept into the LARGEST buy leg
    instead of sitting idle (study6 cash-drag droplet)."""
    fake = FakeClient(
        accounts=[
            make_account(100_000, 100_000),  # pre-wait
            make_account(100_000, 100_000),  # post-open re-fetch
            make_account(100_000, 101_000),  # post-sell: extra cash appeared
            make_account(100_000, 0.0),      # reconcile
        ],
        positions=[{}, {}, {}],
    )
    execu = StrategyExecutor("TEST", fake)
    result = execu.execute_rebalance({"SPY": 0.6, "QQQ": 0.4}, dry_run=False)

    available = round(101_000 * BUY_CASH_HEADROOM, 2)
    buys = {s["ticker"]: s["notional"] for s in fake.submitted if s["side"] == "buy"}
    # Every available dollar deployed; the residual went to SPY (largest leg).
    assert sum(buys.values()) == pytest.approx(available, abs=0.02)
    assert result["swept_residual"] > 0
    assert buys["SPY"] > 0.6 * 100_000 * PLAN_EQUITY_HEADROOM
    assert buys["QQQ"] == pytest.approx(0.4 * 100_000 * PLAN_EQUITY_HEADROOM, abs=0.02)


def test_new_position_exempt_from_noise_gate() -> None:
    """A sub-1% target on an UNHELD ticker must still be opened — the noise
    gate only applies to adjustments of existing positions (study6 found S7
    holding 2.9% permanent idle cash from silently-skipped sub-1% legs)."""
    fake = FakeClient(
        accounts=[make_account(100_000, 100_000)],
        positions=[{}],
    )
    execu = StrategyExecutor("TEST", fake)
    result = execu.execute_rebalance(
        {"XLE": 0.98, "SOXX": 0.012, "GLD": 0.008}, dry_run=True
    )

    planned = {o["ticker"] for o in result["orders"]}
    assert planned == {"XLE", "SOXX", "GLD"}  # GLD 0.8% new leg NOT dropped


def test_sub_dollar_buy_dropped_not_failed() -> None:
    """Buys scaled below $1 are dropped from the plan (not submitted, and not
    counted as failures)."""
    fake = FakeClient(
        accounts=[
            make_account(100_000, 100_000),  # pre-wait
            make_account(100_000, 100_000),  # post-open re-fetch
            make_account(100_000, 50.0),     # post-sell: almost no cash
            make_account(100_000, 0.0),      # reconcile
        ],
        positions=[{}, {}, {}],
    )
    execu = StrategyExecutor("TEST", fake)
    result = execu.execute_rebalance({"SPY": 0.99, "IEF": 0.01}, dry_run=False)

    buy_tickers = [s["ticker"] for s in fake.submitted if s["side"] == "buy"]
    assert buy_tickers == ["SPY"]  # IEF scaled to ~$0.50 and dropped
    assert [d["ticker"] for d in result["dropped_orders"]] == ["IEF"]
    assert all(o["ticker"] != "IEF" for o in result["orders"])
    assert result["failed_orders"] == []
    assert result["success"] is True


def test_dry_run_single_shot_plan_no_orders() -> None:
    """Dry run keeps the immediate single-shot plan: no market wait, no
    submissions."""
    fake = FakeClient(
        accounts=[make_account(100_000, 0.0, 100_000)],
        positions=[{"TLT": make_position(100_000, qty=250)}],
    )
    execu = StrategyExecutor("TEST", fake)
    result = execu.execute_rebalance({"SPY": 1.0}, dry_run=True)

    assert result["success"] is True
    assert fake.submitted == []
    assert fake.market_open_calls == 0
    sides = [(o["ticker"], o["side"]) for o in result["orders"]]
    assert sides == [("TLT", "sell"), ("SPY", "buy")]


def test_public_reconcile_reports_deviations() -> None:
    """reconcile() is usable standalone (e.g. by the health check)."""
    fake = FakeClient(
        accounts=[make_account(100_000, 5_000)],
        positions=[{"SPY": make_position(95_000)}],
    )
    execu = StrategyExecutor("TEST", fake)
    recon = execu.reconcile({"SPY": 1.0})

    assert recon["max_deviation"] == pytest.approx(0.05)
    assert recon["deviations"]["SPY"] == pytest.approx(0.05)
    assert recon["reconciled"] is False  # 5% > 2% tolerance

    recon_ok = execu.reconcile({"SPY": 0.95})
    assert recon_ok["reconciled"] is True
