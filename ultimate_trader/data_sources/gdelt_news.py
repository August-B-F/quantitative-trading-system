"""GDELT news sentiment fetcher for macro-level market context features.

Provides: gdelt_avg_tone, gdelt_article_count, gdelt_goldstein_scale
These are aggregated market-level signals (not per-symbol) fed into macro branch.

Rate limit: 1 request/second per GDELT API ToS.
Cache: data/raw/gdelt/{symbol}.parquet
Coverage: 2018-present for training data.
"""
import os
import time
import pandas as pd
import numpy as np
from typing import List, Optional
from ultimate_trader.utils.logging import get_logger

logger = get_logger(__name__)

GDELT_CACHE_DIR = "data/raw/gdelt"
_GDELT_API = "https://api.gdeltproject.org/api/v2/doc/doc"


class GDELTFetcher:
    """
    Fetches news sentiment data from the GDELT 2.0 API.

    Uses the 'timelinetone' and 'timelinevolinfo' query modes which return
    aggregated daily tone scores and article volumes — no per-article scraping.

    Results are cached as parquet files and merged into the macro feature
    DataFrame by AltDataBuilder.
    """

    def __init__(self, cache_dir: str = GDELT_CACHE_DIR):
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)

    def fetch(self, query: str, start: str, end: str,
              cache_key: str = "market") -> pd.DataFrame:
        """
        Fetch GDELT tone data for a query term over a date range.

        Args:
            query:     Search query (e.g. 'stock market')
            start:     Start date 'YYYY-MM-DD'
            end:       End date 'YYYY-MM-DD'
            cache_key: Filename key for parquet cache

        Returns:
            Date-indexed DataFrame with columns:
            gdelt_avg_tone, gdelt_article_count, gdelt_goldstein_scale
        """
        cache_path = os.path.join(self.cache_dir, f"{cache_key}.parquet")

        # Check cache
        if os.path.exists(cache_path):
            try:
                cached = pd.read_parquet(cache_path)
                start_ts = pd.Timestamp(start)
                end_ts = pd.Timestamp(end)
                if (len(cached) > 0
                        and cached.index.min() <= start_ts
                        and cached.index.max() >= end_ts - pd.Timedelta(days=14)):
                    logger.debug(f"GDELT cache hit for {cache_key}")
                    return cached[start:end]
            except Exception:
                pass

        df = self._fetch_chunked(query, start, end)
        if not df.empty:
            try:
                df.to_parquet(cache_path)
            except Exception as e:
                logger.debug(f"GDELT cache write failed: {e}")
        return df

    def _fetch_chunked(self, query: str, start: str, end: str) -> pd.DataFrame:
        """Fetch in 3-month chunks (GDELT API limit)."""
        try:
            import httpx
        except ImportError:
            logger.warning("httpx not installed — GDELT features disabled. Run: pip install httpx")
            return pd.DataFrame()

        start_ts = pd.Timestamp(start)
        end_ts = pd.Timestamp(end)

        tone_frames = []
        vol_frames = []
        current = start_ts

        while current < end_ts:
            chunk_end = min(current + pd.DateOffset(months=3), end_ts)
            s = current.strftime("%Y%m%d%H%M%S")
            e = chunk_end.strftime("%Y%m%d%H%M%S")

            # Tone timeline
            tone_df = self._query_api(httpx, query, s, e, mode="timelinetone")
            if tone_df is not None:
                tone_frames.append(tone_df)

            time.sleep(1.0)  # rate limit

            # Volume timeline
            vol_df = self._query_api(httpx, query, s, e, mode="timelinevolinfo")
            if vol_df is not None:
                vol_frames.append(vol_df)

            time.sleep(1.0)
            current = chunk_end

        if not tone_frames:
            return pd.DataFrame()

        tone = pd.concat(tone_frames).sort_index()
        tone = tone[~tone.index.duplicated(keep="last")]

        result = pd.DataFrame(index=tone.index)
        result["gdelt_avg_tone"] = tone.get("avg_tone", 0.0)
        result["gdelt_goldstein_scale"] = tone.get("goldstein", 0.0)

        if vol_frames:
            vol = pd.concat(vol_frames).sort_index()
            vol = vol[~vol.index.duplicated(keep="last")]
            result["gdelt_article_count"] = vol.reindex(result.index).get(
                "article_count", 0.0
            ).fillna(0.0)
        else:
            result["gdelt_article_count"] = 0.0

        return result

    def _query_api(self, httpx_mod, query: str, start: str, end: str,
                   mode: str) -> Optional[pd.DataFrame]:
        """Single GDELT API request, returns parsed DataFrame or None."""
        import urllib.parse
        encoded_query = urllib.parse.quote(query)
        url = (
            f"{_GDELT_API}"
            f"?query={encoded_query}&mode={mode}"
            f"&startdatetime={start}&enddatetime={end}&format=json"
        )
        try:
            with httpx_mod.Client(timeout=30.0) as client:
                resp = client.get(url)
            if resp.status_code != 200:
                logger.debug(f"GDELT {mode} returned HTTP {resp.status_code}")
                return None
            data = resp.json()
        except Exception as e:
            logger.debug(f"GDELT {mode} request failed: {e}")
            return None

        # Both timelinetone and timelinevolinfo return:
        # {"timeline": [{"date": "YYYYMMDDTHHMMSSZ", "value": float}, ...]}
        # (timelinetone also has "value2" = positive tone, "value3" = goldstein in some endpoints)
        timeline = data.get("timeline", [])
        if not timeline:
            return None

        rows = []
        for entry in timeline:
            try:
                date_str = entry.get("date", "")[:8]  # YYYYMMDD
                date = pd.Timestamp(date_str)
                if mode == "timelinetone":
                    rows.append({
                        "date": date,
                        "avg_tone": float(entry.get("value", 0)),
                        "goldstein": float(entry.get("value2", 0)),
                    })
                else:  # timelinevolinfo
                    rows.append({
                        "date": date,
                        "article_count": float(entry.get("value", 0)),
                    })
            except Exception:
                continue

        if not rows:
            return None

        df = pd.DataFrame(rows).set_index("date")
        df.index = pd.DatetimeIndex(df.index)
        return df.sort_index()

    def fetch_market_sentiment(
        self,
        start: str = "2018-01-01",
        end: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        Fetch broad US equity market sentiment from GDELT.
        Returns date-indexed DataFrame with gdelt_avg_tone, gdelt_article_count,
        gdelt_goldstein_scale columns ready to merge into macro_df.
        """
        if end is None:
            end = pd.Timestamp.now().strftime("%Y-%m-%d")
        return self.fetch(
            query="stock market economy finance",
            start=start,
            end=end,
            cache_key="market_sentiment",
        )
