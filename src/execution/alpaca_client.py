"""Thin Alpaca paper-trading REST client.

One instance == one paper account. All public methods return dicts and
swallow errors as ``{"error": str}`` so calling code never has to wrap
network failures in try/except.
"""
from __future__ import annotations

import logging
import time
from typing import Any

import requests

log = logging.getLogger(__name__)

PAPER_BASE = "https://paper-api.alpaca.markets"
LIVE_BASE  = "https://api.alpaca.markets"
# Market data lives on a SEPARATE host from the trading API: ``base_url``
# (paper or live) serves accounts/orders/positions only, while quotes and
# trades come from data.alpaca.markets regardless of paper/live.
DATA_BASE = "https://data.alpaca.markets"
DEFAULT_TIMEOUT = 15  # seconds

# TIFs whose orders must be whole-share qty (Alpaca rejects notional /
# fractional qty outside 'day'): the closing auction ('cls', submit cutoff
# 15:50 ET) and the opening auction ('opg', cutoff 09:28 ET).
AUCTION_TIFS = ("cls", "opg")


class AlpacaPaperClient:
    def __init__(self, api_key: str, secret_key: str, base_url: str = PAPER_BASE,
                 data_url: str = DATA_BASE):
        self.base_url = base_url.rstrip("/")
        self.data_url = data_url.rstrip("/")
        self._headers = {
            "APCA-API-KEY-ID": api_key or "",
            "APCA-API-SECRET-KEY": secret_key or "",
            "Content-Type": "application/json",
        }
        self._session = requests.Session()

    # ---- low-level ---------------------------------------------------------

    def _request(self, method: str, path: str, base: str | None = None, **kwargs) -> Any:
        url = f"{base or self.base_url}{path}"
        for attempt in range(3):
            try:
                resp = self._session.request(
                    method, url, headers=self._headers, timeout=DEFAULT_TIMEOUT, **kwargs
                )
            except requests.RequestException as exc:
                if attempt == 2:
                    return {"error": f"network: {exc}"}
                time.sleep(0.5 * (attempt + 1))
                continue
            if resp.status_code == 429:
                time.sleep(1.0 * (attempt + 1))
                continue
            if resp.status_code >= 400:
                try:
                    body = resp.json()
                    msg = body.get("message") or body
                except ValueError:
                    msg = resp.text
                return {"error": f"http {resp.status_code}: {msg}"}
            try:
                return resp.json()
            except ValueError:
                return {"error": "non-json response"}
        return {"error": "exhausted retries"}

    # ---- account / market --------------------------------------------------

    def get_account(self) -> dict:
        data = self._request("GET", "/v2/account")
        if "error" in data:
            return data
        try:
            return {
                "equity": float(data["equity"]),
                "cash": float(data["cash"]),
                "buying_power": float(data["buying_power"]),
                "status": data.get("status"),
                "raw": data,
            }
        except (KeyError, TypeError, ValueError) as exc:
            return {"error": f"parse: {exc}"}

    def get_positions(self) -> dict:
        data = self._request("GET", "/v2/positions")
        if isinstance(data, dict) and "error" in data:
            return data
        out: dict[str, dict] = {}
        for p in data:
            try:
                out[p["symbol"]] = {
                    "qty": float(p["qty"]),
                    "market_value": float(p["market_value"]),
                    "avg_entry": float(p["avg_entry_price"]),
                    "pnl": float(p["unrealized_pl"]),
                }
            except (KeyError, TypeError, ValueError):
                continue
        return out

    def get_clock(self) -> dict:
        return self._request("GET", "/v2/clock")

    def get_latest_trade(self, ticker: str) -> dict:
        """Latest trade for ``ticker`` from the market-data API.

        Hits ``GET {data_url}/v2/stocks/{ticker}/trades/latest`` — note this
        is the separate data host (``DATA_BASE``), NOT ``base_url`` (the
        trading API). Returns ``{"symbol", "price", "size", "timestamp",
        "raw"}`` or ``{"error": ...}``.
        """
        data = self._request(
            "GET", f"/v2/stocks/{ticker}/trades/latest", base=self.data_url
        )
        if not isinstance(data, dict):
            return {"error": f"unexpected response type: {type(data).__name__}"}
        if "error" in data:
            return data
        try:
            trade = data["trade"]
            price = float(trade["p"])
        except (KeyError, TypeError, ValueError) as exc:
            return {"error": f"parse: {exc}"}
        if price <= 0:
            return {"error": f"non-positive latest trade price for {ticker}: {price}"}
        return {
            "symbol": data.get("symbol", ticker),
            "price": price,
            "size": trade.get("s"),
            "timestamp": trade.get("t"),
            "raw": data,
        }

    def get_portfolio_history(self, period: str = "1M", timeframe: str = "1D") -> dict:
        data = self._request(
            "GET", "/v2/account/portfolio/history",
            params={"period": period, "timeframe": timeframe, "extended_hours": "false"},
        )
        if isinstance(data, dict) and "error" in data:
            return data
        ts   = data.get("timestamp") or []
        eqs  = data.get("equity") or []
        pnl  = data.get("profit_loss") or []
        base = data.get("base_value")
        from datetime import datetime, timezone
        points = []
        for i, t in enumerate(ts):
            if i >= len(eqs) or eqs[i] is None:
                continue
            points.append({
                "date":  datetime.fromtimestamp(t, tz=timezone.utc).strftime("%Y-%m-%d"),
                "equity": float(eqs[i]),
                "pnl":    float(pnl[i]) if i < len(pnl) and pnl[i] is not None else 0.0,
            })
        return {"base_value": base, "points": points}

    def list_orders(self, status: str = "all", limit: int = 100) -> list:
        data = self._request(
            "GET", "/v2/orders",
            params={"status": status, "limit": limit, "direction": "desc"},
        )
        if isinstance(data, dict) and "error" in data:
            return [data]
        out = []
        for o in data or []:
            out.append({
                "id":         o.get("id"),
                "symbol":     o.get("symbol"),
                "side":       o.get("side"),
                "qty":        o.get("qty"),
                "notional":   o.get("notional"),
                "status":     o.get("status"),
                "submitted":  o.get("submitted_at"),
                "filled_at":  o.get("filled_at"),
                "filled_avg": o.get("filled_avg_price"),
            })
        return out

    # ---- orders ------------------------------------------------------------

    def submit_order(
        self,
        ticker: str,
        notional: float,
        side: str,
        order_type: str = "market",
        time_in_force: str = "day",
    ) -> dict:
        if notional <= 0:
            return {"error": "notional must be > 0"}
        body = {
            "symbol": ticker,
            "notional": round(float(notional), 2),
            "side": side,
            "type": order_type,
            "time_in_force": time_in_force,
        }
        data = self._request("POST", "/v2/orders", json=body)
        if "error" in data:
            return data
        return {
            "id": data.get("id"),
            "status": data.get("status"),
            "symbol": data.get("symbol"),
            "side": data.get("side"),
            "notional": data.get("notional"),
            "raw": data,
        }

    def submit_order_qty(
        self,
        ticker: str,
        qty: int,
        side: str,
        order_type: str = "market",
        time_in_force: str = "day",
        limit_price: float | None = None,
    ) -> dict:
        """Submit a WHOLE-SHARE ``qty`` order (required for auction TIFs).

        Alpaca constraints (docs, verified 2026-07): ``cls`` (closing
        auction, submit cutoff 15:50 ET) and ``opg`` (opening auction,
        cutoff 09:28 ET) accept market/limit only and whole-share qty only —
        notional / fractional orders are ``day`` TIF only, which is why the
        existing :meth:`submit_order` (notional) cannot serve auction
        execution. ``qty`` is sent as a string per the API.
        """
        try:
            qty_int = int(qty)
        except (TypeError, ValueError):
            return {"error": f"qty must be a whole number of shares, got {qty!r}"}
        if float(qty_int) != float(qty):
            return {"error": f"qty must be a whole number of shares, got {qty!r}"}
        if qty_int <= 0:
            return {"error": "qty must be > 0"}
        if time_in_force in AUCTION_TIFS and order_type not in ("market", "limit"):
            return {"error": f"'{time_in_force}' orders must be market or limit, "
                             f"got '{order_type}'"}
        if order_type == "limit" and limit_price is None:
            return {"error": "limit orders require limit_price"}
        body: dict[str, Any] = {
            "symbol": ticker,
            "qty": str(qty_int),
            "side": side,
            "type": order_type,
            "time_in_force": time_in_force,
        }
        if limit_price is not None:
            body["limit_price"] = str(limit_price)
        data = self._request("POST", "/v2/orders", json=body)
        if "error" in data:
            return data
        return {
            "id": data.get("id"),
            "status": data.get("status"),
            "symbol": data.get("symbol"),
            "side": data.get("side"),
            "qty": data.get("qty"),
            "time_in_force": data.get("time_in_force"),
            "raw": data,
        }

    def get_order_status(self, order_id: str) -> dict:
        data = self._request("GET", f"/v2/orders/{order_id}")
        if "error" in data:
            return data
        return {
            "id": data.get("id"),
            "status": data.get("status"),
            "filled_qty": data.get("filled_qty"),
            "filled_avg_price": data.get("filled_avg_price"),
            "raw": data,
        }

    def cancel_order(self, order_id: str) -> dict:
        data = self._request("DELETE", f"/v2/orders/{order_id}")
        # Alpaca returns 204 No Content on successful cancel, which the
        # generic JSON decode reports as "non-json response".
        if isinstance(data, dict) and data.get("error") == "non-json response":
            return {"id": order_id, "status": "canceled"}
        if isinstance(data, dict) and "error" in data:
            return data
        return {"id": order_id, "status": "canceled", "raw": data}

    def wait_for_fill(self, order_id: str, timeout_s: float = 60.0, poll: float = 1.0) -> dict:
        deadline = time.time() + timeout_s
        last: dict = {}
        while time.time() < deadline:
            last = self.get_order_status(order_id)
            if "error" in last:
                return last
            if last.get("status") in ("filled", "canceled", "rejected", "expired"):
                return last
            time.sleep(poll)
        # Deadline lapsed without reaching a terminal state: flag the timeout
        # so callers can cancel, while still returning the last known status.
        last = dict(last) if last else {"error": "timeout waiting for fill"}
        last["timeout"] = True
        return last

    def wait_for_market_open(self, poll: float = 30.0,
                             max_wait_s: float = 20 * 3600.0) -> dict:
        """Block until NYSE is open. Returns the final clock response.

        ``max_wait_s`` bounds the wait (default 20h — covers the scheduled
        04:15-Stockholm start through the 15:30 open with margin). Without a
        deadline, a persistent clock/network outage would hold the process
        (and the rebalance instance lock) forever.
        """
        from datetime import datetime, timezone
        deadline = time.time() + max_wait_s

        clock = self.get_clock()
        if "error" in clock:
            return clock
        if clock.get("is_open"):
            return clock

        next_open = clock.get("next_open", "unknown")
        log.info("Market closed — waiting for open at %s", next_open)

        while True:
            if time.time() >= deadline:
                return {"error": f"market did not open within {max_wait_s/3600:.0f}h"}
            try:
                open_str = str(clock.get("next_open", ""))
                open_dt = datetime.fromisoformat(open_str.replace("Z", "+00:00"))
                now = datetime.now(timezone.utc)
                remaining = (open_dt - now).total_seconds()
                if remaining > 60:
                    log.info("Market opens in %.1f hours — sleeping",
                             remaining / 3600)
                until_deadline = max(1.0, deadline - time.time())
                if remaining > poll * 2:
                    time.sleep(min(remaining - poll, until_deadline))
                else:
                    time.sleep(max(1.0, min(poll, remaining, until_deadline)))
            except (ValueError, TypeError):
                time.sleep(poll)

            clock = self.get_clock()
            if "error" in clock:
                log.warning("Clock check failed: %s — retrying", clock["error"])
                time.sleep(poll)
                continue
            if clock.get("is_open"):
                log.info("Market is now open")
                return clock

    def close_position(self, ticker: str) -> dict:
        data = self._request("DELETE", f"/v2/positions/{ticker}")
        if isinstance(data, dict) and "error" in data:
            return data
        return {"status": "submitted", "symbol": ticker, "raw": data}

    def close_all_positions(self) -> list:
        data = self._request("DELETE", "/v2/positions")
        if isinstance(data, dict) and "error" in data:
            return [data]
        if isinstance(data, list):
            return data
        return [{"raw": data}]
