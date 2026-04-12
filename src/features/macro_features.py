"""Macro feature builder — Session 4.x.

Reads /data/clean/macro/*.parquet and /data/clean/prices/_VIX.parquet, applies
publication-lag shifts to avoid lookahead, computes features, and writes to
/data/features/macro/<group>_<signal>.parquet.
"""
from __future__ import annotations

from pathlib import Path
import pandas as pd
import numpy as np

from src.data.utils import load_clean, save_clean, get_trading_calendar

ROOT = Path(__file__).resolve().parents[2]
MACRO = ROOT / "data" / "clean" / "macro"
PRICES = ROOT / "data" / "clean" / "prices"
OUT = ROOT / "data" / "features" / "macro"
OUT.mkdir(parents=True, exist_ok=True)

# Publication lag in calendar days. 0 = market-observable same day.
LAG_DAYS = {
    # daily / market-observable
    "treasury_10y": 0, "treasury_2y": 0, "treasury_5y": 0, "treasury_3m": 0,
    "treasury_30y": 0, "spread_10y_2y": 0, "spread_10y_3m": 0,
    "fed_funds_daily": 0, "hy_oas": 0, "bbb_oas": 0, "spread_baa_aaa": 0,
    "ted_spread": 0, "moodys_aaa": 0, "moodys_baa": 0, "mortgage_30y": 3,
    "breakeven_5y": 0, "breakeven_10y": 0,
    "breakeven5_minus_cpi_yoy": 30, "breakeven10_minus_cpi_yoy": 30,
    # weekly
    "initial_claims": 5, "continuing_claims": 5, "nfci": 3,
    "stlfsi": 3, "stlfsi4": 3, "fed_balance_sheet": 5, "overnight_repo": 1,
    # monthly (shift to ~release date)
    "cpi_yoy": 30, "cpi_core_yoy": 30, "cpi_mom": 30, "pce_core": 30,
    "ism_manufacturing_pmi": 5, "ism_services_pmi": 5,
    "unemployment_rate": 7, "industrial_production": 16, "capacity_utilization": 16,
    "retail_sales_ex_food": 16, "personal_savings_rate": 30,
    "consumer_credit_total": 35, "housing_starts": 18,
    "credit_card_delinq": 45, "umich_sentiment": 14,
    "conference_board_conf": 25, "leading_econ_index": 21, "oecd_cli_us": 35,
    "m2_money_supply": 30, "m2_yoy": 30, "fed_funds_rate": 30,
    # quarterly
    "gdp_real_growth_annualized": 30,
}


def load_lagged(name: str) -> pd.Series | None:
    p = MACRO / f"{name}.parquet"
    if not p.exists():
        return None
    df = load_clean(p)
    s = df.iloc[:, 0]
    s.index = pd.to_datetime(s.index)
    s = s[~s.index.duplicated(keep="last")].sort_index()
    lag = LAG_DAYS.get(name, 0)
    if lag:
        s.index = s.index + pd.Timedelta(days=lag)
    return s


def to_cal(series: pd.Series, cal: pd.DatetimeIndex) -> pd.Series:
    union = cal.union(series.index)
    return series.reindex(union).ffill().reindex(cal)


def save(df: pd.DataFrame, name: str) -> int:
    df = df.dropna(how="all")
    save_clean(df, OUT / f"{name}.parquet", metadata={"builder": "macro_features", "group": name.split("_")[0]})
    return df.shape[1]


def build():
    # Master trading calendar from VIX
    vix_df = load_clean(PRICES / "_VIX.parquet")
    vix_df.index = pd.to_datetime(vix_df.index)
    cal_start = pd.Timestamp("2003-01-01")
    cal_end = vix_df.index.max()
    cal = get_trading_calendar(cal_start, cal_end)

    L = lambda n: to_cal(load_lagged(n), cal) if load_lagged(n) is not None else None

    feat_count = 0

    # ========== STEP 1 — YIELD CURVE & RATES ==========
    t10 = L("treasury_10y"); t2 = L("treasury_2y"); t5 = L("treasury_5y")
    t3m = L("treasury_3m"); ffd = L("fed_funds_daily"); cpi_yoy = L("cpi_yoy")

    slope_10_2 = (t10 - t2).rename("yc_slope_10y_2y")
    df = pd.DataFrame({
        "yc_slope_10y_2y": slope_10_2,
        "yc_slope_10y_2y_chg21": slope_10_2.diff(21),
        "yc_slope_10y_2y_chg63": slope_10_2.diff(63),
        "yc_inversion_flag": (slope_10_2 < 0).astype(float),
    })
    inv = (slope_10_2 < 0).astype(int)
    grp = (inv != inv.shift()).cumsum()
    df["yc_inversion_duration_days"] = inv.groupby(grp).cumsum().astype(float)
    df["yc_spread_10y_3m"] = (t10 - t3m)
    df["yc_spread_10y_3m_chg21"] = (t10 - t3m).diff(21)
    df["fed_funds_level"] = ffd
    df["fed_funds_hiking_flag"] = (ffd > ffd.shift(63)).astype(float)
    df["real_rate_10y"] = t10 - cpi_yoy
    df["yc_curvature"] = 2.0 * t5 - t2 - t10
    feat_count += save(df, "yield_curve_features")

    # ========== STEP 2 — INFLATION ==========
    cpi_core = L("cpi_core_yoy"); cpi_mom = L("cpi_mom"); pce_core = L("pce_core")
    be5 = L("breakeven_5y"); be10 = L("breakeven_10y")

    pce_core_yoy = pce_core.pct_change(252) * 100  # daily-aligned monthly: ~1y diff
    df = pd.DataFrame({
        "cpi_yoy": cpi_yoy,
        "cpi_yoy_3m_trend": cpi_yoy.diff(63),
        "cpi_mom": cpi_mom,
        "cpi_core_yoy": cpi_core,
        "cpi_core_yoy_3m_trend": cpi_core.diff(63),
        "pce_core_yoy": pce_core_yoy,
        "pce_core_yoy_3m_trend": pce_core_yoy.diff(63),
        "breakeven_5y": be5,
        "breakeven_5y_chg21": be5.diff(21),
        "breakeven_10y": be10,
        "breakeven_10y_chg21": be10.diff(21),
        "inflation_surprise_5y": be5 - cpi_yoy,
        "inflation_regime_hot_flag": (cpi_yoy > 4.0).astype(float),
    })
    # disinflation flag — CPI YoY declining 3+ consecutive months
    cpi_m = cpi_yoy.resample("ME").last()
    decl = (cpi_m.diff() < 0).rolling(3).sum() >= 3
    df["disinflation_flag"] = decl.reindex(cpi_yoy.index, method="ffill").astype(float)
    feat_count += save(df, "inflation_features")

    # ========== STEP 3 — ECONOMIC ACTIVITY ==========
    pmi = L("ism_manufacturing_pmi"); unemp = L("unemployment_rate")
    ic = L("initial_claims"); ip = L("industrial_production")
    cu = L("capacity_utilization"); retail = L("retail_sales_ex_food")
    gdp = L("gdp_real_growth_annualized"); lei = L("leading_econ_index")
    cli = L("oecd_cli_us")

    ic_4w = ic.rolling(20, min_periods=5).mean()
    df = pd.DataFrame({
        "ism_pmi": pmi,
        "ism_pmi_expansion_flag": (pmi > 50).astype(float),
        "ism_pmi_3m_trend": pmi.diff(63),
        "unemployment_rate": unemp,
        "unemployment_3m_chg": unemp.diff(63),
        "initial_claims_4wma": ic_4w,
        "initial_claims_13w_trend": ic_4w.diff(65),
        "industrial_production_yoy": ip.pct_change(252) * 100,
        "capacity_utilization": cu,
        "retail_sales_mom": retail.pct_change(21) * 100,
        "gdp_growth_annualized": gdp,
        "lei_level": lei,
        "lei_6m_change": lei.diff(126),
        "oecd_cli": cli,
        "oecd_cli_3m_change": cli.diff(63),
    })
    feat_count += save(df, "activity_features")

    # ========== STEP 4 — CREDIT ==========
    hy = L("hy_oas"); ig = L("bbb_oas")
    baa_aaa = L("spread_baa_aaa"); ted = L("ted_spread")
    nfci = L("nfci"); stlfsi = L("stlfsi4") if L("stlfsi4") is not None else L("stlfsi")

    hy_ig = (hy - ig).rename("hy_ig_spread")
    z = (hy_ig - hy_ig.rolling(252, min_periods=60).mean()) / hy_ig.rolling(252, min_periods=60).std()
    df = pd.DataFrame({
        "hy_ig_spread": hy_ig,
        "hy_ig_spread_chg21": hy_ig.diff(21),
        "hy_ig_spread_chg63": hy_ig.diff(63),
        "hy_ig_spread_z252": z,
        "baa_aaa_spread": baa_aaa,
        "baa_aaa_spread_chg21": baa_aaa.diff(21),
        "ted_spread": ted,
        "ted_spread_chg21": ted.diff(21) if ted is not None else None,
        "nfci": nfci,
        "nfci_chg21": nfci.diff(21),
        "stlfsi": stlfsi,
        "credit_tightening_flag": (z > 1.5).astype(float),
    })
    feat_count += save(df, "credit_features")

    # ========== STEP 5 — LIQUIDITY ==========
    m2 = L("m2_money_supply"); m2y = L("m2_yoy")
    fbs = L("fed_balance_sheet"); rrp = L("overnight_repo")

    df = pd.DataFrame({
        "m2_yoy": m2y,
        "m2_yoy_6m_chg": m2y.diff(126),
        "fed_balance_sheet_yoy": fbs.pct_change(252) * 100 if fbs is not None else None,
        "overnight_repo_level": rrp,
        "monetary_loose_flag": (m2y > 10.0).astype(float),
    })
    feat_count += save(df, "liquidity_features")

    # ========== STEP 6 — CONSUMER ==========
    umich = L("umich_sentiment"); cbconf = L("conference_board_conf")
    psr = L("personal_savings_rate"); cct = L("consumer_credit_total")
    mort = L("mortgage_30y"); hs = L("housing_starts")
    ccd = L("credit_card_delinq")

    # consumer stress composite
    def z252(s):
        return (s - s.rolling(252, min_periods=60).mean()) / s.rolling(252, min_periods=60).std()
    stress = (z252(unemp) + z252(ccd) - z252(psr)) / 3.0

    df = pd.DataFrame({
        "umich_sentiment": umich,
        "umich_sentiment_3m_chg": umich.diff(63),
        "cb_consumer_conf": cbconf,
        "cb_consumer_conf_3m_chg": cbconf.diff(63),
        "personal_savings_rate": psr,
        "consumer_credit_yoy": cct.pct_change(252) * 100,
        "mortgage_30y": mort,
        "mortgage_30y_13w_chg": mort.diff(65),
        "housing_starts_yoy": hs.pct_change(252) * 100,
        "consumer_stress_composite": stress,
    })
    feat_count += save(df, "consumer_features")

    # ========== STEP 7 — VOLATILITY ==========
    vix = vix_df["close"].reindex(cal).ffill()
    spy_path = PRICES / "SPY.parquet"
    if spy_path.exists():
        spy = load_clean(spy_path)["close"].reindex(cal).ffill()
        rv = spy.pct_change().rolling(21).std() * np.sqrt(252) * 100
    else:
        rv = pd.Series(np.nan, index=cal)

    vix_pct = vix.rolling(252, min_periods=60).rank(pct=True) * 100
    bins = pd.cut(vix, bins=[-np.inf, 15, 25, 35, np.inf], labels=["low", "medium", "high", "extreme"])

    df = pd.DataFrame({
        "vix": vix,
        "vix_chg21": vix.diff(21),
        "vix_chg63": vix.diff(63),
        "vix_pct252": vix_pct,
        "vix_vs_21d_ma": vix - vix.rolling(21).mean(),
        "vol_risk_premium": vix - rv,
        "vix_regime_low": (bins == "low").astype(float),
        "vix_regime_medium": (bins == "medium").astype(float),
        "vix_regime_high": (bins == "high").astype(float),
        "vix_regime_extreme": (bins == "extreme").astype(float),
    })
    feat_count += save(df, "vol_features")

    # ========== STEP 8 — REGIMES ==========
    # Regime 1 already saved as part of vol_features; also save standalone
    reg1 = df[["vix_regime_low", "vix_regime_medium", "vix_regime_high", "vix_regime_extreme"]].copy()
    feat_count += save(reg1, "regime_vix")

    # Regime 2 — yield curve
    yc = slope_10_2
    reg2 = pd.DataFrame({
        "yc_regime_normal": (yc > 0.5).astype(float),
        "yc_regime_flat": ((yc > -0.25) & (yc <= 0.5)).astype(float),
        "yc_regime_inverted": (yc <= -0.25).astype(float),
    })
    feat_count += save(reg2, "regime_yield_curve")

    # Regime 3 — growth/inflation quadrant
    hg = pmi > 50
    hi = cpi_yoy >= 3.0
    reg3 = pd.DataFrame({
        "regime_hg_li": (hg & ~hi).astype(float),
        "regime_hg_hi": (hg & hi).astype(float),
        "regime_lg_li": (~hg & ~hi).astype(float),
        "regime_lg_hi_stagflation": (~hg & hi).astype(float),
    })
    feat_count += save(reg3, "regime_growth_inflation")

    # Regime 4 — credit
    reg4 = pd.DataFrame({
        "credit_regime_loose": (z < -0.5).astype(float),
        "credit_regime_normal": ((z >= -0.5) & (z <= 1.0)).astype(float),
        "credit_regime_tight": ((z > 1.0) & (z <= 2.0)).astype(float),
        "credit_regime_crisis": (z > 2.0).astype(float),
    })
    feat_count += save(reg4, "regime_credit")

    # Regime 5 — monetary (use fed funds daily, 6mo = 126 trading days)
    ff_chg = ffd - ffd.shift(126)
    ff_3m_range = ffd.rolling(63).max() - ffd.rolling(63).min()
    holding = (ff_3m_range.abs() < 0.1)
    reg5 = pd.DataFrame({
        "monetary_regime_easing": (ff_chg < -0.1).astype(float),
        "monetary_regime_holding": holding.astype(float),
        "monetary_regime_tightening": (ff_chg > 0.1).astype(float),
    })
    feat_count += save(reg5, "regime_monetary")

    # ========== VALIDATION ==========
    print("\n=== VALIDATION ===")
    # 1) HG/HI in 2021-2022
    hghi_2122 = reg3.loc["2021-01-01":"2022-12-31", "regime_hg_hi"].sum()
    print(f"HG/HI days in 2021-2022: {int(hghi_2122)}")
    # 2) credit crisis
    crisis_days = reg4["credit_regime_crisis"]
    mar20 = crisis_days.loc["2020-03-01":"2020-04-30"].sum()
    late22 = crisis_days.loc["2022-09-01":"2022-12-31"].sum()
    print(f"Credit crisis days: Mar 2020={int(mar20)}, late 2022={int(late22)}")
    # 3) VIX extreme on 2020-03-16
    try:
        v = float(vix.loc["2020-03-16"])
        print(f"VIX 2020-03-16: {v:.2f} extreme={v >= 35}")
    except KeyError:
        print("VIX 2020-03-16 missing")
    # 4) yield curve inverted mid-2022 to 2023
    inv_22_23 = reg2.loc["2022-07-01":"2023-12-31", "yc_regime_inverted"].mean()
    print(f"YC inverted share mid-2022..2023: {inv_22_23:.2%}")

    print(f"\nTotal feature columns created this session: {feat_count}")
    return feat_count


if __name__ == "__main__":
    build()
