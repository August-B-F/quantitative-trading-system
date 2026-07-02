"""One-shot backfill of SPY benchmark columns in logs/monthly_comparison.csv.

The rebalance writer historically hardcoded spy_return=None, so the column
was always blank. This script rewrites the CSV in place:

    * spy_return — SPY adj_close return between consecutive row dates
      (data/clean/prices/SPY.parquet, price as-of each row date);
      the first row stays blank.
    * spy_equity — initial capital (100000) compounded through spy_return;
      the first row anchors at 100000.

Schema after rewrite (must match run_rebalance.write_monthly_comparison_row):
    date,s1_equity..s9_equity,spy_return,spy_equity

Usage:
    py -3 scripts/backfill_benchmarks.py
"""
from __future__ import annotations

import csv
import logging
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = ROOT / "logs" / "monthly_comparison.csv"
SPY_PATH = ROOT / "data" / "clean" / "prices" / "SPY.parquet"

INITIAL_CAPITAL = 100_000.0
HEADERS = ["date"] + [f"s{i}_equity" for i in range(1, 10)] + ["spy_return", "spy_equity"]

log = logging.getLogger("backfill_benchmarks")


def load_spy_series() -> pd.Series:
    """SPY adj_close indexed by normalized trading date, sorted."""
    df = pd.read_parquet(SPY_PATH)
    ser = df["adj_close"].dropna()
    ser.index = pd.DatetimeIndex(ser.index).normalize()
    return ser.sort_index()


def backfill_rows(rows: list[dict], spy: pd.Series) -> list[dict]:
    """Fill spy_return / spy_equity in place; returns the same list."""
    rows.sort(key=lambda r: r["date"])
    prev_px: float | None = None
    equity = INITIAL_CAPITAL
    for row in rows:
        date = pd.Timestamp(row["date"]).normalize()
        px = spy.asof(date)  # last price at or before the row date
        if pd.isna(px):
            log.warning("no SPY price at or before %s — leaving row blank", date.date())
            row["spy_return"] = ""
            row["spy_equity"] = ""
            continue
        if prev_px is None:
            row["spy_return"] = ""
            equity = INITIAL_CAPITAL
        else:
            r = float(px) / prev_px - 1.0
            row["spy_return"] = f"{r:.6f}"
            equity *= 1.0 + r
        row["spy_equity"] = f"{equity:.2f}"
        prev_px = float(px)
    return rows


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    if not CSV_PATH.exists():
        log.error("%s not found — nothing to backfill", CSV_PATH)
        return 1
    if not SPY_PATH.exists():
        log.error("%s not found — cannot compute SPY returns", SPY_PATH)
        return 1

    with open(CSV_PATH, "r", newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        log.error("%s has no data rows", CSV_PATH)
        return 1

    rows = backfill_rows(rows, load_spy_series())

    with open(CSV_PATH, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=HEADERS, restval="", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    log.info("rewrote %s (%d rows)", CSV_PATH, len(rows))

    print(pd.read_csv(CSV_PATH).to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
