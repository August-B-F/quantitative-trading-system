"""
USSLIND vs OECD CLI swap test.

Evaluates whether the Philadelphia Fed / FRB USSLIND leading index can
replace the discontinued OECD CLI (FRED: USALOLITONOSTSAM) as the
`activity_features__oecd_cli` input to the regime classifier.

Usage
-----
    py scripts/test_usslind_swap.py

The script:
  1. Fetches USSLIND from FRED (direct CSV, no API key required).
  2. Loads the existing cleaned oecd_cli panel from
     data/clean/macro/oecd_cli_us.parquet.
  3. Resamples oecd_cli to monthly, aligns on the overlap, and reports
     Pearson correlation on levels, 3m change, and 12m change.
  4. If correlation on levels >= 0.85 AND USSLIND is publishing
     through the present: prints a NEXT-STEPS block showing how to
     wire the swap into the master panel and retrain.
  5. Otherwise: prints the reason USSLIND is rejected.

Decision rule (from MASTER_ARCHITECTURE.md §8.1):
    adopt USSLIND only if corr(levels) >= 0.85 AND series is current
    (last obs within 60 days of today) AND ablation retrain shows
    delta_sharpe >= -0.05 AND delta_cagr >= -1pp vs 23.61%/1.50.

As of this script's initial authoring (2026-04-12), USSLIND is
itself discontinued with last observation 2020-02-01, so step (5)
short-circuits. This script is retained so the evaluation is
reproducible if FRED resumes publication or as a template for the
CFNAI / USPHCI follow-up tests.
"""

from __future__ import annotations

import io
import sys
import urllib.request
from pathlib import Path

import pandas as pd

FRED_CSV_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}"
OECD_CLEAN = Path("data/clean/macro/oecd_cli_us.parquet")
ADOPT_CORR_THRESHOLD = 0.85
CURRENCY_DAYS = 60  # series must have an observation within this many days of today


def fetch_fred_csv(series_id: str) -> pd.Series:
    url = FRED_CSV_URL.format(sid=series_id)
    raw = urllib.request.urlopen(url, timeout=15).read().decode()
    df = pd.read_csv(io.StringIO(raw), parse_dates=["observation_date"])
    df = df.set_index("observation_date")
    col = [c for c in df.columns if c != "observation_date"][0]
    s = pd.to_numeric(df[col], errors="coerce").dropna()
    s.name = series_id
    return s


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    oecd_path = repo_root / OECD_CLEAN
    if not oecd_path.exists():
        print(f"ERROR: {oecd_path} not found; run data pipeline first", file=sys.stderr)
        return 2

    print("Fetching USSLIND from FRED...")
    usslind = fetch_fred_csv("USSLIND")
    print(f"  rows: {len(usslind)}  range: {usslind.index.min().date()} -> {usslind.index.max().date()}")

    oecd = pd.read_parquet(oecd_path)["oecd_cli_us"].dropna()
    oecd_monthly = oecd.resample("MS").last().dropna()
    print(
        f"OECD CLI:  rows={len(oecd_monthly)}  "
        f"range={oecd_monthly.index.min().date()} -> {oecd_monthly.index.max().date()}"
    )

    # Currency check
    today = pd.Timestamp.today().normalize()
    last_obs = usslind.index.max()
    stale_days = (today - last_obs).days
    is_current = stale_days <= CURRENCY_DAYS
    print(f"USSLIND staleness: {stale_days} days (threshold {CURRENCY_DAYS})  is_current={is_current}")

    # Align + correlation on the overlap
    df = pd.concat({"USSLIND": usslind, "OECD": oecd_monthly}, axis=1).dropna()
    overlap_06_23 = df.loc["2006-01-01":"2023-12-31"]
    print(
        f"Overlap (2006-2023): n={len(overlap_06_23)}  "
        f"{overlap_06_23.index.min().date()} -> {overlap_06_23.index.max().date()}"
    )
    corr_level = overlap_06_23.corr().iloc[0, 1]
    corr_3m = overlap_06_23.diff(3).dropna().corr().iloc[0, 1]
    corr_12m = overlap_06_23.diff(12).dropna().corr().iloc[0, 1]
    print(f"Correlation (levels):        {corr_level:.4f}")
    print(f"Correlation (3m change):     {corr_3m:.4f}")
    print(f"Correlation (12m change):    {corr_12m:.4f}")

    print()
    adopt_ok = corr_level >= ADOPT_CORR_THRESHOLD and is_current
    if not is_current:
        print(f"REJECT: USSLIND is stale by {stale_days} days (last obs {last_obs.date()}).")
        print("        It cannot replace a feature that went stale 2023-12.")
    elif corr_level < ADOPT_CORR_THRESHOLD:
        print(f"REJECT: level correlation {corr_level:.3f} < threshold {ADOPT_CORR_THRESHOLD}.")
    if not adopt_ok:
        print("DECISION: keep `oecd_cli` with forward-fill. See §8.1 for alternatives (CFNAI, USPHCI).")
        return 0

    # If we ever get here: print the retrain plan
    print("ACCEPT candidates: level correlation passes AND series is current.")
    print()
    print("Next steps (manual):")
    print("  1. Backfill USSLIND into the master panel:")
    print("     - add fetcher row in src/data/fetchers/fred.py for ('USSLIND', 'usslind', 'monthly', 'leading')")
    print("     - re-run scripts/phase1_fred.py to refresh data/clean/macro/usslind.parquet")
    print("  2. Edit src/features/macro_features.py: swap `L('oecd_cli_us')` -> `L('usslind')`")
    print("     (keep output column name `oecd_cli` to avoid touching configs/feature_sets.yaml)")
    print("  3. Rebuild master panel: py scripts/phase3_integrate_and_health.py")
    print("  4. Retrain + backtest: py scripts/model/run_optimization_block.py")
    print("  5. Compare to canonical 23.61% / 1.50 / -12.94%. Adopt if within:")
    print("       dCAGR >= -1pp AND dSharpe >= -0.05")
    return 0


if __name__ == "__main__":
    sys.exit(main())
