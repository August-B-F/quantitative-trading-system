"""Reconstructed CNN Fear & Greed Index.

Six components (CNN uses seven — we drop Put/Call because we have no
reliable historical put/call history; logged in FAILED_SOURCES).
Each component is percentile-ranked vs a trailing 2-year window and
mapped to 0-100 (0 = extreme fear, 100 = extreme greed). The composite
is the equal-weighted mean of whichever components are non-NaN on a
given day.

Components:
  1. Market Momentum     : (SPY - MA125)/MA125, percentile vs 2y, direct
  2. Price Strength      : share of equity-ETF universe at 63d high
                           minus share at 63d low, percentile vs 2y
  3. Price Breadth       : share of universe with positive 21d return
  4. Market Volatility   : -(VIX - MA50)/MA50, percentile (inverted)
  5. Safe Haven Demand   : SPY_20d_ret - TLT_20d_ret, percentile
  6. Junk Bond Demand    : -HY OAS, percentile (tight spread = greed)

(Component 4 is a volatility reading; CNN's put/call would otherwise
sit here. Using VIX for volatility still, and flagging put/call as
missing per the task instructions.)
"""
from __future__ import annotations


import numpy as np
import pandas as pd

from src.data.utils import (
    CATALOG_PATH,
    DATA_DIR,
    align_to_trading_days,
    load_clean,
    log_to_catalog,
    save_clean,
    validate_data,
)

CLEAN_DIR = DATA_DIR / "clean" / "sentiment"
PRICES = DATA_DIR / "clean" / "prices"

# Equity ETFs used for breadth + strength components
BREADTH_TICKERS = [
    "SPY", "QQQ", "IWM", "EFA", "EEM", "XLK", "XLF", "XLE", "XLI", "XLV",
    "XLU", "XLP", "XLB", "XLY" if (PRICES / "XLY.parquet").exists() else "VGT",
    "IBB", "SMH", "SOXX", "VNQ", "KWEB", "FXI", "EWJ", "EWG", "EWZ",
]
ROLL_WIN = 504  # ~2 trading years


def _load_close(tkr: str) -> pd.Series:
    p = PRICES / f"{tkr}.parquet"
    if not p.exists():
        return pd.Series(dtype=float, name=tkr)
    df = load_clean(p)
    col = "adj_close" if "adj_close" in df.columns else "close"
    s = df[col].astype(float)
    s.name = tkr
    return s


def _pct_rank(s: pd.Series, window: int = ROLL_WIN) -> pd.Series:
    """Rolling percentile rank in [0,100]. Uses ranking of the *last*
    value against the preceding `window` observations."""
    def _last_rank(x: np.ndarray) -> float:
        v = x[-1]
        valid = x[~np.isnan(x)]
        if len(valid) < 20 or np.isnan(v):
            return np.nan
        return float((valid <= v).sum() / len(valid) * 100.0)
    return s.rolling(window, min_periods=60).apply(_last_rank, raw=True)


def _component_momentum(spy: pd.Series) -> pd.Series:
    ma125 = spy.rolling(125, min_periods=60).mean()
    raw = (spy - ma125) / ma125
    return _pct_rank(raw)


def _component_volatility(vix: pd.Series) -> pd.Series:
    ma50 = vix.rolling(50, min_periods=25).mean()
    raw = -((vix - ma50) / ma50)  # invert: low vol = greed
    return _pct_rank(raw)


def _component_safe_haven(spy: pd.Series, tlt: pd.Series) -> pd.Series:
    s20 = spy.pct_change(20)
    t20 = tlt.pct_change(20)
    spread = s20 - t20
    return _pct_rank(spread)


def _component_junk(hy_oas: pd.Series) -> pd.Series:
    raw = -hy_oas  # tight spread = greed
    return _pct_rank(raw)


def _universe_panel() -> pd.DataFrame:
    cols = {}
    for t in BREADTH_TICKERS:
        s = _load_close(t)
        if not s.empty:
            cols[t] = s
    panel = pd.DataFrame(cols).sort_index()
    return panel


def _component_strength(panel: pd.DataFrame) -> pd.Series:
    highs = panel.rolling(63, min_periods=40).max()
    lows = panel.rolling(63, min_periods=40).min()
    at_high = (panel >= highs - 1e-9).sum(axis=1)
    at_low = (panel <= lows + 1e-9).sum(axis=1)
    n = panel.notna().sum(axis=1).replace(0, np.nan)
    raw = (at_high - at_low) / n
    return _pct_rank(raw)


def _component_breadth(panel: pd.DataFrame) -> pd.Series:
    r21 = panel.pct_change(21)
    share = (r21 > 0).sum(axis=1) / r21.notna().sum(axis=1).replace(0, np.nan)
    return _pct_rank(share)


def main() -> None:
    CLEAN_DIR.mkdir(parents=True, exist_ok=True)
    print("[fg_recon] loading prices")
    spy = _load_close("SPY")
    tlt = _load_close("TLT")
    vix = _load_close("_VIX")
    hy = load_clean(DATA_DIR / "clean" / "macro" / "hy_oas.parquet")["hy_oas"].astype(float)
    panel = _universe_panel()
    print(f"[fg_recon] breadth panel: {panel.shape[1]} tickers, {panel.index.min().date()}..{panel.index.max().date()}")

    comps = pd.DataFrame({
        "momentum": _component_momentum(spy),
        "strength": _component_strength(panel),
        "breadth": _component_breadth(panel),
        "volatility": _component_volatility(vix),
        "safe_haven": _component_safe_haven(spy, tlt),
        "junk_bond": _component_junk(hy),
    }).dropna(how="all")

    comps["fear_greed_reconstructed"] = comps.mean(axis=1, skipna=True)
    comps = comps.dropna(subset=["fear_greed_reconstructed"])

    aligned = align_to_trading_days(comps, source_freq="daily")
    path = CLEAN_DIR / "fear_greed_reconstructed.parquet"
    save_clean(aligned, path, metadata={"source": "reconstructed", "components": list(comps.columns)})
    validate_data(aligned, name="fear_greed_reconstructed")

    # Correlation vs true CNN F&G (short 1y sample)
    cnn_path = CLEAN_DIR / "cnn_fear_greed.parquet"
    if cnn_path.exists():
        cnn = load_clean(cnn_path)["cnn_fear_greed"].astype(float)
        both = pd.concat([aligned["fear_greed_reconstructed"], cnn], axis=1, join="inner").dropna()
        both.columns = ["recon", "cnn"]
        if len(both) > 20:
            pr = both.corr(method="pearson").iloc[0, 1]
            sp = both.corr(method="spearman").iloc[0, 1]
            print(f"[fg_recon] vs CNN (n={len(both)}): pearson={pr:.3f} spearman={sp:.3f}")
            status = "OK" if pr > 0.6 else "UNRELIABLE"
        else:
            pr = sp = float("nan")
            status = "NO_OVERLAP"
    else:
        pr = sp = float("nan")
        status = "OK"

    # Correlation with inverted VIX (sanity — related but not identical)
    inv_vix = -vix
    chk = pd.concat([aligned["fear_greed_reconstructed"], inv_vix.rename("inv_vix")], axis=1, join="inner").dropna()
    if len(chk) > 50:
        pv = chk.corr().iloc[0, 1]
        print(f"[fg_recon] vs -VIX: pearson={pv:.3f}")

    # Extreme episode checks
    def _lookup(idx: pd.Index, date: str) -> float:
        ts = pd.Timestamp(date)
        sub = aligned["fear_greed_reconstructed"].loc[ts - pd.Timedelta(days=3):ts + pd.Timedelta(days=3)]
        return float(sub.mean()) if len(sub) else float("nan")

    episodes = {
        "fear_2020_03_23": _lookup(aligned.index, "2020-03-23"),
        "fear_2018_12_24": _lookup(aligned.index, "2018-12-24"),
        "fear_2015_08_24": _lookup(aligned.index, "2015-08-24"),
        "greed_2021_11_08": _lookup(aligned.index, "2021-11-08"),
        "greed_2018_01_26": _lookup(aligned.index, "2018-01-26"),
        "greed_2024_03_28": _lookup(aligned.index, "2024-03-28"),
    }
    print("[fg_recon] extreme episode scores:")
    for k, v in episodes.items():
        print(f"   {k}: {v:.1f}")

    notes = f"6-component reconstruction; pearson_vs_cnn={pr:.3f}"
    log_to_catalog(CATALOG_PATH, {
        "source": "reconstructed",
        "series_name": "fear_greed_reconstructed",
        "frequency": "daily",
        "date_range": f"{aligned.index.min().date()}..{aligned.index.max().date()}",
        "file_path": str(path.relative_to(DATA_DIR.parent)).replace("\\", "/"),
        "status": status,
        "notes": notes,
    })


if __name__ == "__main__":
    main()
