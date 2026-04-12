"""Phase 1 Step 3+4: download Yahoo universe + validation."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd

from src.data.fetchers.yahoo import fetch_universe, CLEAN_DIR
from src.data.utils import load_clean

PRIMARY = ["SOXX", "QQQ", "XLK", "VGT", "IGV", "XLE", "GLD", "SHY"]
BENCHMARK = ["SPY"]
EXPANSION = ["TLT", "DBC", "PDBC", "XLF", "XLI", "XLV", "XLU", "IWM", "EEM",
             "GDX", "XLB", "XLP", "XLRE", "IBB", "SMH", "ARKK"]
CANARY = ["AGG"]  # EEM already in EXPANSION
INTL = ["EFA", "FXI", "EWJ", "EWZ", "EWG"]
FACTOR = ["MTUM", "VLUE", "QUAL", "SIZE", "USMV"]
THEMATIC = ["HACK", "LIT", "TAN", "ICLN", "XBI", "JETS", "KWEB"]
BONDS = ["TIP", "HYG", "LQD", "BND", "SHV", "IEF", "IEI"]
COMMOD = ["USO", "UNG", "COPX", "SLV", "PPLT", "WEAT", "CORN", "DBA"]
CRYPTO = ["BITO", "GBTC"]
VOL = ["^VIX", "VIXY", "UVXY"]
FX = ["UUP", "FXE", "FXY", "FXA"]
REIT = ["VNQ", "IYR"]

ALL = (PRIMARY + BENCHMARK + EXPANSION + CANARY + INTL + FACTOR + THEMATIC
       + BONDS + COMMOD + CRYPTO + VOL + FX + REIT)


def bucket_by_start(starts: dict) -> None:
    buckets = {"<=2005": [], "2006-2010": [], "2011-2015": [], "2016+": []}
    for t, s in starts.items():
        y = int(s[:4])
        if y <= 2005:
            buckets["<=2005"].append(t)
        elif y <= 2010:
            buckets["2006-2010"].append(t)
        elif y <= 2015:
            buckets["2011-2015"].append(t)
        else:
            buckets["2016+"].append(t)
    print("\n--- start-date buckets ---")
    for k, v in buckets.items():
        print(f"  {k} ({len(v)}): {sorted(v)}")


def alignment_check() -> None:
    files = list(CLEAN_DIR.glob("*.parquet"))
    if len(files) < 5:
        print("alignment check: not enough files")
        return
    rng = np.random.default_rng(0)
    pick = rng.choice(files, size=5, replace=False)
    print("\n--- alignment check (5 random tickers) ---")
    dfs = {p.stem: load_clean(p) for p in pick}
    common_start = max(d.index.min() for d in dfs.values())
    common_end = min(d.index.max() for d in dfs.values())
    ref = None
    for name, d in dfs.items():
        sliced = d.loc[common_start:common_end].index
        if ref is None:
            ref = sliced
            print(f"  ref={name}  {sliced.min().date()}..{sliced.max().date()}  rows={len(sliced)}")
        else:
            same = sliced.equals(ref)
            print(f"  {name}: equal={same}  rows={len(sliced)}")


def spot_checks() -> None:
    print("\n--- spot checks ---")
    spy = load_clean(CLEAN_DIR / "SPY.parquet")
    for d in ["2020-02-19", "2020-03-23"]:
        v = spy["adj_close"].asof(pd.Timestamp(d))
        print(f"  SPY adj_close on {d}: {v:.2f}")
    gld = load_clean(CLEAN_DIR / "GLD.parquet")
    print(f"  GLD min adj_close: {gld['adj_close'].min():.2f}")
    vix_p = CLEAN_DIR / "_VIX.parquet"
    if vix_p.exists():
        vix = load_clean(vix_p)
        print(f"  ^VIX close on 2020-03-16: {vix['close'].asof(pd.Timestamp('2020-03-16')):.2f}")


def tech_overlap() -> None:
    print("\n--- tech overlap (2018-2024 63d return corr) ---")
    tickers = ["SOXX", "QQQ", "XLK", "VGT", "IGV"]
    closes = {}
    for t in tickers:
        p = CLEAN_DIR / f"{t}.parquet"
        if p.exists():
            closes[t] = load_clean(p)["adj_close"]
    px = pd.DataFrame(closes).loc["2018-01-01":"2024-12-31"]
    rets = px.pct_change(63)
    corr = rets.corr()
    print(corr.round(3).to_string())
    n = len(corr)
    avg = (corr.values.sum() - n) / (n * n - n)
    print(f"  average pairwise corr: {avg:.3f}")


def main() -> None:
    print(f"total tickers requested: {len(ALL)}")
    summary = fetch_universe(ALL, start="2005-01-01", batch_size=12, pause=1.0)
    print(f"\nok={len(summary['ok'])}  failed={len(summary['failed'])}")
    if summary["failed"]:
        print(f"failed tickers: {summary['failed']}")
    bucket_by_start(summary["starts"])
    alignment_check()
    spot_checks()
    tech_overlap()


if __name__ == "__main__":
    main()
