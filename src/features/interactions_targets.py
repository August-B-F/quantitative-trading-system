"""Phase 4.x — interaction features and Phase 5 prediction targets.

Interaction features combine momentum with macro/sentiment context (saved
under data/features/interaction). Targets are forward-looking and saved
under data/features/targets with TARGET_ prefixed columns so they can never
be confused with features.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.data.utils import DATA_DIR, load_clean
from src.features.engineer import (
    FEATURES_DIR, PRIMARY_UNIVERSE, load_prices, _stack, save_features,
    rolling_return,
)


# ----------------------------- IO helpers -----------------------------

def _load_feature(category: str, name: str) -> pd.DataFrame:
    return pd.read_parquet(FEATURES_DIR / category / f"{name}.parquet")


def _align(df: pd.DataFrame, cal: pd.DatetimeIndex) -> pd.DataFrame:
    return df.reindex(cal)


# ============================ STEP 1: INTERACTIONS ============================

def build_interactions(close: pd.DataFrame) -> int:
    cal = close.index
    primary = close[PRIMARY_UNIVERSE]
    mom63 = rolling_return(primary, 63)

    # Regime one-hots, aligned
    vix = _align(_load_feature("macro", "regime_vix"), cal)
    yc = _align(_load_feature("macro", "regime_yield_curve"), cal)
    infl = _align(_load_feature("macro", "inflation_features"), cal)
    cpi_yoy = infl["cpi_yoy"]
    cpi_hot = (cpi_yoy > 4.0).astype(float)

    n_files = 0

    # mom_63d × VIX extreme: zero out momentum when VIX = extreme
    extreme = vix["vix_regime_extreme"].fillna(0).astype(bool)
    mom_x_vix = mom63.mask(extreme, 0.0)
    save_features(mom_x_vix, "interaction", "mom63_x_vix_regime")
    n_files += 1

    # mom_63d × yield curve: split into normal vs inverted columns
    yc_norm = yc["yc_regime_normal"].fillna(0).astype(bool)
    yc_inv = yc["yc_regime_inverted"].fillna(0).astype(bool)
    mom_yc_normal = mom63.where(yc_norm, 0.0)
    mom_yc_inverted = mom63.where(yc_inv, 0.0)
    save_features(mom_yc_normal, "interaction", "mom63_when_yc_normal")
    save_features(mom_yc_inverted, "interaction", "mom63_when_yc_inverted")
    n_files += 2

    # mom_63d × inflation regime
    cpi_hot_mask = cpi_hot.reindex(cal).fillna(0).astype(bool)
    mom_cpi_hot = mom63.where(cpi_hot_mask, 0.0)
    mom_cpi_cool = mom63.where(~cpi_hot_mask, 0.0)
    save_features(mom_cpi_hot, "interaction", "mom63_when_cpi_hot")
    save_features(mom_cpi_cool, "interaction", "mom63_when_cpi_cool")
    n_files += 2

    # mom_63d × AAII spread (sentiment confirmation):
    # product is positive when momentum and sentiment agree.
    aaii = _align(_load_feature("sentiment", "survey_aaii_spread"), cal)["aaii_spread"]
    mom_x_aaii = mom63.mul(aaii, axis=0)
    save_features(mom_x_aaii, "interaction", "mom63_x_aaii_spread")
    n_files += 1

    # mom_63d × put/call ratio (extreme put buying = potential reversal).
    # Use total PCR z-score; product flips sign as PCR diverges from norm.
    pcr_z = _align(_load_feature("sentiment", "positioning_pcr_total_z252d"), cal)
    pcr_z_col = pcr_z.iloc[:, 0]
    mom_x_pcr = mom63.mul(pcr_z_col, axis=0)
    save_features(mom_x_pcr, "interaction", "mom63_x_pcr_total_z")
    n_files += 1

    # ---- Cross-asset confirmation ----

    # Energy: XLE 63d mom × USO (crude proxy) 63d mom alignment.
    uso_close = load_clean(DATA_DIR / "clean" / "prices" / "USO.parquet")["adj_close"].reindex(cal)
    uso_mom = uso_close.pct_change(63).shift(1)
    xle_mom = mom63["XLE"]
    energy_conf = ((xle_mom > 0) & (uso_mom > 0)).astype(float) - \
                  ((xle_mom < 0) & (uso_mom < 0)).astype(float)
    # +1 both up, -1 both down, 0 divergent
    save_features(energy_conf.to_frame("energy_confirmation"),
                  "interaction", "energy_confirmation")
    n_files += 1

    # Tech: SOXX 63d mom × SMH 63d mom alignment (semiconductor breadth).
    smh_close = load_clean(DATA_DIR / "clean" / "prices" / "SMH.parquet")["adj_close"].reindex(cal)
    smh_mom = smh_close.pct_change(63).shift(1)
    soxx_mom = mom63["SOXX"]
    tech_conf = ((soxx_mom > 0) & (smh_mom > 0)).astype(float) - \
                ((soxx_mom < 0) & (smh_mom < 0)).astype(float)
    save_features(tech_conf.to_frame("tech_confirmation"),
                  "interaction", "tech_confirmation")
    n_files += 1

    # Safe haven: GLD 63d mom × HY-IG credit spread direction (rising spread = stress).
    credit = _align(_load_feature("macro", "credit_features"), cal)
    hyig_chg = credit["hy_ig_spread_chg63"]
    gld_mom = mom63["GLD"]
    safe_haven_conf = ((gld_mom > 0) & (hyig_chg > 0)).astype(float) - \
                      ((gld_mom < 0) & (hyig_chg < 0)).astype(float)
    save_features(safe_haven_conf.to_frame("safe_haven_confirmation"),
                  "interaction", "safe_haven_confirmation")
    n_files += 1

    # Bond: TLT (extra ticker, not in primary). Load it directly.
    tlt_close = load_clean(DATA_DIR / "clean" / "prices" / "TLT.parquet")["adj_close"].reindex(cal)
    tlt_mom = tlt_close.pct_change(63).shift(1)
    yc_feat = _align(_load_feature("macro", "yield_curve_features"), cal)
    yc_slope_chg = yc_feat["yc_slope_10y_2y_chg63"]
    # falling yields ~ TLT up; we approximate "yields falling" by slope_chg < 0 OR
    # use real_rate signal. Use TLT mom up + yc slope steepening down (yields falling).
    bond_conf = ((tlt_mom > 0) & (yc_slope_chg < 0)).astype(float) - \
                ((tlt_mom < 0) & (yc_slope_chg > 0)).astype(float)
    save_features(bond_conf.to_frame("bond_confirmation"),
                  "interaction", "bond_confirmation")
    n_files += 1

    # ---- Spread signals ----
    spreads = pd.DataFrame(index=cal)
    spreads["soxx_minus_xle_63d"] = mom63["SOXX"] - mom63["XLE"]
    spreads["qqq_minus_xlv_63d"] = mom63["QQQ"] - close["XLV"].pct_change(63).shift(1)
    spreads["spy_minus_gld_63d"] = close["SPY"].pct_change(63).shift(1) - mom63["GLD"]
    spreads["spy_minus_eem_63d"] = close["SPY"].pct_change(63).shift(1) - close["EEM"].pct_change(63).shift(1)
    save_features(spreads, "interaction", "momentum_spreads_63d")
    n_files += 1

    return n_files


# ============================ STEP 2: TARGETS ============================

TARGET_UNIVERSE = ["SOXX", "QQQ", "XLK", "VGT", "IGV", "XLE", "GLD", "SHY"]
HORIZON = 21


def _forward_returns(close: pd.DataFrame, horizon: int) -> pd.DataFrame:
    """Forward return from T using prices T+1 .. T+horizon."""
    px = close[TARGET_UNIVERSE]
    return px.shift(-horizon - 1).div(px.shift(-1)) - 1.0


def build_targets(close: pd.DataFrame) -> dict:
    fwd = _forward_returns(close, HORIZON)
    fwd.columns = [f"TARGET_FWD21_{c}" for c in fwd.columns]
    save_features(fwd, "targets", "T2_forward_returns_21d")

    # T1: 8-class winner
    raw = fwd.copy()
    raw.columns = TARGET_UNIVERSE
    valid = raw.dropna(how="all")
    winner_idx = pd.Series(index=raw.index, dtype=object)
    winner_idx.loc[valid.index] = valid.idxmax(axis=1)
    code = {t: i for i, t in enumerate(TARGET_UNIVERSE)}
    t1 = winner_idx.map(code).astype("Int64").to_frame("TARGET_T1_winner_idx")
    t1["TARGET_T1_winner_ticker"] = winner_idx
    save_features(t1, "targets", "T1_winner_8class")

    # Strategy holding = top-ranked by 63d momentum (T-1 close info)
    primary_close = close[PRIMARY_UNIVERSE]
    mom63 = rolling_return(primary_close, 63)
    valid_mom = mom63.dropna(how="all")
    pick = pd.Series(index=mom63.index, dtype=object)
    pick.loc[valid_mom.index] = valid_mom.idxmax(axis=1)

    # Forward 21d return of held ETF
    fwd_primary = _forward_returns(close, HORIZON)
    fwd_primary.columns = TARGET_UNIVERSE
    held_fwd = pd.Series(
        [fwd_primary.at[d, t] if isinstance(t, str) and d in fwd_primary.index else np.nan
         for d, t in pick.items()],
        index=pick.index, name="held_fwd_ret",
    )

    # T4: drawdown thresholds
    t4 = pd.DataFrame(index=close.index)
    for thr in [0.03, 0.05, 0.07]:
        col = f"TARGET_T4_drawdown_gt_{int(thr*100)}pct"
        t4[col] = (held_fwd < -thr).astype("Int64")
    t4.loc[held_fwd.isna()] = pd.NA
    save_features(t4, "targets", "T4_drawdown")

    # T5: was systematic strategy correct?
    actual_winner = winner_idx
    t5 = (pick == actual_winner).astype("Int64").to_frame("TARGET_T5_strategy_correct")
    t5.loc[pick.isna() | actual_winner.isna()] = pd.NA
    save_features(t5, "targets", "T5_strategy_correct")

    # T_REGIME: VIX regime + growth-inflation quadrant 21d forward
    vix = _load_feature("macro", "regime_vix").reindex(close.index)
    gi = _load_feature("macro", "regime_growth_inflation").reindex(close.index)
    vix_v = vix.dropna(how="all")
    gi_v = gi.dropna(how="all")
    vix_label = pd.Series(index=vix.index, dtype=object)
    vix_label.loc[vix_v.index] = vix_v.idxmax(axis=1).where(vix_v.sum(axis=1) > 0)
    gi_label = pd.Series(index=gi.index, dtype=object)
    gi_label.loc[gi_v.index] = gi_v.idxmax(axis=1).where(gi_v.sum(axis=1) > 0)
    treg = pd.DataFrame(index=close.index)
    treg["TARGET_TREG_vix_regime_fwd21"] = vix_label.shift(-HORIZON)
    treg["TARGET_TREG_growth_inflation_fwd21"] = gi_label.shift(-HORIZON)
    save_features(treg, "targets", "T_regime_fwd21")

    return {
        "fwd": fwd_primary,
        "winner": winner_idx,
        "pick": pick,
        "held_fwd": held_fwd,
        "t1": t1,
        "t4": t4,
        "t5": t5,
    }


# ============================ VALIDATION ============================

def validate(close: pd.DataFrame, ctx: dict) -> None:
    print("\n=== TARGETS VALIDATION ===")
    winner = ctx["winner"].dropna()
    print("\n[T1] win frequency across history:")
    counts = winner.value_counts(normalize=True).reindex(TARGET_UNIVERSE).fillna(0)
    for t, p in counts.items():
        print(f"  {t}: {p*100:5.1f}%")

    # 2022 vs 2023-24
    for label, sl in [("2022", slice("2022-01-01", "2022-12-31")),
                      ("2023-2024", slice("2023-01-01", "2024-12-31"))]:
        sub = winner.loc[sl]
        if len(sub):
            top = sub.value_counts(normalize=True).head(3)
            print(f"  [{label}] top winners: {top.to_dict()}")

    t4 = ctx["t4"].dropna(how="all")
    print("\n[T4] drawdown frequencies (any holding):")
    for col in t4.columns:
        s = t4[col].dropna()
        if len(s):
            print(f"  {col}: {float(s.mean())*100:5.2f}%  (n={len(s)})")

    t5 = ctx["t5"]["TARGET_T5_strategy_correct"].dropna()
    print(f"\n[T5] systematic strategy base accuracy: {float(t5.mean())*100:5.2f}% "
          f"(n={len(t5)}, random baseline ~12.5%)")

    # March 2020 drawdown flag
    mar = ctx["t4"].loc["2020-02-15":"2020-03-15"]
    print(f"\n[T4 March 2020] >5% drawdown flagged days: "
          f"{int(mar['TARGET_T4_drawdown_gt_5pct'].fillna(0).sum())}/{len(mar)}")

    print("\n=== INTERACTIONS VALIDATION ===")
    energy = pd.read_parquet(FEATURES_DIR / "interaction" / "energy_confirmation.parquet")
    win = energy.loc["2021-09-01":"2021-12-31"]["energy_confirmation"]
    print(f"[energy_confirmation Sep-Dec 2021] mean={win.mean():.3f} "
          f"(>0 means confirming, expect positive: XLE & crude both rising)")


# ============================ MAIN ============================

def main() -> None:
    from src.features.engineer import ALL_TICKERS
    prices = load_prices(ALL_TICKERS)
    close = _stack("adj_close", prices)
    print(f"Loaded {len(prices)} tickers, rows={len(close)}, "
          f"{close.index.min().date()}..{close.index.max().date()}")

    n_int = build_interactions(close)
    print(f"\nInteraction feature files: {n_int}")

    ctx = build_targets(close)
    print("Targets built.")

    validate(close, ctx)


if __name__ == "__main__":
    main()
