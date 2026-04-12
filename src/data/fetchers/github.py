"""GitHub commit activity fetcher. Aggregates weekly commit counts per company.

Uses /repos/{owner}/{repo}/stats/participation which returns 52 weeks of weekly
totals. Optional GITHUB_TOKEN env var raises rate limits. Note: this gives only
the most recent ~52 weeks; longer history is not available via this endpoint.
"""
from __future__ import annotations

import json
import os
import time
import urllib.request
from datetime import datetime, timedelta, timezone

import pandas as pd

from src.data.utils import (
    CATALOG_PATH,
    DATA_DIR,
    FAILED_PATH,
    align_to_trading_days,
    log_failure,
    log_to_catalog,
    save_clean,
)

CLEAN_DIR = DATA_DIR / "clean" / "alternative"

COMPANIES = {
    "microsoft": [("microsoft", "vscode"), ("microsoft", "TypeScript"), ("Azure", "azure-sdk-for-python")],
    "google":    [("tensorflow", "tensorflow"), ("chromium", "chromium")],
    "meta":      [("facebook", "react"), ("pytorch", "pytorch")],
    "apple":     [("apple", "swift")],
    "nvidia":    [("NVIDIA", "cuda-samples"), ("NVIDIA", "TensorRT")],
    "amd":       [("ROCm", "ROCm")],
}

BASE = "https://api.github.com/repos/{owner}/{repo}/stats/participation"


def _get(owner: str, repo: str, timeout: int = 60) -> list[int] | None:
    url = BASE.format(owner=owner, repo=repo)
    req = urllib.request.Request(url, headers={"User-Agent": "quant-bot/1.0", "Accept": "application/vnd.github+json"})
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                if resp.status == 202:
                    time.sleep(2 ** attempt)
                    continue
                payload = json.loads(resp.read())
            return payload.get("all", [])
        except Exception as e:
            print(f"  ! {owner}/{repo}: {e}")
            return None
    return None


def main() -> None:
    CLEAN_DIR.mkdir(parents=True, exist_ok=True)
    end = datetime.now(timezone.utc).date()
    # Endpoint returns 52 weekly counts ending today
    # GitHub returns 52 weekly counts ending on the most recent Sunday; map them to
    # the trailing Friday so the index lands on NYSE trading days (W-SUN never does).
    weeks = pd.date_range(end=end, periods=52, freq="W-SUN") - pd.Timedelta(days=2)
    for company, repos in COMPANIES.items():
        print(f"[github] {company}")
        agg = pd.Series(0, index=weeks, dtype=float)
        ok = False
        for owner, repo in repos:
            arr = _get(owner, repo)
            if not arr or len(arr) != 52:
                log_failure(FAILED_PATH, f"github:{owner}/{repo}", "no participation data", attempted=BASE)
                continue
            s = pd.Series(arr, index=weeks, dtype=float)
            agg = agg.add(s, fill_value=0)
            ok = True
            time.sleep(0.5)
        if not ok:
            continue
        df = agg.to_frame(name=f"github_{company}_weekly_commits")
        aligned = align_to_trading_days(df, source_freq="weekly")
        path = CLEAN_DIR / f"github_{company}.parquet"
        save_clean(aligned, path, metadata={"source": "github", "company": company, "repos": [f"{o}/{r}" for o, r in repos]})
        log_to_catalog(CATALOG_PATH, {
            "source": "github",
            "series_name": f"github_{company}",
            "frequency": "weekly",
            "date_range": f"{aligned.index.min().date()}..{aligned.index.max().date()}",
            "file_path": str(path.relative_to(DATA_DIR.parent)).replace("\\", "/"),
            "status": "SHORT",
            "notes": "history capped at 52 weeks by GitHub API",
        })


if __name__ == "__main__":
    main()
