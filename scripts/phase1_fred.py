"""Phase 1: FRED macro download + derived series + validation.

Downloads ~75 macro series from FRED via direct CSV fallback, aligns them
to NYSE trading days, computes derived spreads / YoY transforms, and runs
sanity checks (inverted yield curve 2022-23, CPI peak mid-2022, VIX~NFCI).
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd

from src.data.fetchers.fred import (
    SERIES,
    CLEAN_DIR,
    fetch_all,
)
from src.data.utils import (
    CATALOG_PATH,
    DATA_DIR,
    align_to_trading_days,
    load_clean,
    log_to_catalog,
    save_clean,
)


START = "2000-01-01"


def _load(name: str) -> pd.Series:
    path = CLEAN_DIR / f"{name}.parquet"
    if not path.exists():
        return pd.Series(dtype=float)
    return load_clean(path).iloc[:, 0]


def _save_derived(name: str, s: pd.Series, freq: str, notes: str = "") -> None:
    if s is None or s.dropna().empty:
        print(f"  x derived {name}: empty")
        return
    df = s.to_frame(name=name)
    path = CLEAN_DIR / f"{name}.parquet"
    save_clean(df, path, metadata={"source": "fred", "derived": True, "frequency": freq})
    valid = df.dropna()
    s_date = str(valid.index.min().date())
    e_date = str(valid.index.max().date())
    log_to_catalog(
        CATALOG_PATH,
        {
            "source": "fred",
            "series_name": name,
            "frequency": freq,
            "date_range": f"{s_date}..{e_date}",
            "file_path": str(path.relative_to(DATA_DIR.parent)).replace("\\", "/"),
            "status": "OK",
            "notes": ("derived; " + notes).strip("; "),
        },
    )
    print(f"  + derived {name}: {s_date}..{e_date}  rows={len(valid)}")


def build_derived() -> None:
    print("\n=== derived series ===")
    t10 = _load("treasury_10y")
    t2  = _load("treasury_2y")
    t3m = _load("treasury_3m")
    aaa = _load("moodys_aaa")
    baa = _load("moodys_baa")
    cpi = _load("cpi_all_urban")
    cpi_core = _load("cpi_core")
    m2 = _load("m2_money_supply")
    payems = _load("nonfarm_payrolls")
    gdp_real = _load("gdp_real")
    ahe = _load("avg_hourly_earnings")
    be10 = _load("breakeven_10y")
    be5 = _load("breakeven_5y")

    if not t10.empty and not t2.empty:
        _save_derived("spread_10y_2y", (t10 - t2).dropna(), "daily", "DGS10 - DGS2")
    if not t10.empty and not t3m.empty:
        _save_derived("spread_10y_3m", (t10 - t3m).dropna(), "daily", "DGS10 - DGS3MO")
    if not aaa.empty and not baa.empty:
        _save_derived("spread_baa_aaa", (baa - aaa).dropna(), "daily", "BAA - AAA")

    # CPI transforms — monthly data that has been ffilled onto the trading cal.
    # To compute 12-month / 1-month % change we resample back to month-end then
    # align to trading days again, otherwise the ffilled plateau produces zeros.
    def _monthly(s: pd.Series) -> pd.Series:
        return s.dropna().resample("ME").last()

    if not cpi.empty:
        m = _monthly(cpi)
        yoy = m.pct_change(12) * 100.0
        mom = m.pct_change(1) * 100.0
        _save_derived("cpi_yoy", align_to_trading_days(yoy.to_frame("cpi_yoy"), source_freq="monthly").iloc[:, 0], "monthly", "CPIAUCSL 12m % change")
        _save_derived("cpi_mom", align_to_trading_days(mom.to_frame("cpi_mom"), source_freq="monthly").iloc[:, 0], "monthly", "CPIAUCSL 1m % change")
    if not cpi_core.empty:
        m = _monthly(cpi_core)
        yoy = m.pct_change(12) * 100.0
        _save_derived("cpi_core_yoy", align_to_trading_days(yoy.to_frame("cpi_core_yoy"), source_freq="monthly").iloc[:, 0], "monthly", "CPILFESL 12m % change")
    if not m2.empty:
        m = _monthly(m2)
        yoy = m.pct_change(12) * 100.0
        _save_derived("m2_yoy", align_to_trading_days(yoy.to_frame("m2_yoy"), source_freq="monthly").iloc[:, 0], "monthly", "M2SL 12m % change")
    if not payems.empty:
        m = _monthly(payems)
        mom = m.diff(1)  # thousands of jobs
        _save_derived("payems_mom", align_to_trading_days(mom.to_frame("payems_mom"), source_freq="monthly").iloc[:, 0], "monthly", "PAYEMS 1m diff (thousands)")
    if not gdp_real.empty:
        q = gdp_real.dropna().resample("QE").last()
        annualized = ((q.pct_change(1) + 1.0) ** 4 - 1.0) * 100.0
        _save_derived("gdp_real_growth_annualized", align_to_trading_days(annualized.to_frame("gdp_real_growth_annualized"), source_freq="quarterly").iloc[:, 0], "quarterly", "GDPC1 annualized QoQ")
    if not ahe.empty:
        m = _monthly(ahe)
        yoy = m.pct_change(12) * 100.0
        _save_derived("avg_hourly_earnings_yoy", align_to_trading_days(yoy.to_frame("avg_hourly_earnings_yoy"), source_freq="monthly").iloc[:, 0], "monthly", "CES0500000003 12m % change")

    # TIPS breakeven vs realized CPI YoY (inflation surprise proxy)
    cpi_yoy = _load("cpi_yoy")
    if not cpi_yoy.empty:
        if not be10.empty:
            diff = (be10 - cpi_yoy).dropna()
            _save_derived("breakeven10_minus_cpi_yoy", diff, "daily", "T10YIE - CPI YoY")
        if not be5.empty:
            diff = (be5 - cpi_yoy).dropna()
            _save_derived("breakeven5_minus_cpi_yoy", diff, "daily", "T5YIE - CPI YoY")


def validate_all(details: list) -> None:
    print("\n=== validation summary ===")
    short = []
    discontinued = []
    for d in details:
        name = d["descriptive_name"]
        s = _load(name).dropna()
        if s.empty:
            continue
        years = (s.index.max() - s.index.min()).days / 365.25
        print(f"  {d['series_id']:<18} {name:<30} {d['freq']:<10} {d['start']}..{d['end']}  years={years:4.1f}  rows={len(s)}")
        if years < 5:
            short.append((d["series_id"], round(years, 1)))
        # discontinued: no observation in the last 400 days
        if (pd.Timestamp.today() - s.index.max()).days > 400:
            discontinued.append((d["series_id"], str(s.index.max().date())))

    if short:
        print("\n  FLAG short history (<5y):")
        for sid, y in short:
            print(f"    - {sid}: {y}y")
    if discontinued:
        print("\n  FLAG possibly discontinued (no obs in last 400d):")
        for sid, last in discontinued:
            print(f"    - {sid}: last={last}")

    # Sanity check 1: 10Y-2Y inverted in 2022-2023
    sp = _load("spread_10y_2y").dropna()
    if not sp.empty:
        window = sp.loc["2022-01-01":"2023-12-31"]
        n_neg = int((window < 0).sum())
        min_val = float(window.min()) if not window.empty else float("nan")
        status = "PASS" if n_neg > 50 else "FAIL"
        print(f"\n  CHECK 10Y-2Y inversion 2022-23: {status}  neg_days={n_neg}  min={min_val:.2f}")

    # Sanity check 2: CPI YoY peaks near 9% mid-2022
    cy = _load("cpi_yoy").dropna()
    if not cy.empty:
        window = cy.loc["2022-01-01":"2022-12-31"]
        peak = float(window.max()) if not window.empty else float("nan")
        status = "PASS" if 8.0 <= peak <= 10.0 else "FAIL"
        print(f"  CHECK CPI YoY 2022 peak: {status}  peak={peak:.2f}%")

    # Sanity check 3: VIX spot vs NFCI (correlation should be positive and > 0.3)
    vix_path = DATA_DIR / "clean" / "prices" / "_VIX.parquet"
    nfci = _load("nfci").dropna()
    if vix_path.exists() and not nfci.empty:
        vix = load_clean(vix_path)
        vcol = "adj_close" if "adj_close" in vix.columns else "close"
        vix_s = vix[vcol].dropna()
        joined = pd.concat([vix_s.rename("vix"), nfci.rename("nfci")], axis=1).dropna()
        if len(joined) > 100:
            corr = float(joined["vix"].corr(joined["nfci"]))
            status = "PASS" if corr > 0.3 else "FAIL"
            print(f"  CHECK VIX vs NFCI correlation: {status}  corr={corr:.3f}  n={len(joined)}")
        else:
            print("  CHECK VIX vs NFCI: insufficient overlap")
    else:
        print("  CHECK VIX vs NFCI: missing VIX or NFCI")


def main() -> None:
    print(f"Downloading {len(SERIES)} FRED series from {START}...")
    summary = fetch_all(start=START)
    print(f"\n=== fetch summary ===")
    print(f"  ok:     {len(summary['ok'])}")
    print(f"  failed: {len(summary['failed'])}  -> {summary['failed']}")

    build_derived()
    validate_all(summary["details"])


if __name__ == "__main__":
    main()
