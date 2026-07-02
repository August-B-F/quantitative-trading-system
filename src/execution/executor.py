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

FILL_TIMEOUT_S = 600.0            # max wait per order before cancel
# Headroom constants tightened per research/droplets/study6_cash_yield: buys
# are sized from a FRESH post-sell cash snapshot (sells awaited to terminal
# state; Alpaca credits sale proceeds immediately) so only cent rounding
# needs cover. The old 0.99 * 0.995 stack stranded ~1.1% of equity at 0%.
PLAN_EQUITY_HEADROOM = 0.998      # plan-time sizing fraction of equity
BUY_CASH_HEADROOM = 0.999         # buys sized to 99.9% of post-sell cash
RETRY_CASH_HEADROOM = 0.98        # single-order retry sized to 98% of cash
MIN_ORDER_NOTIONAL = 1.00         # drop orders below $1

# Statuses that count as a successfully completed plan entry.
OK_STATUSES = ("filled", "residual_close")


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

    def _fetch_snapshot(self) -> tuple[dict | None, dict | None, str | None]:
        """Fetch account + positions; returns ``(account, positions, error)``."""
        account = self.client.get_account()
        if "error" in account:
            return None, None, f"get_account: {account['error']}"
        positions = self.client.get_positions()
        if isinstance(positions, dict) and "error" in positions:
            return account, None, f"get_positions: {positions['error']}"
        return account, positions, None

    def _build_plan(
        self,
        target_weights: dict,
        account: dict,
        positions: dict,
    ) -> tuple[list[dict], dict[str, float], dict[str, float], str | None]:
        """Build the order plan from an account/positions snapshot.

        Pure function of its inputs so it can run twice: once pre-wait for
        validation/preview, then again from a fresh snapshot after
        ``wait_for_market_open`` (the pre-wait snapshot can be many hours
        stale and mis-sizes orders).

        Returns ``(plan, current_weights, deltas, error)`` where ``error``
        is None when the plan is valid.
        """
        equity = account["equity"]
        buying_power = account["buying_power"]
        current_weights = self._current_weights(equity, positions)

        tickers = set(target_weights) | set(current_weights)
        deltas: dict[str, float] = {}
        for t in tickers:
            d = target_weights.get(t, 0.0) - current_weights.get(t, 0.0)
            # NEW positions are exempt from the noise gate: a sub-1% target
            # leg on an unheld ticker would otherwise NEVER be opened (the
            # live S7 account held 2.9% permanent idle cash this way,
            # ~35 bps/yr of drag — research/droplets/study6_cash_yield).
            is_new = current_weights.get(t, 0.0) == 0.0 and target_weights.get(t, 0.0) > 0.0
            if abs(d) >= NOISE_FRACTION or is_new:
                deltas[t] = d

        # Per-order sanity cap
        for t, d in deltas.items():
            if abs(d) > MAX_SINGLE_ORDER_FRACTION:
                return [], current_weights, deltas, (
                    f"order for {t} is {d*100:.1f}% of equity, exceeds "
                    f"{MAX_SINGLE_ORDER_FRACTION*100:.0f}% sanity cap"
                )

        # Sizing headroom: notional market orders debit exactly the notional,
        # so the only sizing error is cent rounding (<$0.04 across 8 legs).
        # Buys are additionally re-capped against FRESH post-sell cash, so a
        # fat buffer here is pure idle-cash drag — measured at ~13 bps/yr at
        # the old 0.99 (research/droplets/study6_cash_yield).
        usable_equity = equity * PLAN_EQUITY_HEADROOM

        # Sells first, then buys (smallest buys first so the small
        # diversifying legs submit while BP is still full — a large buy
        # submitted first can exhaust BP before small legs reach the wire).
        sells = sorted(((t, d) for t, d in deltas.items() if d < 0),
                       key=lambda x: x[1])       # most negative first
        buys = sorted(((t, d) for t, d in deltas.items() if d > 0),
                      key=lambda x: x[1])        # smallest buy first

        plan: list[dict] = []
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

        # Buying-power pre-check.
        # NOTE: sells free up cash but Alpaca's notional model handles intraday
        # settlement, so we only fail hard if buys exceed BP+sell proceeds.
        total_buys = sum(o["notional"] for o in plan if o["side"] == "buy")
        total_sells = sum(o["notional"] for o in plan if o["side"] == "sell")
        if total_buys > buying_power + total_sells + 1.0:
            return plan, current_weights, deltas, (
                f"insufficient buying power: need ${total_buys:.0f}, "
                f"have BP=${buying_power:.0f} + sells=${total_sells:.0f}"
            )

        return plan, current_weights, deltas, None

    def _record_plan(
        self,
        result: dict,
        account: dict,
        current_weights: dict[str, float],
        deltas: dict[str, float],
        plan: list[dict],
    ) -> None:
        """Copy a plan snapshot into the result dict (runs pre- and post-wait)."""
        result["equity"] = account["equity"]
        result["cash"] = account["cash"]
        result["current_weights"] = current_weights
        result["deltas"] = deltas
        result["orders"] = plan
        warnings_list = [
            f"{t} order is {abs(d)*100:.1f}% of equity"
            for t, d in deltas.items() if abs(d) > ORDER_WARN_FRACTION
        ]
        if warnings_list:
            result["warnings"] = warnings_list

    @staticmethod
    def _is_buying_power_error(message: str) -> bool:
        # Match the specific rejection text, NOT bare "http 403" — Alpaca also
        # 403s for non-fractionable/non-tradable assets and wash-trade blocks,
        # and retrying those at a cash-sized notional would build a large
        # unplanned position.
        msg = str(message).lower()
        return "buying power" in msg or "insufficient" in msg

    def _submit_batch(
        self,
        batch: list[dict],
        result: dict,
        allow_bp_retry: bool = False,
    ) -> None:
        """Submit every order in ``batch``, recording ids and submit errors.

        With ``allow_bp_retry`` an insufficient-buying-power rejection triggers
        exactly one retry sized to ``remaining_cash * RETRY_CASH_HEADROOM``.
        """
        for o in batch:
            resp = self.client.submit_order(o["ticker"], o["notional"], o["side"])
            o["submit"] = resp
            if ("error" in resp and allow_bp_retry
                    and self._is_buying_power_error(resp["error"])):
                acct = self.client.get_account()
                remaining = acct.get("cash", 0.0) if "error" not in acct else 0.0
                # Cap the retry at the ORIGINAL notional: this leg only shrinks
                # to fit available cash, it never grows to absorb cash that is
                # earmarked for the remaining (larger) buys in the batch.
                retry_notional = round(
                    min(o["notional"], remaining * RETRY_CASH_HEADROOM), 2
                )
                if retry_notional >= MIN_ORDER_NOTIONAL:
                    log.warning(
                        "[%s] insufficient buying power for %s $%.2f — "
                        "retrying once at $%.2f",
                        self.name, o["ticker"], o["notional"], retry_notional,
                    )
                    o["notional"] = retry_notional
                    o["retried"] = True
                    resp = self.client.submit_order(
                        o["ticker"], retry_notional, o["side"]
                    )
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

    def _await_batch(self, batch: list[dict], timeout_s: float = FILL_TIMEOUT_S) -> None:
        """Wait each submitted order to a terminal state; cancel on timeout."""
        for o in batch:
            oid = o.get("id")
            if not oid:
                continue  # submit failed — status already 'error'
            final = self.client.wait_for_fill(oid, timeout_s=timeout_s)
            o["filled_qty"] = final.get("filled_qty")
            o["filled_avg_price"] = final.get("filled_avg_price")
            if final.get("timeout"):
                log.warning(
                    "[%s] order %s (%s %s) not terminal after %.0fs — canceling",
                    self.name, oid, o["side"], o["ticker"], timeout_s,
                )
                o["cancel"] = self.client.cancel_order(oid)
                o["status"] = "timeout"
                continue
            o["status"] = final.get("status", "unknown")

    def _close_residuals(
        self,
        target_weights: dict,
        current_weights: dict[str, float],
        plan: list[dict],
    ) -> None:
        """Close leftover shares (notional rounding) on fully-exited tickers."""
        tickers_to_exit = set(current_weights) - set(target_weights)
        for t, w in target_weights.items():
            if w < NOISE_FRACTION and current_weights.get(t, 0) >= NOISE_FRACTION:
                tickers_to_exit.add(t)
        if not tickers_to_exit:
            return
        post_sell_pos = self.client.get_positions()
        if isinstance(post_sell_pos, dict) and "error" in post_sell_pos:
            log.warning("[%s] residual check failed: %s",
                        self.name, post_sell_pos["error"])
            return
        for t in tickers_to_exit:
            if t not in post_sell_pos or post_sell_pos[t]["qty"] <= 0:
                continue
            log.info("[%s] closing residual %.4f shares of %s",
                     self.name, post_sell_pos[t]["qty"], t)
            close_resp = self.client.close_position(t)
            closed_ok = False
            if "error" in close_resp:
                log.warning("[%s] residual close of %s failed: %s",
                            self.name, t, close_resp["error"])
            else:
                close_oid = close_resp.get("raw", {}).get("id")
                if close_oid:
                    final = self.client.wait_for_fill(
                        close_oid, timeout_s=FILL_TIMEOUT_S
                    )
                    closed_ok = final.get("status") == "filled"
                    if not closed_ok:
                        log.warning("[%s] residual close of %s ended '%s'",
                                    self.name, t, final.get("status"))
                else:
                    # No order id to await — verify the position is gone.
                    verify = self.client.get_positions()
                    closed_ok = (
                        not (isinstance(verify, dict) and "error" in verify)
                        and (t not in verify or verify[t]["qty"] <= 0)
                    )
            # Only a VERIFIED close counts as OK; anything else must flip
            # success=False so the unexited position gets alerted, not masked.
            plan.append({
                "ticker": t, "side": "sell",
                "notional": post_sell_pos[t]["market_value"],
                "status": "residual_close" if closed_ok else "error",
            })

    # ---- main --------------------------------------------------------------

    def execute_rebalance(self, target_weights: dict, dry_run: bool = True) -> dict:
        result: dict[str, Any] = {
            "strategy": self.name,
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

        plan, current_weights, deltas, err = self._build_plan(
            target_weights, account, positions
        )
        self._record_plan(result, account, current_weights, deltas, plan)
        if err:
            result["error"] = err
            return result

        if dry_run:
            result["success"] = True
            return result

        # ---- live submission ----
        log.info("[%s] checking market status before order submission ...", self.name)
        clock = self.client.wait_for_market_open()
        if "error" in clock:
            result["error"] = f"market clock failed: {clock['error']}"
            return result

        # The pre-wait plan can be many hours stale (the plan may be built up
        # to ~11h before market open) — re-fetch and rebuild from a fresh
        # snapshot before touching the wire.
        account, positions, err = self._fetch_snapshot()
        if err:
            result["error"] = err
            return result
        plan, current_weights, deltas, err = self._build_plan(
            target_weights, account, positions
        )
        self._record_plan(result, account, current_weights, deltas, plan)
        if err:
            result["error"] = err
            return result
        equity = account["equity"]

        sell_orders = [o for o in plan if o["side"] == "sell"]
        buy_orders = [o for o in plan if o["side"] == "buy"]

        # Sells: submit all, then wait each to a terminal state.
        self._submit_batch(sell_orders, result)
        self._await_batch(sell_orders)

        # Close residual positions left by notional rounding on full exits.
        self._close_residuals(target_weights, current_weights, plan)

        # Buys: sized from actual post-sell cash, not the plan-time snapshot.
        post_sell_account = self.client.get_account()
        if "error" in post_sell_account:
            result["error"] = f"get_account (post-sell): {post_sell_account['error']}"
            return result
        available = post_sell_account["cash"] * BUY_CASH_HEADROOM
        planned_buys = sum(o["notional"] for o in buy_orders)
        if planned_buys > available and planned_buys > 0:
            scale = max(available, 0.0) / planned_buys
            log.warning(
                "[%s] planned buys $%.2f exceed available cash $%.2f — "
                "scaling all buys by %.4f",
                self.name, planned_buys, available, scale,
            )
            result["buy_scale_factor"] = round(scale, 6)
            for o in buy_orders:
                o["notional"] = round(o["notional"] * scale, 2)

        # Drop dust orders.
        kept_buys = []
        for o in buy_orders:
            if o["notional"] < MIN_ORDER_NOTIONAL:
                log.info("[%s] dropping sub-$%.2f buy for %s ($%.2f)",
                         self.name, MIN_ORDER_NOTIONAL, o["ticker"], o["notional"])
                result.setdefault("dropped_orders", []).append(dict(o))
                plan.remove(o)
                continue
            kept_buys.append(o)
        buy_orders = kept_buys

        # Residual-cash sweep: whatever available cash the plan doesn't spend
        # (headroom, dust drops, noise-gated deltas) goes into the LARGEST buy
        # leg instead of sitting at 0% (~11-30 bps/yr recovered — study6).
        # buy_orders is sorted smallest-first, so [-1] is the largest leg,
        # bounding the relative weight distortion; RECONCILE_TOLERANCE covers it.
        if buy_orders:
            residual = round(available - sum(o["notional"] for o in buy_orders), 2)
            if residual > 0:
                buy_orders[-1]["notional"] = round(
                    buy_orders[-1]["notional"] + residual, 2
                )
                result["swept_residual"] = residual
                log.info("[%s] swept $%.2f residual cash into %s",
                         self.name, residual, buy_orders[-1]["ticker"])

        self._submit_batch(buy_orders, result, allow_bp_retry=True)
        self._await_batch(buy_orders)

        # Reconcile
        recon = self.reconcile(target_weights)
        reconcile_ran = "error" not in recon
        if reconcile_ran:
            result["post_rebalance_weights"] = recon["current_weights"]
            result["post_rebalance_equity"] = recon["equity"]
            result["max_deviation"] = recon["max_deviation"]
            result["deviations"] = recon["deviations"]
            result["reconciled"] = recon["reconciled"]
        else:
            result["reconciled"] = False

        # Slippage estimate (bps): equity drift relative to start
        if "post_rebalance_equity" in result:
            drift = (result["post_rebalance_equity"] - equity) / equity
            result["slippage_bps"] = round(drift * 1e4, 2)

        # Success: every plan order reached an OK status, nothing failed on
        # submit, and we could verify the final state. 'residual_close' is a
        # successful close, NOT a failure.
        failed = [
            {
                "ticker": o["ticker"],
                "side": o.get("side"),
                "notional": o.get("notional"),
                "status": o.get("status"),
            }
            for o in plan
            if o.get("status") not in OK_STATUSES
        ]
        result["failed_orders"] = failed
        result["success"] = (
            not result["submit_errors"]
            and not failed
            and reconcile_ran
        )
        return result

    # ---- reconciliation ----------------------------------------------------

    def reconcile(self, target_weights: dict) -> dict:
        """Compare live weights against targets (usable by the health check).

        Returns ``max_deviation``, per-ticker ``deviations`` and a
        ``reconciled`` bool (max deviation within RECONCILE_TOLERANCE).
        """
        account, positions, err = self._fetch_snapshot()
        if err:
            return {"strategy": self.name, "reconciled": False, "error": err}
        equity = account["equity"]
        current = self._current_weights(equity, positions)
        deviations = {
            t: abs(target_weights.get(t, 0.0) - current.get(t, 0.0))
            for t in set(target_weights) | set(current)
        }
        max_dev = max(deviations.values(), default=0.0)
        return {
            "strategy": self.name,
            "equity": equity,
            "current_weights": current,
            "deviations": deviations,
            "max_deviation": max_dev,
            "reconciled": max_dev <= RECONCILE_TOLERANCE,
        }

    # ---- status / kill -----------------------------------------------------

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
