"""Closing-auction (``cls``) rebalance executor — DORMANT alternative path.

STATUS: NOT WIRED. No production caller constructs an :class:`AuctionExecutor`;
``run_rebalance`` keeps using ``StrategyExecutor`` (src/execution/executor.py,
which this module deliberately does NOT touch) until a future explicit config
opt-in adopts this path. Evidence gate: research/droplets/study15_cls_flip —
the pre-registered viability bar (top-3 set identical >= 90% of month-ends AND
gate flips <= 2%) FAILED on the daily-data upper bound (72.5% / 3.1%), so
enabling this additionally requires a live 15:45-vs-close shadow study first.

Semantics vs StrategyExecutor
-----------------------------
- Decide pre-close, fill AT the decision-day closing auction: orders are
  WHOLE-SHARE ``qty`` with ``time_in_force='cls'`` (Alpaca: auction TIFs
  reject notional/fractional; submission cutoff 15:50 ET; market/limit only).
- Share counts are FLOORED from latest trade prices, so residual cash
  implicitly stays in the account (there is no notional sweep here).
- BUYING-POWER CAVEAT (the reason for the hard pre-check): sells and buys
  are submitted together before the cutoff and all fill in the SAME closing
  auction, so sale proceeds are NOT available to fund the buys at submission
  time — Alpaca requires ``buying_power >= total buy notional`` UP FRONT.
  A 1x (cash-like) account fails this whenever the rebalance turns over more
  than its free cash; a 2x margin-multiplier account covers a full
  single-account rotation. ``execute_rebalance_cls`` pre-checks and REFUSES
  with a clear error rather than submitting a half-rebalance.
- Fractional share tails left by earlier notional (day-TIF) fills cannot be
  traded via ``cls``; sells are floored to whole shares and any fractional
  tail on a fully-exited ticker is reported in ``fractional_residuals``
  (an adopter can clean those up post-auction via ``close_position``).
- The result dict has the same load-bearing shape as
  ``StrategyExecutor.execute_rebalance`` (``orders`` / ``submit_errors`` /
  ``failed_orders`` / ``success`` plus equity/cash/current_weights/deltas)
  so ``run_rebalance`` could adopt it behind a config flag later.
"""
from __future__ import annotations

import logging
import math
from typing import Any

from execution.alpaca_client import AlpacaPaperClient

log = logging.getLogger(__name__)

NOISE_FRACTION = 0.01             # ignore deltas < 1% of equity (parity with executor)
WEIGHT_SUM_TOLERANCE = 0.005      # weights must sum to 1 ± 0.5%
PLAN_EQUITY_HEADROOM = 0.998      # sizing fraction of equity (parity with executor)
MAX_SINGLE_ORDER_FRACTION = 1.00  # sanity cap — no single order > 100% of equity
BP_EPSILON = 1.00                 # $1 slack on the buying-power pre-check
FILL_TIMEOUT_S = 30 * 60.0        # cls orders submitted ~15:45 fill at ~16:00 ET

# Statuses that count as a successfully completed plan entry. A cls order
# either fills in the auction or dies; there is no 'residual_close' here.
OK_STATUSES = ("filled",)


class AuctionExecutor:
    """Whole-share closing-auction rebalancer for one strategy/account."""

    def __init__(self, strategy_name: str, client: AlpacaPaperClient):
        self.name = strategy_name
        self.client = client

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
        return None

    def _fetch_snapshot(self) -> tuple[dict | None, dict | None, str | None]:
        account = self.client.get_account()
        if "error" in account:
            return None, None, f"get_account: {account['error']}"
        positions = self.client.get_positions()
        if isinstance(positions, dict) and "error" in positions:
            return account, None, f"get_positions: {positions['error']}"
        return account, positions, None

    def _latest_prices(self, tickers) -> tuple[dict[str, float], str | None]:
        prices: dict[str, float] = {}
        for t in sorted(tickers):
            trade = self.client.get_latest_trade(t)
            if "error" in trade:
                return prices, f"get_latest_trade({t}): {trade['error']}"
            prices[t] = float(trade["price"])
        return prices, None

    def _build_plan(
        self,
        target_weights: dict,
        account: dict,
        positions: dict,
        prices: dict[str, float],
    ) -> tuple[list[dict], dict[str, float], dict[str, float], dict[str, float], str | None]:
        """Whole-share order plan. Returns (plan, current_weights, deltas,
        fractional_residuals, error)."""
        equity = account["equity"]
        buying_power = account["buying_power"]
        current_weights = self._current_weights(equity, positions)
        usable = equity * PLAN_EQUITY_HEADROOM

        tickers = set(target_weights) | set(positions)
        deltas: dict[str, float] = {}
        share_deltas: dict[str, int] = {}
        fractional_residuals: dict[str, float] = {}
        for t in sorted(tickers):
            price = prices[t]
            tgt_w = target_weights.get(t, 0.0)
            target_shares = int(math.floor(tgt_w * usable / price))
            held = float(positions.get(t, {}).get("qty", 0.0))
            held_whole = int(math.floor(held))
            frac_tail = held - held_whole
            d_shares = target_shares - held_whole
            d_weight = tgt_w - current_weights.get(t, 0.0)

            # Noise gate (parity with StrategyExecutor): skip small
            # adjustments, but never skip opening a NEW position (study6) or
            # a full exit.
            is_new = held_whole == 0 and target_shares > 0
            is_exit = tgt_w < NOISE_FRACTION and held_whole > 0 and target_shares == 0
            if abs(d_weight) < NOISE_FRACTION and not (is_new or is_exit):
                d_shares = 0

            if tgt_w < NOISE_FRACTION and target_shares == 0 and frac_tail > 1e-9:
                # cls trades whole shares only; the tail can't ride along —
                # reported (never silently dropped) even when the position is
                # PURELY fractional (held_whole == 0, nothing to sell via cls).
                fractional_residuals[t] = round(frac_tail, 6)
            if d_shares != 0:
                share_deltas[t] = d_shares
                deltas[t] = d_weight

        for t, d in deltas.items():
            if abs(d) > MAX_SINGLE_ORDER_FRACTION:
                return [], current_weights, deltas, fractional_residuals, (
                    f"order for {t} is {d*100:.1f}% of equity, exceeds "
                    f"{MAX_SINGLE_ORDER_FRACTION*100:.0f}% sanity cap"
                )

        # Sells first in the list (readability/log parity) — but note ALL
        # orders are submitted together and fill in the same auction.
        sells = sorted(((t, q) for t, q in share_deltas.items() if q < 0),
                       key=lambda x: x[1])
        buys = sorted(((t, q) for t, q in share_deltas.items() if q > 0),
                      key=lambda x: x[1])
        plan: list[dict] = []
        for t, q in sells:
            plan.append({"ticker": t, "side": "sell", "qty": -q,
                         "est_price": prices[t],
                         "est_notional": round(-q * prices[t], 2)})
        for t, q in buys:
            plan.append({"ticker": t, "side": "buy", "qty": q,
                         "est_price": prices[t],
                         "est_notional": round(q * prices[t], 2)})

        # Buying-power pre-check — see module docstring. Unlike the notional
        # day-TIF path, sell proceeds do NOT count: everything fills in the
        # same auction, so the buys must be covered by buying_power alone.
        total_buys = sum(o["est_notional"] for o in plan if o["side"] == "buy")
        if total_buys > buying_power + BP_EPSILON:
            return plan, current_weights, deltas, fractional_residuals, (
                f"insufficient buying power for same-auction cls buys: need "
                f"${total_buys:.2f} up front but buying_power is "
                f"${buying_power:.2f}. Sells and buys fill in the SAME closing "
                f"auction, so sale proceeds cannot fund the buys at submission "
                f"time — this account needs a margin multiplier (2x buying "
                f"power) covering the full buy notional. Refusing to submit a "
                f"partial rebalance; use the notional day-TIF path "
                f"(StrategyExecutor) or a margin-enabled account."
            )
        return plan, current_weights, deltas, fractional_residuals, None

    def _record_plan(
        self,
        result: dict,
        account: dict,
        current_weights: dict[str, float],
        deltas: dict[str, float],
        plan: list[dict],
        fractional_residuals: dict[str, float],
    ) -> None:
        result["equity"] = account["equity"]
        result["cash"] = account["cash"]
        result["buying_power"] = account["buying_power"]
        result["current_weights"] = current_weights
        result["deltas"] = deltas
        result["orders"] = plan
        if fractional_residuals:
            result["fractional_residuals"] = fractional_residuals
            log.warning(
                "[%s] fractional share tails cannot be traded via cls "
                "(whole-share only) and are left in the account: %s",
                self.name, fractional_residuals,
            )

    def _submit_all(self, plan: list[dict], result: dict) -> None:
        """Submit every order as a cls auction order (sells and buys together)."""
        for o in plan:
            resp = self.client.submit_order_qty(
                o["ticker"], o["qty"], o["side"],
                order_type="market", time_in_force="cls",
            )
            o["submit"] = resp
            if "error" in resp:
                o["status"] = "error"
                result["submit_errors"].append({
                    "ticker": o["ticker"],
                    "side": o["side"],
                    "qty": o["qty"],
                    "error_message": resp.get("error"),
                })
                continue
            o["id"] = resp.get("id")

    def _await_fills(self, plan: list[dict], timeout_s: float = FILL_TIMEOUT_S) -> None:
        """After the close, verify every submitted order reached 'filled'."""
        for o in plan:
            oid = o.get("id")
            if not oid:
                continue  # submit failed — status already 'error'
            final = self.client.wait_for_fill(oid, timeout_s=timeout_s)
            o["filled_qty"] = final.get("filled_qty")
            o["filled_avg_price"] = final.get("filled_avg_price")
            if final.get("timeout"):
                log.warning(
                    "[%s] cls order %s (%s %s x%d) not terminal %.0fs after "
                    "submission — canceling",
                    self.name, oid, o["side"], o["ticker"], o["qty"], timeout_s,
                )
                o["cancel"] = self.client.cancel_order(oid)
                o["status"] = "timeout"
                continue
            o["status"] = final.get("status", "unknown")

    # ---- main --------------------------------------------------------------

    def execute_rebalance_cls(self, target_weights: dict, dry_run: bool = True) -> dict:
        """Rebalance to ``target_weights`` via closing-auction orders.

        Must be called before the 15:50 ET cls cutoff. With ``dry_run=True``
        (the default) nothing is submitted. Result-dict shape matches
        ``StrategyExecutor.execute_rebalance``.
        """
        result: dict[str, Any] = {
            "strategy": self.name,
            "mode": "cls_auction",
            "dry_run": dry_run,
            "target_weights": dict(target_weights),
            "orders": [],
            "submit_errors": [],
            "failed_orders": [],
            "success": False,
        }

        err = self._validate_targets(target_weights)
        if err:
            result["error"] = err
            return result

        account, positions, err = self._fetch_snapshot()
        if err:
            result["error"] = err
            return result

        prices, err = self._latest_prices(set(target_weights) | set(positions))
        if err:
            result["error"] = err
            return result

        plan, current_weights, deltas, frac, err = self._build_plan(
            target_weights, account, positions, prices
        )
        self._record_plan(result, account, current_weights, deltas, plan, frac)
        if err:
            result["error"] = err
            return result

        if dry_run:
            result["success"] = True
            return result

        # ---- live: submit sells and buys together, then verify post-close.
        self._submit_all(plan, result)
        self._await_fills(plan)

        failed = [
            {
                "ticker": o["ticker"],
                "side": o.get("side"),
                "qty": o.get("qty"),
                "status": o.get("status"),
            }
            for o in plan
            if o.get("status") not in OK_STATUSES
        ]
        result["failed_orders"] = failed
        result["success"] = not result["submit_errors"] and not failed
        return result
