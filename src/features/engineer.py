"""Feature engineering for the price-based strategy.

Naming convention: <category>_<signal>_<lookback>_<ticker>.
All rolling computations are .shift(1) so the value on date T uses only
information available at the close of T-1, ready as a signal for T's open.
For 63d return as a signal for tomorrow, we compute the 63d window ending
yesterday (i.e., pct_change(63).shift(1)).
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

from src.data.utils import DATA_DIR, load_clean

FEATURES_DIR = DATA_DIR / "features"
CATALOG_PATH = DATA_DIR / "FEATURE_CATALOG.md"

PRIMARY_UNIVERSE = ["SOXX", "QQQ", "XLK", "VGT", "IGV", "XLE", "GLD", "SHY"]
EXTRA_TICKERS = ["SPY", "TLT", "DBC", "XLF", "XLI", "XLV", "AGG", "EEM", "IWM"]
ALL_TICKERS = PRIMARY_UNIVERSE + EXTRA_TICKERS


# ----------------------------- IO helpers -----------------------------

def load_prices(tickers: Iterable[str]) -> dict[str, pd.DataFrame]:
    out = {}
    for t in tickers:
        path = DATA_DIR / "clean" / "prices" / f"{t}.parquet"
        df = load_clean(path)
        df.index.name = "date"
        out[t] = df
    return out


def _stack(field: str, prices: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Stack one OHLCV field across tickers into a wide DataFrame."""
    return pd.DataFrame({t: prices[t][field] for t in prices}).sort_index()


def save_features(df: pd.DataFrame, category: str, name: str) -> Path:
    """Save a feature DataFrame to /data/features/<category>/<name>.parquet
    and append a row to FEATURE_CATALOG.md.
    """
    out_dir = FEATURES_DIR / category
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{name}.parquet"
    out = df.copy()
    if not isinstance(out.index, pd.DatetimeIndex):
        out.index = pd.to_datetime(out.index)
    out.index.name = "date"
    out.to_parquet(path)

    if not CATALOG_PATH.exists():
        CATALOG_PATH.write_text(
            "# Feature Catalog\n\n"
            "| Category | Name | Columns | Rows | Date Range | Path | Created |\n"
            "|----------|------|---------|------|------------|------|---------|\n"
        )
    rng = f"{out.index.min().date()}..{out.index.max().date()}" if len(out) else "empty"
    row = (
        f"| {category} | {name} | {len(out.columns)} | {len(out)} | {rng} | "
        f"data/features/{category}/{name}.parquet | "
        f"{datetime.utcnow().strftime('%Y-%m-%d')} |\n"
    )
    with open(CATALOG_PATH, "a") as f:
        f.write(row)
    return path


# ------------------------- Feature primitives -------------------------

def rolling_return(prices_wide: pd.DataFrame, n: int) -> pd.DataFrame:
    return prices_wide.pct_change(n).shift(1)


def rolling_vol(prices_wide: pd.DataFrame, n: int) -> pd.DataFrame:
    daily = prices_wide.pct_change()
    return daily.rolling(n).std().shift(1) * np.sqrt(252)


def true_range(high: pd.DataFrame, low: pd.DataFrame, close: pd.DataFrame) -> pd.DataFrame:
    prev_close = close.shift(1)
    a = high - low
    b = (high - prev_close).abs()
    c = (low - prev_close).abs()
    return pd.concat([a, b, c]).groupby(level=0).max()


def atr(high, low, close, n: int) -> pd.DataFrame:
    tr = true_range(high, low, close)
    return tr.rolling(n).mean().shift(1)


def rsi(prices_wide: pd.DataFrame, n: int) -> pd.DataFrame:
    delta = prices_wide.diff()
    up = delta.clip(lower=0)
    down = -delta.clip(upper=0)
    roll_up = up.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    roll_dn = down.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    rs = roll_up / roll_dn.replace(0, np.nan)
    return (100 - 100 / (1 + rs)).shift(1)


# ------------------------------- Steps -------------------------------

def step2_returns(close: pd.DataFrame) -> int:
    n_files = 0
    for n in [5, 10, 21, 42, 63, 126, 252]:
        save_features(rolling_return(close, n), "price", f"returns_{n}d")
        n_files += 1
    r252 = rolling_return(close, 252)
    r21 = rolling_return(close, 21)
    save_features(r252 - r21, "price", "returns_12_1_mom")
    return n_files + 1


def step3_volatility(close: pd.DataFrame, high: pd.DataFrame, low: pd.DataFrame) -> int:
    n_files = 0
    for n in [21, 42, 63]:
        save_features(rolling_vol(close, n), "price", f"vol_{n}d")
        n_files += 1
    for n in [14, 21]:
        save_features(atr(high, low, close, n), "price", f"atr_{n}d")
        n_files += 1
    intraday = ((high - low) / close).rolling(21).mean().shift(1)
    save_features(intraday, "price", "intraday_range_21d")
    return n_files + 1


def step4_quality(close: pd.DataFrame, high: pd.DataFrame, low: pd.DataFrame) -> int:
    n_files = 0
    daily = close.pct_change()
    for n in [21, 42, 63, 126]:
        ret_n = rolling_return(close, n)
        vol_n = daily.rolling(n).std().shift(1) * np.sqrt(252)
        save_features(ret_n / vol_n.replace(0, np.nan), "price", f"quality_voladj_mom_{n}d")
        n_files += 1

    save_features(rolling_return(close, 21) - rolling_return(close, 63),
                  "price", "quality_mom_accel")
    n_files += 1

    high52 = close.rolling(252).max().shift(1)
    save_features((close.shift(1) / high52), "price", "quality_52w_high_ratio")
    n_files += 1

    sma200 = close.rolling(200).mean().shift(1)
    sma50 = close.rolling(50).mean().shift(1)
    save_features((close.shift(1) - sma200) / sma200, "price", "quality_dist_sma200")
    save_features((close.shift(1) - sma50) / sma50, "price", "quality_dist_sma50")
    save_features((sma50 > sma200).astype(float), "price", "quality_golden_cross")
    n_files += 3

    save_features((close.shift(1) - high52) / high52, "price", "quality_drawdown_252d")
    n_files += 1

    save_features(rsi(close, 14), "price", "quality_rsi_14d")
    save_features(rsi(close, 28), "price", "quality_rsi_28d")
    n_files += 2

    sma21 = close.rolling(21).mean().shift(1)
    std21 = close.rolling(21).std().shift(1)
    save_features((close.shift(1) - sma21) / (2 * std21.replace(0, np.nan)),
                  "price", "quality_bb_position")
    n_files += 1
    return n_files


def step5_cross_sectional(close: pd.DataFrame) -> int:
    n_files = 0
    primary = close[PRIMARY_UNIVERSE]
    for n in [21, 42, 63, 126]:
        ret = rolling_return(primary, n)
        rank = ret.rank(axis=1, ascending=False)
        save_features(rank, "price", f"cross_sectional_mom_rank_{n}d")
        n_files += 1

    ret63 = rolling_return(primary, 63)
    save_features(ret63.sub(ret63.mean(axis=1), axis=0), "price",
                  "cross_sectional_relative_mom_63d")
    z63 = ret63.sub(ret63.mean(axis=1), axis=0).div(
        ret63.std(axis=1).replace(0, np.nan), axis=0)
    save_features(z63, "price", "cross_sectional_mom_zscore_63d")
    n_files += 2

    rank63 = ret63.rank(axis=1, ascending=False)
    rank63_lag = rank63.shift(21)
    stab = pd.Series(
        [rank63.iloc[max(0, i - 20):i + 1].corrwith(rank63_lag.iloc[max(0, i - 20):i + 1]).mean()
         if i >= 21 else np.nan for i in range(len(rank63))],
        index=rank63.index, name="rank_stability_21d")
    save_features(stab.to_frame(), "price", "cross_sectional_rank_stability_21d")
    n_files += 1

    sorted_ret = np.sort(ret63.values, axis=1)[:, ::-1]
    margin = pd.DataFrame({"top_margin": sorted_ret[:, 0] - sorted_ret[:, 1]},
                          index=ret63.index)
    save_features(margin, "price", "cross_sectional_top_margin_63d")
    save_features(ret63.std(axis=1).to_frame("dispersion"),
                  "price", "cross_sectional_dispersion_63d")
    n_files += 2
    return n_files


def step6_volume(prices: dict[str, pd.DataFrame]) -> int:
    tickers = PRIMARY_UNIVERSE + ["SPY"]
    vol = pd.DataFrame({t: prices[t]["volume"] for t in tickers}).sort_index()
    close = pd.DataFrame({t: prices[t]["adj_close"] for t in tickers}).sort_index()

    save_features((vol.rolling(21).mean() / vol.rolling(63).mean()).shift(1),
                  "price", "volume_trend_21_63")
    save_features((vol / vol.rolling(21).mean()).shift(1),
                  "price", "volume_relative_21d")

    direction = np.sign(close.diff()).fillna(0)
    obv = (direction * vol).cumsum()

    def _slope(s: pd.Series) -> float:
        if s.isna().all():
            return np.nan
        x = np.arange(len(s))
        y = s.values
        m = ~np.isnan(y)
        if m.sum() < 5:
            return np.nan
        return np.polyfit(x[m], y[m], 1)[0]

    obv_slope = obv.rolling(21).apply(_slope, raw=False).shift(1)
    save_features(obv_slope, "price", "volume_obv_slope_21d")
    return 3


def step7_relative_strength(close: pd.DataFrame) -> int:
    spy = close["SPY"]
    primary = close[PRIMARY_UNIVERSE]
    n_files = 0
    rs = {}
    for n in [63, 126]:
        ret_etf = rolling_return(primary, n)
        ret_spy = spy.pct_change(n).shift(1)
        rs_n = ret_etf.sub(ret_spy, axis=0)
        save_features(rs_n, "price", f"relative_strength_{n}d")
        rs[n] = rs_n
        n_files += 1

    ret_etf_21 = rolling_return(primary, 21)
    ret_spy_21 = spy.pct_change(21).shift(1)
    rs_21 = ret_etf_21.sub(ret_spy_21, axis=0)
    accel = (rs_21 > rs[63]).astype(float)
    save_features(accel, "price", "relative_strength_trend_accel")
    return n_files + 1


# ------------------------------ Validation ------------------------------

def validate(close: pd.DataFrame) -> None:
    print("\n=== VALIDATION ===")

    # Lookahead check on a random date
    rng = np.random.default_rng(42)
    valid_idx = close.dropna().index
    pick = valid_idx[rng.integers(300, len(valid_idx) - 5)]
    feat = pd.read_parquet(FEATURES_DIR / "price" / "returns_63d.parquet")
    pos = close.index.get_loc(pick)
    manual = close["SPY"].iloc[pos - 1] / close["SPY"].iloc[pos - 1 - 63] - 1
    feat_val = feat.loc[pick, "SPY"]
    print(f"[lookahead] {pick.date()} SPY 63d ret manual={manual:.6f} feature={feat_val:.6f} "
          f"match={np.isclose(manual, feat_val)}")

    # Oct 2021 XLE rank check
    rank63 = pd.read_parquet(FEATURES_DIR / "price" / "cross_sectional_mom_rank_63d.parquet")
    oct21 = rank63.loc["2021-10-25":"2021-10-29"]
    print(f"[oct 2021 ranks]\n{oct21}")

    # Dispersion check
    disp = pd.read_parquet(FEATURES_DIR / "price" / "cross_sectional_dispersion_63d.parquet")
    for year in [2017, 2020, 2022]:
        d = disp.loc[str(year)].mean().iloc[0]
        print(f"[dispersion {year}] mean={d:.4f}")

    # Vol-adjusted XLE momentum sanity
    voladj = pd.read_parquet(FEATURES_DIR / "price" / "quality_voladj_mom_63d.parquet")
    raw = pd.read_parquet(FEATURES_DIR / "price" / "returns_63d.parquet")
    print(f"[XLE 2021] raw_mom_mean={raw['XLE'].loc['2021'].mean():.4f} "
          f"voladj_mom_mean={voladj['XLE'].loc['2021'].mean():.4f}")


# ---------------------------------- Main ----------------------------------

def main() -> None:
    prices = load_prices(ALL_TICKERS)
    close = _stack("adj_close", prices)
    high = _stack("high", prices)
    low = _stack("low", prices)
    print(f"Loaded {len(prices)} tickers, {len(close)} rows, "
          f"{close.index.min().date()}..{close.index.max().date()}")

    total = 0
    total += step2_returns(close)
    total += step3_volatility(close, high, low)
    total += step4_quality(close, high, low)
    total += step5_cross_sectional(close)
    total += step6_volume(prices)
    total += step7_relative_strength(close)

    print(f"\nTotal feature files created: {total}")
    validate(close)


if __name__ == "__main__":
    main()
