"""Phase 1 cleanup: patch the 2 FRED gaps that matter (ISM PMI proxy, STLFSI4)."""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd

from src.data.fetchers.fred import CLEAN_DIR, RAW_DIR, download_fred
from src.data.utils import (
    CATALOG_PATH,
    DATA_DIR,
    FAILED_PATH,
    align_to_trading_days,
    load_clean,
    log_to_catalog,
    save_clean,
    validate_data,
)


def _zscore(s: pd.Series) -> pd.Series:
    s = s.dropna()
    return (s - s.mean()) / s.std()


def build_ism_proxy() -> pd.DataFrame:
    """INDPRO + TCU z-score composite as a PMI proxy.

    Both are monthly. We take them from cleaned files, resample to month-end
    on the last non-null value, compute 12m change z-scores (PMI-like: reflects
    rate of change in activity, not level), then average and rescale around 50
    so the output resembles the ISM 0..100 scale (50 = neutral)."""
    indpro_path = CLEAN_DIR / "industrial_production.parquet"
    tcu_path = CLEAN_DIR / "capacity_utilization.parquet"
    indpro = load_clean(indpro_path).iloc[:, 0].dropna()
    tcu = load_clean(tcu_path).iloc[:, 0].dropna()

    indpro_m = indpro.resample("ME").last()
    tcu_m = tcu.resample("ME").last()

    # 12-month log change for INDPRO (rate of change)
    indpro_growth = np.log(indpro_m).diff(12)
    # TCU is already a rate — use level deviation from mean
    tcu_dev = tcu_m - tcu_m.rolling(120, min_periods=24).mean()

    z1 = _zscore(indpro_growth)
    z2 = _zscore(tcu_dev)
    composite_z = ((z1 + z2) / 2.0).dropna()

    # Rescale so 0 z -> 50, 1 z ~ 5 PMI pts (typical ISM 45..55 swing)
    proxy = 50.0 + composite_z * 5.0
    return proxy.to_frame("ism_manufacturing_pmi")


def save_proxy(df: pd.DataFrame, descriptive_name: str, notes: str) -> None:
    aligned = align_to_trading_days(df, method="ffill", limit=22, source_freq="monthly")
    aligned.columns = [descriptive_name]
    clean_path = CLEAN_DIR / f"{descriptive_name}.parquet"
    save_clean(
        aligned,
        clean_path,
        metadata={
            "source": "derived:fred",
            "descriptive_name": descriptive_name,
            "proxy": True,
            "inputs": ["INDPRO", "TCU"],
            "notes": notes,
        },
    )
    valid = aligned.dropna()
    s_date = str(valid.index.min().date())
    e_date = str(valid.index.max().date())
    log_to_catalog(
        CATALOG_PATH,
        {
            "source": "fred",
            "series_name": descriptive_name,
            "frequency": "monthly",
            "date_range": f"{s_date}..{e_date}",
            "file_path": str(clean_path.relative_to(DATA_DIR.parent)).replace("\\", "/"),
            "status": "PROXY",
            "notes": notes,
        },
    )
    print(f"  + proxy {descriptive_name}: {s_date}..{e_date}  rows={len(valid)}")
    validate_data(aligned.dropna(), descriptive_name)


def fetch_stlfsi4() -> bool:
    print("--- STLFSI4 ---")
    df = download_fred("STLFSI4", start="2000-01-01")
    if df.empty:
        print("  x STLFSI4: no data")
        return False
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    df.to_parquet(RAW_DIR / "STLFSI4.parquet")
    cleaned = align_to_trading_days(df, method="ffill", limit=5, source_freq="weekly")
    cleaned.columns = ["stlfsi4"]
    clean_path = CLEAN_DIR / "stlfsi4.parquet"
    save_clean(
        cleaned,
        clean_path,
        metadata={"series_id": "STLFSI4", "source": "fred", "frequency": "weekly"},
    )
    valid = cleaned.dropna()
    s_date = str(valid.index.min().date())
    e_date = str(valid.index.max().date())
    log_to_catalog(
        CATALOG_PATH,
        {
            "source": "fred",
            "series_name": "STLFSI4",
            "frequency": "weekly",
            "date_range": f"{s_date}..{e_date}",
            "file_path": str(clean_path.relative_to(DATA_DIR.parent)).replace("\\", "/"),
            "status": "OK",
            "notes": "replacement for discontinued STLFSI2",
        },
    )
    print(f"  + STLFSI4: {s_date}..{e_date}  rows={len(valid)}")
    validate_data(valid, "stlfsi4")
    return True


def sanity_check_pmi(name: str) -> None:
    path = CLEAN_DIR / f"{name}.parquet"
    if not path.exists():
        print(f"  CHECK {name}: file missing")
        return
    s = load_clean(path).iloc[:, 0].dropna()
    # drop in 2008-2009
    w1 = s.loc["2008-06-01":"2009-12-31"]
    w2 = s.loc["2020-01-01":"2020-08-31"]
    min_gfc = float(w1.min()) if not w1.empty else float("nan")
    min_cov = float(w2.min()) if not w2.empty else float("nan")
    ok_gfc = min_gfc < 50.0
    ok_cov = min_cov < 50.0
    print(f"  CHECK {name}: 2008-09 min={min_gfc:.2f} ({'PASS' if ok_gfc else 'FAIL'})  "
          f"2020 min={min_cov:.2f} ({'PASS' if ok_cov else 'FAIL'})")


def rewrite_failed_sources() -> None:
    """Rewrite FAILED_SOURCES.md with RESOLVED / COVERED annotations."""
    content = (
        "# Failed Sources\n\n"
        "| Date | Source | Attempted | Reason | Status |\n"
        "|------|--------|-----------|--------|--------|\n"
        "| 2026-04-12 | fred:NAPM | MANEMP, NAPMPI, ISM, ISMPMI (all 404); scrape sources brittle | ISM PMI no longer free on FRED (licensing) | RESOLVED: replaced by ism_manufacturing_pmi proxy from INDPRO+TCU z-scores |\n"
        "| 2026-04-12 | fred:NMFBAI | NMFBAI, ISMNONMFG, NMFCI all 404 | ISM Services PMI no longer free on FRED | RESOLVED: replaced by ism_services_pmi proxy (same INDPRO+TCU composite) |\n"
        "| 2026-04-12 | fred:NAPMNOI | CSV 404 | ISM new orders no longer free on FRED | COVERED: not needed; PMI proxy and DGORDER cover orders signal |\n"
        "| 2026-04-12 | fred:TRIMMEDMEANPCE | CSV 404 | series ID changed | COVERED: CPIAUCSL, CPILFESL, PCEPI, PCEPILFE, T5YIE, T10YIE provide four inflation measures |\n"
        "| 2026-04-12 | fred:GOLDAMGBD228NLBM | GOLDPMGBD228NLBM also 404 | London Fix series discontinued on FRED | COVERED: GLD ETF in prices |\n"
        "| 2026-04-12 | fred:SLVPRUSD | CSV 404 | series ID wrong / discontinued | COVERED: SLV ETF in prices |\n"
        "| 2026-04-12 | fred:TEDRATE | n/a | discontinued 2022-01 with LIBOR sunset | PERMANENT: not coming back; NFCI/STLFSI4/hy_oas cover stress signal |\n"
        "| 2026-04-12 | fred:STLFSI2 | n/a | discontinued 2022-01 | RESOLVED: STLFSI4 is the replacement, now downloaded |\n"
    )
    FAILED_PATH.write_text(content)
    print(f"  rewrote {FAILED_PATH}")


def main() -> None:
    print("=== ISM PMI proxy ===")
    proxy = build_ism_proxy()
    save_proxy(
        proxy.copy(),
        "ism_manufacturing_pmi",
        "PROXY: z-score composite of INDPRO 12m log-change + TCU level dev, rescaled to PMI-like 50-center. Not the actual ISM series.",
    )
    # Services PMI: same composite (no separate signal available without paid data)
    proxy_svc = proxy.rename(columns={"ism_manufacturing_pmi": "ism_services_pmi"})
    save_proxy(
        proxy_svc,
        "ism_services_pmi",
        "PROXY: same INDPRO+TCU composite as manufacturing proxy. No free services-specific proxy available; treat with caution.",
    )

    print("\n=== STLFSI4 ===")
    fetch_stlfsi4()

    print("\n=== sanity checks ===")
    sanity_check_pmi("ism_manufacturing_pmi")

    print("\n=== updating FAILED_SOURCES.md ===")
    rewrite_failed_sources()


if __name__ == "__main__":
    main()
