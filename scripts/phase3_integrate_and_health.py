"""Phase 3 PARTS B/C/D: cross-source integration, health check, catalog reconcile."""
from __future__ import annotations

import re
import sys
from pathlib import Path
from collections import defaultdict

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.data.utils import (
    get_trading_calendar,
    align_to_trading_days,
    load_clean,
    validate_data,
    DATA_DIR,
    CATALOG_PATH,
    HEALTH_PATH,
    FAILED_PATH,
)

CLEAN = DATA_DIR / "clean"
RAW = DATA_DIR / "raw"
AVAIL_PATH = CLEAN / "data_availability_matrix.parquet"

PRIMARY_UNIVERSE = ["SPY", "QQQ", "IWM", "TLT", "GLD", "EFA", "EEM", "XLK", "XLF", "XLE", "XLV"]
CORE_MACRO = ["cpi_yoy", "fed_funds_rate", "treasury_10y", "treasury_2y", "unemployment_rate", "ism_manufacturing_pmi"]


def list_parquets() -> list[Path]:
    return sorted([p for p in CLEAN.rglob("*.parquet") if p.name != "data_availability_matrix.parquet"])


def series_id(p: Path) -> str:
    return f"{p.parent.name}/{p.stem}"


def load_first_column(p: Path) -> pd.Series | None:
    try:
        df = load_clean(p)
    except Exception as e:
        print(f"[WARN] failed to load {p}: {e}")
        return None
    if df.empty:
        return None
    if df.index.tz is not None:
        df.index = df.index.tz_localize(None)
    df = df.sort_index()
    df = df[~df.index.duplicated(keep="last")]
    # Pick first numeric column for representativeness
    num = df.select_dtypes(include=[np.number])
    if num.shape[1] == 0:
        return None
    s = num.iloc[:, 0]
    s.name = series_id(p)
    return s


def part_b_integration(files: list[Path]) -> tuple[pd.DataFrame, dict]:
    print("\n=== PART B: integration ===")
    cal = get_trading_calendar("2005-01-01", pd.Timestamp.today())
    series_list = []
    issues = {"tz": [], "dupes": [], "empty": [], "load_fail": []}
    for p in files:
        try:
            df = load_clean(p)
        except Exception as e:
            issues["load_fail"].append((series_id(p), str(e)))
            continue
        if df.empty:
            issues["empty"].append(series_id(p))
            continue
        if df.index.tz is not None:
            issues["tz"].append(series_id(p))
            df.index = df.index.tz_localize(None)
        if df.index.duplicated().any():
            issues["dupes"].append(series_id(p))
            df = df[~df.index.duplicated(keep="last")]
        df = df.sort_index()
        num = df.select_dtypes(include=[np.number])
        if num.shape[1] == 0:
            continue
        for col in num.columns:
            name = f"{series_id(p)}::{col}" if num.shape[1] > 1 else series_id(p)
            s = num[col].copy()
            s.name = name
            series_list.append(s)

    print(f"Loaded {len(series_list)} numeric series from {len(files)} files")
    print(f"Issues: tz={len(issues['tz'])} dupes={len(issues['dupes'])} empty={len(issues['empty'])} load_fail={len(issues['load_fail'])}")

    # Build availability matrix on master trading calendar
    avail = pd.DataFrame(0, index=cal, columns=[s.name for s in series_list], dtype=np.int8)
    for s in series_list:
        # mark 1 where original (pre-fill) had a value within cal range
        s_in = s.reindex(cal)
        avail[s.name] = s_in.notna().astype(np.int8).values

    avail.index.name = "date"
    avail.to_parquet(AVAIL_PATH)
    print(f"Wrote {AVAIL_PATH}: {avail.shape}")

    # Per-year coverage
    yearly = avail.groupby(avail.index.year).apply(lambda g: (g.sum(axis=0) > 0).mean() * 100)
    print("\nPer-year % of series with ANY data:")
    for y, pct in yearly.items():
        print(f"  {y}: {pct:.1f}%")

    return avail, issues


def find_recommended_start(avail: pd.DataFrame) -> int:
    """Earliest year where all PRIMARY_UNIVERSE prices and CORE_MACRO have coverage."""
    cols = avail.columns
    primary = [c for c in cols if any(c == f"prices/{t}" for t in PRIMARY_UNIVERSE)]
    macro = [c for c in cols if any(c == f"macro/{m}" for m in CORE_MACRO)]
    needed = primary + macro
    if not needed:
        return 2005
    for y in sorted(set(avail.index.year)):
        sub = avail[avail.index.year == y][needed]
        if (sub.sum(axis=0) > 0).all():
            return y
    return 2005


def part_c_health(files: list[Path], avail: pd.DataFrame, issues: dict) -> None:
    print("\n=== PART C: health check ===")

    rows = []
    drop_recommendations = []
    for p in files:
        try:
            df = load_clean(p)
        except Exception:
            continue
        if df.empty:
            continue
        if df.index.tz is not None:
            df.index = df.index.tz_localize(None)
        df = df.sort_index()
        df = df[~df.index.duplicated(keep="last")]
        rep = validate_data(df, name=series_id(p))
        if rep.get("empty"):
            continue
        nan_pct = max(rep.get("nan_pct", {}).values(), default=0.0)
        gaps = rep.get("gaps_gt_5d", [])
        outliers = rep.get("outliers_5sigma", {})
        # rough freq
        if len(df) >= 2:
            try:
                med = pd.Series(df.index).diff().dt.days.median()
            except Exception:
                med = float("nan")
        else:
            med = float("nan")
        if pd.isna(med):
            freq = "?"
        elif med <= 1.5:
            freq = "daily"
        elif med <= 8:
            freq = "weekly"
        elif med <= 35:
            freq = "monthly"
        elif med <= 100:
            freq = "quarterly"
        else:
            freq = "annual"

        # status
        status = "OK"
        years_span = (df.index.max() - df.index.min()).days / 365.25
        if years_span < 3:
            status = "SHORT"
        if len(gaps) > 5:
            status = "GAPS"
        if nan_pct > 50:
            status = "UNRELIABLE"
            drop_recommendations.append(series_id(p))

        rows.append({
            "series": series_id(p),
            "source": p.parent.name,
            "freq": freq,
            "start": rep["start"],
            "end": rep["end"],
            "nan_pct": round(nan_pct, 2),
            "gaps_5d": len(gaps),
            "outliers": sum(outliers.values()) if outliers else 0,
            "status": status,
        })

    rows.sort(key=lambda r: (r["source"], r["series"]))

    # Correlation spot checks
    corrs = {}
    try:
        spy = load_clean(CLEAN / "prices" / "SPY.parquet")["close"].pct_change()
        qqq = load_clean(CLEAN / "prices" / "QQQ.parquet")["close"].pct_change()
        corrs["SPY vs QQQ daily ret"] = float(spy.corr(qqq))
        vix = load_clean(CLEAN / "prices" / "_VIX.parquet")
        vix_col = "close" if "close" in vix.columns else vix.columns[0]
        vret = vix[vix_col].pct_change()
        corrs["VIX vs SPY daily ret"] = float(vret.corr(spy))
    except Exception as e:
        corrs["price_corr_err"] = str(e)
    try:
        cpi = load_clean(CLEAN / "macro" / "cpi_yoy.parquet").iloc[:, 0]
        be10 = load_clean(CLEAN / "macro" / "breakeven_10y.parquet").iloc[:, 0]
        joined = pd.concat([cpi, be10], axis=1).dropna()
        corrs["CPI YoY vs 10y breakeven"] = float(joined.iloc[:, 0].corr(joined.iloc[:, 1]))
    except Exception as e:
        corrs["cpi_be_err"] = str(e)
    try:
        aaii = load_clean(CLEAN / "sentiment" / "aaii_sentiment.parquet")
        bull_col = "bullish" if "bullish" in aaii.columns else aaii.columns[0]
        spy_close = load_clean(CLEAN / "prices" / "SPY.parquet")["close"]
        fwd_1m = spy_close.pct_change(21).shift(-21)
        joined = pd.concat([aaii[bull_col], fwd_1m], axis=1).dropna()
        corrs["AAII bull% vs SPY fwd 21d ret"] = float(joined.iloc[:, 0].corr(joined.iloc[:, 1]))
    except Exception as e:
        corrs["aaii_err"] = str(e)

    # Failed sources count
    failed_count = 0
    if FAILED_PATH.exists():
        for line in FAILED_PATH.read_text(errors="ignore").splitlines():
            if line.startswith("|") and not line.startswith("| Date") and not line.startswith("|---"):
                failed_count += 1

    # Coverage summary
    rec_year = find_recommended_start(avail)
    yearly_cov = avail.groupby(avail.index.year).apply(lambda g: (g.sum(axis=0) > 0).mean() * 100)
    cov80 = yearly_cov[yearly_cov > 80]
    cov80_start = int(cov80.index.min()) if len(cov80) else None

    # Write health doc
    lines = []
    lines.append("# Data Health Report\n")
    lines.append(f"_Generated: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}_\n")
    lines.append("## 1. Coverage Summary\n")
    lines.append(f"- Total clean series: **{len(rows)}**")
    lines.append(f"- Total failed source attempts: **{failed_count}**")
    lines.append(f"- Date range with >80% series coverage: **{cov80_start}..present**" if cov80_start else "- No year reaches 80% series coverage")
    lines.append(f"- Recommended training start (primary universe + core macro all present): **{rec_year}**\n")

    lines.append("## 2. Per-Series Health Table\n")
    lines.append("| Series | Source | Freq | Start | End | NaN% | Gaps>5d | Outliers | Status |")
    lines.append("|--------|--------|------|-------|-----|------|---------|----------|--------|")
    for r in rows:
        lines.append(
            f"| {r['series']} | {r['source']} | {r['freq']} | {r['start']} | {r['end']} | "
            f"{r['nan_pct']} | {r['gaps_5d']} | {r['outliers']} | {r['status']} |"
        )

    lines.append("\n## 3. Correlation Spot Checks\n")
    for k, v in corrs.items():
        if isinstance(v, float):
            lines.append(f"- **{k}**: {v:+.3f}")
        else:
            lines.append(f"- {k}: ERROR — {v}")
    lines.append("\nExpected: SPY~QQQ ~0.85-0.92; VIX~SPY ~-0.75 to -0.85; CPI~breakeven positive; AAII bull weakly negative.\n")

    lines.append("## 4. Known Issues\n")
    lines.append(f"- TZ-aware indexes detected and stripped: {len(issues['tz'])}")
    lines.append(f"- Series with duplicate dates (kept last): {len(issues['dupes'])}")
    lines.append(f"- Empty parquet files: {len(issues['empty'])}")
    lines.append(f"- Files that failed to load: {len(issues['load_fail'])}")
    short = [r['series'] for r in rows if r['status'] == 'SHORT']
    gaps = [r['series'] for r in rows if r['status'] == 'GAPS']
    unrel = [r['series'] for r in rows if r['status'] == 'UNRELIABLE']
    lines.append(f"- Series flagged SHORT (<3y span): {len(short)}")
    if short:
        lines.append("  - " + ", ".join(short[:25]) + (" ..." if len(short) > 25 else ""))
    lines.append(f"- Series flagged GAPS (>5 gap runs): {len(gaps)}")
    if gaps:
        lines.append("  - " + ", ".join(gaps[:25]) + (" ..." if len(gaps) > 25 else ""))
    lines.append(f"- Series flagged UNRELIABLE (>50% NaN): {len(unrel)}")
    if unrel:
        lines.append("  - " + ", ".join(unrel))

    lines.append("\n## 5. Recommendations\n")
    lines.append("- **Drop before Phase 4**: any series in UNRELIABLE list above.")
    lines.append("- **Keep but use cautiously**: SHORT series — only usable from their start date; cannot drive pre-2015 training.")
    lines.append("- **Alternative data**: Reddit/GitHub/Wikipedia signals are noisy but cheap; keep if they survive a feature-importance pass in Phase 4. Drop sources whose history begins after 2020 unless used as a regime overlay.")
    lines.append("- **Gaps to fill**: anything tagged GAPS — re-run align_to_trading_days() with appropriate source_freq before model training.")
    lines.append("- **Phase 4 needs not yet collected**: intraday volatility (realized vol), futures term structure for commodities, individual stock fundamentals (if going single-name).")

    HEALTH_PATH.write_text("\n".join(lines))
    print(f"Wrote {HEALTH_PATH} ({len(rows)} series rows)")
    print("Correlations:", {k: round(v, 3) if isinstance(v, float) else v for k, v in corrs.items()})


def part_d_reconcile(files: list[Path]) -> None:
    print("\n=== PART D: catalog reconciliation ===")

    text = CATALOG_PATH.read_text()
    # Parse rows: any line starting with "| " that isn't header/separator
    rows = []
    for line in text.splitlines():
        if not line.startswith("| "):
            continue
        if line.startswith("| Source") or line.startswith("|---") or line.startswith("|--"):
            continue
        parts = [p.strip() for p in line.strip().strip("|").split("|")]
        if len(parts) < 7:
            continue
        rows.append(parts)

    # Map: file_path -> row
    by_path = {}
    duplicates = []
    for r in rows:
        fp = r[4]
        if fp in by_path:
            duplicates.append(fp)
        by_path[fp] = r

    print(f"Catalog rows: {len(rows)}, unique file paths: {len(by_path)}, duplicates removed: {len(duplicates)}")

    # Files on disk relative to project
    project = Path(__file__).resolve().parents[1]
    disk_paths = set()
    for p in files:
        rel = p.relative_to(project).as_posix()
        disk_paths.add(rel)

    catalog_paths = set(by_path.keys())
    orphans = catalog_paths - disk_paths  # in catalog but file gone
    missing = disk_paths - catalog_paths  # on disk but no catalog row
    print(f"Disk parquet files: {len(disk_paths)}")
    print(f"Catalog->file orphans (catalog rows pointing to missing files): {len(orphans)}")
    print(f"Disk files missing from catalog: {len(missing)}")

    # Rewrite catalog: header + dedupe + drop orphans + add missing
    new_lines = [
        "# Data Catalog\n",
        "| Source | Series | Frequency | Date Range | File Path | Status | Notes |",
        "|--------|--------|-----------|------------|-----------|--------|-------|",
    ]
    kept = 0
    for fp in sorted(disk_paths):
        if fp in by_path:
            r = by_path[fp]
            new_lines.append("| " + " | ".join(r[:7]) + " |")
            kept += 1
        else:
            # add a stub
            p = project / fp
            try:
                df = load_clean(p)
                dr = f"{df.index.min().date()}..{df.index.max().date()}"
            except Exception:
                dr = "?"
            stem = Path(fp).stem
            cat = Path(fp).parent.name
            new_lines.append(f"| auto | {stem} | ? | {dr} | {fp} | OK | auto-added during phase3 reconcile |")
            kept += 1
    CATALOG_PATH.write_text("\n".join(new_lines) + "\n")
    print(f"Rewrote catalog: {kept} rows ({len(missing)} added, {len(orphans)} orphans dropped, {len(duplicates)} dupes removed)")

    # Final summary
    failed_count = 0
    if FAILED_PATH.exists():
        for line in FAILED_PATH.read_text(errors="ignore").splitlines():
            if line.startswith("|") and not line.startswith("| Date") and not line.startswith("|---"):
                failed_count += 1

    def du(p: Path) -> str:
        if not p.exists():
            return "missing"
        total = sum(f.stat().st_size for f in p.rglob("*") if f.is_file())
        return f"{total / (1024**2):.1f} MB"

    print("\n=== FINAL SUMMARY ===")
    print(f"Total parquet files in data/clean/: {len(disk_paths)}")
    print(f"Total catalog rows: {kept}")
    print(f"Total failed source entries: {failed_count}")
    print(f"data/clean/ disk usage: {du(CLEAN)}")
    print(f"data/raw/ disk usage: {du(RAW)}")


def main():
    files = list_parquets()
    avail, issues = part_b_integration(files)
    part_c_health(files, avail, issues)
    part_d_reconcile(files)


if __name__ == "__main__":
    main()
