"""Phase 2 alternative data orchestrator.

Runs all phase 2 fetchers (CFTC, EIA, Wikipedia, GitHub, FINRA, Treasury, USPTO,
AAR), then prints a summary of what landed in /data/clean and validates a few
known signals (COT extreme positioning, Wikipedia recession spikes).
"""
from __future__ import annotations

import argparse
import sys
import traceback
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.data.fetchers import cftc, eia, wikipedia, github, finra, treasury, uspto, aar  # noqa: E402
from src.data.utils import DATA_DIR, load_clean  # noqa: E402


SOURCES = [
    ("cftc", cftc.main),
    ("eia", eia.main),
    ("wikipedia", wikipedia.main),
    ("github", github.main),
    ("finra", finra.main),
    ("treasury", treasury.main),
    ("uspto", uspto.main),
    ("aar", aar.main),
]


def run_all(only: list[str] | None = None) -> None:
    for name, fn in SOURCES:
        if only and name not in only:
            continue
        print(f"\n========== {name.upper()} ==========")
        try:
            fn()
        except Exception as e:
            print(f"  !! {name} crashed: {e}")
            traceback.print_exc()


def summarize() -> pd.DataFrame:
    rows = []
    targets = [
        DATA_DIR / "clean" / "sentiment",
        DATA_DIR / "clean" / "alternative",
        DATA_DIR / "clean" / "macro",
    ]
    seen = set()
    for d in targets:
        if not d.exists():
            continue
        for p in sorted(d.glob("*.parquet")):
            if p.name in seen:
                continue
            try:
                df = load_clean(p)
            except Exception:
                continue
            if df.empty:
                continue
            years = (df.index.max() - df.index.min()).days / 365.25
            rows.append({
                "name": p.stem,
                "path": str(p.relative_to(DATA_DIR.parent)).replace("\\", "/"),
                "rows": len(df),
                "start": df.index.min().date(),
                "end": df.index.max().date(),
                "years": round(years, 2),
                "short_history": years < 3,
            })
            seen.add(p.name)
    df = pd.DataFrame(rows)
    if df.empty:
        print("\n[summary] no parquet files found")
        return df
    print("\n========== PHASE 2 SUMMARY ==========")
    print(df.to_string(index=False))
    short = df[df["short_history"]]
    if not short.empty:
        print(f"\n[!] {len(short)} sources have <3 years of data:")
        for _, r in short.iterrows():
            print(f"    {r['name']:40s}  {r['years']}y  ({r['start']}..{r['end']})")
    return df


def validate_signals() -> None:
    print("\n========== VALIDATION ==========")
    sp = DATA_DIR / "clean" / "sentiment" / "cot_sp500_emini.parquet"
    if sp.exists():
        df = load_clean(sp)
        if df.index.min() <= pd.Timestamp("2020-03-31"):
            win = df.loc["2020-01-01":"2020-04-30"]
            if "managed_money_net" in df.columns and not win.empty:
                mm = win["managed_money_net"].dropna()
                print(f"[validate] S&P COT mm_net Jan-Apr 2020: min={mm.min():.0f} max={mm.max():.0f}")
                if "mm_net_zscore_52w" in df.columns:
                    z = win["mm_net_zscore_52w"].dropna()
                    print(f"[validate] S&P COT mm_net 52w z-score range: {z.min():.2f}..{z.max():.2f}")
                    if (z < -1).any():
                        print("    -> extreme net SHORT positioning detected pre-March 2020 [OK]")
        else:
            print(f"[validate] cot_sp500_emini history starts {df.index.min().date()}, no March 2020 coverage")
    else:
        print("[validate] cot_sp500_emini.parquet not found, skipping")

    rec = DATA_DIR / "clean" / "alternative" / "wikipedia_recession.parquet"
    if rec.exists():
        df = load_clean(rec)
        col = df.columns[0]
        for label, lo, hi in [("Mar 2020", "2020-02-15", "2020-04-15"),
                              ("mid 2022", "2022-06-01", "2022-08-31")]:
            win = df.loc[lo:hi, col].dropna()
            base = df[col].rolling(90, min_periods=20).median()
            if win.empty:
                print(f"[validate] Wikipedia 'Recession' {label}: no data")
                continue
            ratio = win.max() / max(base.loc[lo:hi].median(), 1)
            print(f"[validate] Wikipedia 'Recession' {label}: peak={int(win.max())}  vs 90d median ratio={ratio:.2f}x")
    else:
        print("[validate] wikipedia_recession.parquet not found, skipping")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*", default=None, help="run a subset (e.g. --only wikipedia treasury)")
    ap.add_argument("--skip-fetch", action="store_true", help="only summarize / validate, no downloads")
    args = ap.parse_args()
    if not args.skip_fetch:
        run_all(args.only)
    summarize()
    validate_signals()
