"""
CFNAI / USPHCI vs OECD CLI swap test.

Evaluates whether the Chicago Fed National Activity Index (CFNAI) or the
Philadelphia Fed US Coincident Index (USPHCI) can replace the
discontinued OECD CLI (FRED: USALOLITONOSTSAM) as the
`activity_features__oecd_cli` input to the regime classifier.

Usage
-----
    py scripts/test_cfnai_swap.py

The script:
  1. Fetches CFNAI from the Chicago Fed direct xlsx (no API key). If
     that fetch fails, falls back to FRED direct CSV.
  2. Fetches USPHCI from FRED direct CSV (no API key).
  3. Loads the existing cleaned oecd_cli panel from
     data/clean/macro/oecd_cli_us.parquet.
  4. Resamples everything to monthly, aligns on the 2000-02 -> 2023-12
     overlap, and reports Pearson correlation on levels, 3m change,
     and 12m change.
  5. Applies the §8.1 adoption rule:
       - max of {levels, 3m, 12m} >= 0.85  -> ADOPT (clean)
       - 0.70 <= max < 0.85                -> MARGINAL (test anyway)
       - max < 0.70                        -> REJECT
     AND the candidate must be publishing within the last 60 days.

Result as of 2026-04-12 (this script's initial run):
  CFNAI   publishes through 2026-02. max corr 0.36 -> REJECT.
  USPHCI  publishes through 2025-12. max corr 0.64 -> REJECT.

Both rejected. Decision: retain oecd_cli with forward-fill and monitor
staleness as a WARNING-level alert (see configs/alerts.yaml and
src/risk/monitoring.py::check_oecd_age). Re-run this script quarterly
in case FRED resumes OECD CLI publication or the candidate dynamics
shift enough to clear the 0.70 floor.

See MASTER_ARCHITECTURE.md §8.1 for full context.
"""

from __future__ import annotations

import io
import sys
import urllib.request
from pathlib import Path

import pandas as pd

try:
    import requests  # type: ignore
    _HAS_REQUESTS = True
except ImportError:
    _HAS_REQUESTS = False

FRED_CSV_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}"
CHICAGO_FED_XLSX = "https://www.chicagofed.org/~/media/publications/cfnai/cfnai-data-series-xlsx.xlsx"
OECD_CLEAN = Path("data/clean/macro/oecd_cli_us.parquet")

ADOPT_CORR_CLEAN = 0.85
ADOPT_CORR_RETEST = 0.70
CURRENCY_DAYS = 75  # CFNAI/USPHCI publish ~3 weeks after month-end; give one monthly release cycle of slack


def fetch_fred_csv(series_id: str, timeout: int = 300) -> pd.Series:
    # Prefer a cached raw copy if it exists; FRED can be slow from some networks.
    cache = Path(__file__).resolve().parents[1] / "data" / "raw" / "fred" / f"{series_id}.csv"
    raw_text = None
    if cache.exists():
        raw_text = cache.read_text()
    else:
        url = FRED_CSV_URL.format(sid=series_id)
        if _HAS_REQUESTS:
            r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=timeout)
            r.raise_for_status()
            raw_text = r.text
        else:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            raw_text = urllib.request.urlopen(req, timeout=timeout).read().decode()
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(raw_text)
    df = pd.read_csv(io.StringIO(raw_text))
    date_col = "observation_date" if "observation_date" in df.columns else "DATE"
    df[date_col] = pd.to_datetime(df[date_col])
    df = df.set_index(date_col).sort_index()
    val_col = [c for c in df.columns if c != date_col][0]
    s = pd.to_numeric(df[val_col], errors="coerce").dropna()
    s.name = series_id
    return s


def fetch_cfnai_chicago() -> pd.Series:
    """Direct xlsx from Chicago Fed. No API key needed."""
    cache = Path(__file__).resolve().parents[1] / "data" / "raw" / "fred" / "CFNAI.xlsx"
    if cache.exists():
        raw = cache.read_bytes()
    else:
        if _HAS_REQUESTS:
            r = requests.get(CHICAGO_FED_XLSX, headers={"User-Agent": "Mozilla/5.0"}, timeout=300)
            r.raise_for_status()
            raw = r.content
        else:
            req = urllib.request.Request(CHICAGO_FED_XLSX, headers={"User-Agent": "Mozilla/5.0"})
            raw = urllib.request.urlopen(req, timeout=300).read()
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_bytes(raw)
    df = pd.read_excel(io.BytesIO(raw), sheet_name="data")
    # Date column is strings like "2026:02"
    df["date"] = pd.to_datetime(df["Date"].str.replace(":", "-") + "-01")
    s = pd.to_numeric(df.set_index("date")["CFNAI"], errors="coerce").dropna()
    s.name = "CFNAI"
    return s


def evaluate(candidate: pd.Series, oecd_monthly: pd.Series, name: str) -> dict:
    print(f"\n=== {name} ===")
    print(f"  range: {candidate.index.min().date()} -> {candidate.index.max().date()}  n={len(candidate)}")

    today = pd.Timestamp.today().normalize()
    last_obs = candidate.index.max()
    stale_days = (today - last_obs).days
    is_current = stale_days <= CURRENCY_DAYS
    print(f"  staleness: {stale_days} days (floor {CURRENCY_DAYS})  is_current={is_current}")

    cand_m = candidate.resample("ME").last().dropna()
    both = pd.concat([oecd_monthly.rename("oecd"), cand_m.rename("cand")], axis=1, join="inner").dropna()
    if both.empty:
        print("  ERROR: no overlap with oecd_cli")
        return {"name": name, "adopt": False, "max_corr": 0.0, "is_current": is_current}
    print(f"  overlap: {both.index.min().date()} -> {both.index.max().date()}  n={len(both)}")

    c_lvl = both["oecd"].corr(both["cand"])
    c_3m = both.diff(3).dropna().corr().iloc[0, 1]
    c_12m = both.diff(12).dropna().corr().iloc[0, 1]
    max_c = max(c_lvl, c_3m, c_12m)
    print(f"  corr levels:    {c_lvl:+.4f}")
    print(f"  corr 3m-change: {c_3m:+.4f}")
    print(f"  corr 12m-change:{c_12m:+.4f}")
    print(f"  MAX:            {max_c:+.4f}")

    if not is_current:
        print(f"  DECISION: REJECT ({name} is stale by {stale_days}d; needs <= {CURRENCY_DAYS}d).")
        adopt = False
    elif max_c < ADOPT_CORR_RETEST:
        print(f"  DECISION: REJECT (max corr {max_c:.3f} < retest floor {ADOPT_CORR_RETEST}).")
        adopt = False
    elif max_c < ADOPT_CORR_CLEAN:
        print(f"  DECISION: MARGINAL (0.70 <= {max_c:.3f} < 0.85). Run the backtest before adopting.")
        adopt = True  # warrants a retrain+backtest
    else:
        print(f"  DECISION: CLEAN ADOPT CANDIDATE (max corr {max_c:.3f} >= {ADOPT_CORR_CLEAN}).")
        adopt = True

    return {
        "name": name,
        "adopt": adopt,
        "max_corr": max_c,
        "is_current": is_current,
        "corr_levels": c_lvl,
        "corr_3m": c_3m,
        "corr_12m": c_12m,
        "stale_days": stale_days,
    }


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    oecd_path = repo_root / OECD_CLEAN
    if not oecd_path.exists():
        print(f"ERROR: {oecd_path} not found; run data pipeline first", file=sys.stderr)
        return 2

    oecd = pd.read_parquet(oecd_path)["oecd_cli_us"].dropna()
    oecd_monthly = oecd.resample("ME").last().dropna()
    print(
        f"OECD CLI baseline: n={len(oecd_monthly)}  "
        f"{oecd_monthly.index.min().date()} -> {oecd_monthly.index.max().date()}  "
        f"(FRED series discontinued 2023-12)"
    )

    # CFNAI
    print("\nFetching CFNAI from Chicago Fed...")
    try:
        cfnai = fetch_cfnai_chicago()
    except Exception as e:
        print(f"  Chicago Fed fetch failed ({type(e).__name__}: {e}); trying FRED direct...")
        cfnai = fetch_fred_csv("CFNAI")

    # USPHCI
    print("\nFetching USPHCI from FRED...")
    usphci = fetch_fred_csv("USPHCI")

    results = [
        evaluate(cfnai, oecd_monthly, "CFNAI"),
        evaluate(usphci, oecd_monthly, "USPHCI"),
    ]

    print("\n=== SUMMARY ===")
    for r in results:
        print(f"  {r['name']:7s}  max_corr={r['max_corr']:+.3f}  "
              f"current={r['is_current']}  adopt={r['adopt']}")

    any_adopt = any(r["adopt"] for r in results)
    if not any_adopt:
        print("\nFINAL DECISION: keep `oecd_cli` with forward-fill.")
        print("                Staleness tracked as WARNING-level alert "
              "(configs/alerts.yaml::oecd_cli_age).")
        print("                See MASTER_ARCHITECTURE.md §8.1 for context.")
        return 0

    print("\nNEXT STEPS for adoption (manual):")
    print("  1. Back up the existing panel:")
    print("     cp data/features/master_panel.parquet "
          "data/features/master_panel_oecd_legacy.parquet")
    print("  2. Rebuild master panel with the candidate column substituted for")
    print("     oecd_cli (ffill up to 31 days; same treatment as other monthly macros).")
    print("  3. Retrain: py scripts/model/run_optimization_block.py")
    print("  4. Canary: py scripts/run_backtest.py  (expect 23.61/1.50/-12.94)")
    print("  5. Adopt only if dCAGR >= -1pp AND dSharpe >= -0.05 vs canonical.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
