"""Per-strategy rebalance executor (one Alpaca paper account)."""
from __future__ import annotations

import logging
from typing import Any

from execution.alpaca_client import AlpacaPaperClient

log = logging.getLogger(__name__)

NOISE_FRACTION = 0.01            # ignore deltas < 1% of equity
MAX_SINGLE_ORDER_FRACTION = 1.00  # sanity cap — no single order > 100% of equity
ORDER_WARN_FRACTION = 0.40        # warn (don't block) above 40%
RECONCILE_TOLERANCE = 0.02        # flag deviations > 2%
WEIGHT_SUM_TOLERANCE = 0.005      # weights must sum to 1 ± 0.5%
DEFAULT_INITIAL_CAPITAL = 100_000.0


class StrategyExecutor:
    def __init__(
        self,
        strategy_name: str,
        client: AlpacaPaperClient,
        initial_capital: float = DEFAULT_INITIAL_CAPITAL,
    ):
        self.name = strategy_name
        self.client = client
        self.initial_capital = float(initial_capital)

    # ---- helpers -----------------------------------------------------------

    def _current_weights(self, equity: float, positions: dict) -> dict[str, float]:
        if equity <= 0:
            return {}
        return {t: p["market_value"] / equity for t, p in positions.items()}

    def _validate_targets(self, targets: dict) -> str | None:
        total = sum(targets.values())
        if abs(total - 1.0) > WEIGHT_SUM_TOLERANCE:
            return f"target weights sum to {total:.4f}, not 1.0"
        for t, w in targets.items():
            if w < -1e-9:
                return f"negative weight for {t}: {w}"
            if w > MAX_SINGLE_ORDER_FRACTION + 1e-9 and w > 0.0:
                # a single position above 40% is allowed (e.g. OPTIMIZED top1=0.89);
                # what's capped is per-order notional, computed below.
                pass
        return None

    # ---- main --------------------------------------------------------------

    def execute_rebalance(self, target_weights: dict, dry_run: bool = True) -> dict:
        result: dict[str, Any] = {
            "strategy": self.name,
            "dry_run": dry_run,
            "target_weights": dict(target_weights),
            "orders": [],
            "submit_errors": [],
            "success": False,
        }

        err = self._validate_targets(target_weights)
        if err:
            result["error"] = err
            return result

        account = self.client.get_account()
        if "error" in account:
            result["error"] = f"get_account: {account['error']}"
            return result
        equity = account["equity"]
        buying_power = account["buying_power"]
        result["equity"] = equity
        result["cash"] = account["cash"]

        positions = self.client.get_positions()
        if isinstance(positions, dict) and "error" in positions:
            result["error"] = f"get_positions: {positions['error']}"
            return result
        result["current_weights"] = self._current_weights(equity, positions)

        # Compute deltas
        tickers = set(target_weights) | set(result["current_weights"])
        deltas: dict[str, float] = {}
        for t in tickers:
            d = target_weights.get(t, 0.0) - result["current_weights"].get(t, 0.0)
            if abs(d) >= NOISE_FRACTION:
                deltas[t] = d
        result["deltas"] = deltas

        # Per-order sanity cap + soft warnings
        warnings_list = []
        for t, d in deltas.items():
            if abs(d) > MAX_SINGLE_ORDER_FRACTION:
                result["error"] = (
                    f"order for {t} is {d*100:.1f}% of equity, exceeds "
                    f"{MAX_SINGLE_ORDER_FRACTION*100:.0f}% sanity cap"
                )
                return result
            if abs(d) > ORDER_WARN_FRACTION:
                warnings_list.append(f"{t} order is {abs(d)*100:.1f}% of equity")
        if warnings_list:
            result["warnings"] = warnings_list

        # 1% buying-power headroom: leaves a small cash buffer so the sum of
        # notional orders can't exceed BP due to rounding/fractional shares.
        usable_equity = equity * 0.99

        # Build order plan: sells first, then buys (smallest buys first so the
        # small diversifying legs submit while BP is still full — a large buy
        # submitted first can exhaust BP before small legs reach the wire).
        sells = [(t, d) for t, d in deltas.items() if d < 0]
        buys = [(t, d) for t, d in deltas.items() if d > 0]
        sells.sort(key=lambda x: x[1])           # most negative first
        buys.sort(key=lambda x: x[1])            # smallest buy first

        plan = []
        for t, d in sells:
            plan.append({
                "ticker": t, "side": "sell",
                "notional": round(abs(d) * usable_equity, 2),
            })
        for t, d in buys:
            plan.append({
                "ticker": t, "side": "buy",
                "notional": round(abs(d) * usable_equity, 2),
            })

        # Buying-power pre-check
        total_buys = sum(o["notional"] for o in plan if o["side"] == "buy")
        # NOTE: sells free up cash but Alpaca's notional model handles intraday
        # settlement, so we only fail hard if buys exceed BP+sell proceeds.
        total_sells = sum(o["notional"] for o in plan if o["side"] == "sell")
        if total_buys > buying_power + total_sells + 1.0:
            result["error"] = (
                f"insufficient buying power: need ${total_buys:.0f}, "
                f"have BP=${buying_power:.0f} + sells=${total_sells:.0f}"
            )
            return result

        result["orders"] = plan

        if dry_run:
            result["success"] = True
            return result

        # ---- live submission ----
        # Sells first, await fills, then buys.
        sell_orders = [o for o in plan if o["side"] == "sell"]
        buy_orders = [o for o in plan if o["side"] == "buy"]
        for batch in (sell_orders, buy_orders):
            ids = []
            for o in batch:
                resp = self.client.submit_order(o["ticker"], o["notional"], o["side"])
                o["submit"] = resp
                if "error" in resp:
                    o["status"] = "error"
                    result["submit_errors"].append({
                        "ticker": o["ticker"],
                        "side": o["side"],
                        "notional": o["notional"],
                        "error_message": resp.get("error"),
                    })
                    continue
                o["id"] = resp.get("id")
                ids.append((o, resp.get("id")))
            for o, oid in ids:
                if not oid:
                    continue
                final = self.client.wait_for_fill(oid, timeout_s=120)
                o["status"] = final.get("status", "unknown")
                o["filled_qty"] = final.get("filled_qty")
                o["filled_avg_price"] = final.get("filled_avg_price")

        # Reconcile
        post_account = self.client.get_account()
        post_positions = self.client.get_positions()
        if "error" not in post_account and not (isinstance(post_positions, dict) and "error" in post_positions):
            post_equity = post_account["equity"]
            post_w = self._current_weights(post_equity, post_positions)
            result["post_rebalance_weights"] = post_w
            result["post_rebalance_equity"] = post_equity
            max_dev = 0.0
            for t in set(target_weights) | set(post_w):
                dev = abs(target_weights.get(t, 0.0) - post_w.get(t, 0.0))
                if dev > max_dev:
                    max_dev = dev
            result["max_deviation"] = max_dev
            result["reconciled"] = max_dev <= RECONCILE_TOLERANCE
        else:
            result["reconciled"] = False

        # Slippage estimate (bps): equity drift relative to start
        if "post_rebalance_equity" in result:
            drift = (result["post_rebalance_equity"] - equity) / equity
            result["slippage_bps"] = round(drift * 1e4, 2)

        result["success"] = all(
            o.get("status") in ("filled", None) for o in plan
        )
        return result

    def get_status(self) -> dict:
        account = self.client.get_account()
        if "error" in account:
            return {"strategy": self.name, "error": account["error"]}
        positions = self.client.get_positions()
        if isinstance(positions, dict) and "error" in positions:
            return {"strategy": self.name, "error": positions["error"]}
        equity = account["equity"]
        return {
            "strategy": self.name,
            "equity": equity,
            "cash": account["cash"],
            "positions": positions,
            "weights": self._current_weights(equity, positions),
            "total_pnl": equity - self.initial_capital,
            "return_pct": (equity - self.initial_capital) / self.initial_capital
            if self.initial_capital > 0 else 0.0,
        }

    def kill_all(self) -> dict:
        closed = self.client.close_all_positions()
        return {"strategy": self.name, "closed": closed}
