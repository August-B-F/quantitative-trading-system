# ARCHIVED: one-off retry script — superseded by phase1_* pipeline
"""Session 3.5 retry: fetch buyback/rail/bond-issuance/bankruptcy via FRED curl.

Uses curl subprocess because Python requests/urllib hangs on fredgraph.csv in
this environment (HTTP/2 negotiation issue). curl works fine.
"""
from __future__ import annotations

import io
import subprocess
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.data.utils import (  # noqa: E402
    CATALOG_PATH,
    DATA_DIR,
    FAILED_PATH,
    align_to_trading_days,
    log_failure,
    log_to_catalog,
    save_clean,
    validate_data,
)


def fred_curl(series_id: str, timeout: int = 30) -> pd.DataFrame:
    r = subprocess.run(
        [
            "curl", "-s", "-o", "-", "-w", "\n%{http_code}",
            "--max-time", str(timeout),
            f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}",
        ],
        capture_output=True, text=True,
    )
    parts = r.stdout.rsplit("\n", 1)
    if len(parts) < 2 or parts[1] != "200":
        return pd.DataFrame()
    df = pd.read_csv(io.StringIO(parts[0]))
    date_col = "observation_date" if "observation_date" in df.columns else "DATE"
    df[date_col] = pd.to_datetime(df[date_col])
    df = df.set_index(date_col).sort_index()
    df.index.name = None
    for c in df.columns:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df.dropna(how="all")


def save_series(
    series_id: str,
    clean_name: str,
    subdir: str,
    source_freq: str,
    description: str,
    proxy_note: str = "",
) -> dict:
    out_dir = DATA_DIR / "clean" / subdir
    out_dir.mkdir(parents=True, exist_ok=True)
    df = fred_curl(series_id)
    if df.empty:
        log_failure(FAILED_PATH, f"fred:{series_id}", "curl returned empty", "")
        return {"series_id": series_id, "ok": False}
    df.columns = [clean_name]
    aligned = align_to_trading_days(df, source_freq=source_freq)
    path = out_dir / f"{clean_name}.parquet"
    save_clean(
        aligned,
        path,
        metadata={
            "series_id": series_id,
            "source": "fred",
            "source_frequency": source_freq,
            "description": description,
            "proxy_note": proxy_note,
        },
    )
    validate_data(aligned, name=clean_name)
    valid = aligned.dropna()
    s = str(valid.index.min().date())
    e = str(valid.index.max().date())
    log_to_catalog(CATALOG_PATH, {
        "source": "fred",
        "series_name": series_id,
        "frequency": source_freq,
        "date_range": f"{s}..{e}",
        "file_path": str(path.relative_to(DATA_DIR.parent)).replace("\\", "/"),
        "status": "OK",
        "notes": proxy_note or description,
    })
    return {
        "series_id": series_id, "ok": True, "rows": int(len(aligned)),
        "start": s, "end": e,
    }


def main() -> None:
    results = []
    # --- Source 3: S&P 500 buyback yield proxy ---
    # BOGZ1FA106121075Q = Nonfinancial Corporate Business; Net Equity Issuance
    # (Z.1 quarterly). Negative values = net buybacks, positive = net issuance.
    results.append(("buyback", save_series(
        "BOGZ1FA106121075Q",
        "sp500_buyback_yield",
        "fundamental",
        "quarterly",
        "Nonfinancial corporate net equity issuance (Z.1). Negative = net buybacks.",
        proxy_note="proxy for SP500 buyback yield; aggregate US nonfinancial corp net equity issuance",
    )))

    # --- Source 4: Rail freight carloads ---
    # RAILFRTCARLOADSD11 = Rail Freight Carloads, monthly SA index
    results.append(("rail", save_series(
        "RAILFRTCARLOADSD11",
        "rail_traffic",
        "alternative",
        "monthly",
        "Rail Freight Carloads, US, monthly SA index (FRED).",
        proxy_note="substitute for AAR weekly rail (AAR is PDF-only)",
    )))

    # --- Source 5: Corporate bond issuance proxy ---
    # NCBDBIQ027S = Nonfinancial Corporate Business; Debt Securities;
    # Liability, Transactions (quarterly Z.1). Net new issuance flow.
    results.append(("bond_issuance", save_series(
        "NCBDBIQ027S",
        "corp_bond_issuance",
        "fundamental",
        "quarterly",
        "Nonfinancial corporate business debt securities; liability transactions (Z.1).",
        proxy_note="substitute for SIFMA corp bond issuance (HubSpot form-gated); Z.1 net flow",
    )))

    # --- Source 6: Bankruptcy proxy ---
    # DRBLACBS = Delinquency Rate on Business Loans, commercial banks (quarterly).
    # Best available free proxy for corporate bankruptcy stress signal.
    results.append(("bankruptcy", save_series(
        "DRBLACBS",
        "bankruptcy_filings",
        "alternative",
        "quarterly",
        "Business loan delinquency rate, commercial banks (quarterly).",
        proxy_note="proxy for bankruptcy filings; BLS/ABI bankruptcy counts not free-downloadable",
    )))

    print("\n=== session 3.5 results ===")
    for name, r in results:
        print(f"{name}: {r}")


if __name__ == "__main__":
    main()
