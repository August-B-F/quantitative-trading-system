"""Fetch daily close data for ticker-swap equivalents not in the panel.
Tickers: SMH, IAU, VDE, IGM, BIL, IEF, BND, QQQE, USMV
Save to cache/swap_tickers.pkl as a dict {ticker: DataFrame(Date, Close)}
"""
from __future__ import annotations
import sys, pickle, warnings
from pathlib import Path

warnings.filterwarnings("ignore")
HERE = Path(__file__).resolve().parent
import yfinance as yf
import pandas as pd

TICKERS = ["SMH","IAU","VDE","IGM","BIL","IEF","BND","QQQE","USMV"]

OUT = HERE.parent / "cache" / "swap_tickers.pkl"


def main():
    data = {}
    for t in TICKERS:
        try:
            df = yf.download(t, start="2005-01-01", end="2026-04-14",
                            progress=False, auto_adjust=True)
            if df is None or df.empty:
                print(f"{t}: empty")
                continue
            # Handle multiindex columns from yfinance >=0.2.37
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            close = df["Close"].rename(t)
            data[t] = close
            print(f"{t}: {len(close)} rows  {close.index[0].date()} -> {close.index[-1].date()}")
        except Exception as e:
            print(f"{t}: ERROR {type(e).__name__} {e}")

    with open(OUT, "wb") as f:
        pickle.dump(data, f)
    print(f"\nSaved {len(data)} tickers to {OUT}")


if __name__ == "__main__":
    main()
