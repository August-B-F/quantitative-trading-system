"""Automated monthly race report — emits results/RACE_REPORT.md.

Reads (all overridable on the CLI, so tests can point at fixtures):
    logs/monthly_comparison.csv    per-account equity snapshots + SPY benchmark
    logs/rebalance_log.json        execution record (orders, errors, warnings)
    configs/accounts.yaml          slot -> strategy-name mapping, initial capital

Sections: per-arm equity vs SPY, implementation-fidelity placeholder (TODO —
hook the daily-ledger sim per EVALUATION.md §3), drawdown vs the -20%/-25%
tripwires, execution error count, race clock (months elapsed / remaining of
12), and the power-corrected verdict language measured by Study 13
(research/droplets/study13_race_power/).

Offline by design: no network, no broker calls. Until the operator passes
--race-start (the relaunch date), everything in the logs is labelled
PRE-RELAUNCH / VOIDED ERA per docs/POSTMORTEM_2026H1.md and is NOT race data.

Usage:
    py -3 scripts/run_race_report.py [--out results/RACE_REPORT.md]
        [--comparison logs/monthly_comparison.csv]
        [--rebalance-log logs/rebalance_log.json]
        [--accounts configs/accounts.yaml] [--race-start YYYY-MM-DD]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]

RACE_MONTHS = 12          # EVALUATION.md §2
DERISK_DD = -0.20         # EVALUATION.md §3: de-risk the arm 50%
HALT_DD = -0.25           # EVALUATION.md §3: halt the arm (stays in race as halted record)
EDGE_BAR = 0.20           # EVALUATION.md §4: "clear" Sharpe edge

# ---- Study 13 measured decisiveness numbers (research/droplets/study13_race_power/,
# daily-ledger arms, 2018+ window, circular 21d-block bootstrap, B=5000, 10 bps;
# 20 bps confirmatory numbers in power_results.csv are the same picture). ----
POWER_FACTS = {
    "fpr_vs_gem": 0.338,          # P(12m edge_hat >= 0.20 | true edge 0) vs GEM
    "fpr_vs_spy_sma200": 0.354,   # same vs SPY/SMA200
    "fpr_joint_worst_case": 0.203,  # promote-over-BOTH rule, blend true Sharpe = better control
    "fnr_vs_gem": 0.570,          # P(12m edge_hat < 0.20 | true edge = 0.20) vs GEM
    "fnr_vs_spy_sma200": 0.502,
    "edge_sd_12m_vs_gem": 0.81,   # bootstrap SD of the 12m Sharpe edge (daily corr 0.54)
    "edge_sd_12m_vs_spy_sma200": 0.57,  # (daily corr 0.80)
    "min_window_80pct_power": "> 240 months",  # not reached on the tested grid by ANY
    #   statistic: literal rule (structurally capped ~50%), one-sided 5% Sharpe-diff
    #   test (<= 49% at 240m), or paired daily-difference test (<= 62% at 240m).
    "spa_p_vs_gem_10bps": 0.059,        # Hansen SPA, full common window 2007-02..2026-07
    "spa_p_vs_spy_sma200_10bps": 0.008,
}


# ---------- loading -----------------------------------------------------------

def load_accounts(path: Path) -> tuple[dict[int, str], float]:
    """slot -> display name, plus initial capital."""
    cfg = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    slots: dict[int, str] = {}
    for key, s in (cfg.get("strategies") or {}).items():
        slot = s.get("slot")
        if slot is not None:
            slots[int(slot)] = str(s.get("name", key))
    return slots, float(cfg.get("initial_capital", 100_000))


def load_comparison(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, parse_dates=["date"]).sort_values("date")
    return df.set_index("date")


def equity_columns(df: pd.DataFrame) -> list[tuple[int, str]]:
    """[(slot, column)] for every s<N>_equity column present."""
    out = []
    for c in df.columns:
        m = re.fullmatch(r"s(\d+)_equity", c)
        if m:
            out.append((int(m.group(1)), c))
    return sorted(out)


# ---------- metrics -----------------------------------------------------------

def tripwire_flag(min_drawdown: float) -> str:
    """EVALUATION.md §3 drawdown tripwires on equity vs high-water mark."""
    if min_drawdown <= HALT_DD:
        return "HALT"
    if min_drawdown <= DERISK_DD:
        return "DERISK"
    return "OK"


def drawdown_stats(equity: pd.Series, initial_capital: float) -> dict:
    """Max/current drawdown vs high-water mark (HWM seeded at initial capital)."""
    eq = equity.dropna().astype(float)
    if eq.empty:
        return {"max_dd": float("nan"), "current_dd": float("nan"), "flag": "NO DATA"}
    hwm = pd.concat([pd.Series([initial_capital]), eq]).cummax().iloc[1:]
    dd = eq / hwm - 1.0
    return {
        "max_dd": float(dd.min()),
        "current_dd": float(dd.iloc[-1]),
        "flag": tripwire_flag(float(dd.min())),
    }


def count_execution_errors(log_entries: list) -> tuple[pd.DataFrame, int, int]:
    """Per-strategy error tally from logs/rebalance_log.json.

    An error is: a non-null strategy `error`, `success` false, or any entry in
    `submit_errors`. Returns (table, total_errors, n_data_warning_entries).
    """
    rows: dict[str, dict[str, int]] = {}
    warn_entries = 0
    for entry in log_entries:
        if entry.get("data_warnings"):
            warn_entries += 1
        for strat, d in (entry.get("strategies") or {}).items():
            r = rows.setdefault(strat, {"errors": 0, "submit_errors": 0})
            if d.get("error") or d.get("success") is False:
                r["errors"] += 1
            r["submit_errors"] += len(d.get("submit_errors") or [])
    table = pd.DataFrame(
        [{"strategy": k, **v, "total": v["errors"] + v["submit_errors"]}
         for k, v in sorted(rows.items())]
    )
    total = int(table["total"].sum()) if len(table) else 0
    return table, total, warn_entries


def months_elapsed(dates: pd.DatetimeIndex, race_start: pd.Timestamp | None) -> int:
    """Distinct calendar months represented at/after race_start."""
    d = pd.DatetimeIndex(dates)
    if race_start is not None:
        d = d[d >= race_start]
    return int(d.to_period("M").nunique())


# ---------- report ------------------------------------------------------------

def build_report(
    comparison: pd.DataFrame,
    log_entries: list,
    slots: dict[int, str],
    initial_capital: float,
    race_start: pd.Timestamp | None,
) -> str:
    now = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M")
    cols = equity_columns(comparison)
    window = comparison.loc[comparison.index >= race_start] if race_start is not None else comparison
    L: list[str] = []
    L += [
        "# RACE REPORT — paper-trading relaunch race (EVALUATION.md)",
        "",
        f"Generated {now} by `scripts/run_race_report.py` (offline, logs only).",
        f"Data: {len(window)} snapshot rows, "
        f"{window.index.min().date() if len(window) else 'n/a'}"
        f"..{window.index.max().date() if len(window) else 'n/a'}.",
        "",
        "## Data era",
        "",
    ]
    if race_start is None:
        L += [
            "**PRE-RELAUNCH / VOIDED ERA.** No `--race-start` was supplied, so every",
            "number below comes from the voided 2026 H1 record",
            "(`docs/POSTMORTEM_2026H1.md`) and the pre-relaunch account lineup in",
            "`configs/accounts.yaml`. This is plumbing verification output — it is",
            "NOT race evidence and must not be quoted as performance.",
            "",
        ]
    else:
        L += [f"Race window starts {race_start.date()}; rows before it are excluded.", ""]

    # ---- per-arm equity vs SPY ----
    L += ["## Per-arm equity vs SPY", ""]
    if len(window) == 0:
        L += ["No snapshot rows in the window.", ""]
    else:
        last = window.iloc[-1]
        spy_eq = float(last["spy_equity"]) if "spy_equity" in window.columns else float("nan")
        spy_ret = spy_eq / initial_capital - 1.0
        L += [
            f"SPY benchmark equity: {spy_eq:,.2f} ({spy_ret:+.2%} vs initial "
            f"{initial_capital:,.0f}).",
            "",
            "| Arm | Slot | Equity | Return | vs SPY (pp) |",
            "|---|---|---|---|---|",
        ]
        for slot, col in cols:
            name = slots.get(slot, f"s{slot}")
            eq = float(last[col])
            ret = eq / initial_capital - 1.0
            L.append(
                f"| {name} | {slot} | {eq:,.2f} | {ret:+.2%} | "
                f"{(ret - spy_ret) * 100:+.1f} |"
            )
        L.append("")

    # ---- implementation fidelity ----
    L += [
        "## Implementation fidelity",
        "",
        "**PLACEHOLDER — not yet implemented.** TODO: for each arm, re-run the",
        "daily-ledger engine (`src/backtest/ledger.py::run_ledger_backtest`) on the",
        "`target_weights` recorded in `logs/rebalance_log.json` (the signals the live",
        "system claims it traded) and compare the simulated month return with the",
        "realized account return from `logs/monthly_comparison.csv`. Alert when the",
        "divergence exceeds 50 bps/month (EVALUATION.md §3); >2 unexplained failing",
        "months voids the arm's record (§4). Requires the relaunch accounts to map",
        "1:1 to race arms in `configs/accounts.yaml`.",
        "",
    ]

    # ---- drawdown tripwires ----
    L += [
        "## Drawdown vs tripwires",
        "",
        f"Tripwires per EVALUATION.md §3: {DERISK_DD:.0%} de-risk 50% / "
        f"{HALT_DD:.0%} halt the arm. High-water mark seeded at initial capital "
        f"{initial_capital:,.0f}.",
        "",
        "| Arm | Slot | Max DD | Current DD | Tripwire |",
        "|---|---|---|---|---|",
    ]
    any_tripped = False
    for slot, col in cols:
        name = slots.get(slot, f"s{slot}")
        s = drawdown_stats(window[col] if len(window) else pd.Series(dtype=float),
                           initial_capital)
        flag = s["flag"]
        if flag in ("DERISK", "HALT"):
            any_tripped = True
            flag = f"**{flag}**"
        L.append(
            f"| {name} | {slot} | {s['max_dd']:.2%} | {s['current_dd']:.2%} | {flag} |"
        )
    L += ["", "Tripwire action required: "
          + ("YES — see flagged rows above." if any_tripped else "none."), ""]

    # ---- execution errors ----
    err_table, total_errors, warn_entries = count_execution_errors(log_entries)
    L += [
        "## Execution errors",
        "",
        f"Total execution errors in `logs/rebalance_log.json`: **{total_errors}** "
        f"(target 0 per EVALUATION.md §3). Entries with data warnings: {warn_entries}.",
        "",
    ]
    if len(err_table):
        L += ["| Strategy | Errors | Submit errors | Total |", "|---|---|---|---|"]
        for _, r in err_table.iterrows():
            L.append(f"| {r['strategy']} | {r['errors']} | {r['submit_errors']} | {r['total']} |")
        L.append("")
    if total_errors:
        L += ["Any error must be fixed before the next rebalance (§3).", ""]

    # ---- race clock ----
    elapsed = months_elapsed(window.index, race_start) if len(window) else 0
    remaining = max(0, RACE_MONTHS - elapsed)
    L += [
        "## Race clock",
        "",
        f"Months elapsed: {elapsed} / {RACE_MONTHS}. Months remaining: {remaining}."
        + (" (Pre-relaunch data — the race clock has NOT started.)"
           if race_start is None else ""),
        "",
    ]

    # ---- power-corrected verdict ----
    p = POWER_FACTS
    L += [
        "## Power-corrected verdict language (Study 13)",
        "",
        f"The EVALUATION.md §4 rule — promote on a >= {EDGE_BAR:.2f} Sharpe edge over",
        "both controls after 12 months — is **not statistically decisive** at this",
        "window (block-bootstrap of the actual arm returns, "
        "`research/droplets/study13_race_power/`):",
        "",
        f"- 12-month Sharpe-edge sampling SD: {p['edge_sd_12m_vs_gem']:.2f} vs GEM, "
        f"{p['edge_sd_12m_vs_spy_sma200']:.2f} vs SPY/SMA200 — several times the "
        f"{EDGE_BAR:.2f} bar itself.",
        f"- False-positive rate of the rule (true edge 0): {p['fpr_vs_gem']:.0%} vs GEM, "
        f"{p['fpr_vs_spy_sma200']:.0%} vs SPY/SMA200; worst-case {p['fpr_joint_worst_case']:.0%} "
        "for the promote-over-BOTH rule.",
        f"- False-negative rate (true edge exactly {EDGE_BAR:.2f}): {p['fnr_vs_gem']:.0%} vs GEM, "
        f"{p['fnr_vs_spy_sma200']:.0%} vs SPY/SMA200 — a coin flip by construction.",
        f"- Window for 80% power against a true {EDGE_BAR:.2f} edge: "
        f"{p['min_window_80pct_power']} for every statistic tested, including the "
        "paired daily-difference test.",
        "",
        "**Verdict rule this report applies (per Study 13):** the month-12 decision is",
        "judged on (1) implementation fidelity (<= 50 bps/month divergence), (2) drawdown",
        "discipline (tripwire section above), and (3) process compliance (execution",
        "errors, signal freshness). The 12-month Sharpe ordering is a TIEBREAK only and",
        "is quoted with its bootstrap SD; no promotion claim may rest on a 12-month",
        "Sharpe edge. The candidate's long-window statistical case is the SPA test on",
        f"the full common history (p = {p['spa_p_vs_gem_10bps']:.3f} vs GEM, "
        f"p = {p['spa_p_vs_spy_sma200_10bps']:.3f} vs SPY/SMA200 at 10 bps), which the",
        "race verifies for implementability rather than re-litigates.",
        "",
    ]
    return "\n".join(L)


# ---------- cli -----------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--comparison", default=str(ROOT / "logs" / "monthly_comparison.csv"))
    ap.add_argument("--rebalance-log", default=str(ROOT / "logs" / "rebalance_log.json"))
    ap.add_argument("--accounts", default=str(ROOT / "configs" / "accounts.yaml"))
    ap.add_argument("--out", default=str(ROOT / "results" / "RACE_REPORT.md"))
    ap.add_argument("--race-start", default=None,
                    help="relaunch date YYYY-MM-DD; omit => data labelled pre-relaunch/voided")
    args = ap.parse_args(argv)

    comparison = load_comparison(Path(args.comparison))
    log_entries = json.loads(Path(args.rebalance_log).read_text(encoding="utf-8"))
    slots, initial_capital = load_accounts(Path(args.accounts))
    race_start = pd.Timestamp(args.race_start) if args.race_start else None

    report = build_report(comparison, log_entries, slots, initial_capital, race_start)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(report, encoding="utf-8")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
