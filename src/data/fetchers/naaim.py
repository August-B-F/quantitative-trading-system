"""NAAIM Exposure Index.

Weekly mean equity exposure of NAAIM active investment managers.
The program page embeds only the last ~10 rows in HTML; the full history
is in a linked xlsx export (filename includes the last update date),
so we scrape the page to discover the link and download the file.
"""
from __future__ import annotations

import io
import re

import pandas as pd
import requests
from bs4 import BeautifulSoup

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

CLEAN_DIR = DATA_DIR / "clean" / "sentiment"
PAGE = "https://www.naaim.org/programs/naaim-exposure-index/"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    ),
}
XLSX_RE = re.compile(r"https?://[^\s\"'>]+\.xlsx", re.I)


def _find_xlsx(html: str) -> str | None:
    # Prefer the "since-inception" history file
    candidates = XLSX_RE.findall(html)
    for c in candidates:
        if "inception" in c.lower() or "history" in c.lower() or "since" in c.lower():
            return c
    return candidates[0] if candidates else None


def _parse_xlsx(blob: bytes) -> pd.DataFrame:
    raw = pd.read_excel(io.BytesIO(blob), sheet_name=0, header=None)
    # find header row
    header_row = None
    for i in range(min(10, len(raw))):
        row = [str(v).lower() for v in raw.iloc[i].tolist()]
        if any("date" in v for v in row) and any("mean" in v or "average" in v for v in row):
            header_row = i
            break
    if header_row is None:
        return pd.DataFrame()
    headers = [str(v).strip() for v in raw.iloc[header_row].tolist()]
    df = raw.iloc[header_row + 1:].copy()
    df.columns = headers
    date_col = next((c for c in df.columns if "date" in str(c).lower()), None)
    mean_col = next((c for c in df.columns if "mean" in str(c).lower() or "average" in str(c).lower()), None)
    if not date_col or not mean_col:
        return pd.DataFrame()
    out = pd.DataFrame({
        "naaim_exposure": pd.to_numeric(df[mean_col], errors="coerce"),
    })
    out.index = pd.to_datetime(df[date_col], errors="coerce")
    out = out.dropna().sort_index()
    out.index.name = "date"
    # Optional extra columns
    for name, col in (("naaim_bullish", "Bullish"), ("naaim_bearish", "Bearish"), ("naaim_deviation", "Deviation")):
        match = next((c for c in df.columns if str(c).strip().lower() == col.lower()), None)
        if match is not None:
            vals = pd.to_numeric(df[match], errors="coerce").values
            out[name] = pd.Series(vals, index=pd.to_datetime(df[date_col], errors="coerce")).reindex(out.index)
    return out


def main() -> None:
    CLEAN_DIR.mkdir(parents=True, exist_ok=True)
    print(f"[naaim] GET {PAGE}")
    try:
        r = requests.get(PAGE, headers=HEADERS, timeout=45)
    except requests.RequestException as e:
        log_failure(FAILED_PATH, "naaim", f"page error: {e}", attempted=PAGE)
        return
    if r.status_code != 200:
        log_failure(FAILED_PATH, "naaim", f"HTTP {r.status_code}", attempted=PAGE)
        return
    xlsx_url = _find_xlsx(r.text)
    if not xlsx_url:
        log_failure(FAILED_PATH, "naaim", "no xlsx link on page", attempted=PAGE)
        return
    print(f"[naaim] xlsx -> {xlsx_url}")
    try:
        r2 = requests.get(xlsx_url, headers=HEADERS, timeout=60)
    except requests.RequestException as e:
        log_failure(FAILED_PATH, "naaim", f"xlsx error: {e}", attempted=xlsx_url)
        return
    if r2.status_code != 200 or len(r2.content) < 2000:
        log_failure(FAILED_PATH, "naaim", f"xlsx HTTP {r2.status_code}", attempted=xlsx_url)
        return
    df = _parse_xlsx(r2.content)
    if df.empty:
        log_failure(FAILED_PATH, "naaim", "parse empty", attempted=xlsx_url)
        return
    aligned = align_to_trading_days(df, source_freq="weekly")
    path = CLEAN_DIR / "naaim_exposure.parquet"
    save_clean(aligned, path, metadata={"source": "naaim", "url": xlsx_url})
    validate_data(aligned, name="naaim_exposure")
    log_to_catalog(CATALOG_PATH, {
        "source": "naaim",
        "series_name": "naaim_exposure",
        "frequency": "weekly",
        "date_range": f"{aligned.index.min().date()}..{aligned.index.max().date()}",
        "file_path": str(path.relative_to(DATA_DIR.parent)).replace("\\", "/"),
        "status": "OK",
        "notes": "NAAIM mean active-manager exposure (weekly)",
    })


if __name__ == "__main__":
    main()
