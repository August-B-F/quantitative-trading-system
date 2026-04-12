"""USPTO PatentsView fetcher. Annual patent grant counts per assignee.

PatentsView API now requires an API key (PATENTSVIEW_API_KEY env var). If
absent, logs failure and exits without raising.
"""
from __future__ import annotations

import json
import os
import time
import urllib.request

import pandas as pd

from src.data.utils import (
    CATALOG_PATH,
    DATA_DIR,
    FAILED_PATH,
    log_failure,
    log_to_catalog,
    save_clean,
)

CLEAN_DIR = DATA_DIR / "clean" / "alternative"

URL = "https://search.patentsview.org/api/v1/patent/"

COMPANIES = {
    "nvidia":    ["nvidia"],
    "amd":       ["advanced micro devices"],
    "intel":     ["intel"],
    "tsmc":      ["taiwan semiconductor"],
    "samsung":   ["samsung electronics"],
    "qualcomm":  ["qualcomm"],
    "apple":     ["apple inc"],
    "microsoft": ["microsoft"],
    "google":    ["google", "alphabet"],
}


def _query(name: str, key: str, timeout: int = 60):
    body = {
        "q": {"_text_phrase": {"assignees.assignee_organization": name}},
        "f": ["patent_id", "patent_date"],
        "o": {"size": 10000},
    }
    data = json.dumps(body).encode()
    req = urllib.request.Request(URL, data=data, headers={
        "Content-Type": "application/json",
        "X-Api-Key": key,
        "User-Agent": "quant-bot/1.0",
    })
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def main() -> None:
    CLEAN_DIR.mkdir(parents=True, exist_ok=True)
    key = os.environ.get("PATENTSVIEW_API_KEY")
    if not key:
        for c in COMPANIES:
            log_failure(FAILED_PATH, f"uspto:{c}", "PATENTSVIEW_API_KEY env var not set", attempted=URL)
        print("[uspto] no PATENTSVIEW_API_KEY set, skipping all")
        return
    for company, names in COMPANIES.items():
        print(f"[uspto] {company}")
        rows = []
        for name in names:
            try:
                payload = _query(name, key)
            except Exception as e:
                print(f"  ! {company}/{name}: {e}")
                log_failure(FAILED_PATH, f"uspto:{company}", str(e), attempted=name)
                continue
            patents = payload.get("patents", []) or []
            for p in patents:
                d = p.get("patent_date")
                if d:
                    rows.append(d)
            time.sleep(1.0)
        if not rows:
            continue
        s = pd.to_datetime(pd.Series(rows), errors="coerce").dropna()
        annual = s.groupby(s.dt.year).size()
        df = pd.DataFrame({f"patents_{company}_annual": annual.values},
                          index=pd.to_datetime([f"{y}-12-31" for y in annual.index]))
        path = CLEAN_DIR / f"patents_{company}.parquet"
        save_clean(df, path, metadata={"source": "patentsview", "company": company})
        log_to_catalog(CATALOG_PATH, {
            "source": "uspto",
            "series_name": f"patents_{company}",
            "frequency": "annual",
            "date_range": f"{df.index.min().date()}..{df.index.max().date()}",
            "file_path": str(path.relative_to(DATA_DIR.parent)).replace("\\", "/"),
            "status": "OK",
            "notes": "annual grant counts via PatentsView",
        })


if __name__ == "__main__":
    main()
