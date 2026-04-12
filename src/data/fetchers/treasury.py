"""Treasury auction fetcher. Uses FiscalData (Treasury) public JSON API."""
from __future__ import annotations

import json
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

CLEAN_DIR = DATA_DIR / "clean" / "macro"

# Fiscal Data: Treasury Securities Auctions Data
BASE = ("https://api.fiscaldata.treasury.gov/services/api/fiscal_service/"
        "v1/accounting/od/auctions_query")

WANTED = [
    ("note_10y", "Note", "10-Year"),
    ("bond_30y", "Bond", "30-Year"),
    ("note_2y",  "Note", "2-Year"),
]


def _get_page(page: int, size: int = 10000, timeout: int = 90):
    url = f"{BASE}?page[size]={size}&page[number]={page}&sort=auction_date"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def _fetch_all() -> pd.DataFrame:
    rows = []
    for page in range(1, 50):
        payload = _get_page(page)
        data = payload.get("data", [])
        if not data:
            break
        rows.extend(data)
        meta = payload.get("meta", {})
        total_pages = (meta.get("total-pages") or meta.get("totalPages") or 1)
        if page >= int(total_pages):
            break
    return pd.DataFrame(rows)


def main() -> None:
    CLEAN_DIR.mkdir(parents=True, exist_ok=True)
    print("[treasury] auction history (FiscalData)")
    try:
        df = _fetch_all()
    except Exception as e:
        print(f"  ! {e}")
        log_failure(FAILED_PATH, "treasury:auctions", str(e), attempted=BASE)
        return
    if df.empty:
        log_failure(FAILED_PATH, "treasury:auctions", "empty payload", attempted=BASE)
        return

    if "auction_date" not in df.columns:
        log_failure(FAILED_PATH, "treasury:auctions", f"no auction_date col; have {list(df.columns)[:10]}", attempted=BASE)
        return
    df["auction_date"] = pd.to_datetime(df["auction_date"], errors="coerce")
    df = df.dropna(subset=["auction_date"])

    btc_col = next((c for c in df.columns if c.lower() in ("bid_to_cover_ratio", "bidtocoverratio")), None)
    if btc_col is None:
        log_failure(FAILED_PATH, "treasury:auctions", f"no bid-to-cover col; have {list(df.columns)[:20]}", attempted=BASE)
        return

    type_col = "security_type" if "security_type" in df.columns else None
    term_col = "security_term" if "security_term" in df.columns else None
    if type_col is None or term_col is None:
        log_failure(FAILED_PATH, "treasury:auctions", "missing security_type/term", attempted=BASE)
        return

    rows_out = []
    for key, sec_type, term in WANTED:
        sub = df[(df[type_col] == sec_type) & (df[term_col] == term)].copy()
        if sub.empty:
            continue
        sub["contract"] = key
        sub = sub[["auction_date", btc_col, "contract"]].rename(
            columns={"auction_date": "date", btc_col: "bid_to_cover"}
        )
        sub["bid_to_cover"] = pd.to_numeric(sub["bid_to_cover"], errors="coerce")
        rows_out.append(sub.dropna(subset=["bid_to_cover"]))

    if not rows_out:
        log_failure(FAILED_PATH, "treasury:auctions", "no rows for any wanted contract", attempted=BASE)
        return

    out = pd.concat(rows_out).sort_values("date").set_index("date")
    path = CLEAN_DIR / "treasury_auctions.parquet"
    save_clean(out, path, metadata={"source": "fiscaldata", "type": "event"})
    log_to_catalog(CATALOG_PATH, {
        "source": "treasury",
        "series_name": "treasury_auctions",
        "frequency": "event",
        "date_range": f"{out.index.min().date()}..{out.index.max().date()}",
        "file_path": str(path.relative_to(DATA_DIR.parent)).replace("\\", "/"),
        "status": "OK",
        "notes": "bid-to-cover for 2y/10y/30y from FiscalData",
    })


if __name__ == "__main__":
    main()
