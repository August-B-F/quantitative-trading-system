"""Google Trends weekly interest via pytrends.

Heavy rate-limiting from Google. We sleep 45s between queries and
stop on repeated 429s. Each query is normalized independently (0-100
relative scale).
"""
from __future__ import annotations

import time

import pandas as pd

from src.data.utils import (
    CATALOG_PATH,
    DATA_DIR,
    FAILED_PATH,
    align_to_trading_days,
    log_failure,
    log_to_catalog,
    save_clean,
    validate_data,
)

CLEAN_DIR = DATA_DIR / "clean" / "alternative"

TERMS: list[str] = [
    "recession", "inflation", "oil price", "semiconductor shortage",
    "tech stocks", "gold buy", "stock market crash", "layoffs",
    "bankruptcy", "interest rates", "AI stocks", "buy gold",
    "bear market", "bull market", "bitcoin price", "energy crisis",
    "housing crash", "bank run", "unemployment",
]
TIMEFRAME = "2010-01-01 2026-04-12"
SLEEP = 45


def _slug(term: str) -> str:
    return term.lower().replace(" ", "_")


def main() -> None:
    CLEAN_DIR.mkdir(parents=True, exist_ok=True)
    try:
        from pytrends.request import TrendReq
    except Exception as e:
        log_failure(FAILED_PATH, "google_trends", f"pytrends import: {e}", attempted="pytrends")
        return

    py = TrendReq(hl="en-US", tz=360, timeout=(10, 30), retries=2, backoff_factor=1.5)
    fails = 0
    for i, term in enumerate(TERMS):
        print(f"[gtrends] ({i + 1}/{len(TERMS)}) {term}")
        try:
            py.build_payload([term], timeframe=TIMEFRAME, geo="US")
            df = py.interest_over_time()
        except Exception as e:
            msg = str(e)
            print(f"  ! {term}: {msg}")
            log_failure(FAILED_PATH, f"google_trends:{term}", msg[:200], attempted="pytrends")
            fails += 1
            if fails >= 3 and i >= 8:
                print("[gtrends] too many failures, stopping after priority terms")
                break
            time.sleep(SLEEP * 2)
            continue
        if df is None or df.empty:
            log_failure(FAILED_PATH, f"google_trends:{term}", "empty", attempted="pytrends")
            time.sleep(SLEEP)
            continue
        if "isPartial" in df.columns:
            df = df.drop(columns=["isPartial"])
        col = df.columns[0]
        clean = df.rename(columns={col: f"gtrends_{_slug(term)}"})
        clean.index = pd.to_datetime(clean.index)
        aligned = align_to_trading_days(clean, source_freq="weekly")
        path = CLEAN_DIR / f"gtrends_{_slug(term)}.parquet"
        save_clean(aligned, path, metadata={"source": "google_trends", "term": term, "timeframe": TIMEFRAME})
        validate_data(aligned, name=path.stem)
        log_to_catalog(CATALOG_PATH, {
            "source": "google_trends",
            "series_name": path.stem,
            "frequency": "weekly",
            "date_range": f"{aligned.index.min().date()}..{aligned.index.max().date()}",
            "file_path": str(path.relative_to(DATA_DIR.parent)).replace("\\", "/"),
            "status": "OK",
            "notes": f"relative search interest (0-100) for '{term}'",
        })
        time.sleep(SLEEP)


if __name__ == "__main__":
    main()
