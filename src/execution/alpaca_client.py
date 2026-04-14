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
DEFAULT_TIMEOUT = 15  # seconds


class AlpacaPaperClient:
    def __init__(self, api_key: str, secret_key: str, base_url: str = PAPER_BASE):
        self.base_url = base_url.rstrip("/")
        self._headers = {
            "APCA-API-KEY-ID": api_key or "",
            "APCA-API-SECRET-KEY": secret_key or "",
            "Content-Type": "application/json",
        }
        self._session = requests.Session()

    # ---- low-level ---------------------------------------------------------

    def _request(self, method: str, path: str, **kwargs) -> Any:
        url = f"{self.base_url}{path}"
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
        return last or {"error": "timeout waiting for fill"}

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
