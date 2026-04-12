"""Quality audit of downloaded Yahoo data."""
from __future__ import annotations
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd
from src.data.fetchers.yahoo import CLEAN_DIR
from src.data.utils import load_clean, get_trading_calendar

files = sorted(CLEAN_DIR.glob("*.parquet"))
print(f"files: {len(files)}\n")

total_rows = 0
per_ticker = []
nan_offenders = []
split_jumps_close = []   # raw close jumps
split_jumps_adj = []     # adj_close jumps (should be 0 if adjusted properly)
neg_offenders = []
freq_offenders = []

for f in files:
    df = load_clean(f)
    name = f.stem
    rows = len(df)
    total_rows += rows
    yrs = (df.index.max() - df.index.min()).days / 365.25
    per_ticker.append((name, rows, yrs, str(df.index.min().date()), str(df.index.max().date())))

    # frequency check: median spacing in business days
    diffs = df.index.to_series().diff().dt.days.dropna()
    med = diffs.median()
    if med > 1.5:
        freq_offenders.append((name, med))

    # NaN check on adj_close
    if "adj_close" in df.columns:
        nan_pct = df["adj_close"].isna().mean() * 100
        if nan_pct > 1.0:
            nan_offenders.append((name, round(nan_pct, 2)))
        if (df["adj_close"].dropna() < 0).any():
            neg_offenders.append(name)

    # split-jump test: look at single-day returns. >25% drop in raw close is a likely split.
    if "close" in df.columns and "adj_close" in df.columns:
        raw_ret = df["close"].pct_change()
        adj_ret = df["adj_close"].pct_change()
        # Volatility ETFs (UVXY, VIXY) actually have real big moves AND reverse splits
        big_raw = raw_ret[(raw_ret < -0.25) | (raw_ret > 0.50)]
        big_adj = adj_ret[(adj_ret < -0.25) | (adj_ret > 0.50)]
        if len(big_raw) > 0:
            split_jumps_close.append((name, len(big_raw)))
        if len(big_adj) > 0:
            # only count if adj also has big jumps after raw cleared (means adjustment failed)
            split_jumps_adj.append((name, len(big_adj), [str(d.date()) for d in big_adj.index[:3]]))

# summary
years_min = min(p[2] for p in per_ticker)
years_max = max(p[2] for p in per_ticker)
print(f"TOTAL data points (rows across all tickers): {total_rows:,}")
print(f"per-ticker rows: min={min(p[1] for p in per_ticker):,}  max={max(p[1] for p in per_ticker):,}  median={int(np.median([p[1] for p in per_ticker])):,}")
print(f"history span: min={years_min:.1f}y  max={years_max:.1f}y")
print(f"frequency: daily (NYSE trading days)")
print(f"non-daily offenders: {freq_offenders}")
print(f"\nNaN > 1% in adj_close: {nan_offenders or 'none'}")
print(f"negative adj_close: {neg_offenders or 'none'}")

print(f"\n--- split adjustment audit ---")
print(f"tickers with raw close jumps >25% (likely splits in raw): {len(split_jumps_close)}")
for t, n in split_jumps_close[:20]:
    print(f"  raw {t}: {n} jumps")
print(f"\ntickers with adj_close jumps >25% (these should be REAL moves, not splits):")
for t, n, dates in split_jumps_adj[:20]:
    print(f"  adj {t}: {n}  e.g. {dates}")

# quick split sanity: pick a known-split ticker and confirm raw vs adj
print(f"\n--- known-split spot check ---")
for tkr in ["NVDA", "AAPL"]:
    pass  # not in universe

# UVXY/SVXY-like reverse splits — verify adj smooths them
for tkr in ["UVXY", "VIXY"]:
    p = CLEAN_DIR / f"{tkr}.parquet"
    if p.exists():
        d = load_clean(p)
        raw_max = d["close"].max()
        raw_first = d["close"].iloc[0]
        adj_max = d["adj_close"].max()
        adj_first = d["adj_close"].iloc[0]
        print(f"  {tkr}: raw first={raw_first:.2f} max={raw_max:.2f}  |  adj first={adj_first:.2f} max={adj_max:.2f}")
        # if adjusted is much larger than raw at the start, reverse-split adjustment worked
        ratio = adj_first / raw_first if raw_first else 0
        print(f"    adj/raw at start = {ratio:.1f}x  (>1 indicates back-adjustment for reverse splits)")
