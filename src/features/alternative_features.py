"""Phase 4 — alternative-data, cross-asset, and calendar feature builder.

Reads /data/clean/alternative/, /data/clean/calendar/, /data/clean/prices/.
Writes to /data/features/alternative/ and /data/features/calendar/.

Signal semantics follow Phase 4 spec:
 - Google Trends: raw, 4w MA, spike (>2x 13w MA), accel (4w MA - 13w MA)
 - Wikipedia: 21d MA, spike (>3x 63d MA), trend ratio (21d/63d)
 - Activity: MAs, YoY change, z-scores (flagged LAGGING)
 - Cross-asset: ratio features over price data
 - Experimental: github/reddit/bankruptcy — flagged EXPERIMENTAL
 - Calendar: repackage events.parquet into timing + seasonality bundles
"""
from __future__ import annotations


import numpy as np
import pandas as pd

from src.data.utils import DATA_DIR, align_to_trading_days, load_clean
from src.features.engineer import save_features

ALT_CLEAN = DATA_DIR / "clean" / "alternative"
PRICE_CLEAN = DATA_DIR / "clean" / "prices"
CAL_CLEAN = DATA_DIR / "clean" / "calendar"

START = "2005-01-03"
# The builder must never clamp time — always build through today. Upstream
# raw sources may still be stale; that is monitored elsewhere.
END = pd.Timestamp.today().normalize()


def _align(df: pd.DataFrame, freq: str = "daily") -> pd.DataFrame:
    return align_to_trading_days(df, method="ffill", source_freq=freq,
                                 start=START, end=END)


def _load_price(t: str) -> pd.Series:
    return load_clean(PRICE_CLEAN / f"{t}.parquet")["adj_close"]


# Google Trends

GTRENDS_TERMS = [
    "recession", "inflation", "stock_market_crash", "ai_stocks", "gold_buy",
    "bear_market", "bull_market", "layoffs", "unemployment", "interest_rates",
    "tech_stocks", "housing_crash", "bankruptcy", "bank_run", "energy_crisis",
    "semiconductor_shortage", "bitcoin_price", "buy_gold", "oil_price",
]


def step1_gtrends() -> int:
    n = 0
    for term in GTRENDS_TERMS:
        path = ALT_CLEAN / f"gtrends_{term}.parquet"
        if not path.exists():
            continue
        raw = load_clean(path)
        raw = _align(raw, "daily")
        col = raw.columns[0]
        s = raw[col]
        ma_4w = s.rolling(20, min_periods=5).mean().shift(1)
        ma_13w = s.rolling(65, min_periods=20).mean().shift(1)
        spike = (s.shift(1) > 2.0 * ma_13w).astype(float)
        accel = ma_4w - ma_13w
        out = pd.DataFrame({
            f"gtrends_{term}_raw": s.shift(1),
            f"gtrends_{term}_ma4w": ma_4w,
            f"gtrends_{term}_spike": spike,
            f"gtrends_{term}_accel": accel,
        })
        save_features(out, "alternative", f"gtrends_{term}")
        n += 1
    return n


# Wikipedia pageviews

WIKI_PAGES = [
    "recession", "artificial_intelligence", "semiconductor",
    "gold_as_an_investment", "inflation", "stock_market_crash",
    "bear_market", "bank_run", "stagflation", "federal_reserve",
    "quantitative_easing", "yield_curve", "short_selling",
    "subprime_mortgage_crisis", "dot_com_bubble", "nvidia",
    "bitcoin", "cryptocurrency", "nasdaq_100", "s_p_500",
    "margin_finance", "unemployment", "oil_crisis", "trade_war",
]


def step2_wikipedia() -> int:
    n = 0
    for page in WIKI_PAGES:
        path = ALT_CLEAN / f"wikipedia_{page}.parquet"
        if not path.exists():
            continue
        raw = _align(load_clean(path), "daily")
        col = raw.columns[0]
        s = raw[col]
        ma_21 = s.rolling(21, min_periods=5).mean().shift(1)
        ma_63 = s.rolling(63, min_periods=20).mean().shift(1)
        spike = (s.shift(1) > 3.0 * ma_63).astype(float)
        ratio = ma_21 / ma_63.replace(0, np.nan)
        out = pd.DataFrame({
            f"wiki_{page}_ma21": ma_21,
            f"wiki_{page}_spike": spike,
            f"wiki_{page}_trend": ratio,
        })
        save_features(out, "alternative", f"wikipedia_{page}")
        n += 1
    return n


# Economic activity proxies

def _yoy_weekly(s: pd.Series, weeks: int = 52) -> pd.Series:
    return s / s.shift(weeks * 5) - 1.0


def _zscore(s: pd.Series, window: int) -> pd.Series:
    m = s.rolling(window, min_periods=window // 2).mean()
    sd = s.rolling(window, min_periods=window // 2).std()
    return (s - m) / sd.replace(0, np.nan)


def step3_activity() -> int:
    n = 0

    # TSA passengers
    p = ALT_CLEAN / "tsa_passengers.parquet"
    if p.exists():
        s = _align(load_clean(p), "daily").iloc[:, 0]
        out = pd.DataFrame({
            "tsa_passengers_ma7": s.rolling(7, min_periods=2).mean().shift(1),
            "tsa_passengers_yoy": (s / s.shift(252) - 1.0).shift(1),
            "tsa_passengers_z52w": _zscore(s, 252).shift(1),
        })
        save_features(out, "alternative", "activity_tsa_passengers")
        n += 1

    # Airline passengers (broader, longer history)
    p = ALT_CLEAN / "airline_passengers.parquet"
    if p.exists():
        df = _align(load_clean(p), "monthly")
        s = df.iloc[:, 0]
        out = pd.DataFrame({
            "airline_pax_ma3": s.rolling(66, min_periods=20).mean().shift(1),
            "airline_pax_yoy": (s / s.shift(252) - 1.0).shift(1),
            "airline_pax_z52w": _zscore(s, 252).shift(1),
        })
        save_features(out, "alternative", "activity_airline_passengers")
        n += 1

    # EIA gasoline demand
    p = ALT_CLEAN / "eia_gasoline_demand.parquet"
    if p.exists():
        s = _align(load_clean(p), "weekly").iloc[:, 0]
        out = pd.DataFrame({
            "gasoline_demand_ma4w": s.rolling(20, min_periods=5).mean().shift(1),
            "gasoline_demand_yoy": (s / s.shift(252) - 1.0).shift(1),
            "gasoline_demand_z52w": _zscore(s, 252).shift(1),
        })
        save_features(out, "alternative", "activity_gasoline_demand")
        n += 1

    # Rail traffic
    p = ALT_CLEAN / "rail_traffic.parquet"
    if p.exists():
        s = _align(load_clean(p), "weekly").iloc[:, 0]
        out = pd.DataFrame({
            "rail_traffic_ma4w": s.rolling(20, min_periods=5).mean().shift(1),
            "rail_traffic_yoy": (s / s.shift(252) - 1.0).shift(1),
        })
        save_features(out, "alternative", "activity_rail_traffic")
        n += 1

    # Electricity sales
    p = ALT_CLEAN / "eia_electricity_sales.parquet"
    if p.exists():
        s = _align(load_clean(p), "monthly").iloc[:, 0]
        out = pd.DataFrame({
            "electricity_yoy": (s / s.shift(252) - 1.0).shift(1),
            "electricity_trend_3m": (s.rolling(63, min_periods=20).mean() /
                                      s.rolling(252, min_periods=60).mean()).shift(1),
        })
        save_features(out, "alternative", "activity_electricity")
        n += 1

    # Port LA containers
    p = ALT_CLEAN / "port_la_containers.parquet"
    if p.exists():
        df = _align(load_clean(p), "monthly")
        s = df["monthly_total_teus"] if "monthly_total_teus" in df.columns else df.iloc[:, 0]
        out = pd.DataFrame({
            "port_la_teu_yoy": (s / s.shift(252) - 1.0).shift(1),
        })
        save_features(out, "alternative", "activity_port_la")
        n += 1

    return n


# Cross-asset ratios

def step4_cross_asset() -> int:
    n = 0
    # load prices
    need = ["GLD", "TLT", "HYG", "USO", "EEM", "SPY", "IWM", "UUP"]
    px = {}
    for t in need:
        p = PRICE_CLEAN / f"{t}.parquet"
        if p.exists():
            px[t] = _load_price(t)
    close = pd.DataFrame(px)
    close = _align(close, "daily")

    def _save(d: pd.DataFrame, name: str):
        save_features(d, "alternative", name)

    # copper/gold — use pre-cleaned ratio
    p = ALT_CLEAN / "copper_gold_ratio.parquet"
    if p.exists():
        cg = _align(load_clean(p), "daily").iloc[:, 0]
        out = pd.DataFrame({
            "copper_gold_ratio": cg.shift(1),
            "copper_gold_chg_63d": (cg / cg.shift(63) - 1.0).shift(1),
        })
        _save(out, "cross_asset_copper_gold"); n += 1

    # lumber/gold
    p = ALT_CLEAN / "lumber_gold_ratio.parquet"
    if p.exists():
        lg = _align(load_clean(p), "daily").iloc[:, 0]
        out = pd.DataFrame({
            "lumber_gold_ratio": lg.shift(1),
            "lumber_gold_chg_63d": (lg / lg.shift(63) - 1.0).shift(1),
        })
        _save(out, "cross_asset_lumber_gold"); n += 1

    # gold/bonds: GLD 63d ret - TLT 63d ret
    if "GLD" in close and "TLT" in close:
        r63 = close.pct_change(63)
        out = pd.DataFrame({
            "gold_minus_bonds_63d": (r63["GLD"] - r63["TLT"]).shift(1),
        })
        _save(out, "cross_asset_gold_bonds"); n += 1

    # oil/gold: USO / GLD
    if "USO" in close and "GLD" in close:
        ratio = close["USO"] / close["GLD"]
        out = pd.DataFrame({
            "oil_gold_ratio": ratio.shift(1),
            "oil_gold_chg_63d": (ratio / ratio.shift(63) - 1.0).shift(1),
        })
        _save(out, "cross_asset_oil_gold"); n += 1

    # HYG/TLT: 21d credit appetite
    if "HYG" in close and "TLT" in close:
        r21 = close.pct_change(21)
        out = pd.DataFrame({
            "hyg_minus_tlt_21d": (r21["HYG"] - r21["TLT"]).shift(1),
        })
        _save(out, "cross_asset_credit_appetite"); n += 1

    # EEM/SPY 63d
    if "EEM" in close and "SPY" in close:
        r63 = close.pct_change(63)
        out = pd.DataFrame({
            "eem_minus_spy_63d": (r63["EEM"] - r63["SPY"]).shift(1),
        })
        _save(out, "cross_asset_eem_spy"); n += 1

    # IWM/SPY 63d
    if "IWM" in close and "SPY" in close:
        r63 = close.pct_change(63)
        out = pd.DataFrame({
            "iwm_minus_spy_63d": (r63["IWM"] - r63["SPY"]).shift(1),
        })
        _save(out, "cross_asset_iwm_spy"); n += 1

    # DXY inverse via UUP: negative 21d return = dollar weakening
    if "UUP" in close:
        r21 = close["UUP"].pct_change(21)
        out = pd.DataFrame({
            "dxy_inv_21d": (-r21).shift(1),
        })
        _save(out, "cross_asset_dxy_inv"); n += 1

    return n


# Experimental

GITHUB_REPOS = ["amd", "apple", "google", "meta", "microsoft", "nvidia"]
REDDIT_SUBS = ["economics", "investing", "stocks", "wallstreetbets"]


def step5_experimental() -> int:
    n = 0

    # GitHub commits
    gh = {}
    for repo in GITHUB_REPOS:
        p = ALT_CLEAN / f"github_{repo}.parquet"
        if p.exists():
            s = _align(load_clean(p), "weekly").iloc[:, 0]
            gh[f"github_{repo}_ma4w"] = s.rolling(20, min_periods=4).mean().shift(1)
            gh[f"github_{repo}_trend"] = (
                s.rolling(20, min_periods=4).mean() /
                s.rolling(65, min_periods=15).mean().replace(0, np.nan)
            ).shift(1)
    if gh:
        save_features(pd.DataFrame(gh), "alternative", "experimental_github_commits")
        n += 1

    # Reddit
    rd = {}
    for sub in REDDIT_SUBS:
        p = ALT_CLEAN / f"reddit_{sub}.parquet"
        if p.exists():
            df = _align(load_clean(p), "daily")
            if "posts_21d_mean" in df.columns:
                rd[f"reddit_{sub}_posts_ma7"] = df["posts"].rolling(7, min_periods=2).mean().shift(1)
                rd[f"reddit_{sub}_spike"] = (df["posts_spike_ratio"] > 3.0).astype(float).shift(1)
                rd[f"reddit_{sub}_vol_ratio"] = df["posts_spike_ratio"].shift(1)
    if rd:
        save_features(pd.DataFrame(rd), "alternative", "experimental_reddit")
        n += 1

    # Bankruptcy filings
    p = ALT_CLEAN / "bankruptcy_filings.parquet"
    if p.exists():
        s = _align(load_clean(p), "quarterly").iloc[:, 0]
        out = pd.DataFrame({
            "bankruptcy_filings_ma63": s.rolling(63, min_periods=10).mean().shift(1),
            "bankruptcy_filings_yoy": (s / s.shift(252) - 1.0).shift(1),
        })
        save_features(out, "alternative", "experimental_bankruptcy")
        n += 1

    # Baltic Dry Index
    p = ALT_CLEAN / "baltic_dry.parquet"
    if p.exists():
        s = _align(load_clean(p), "daily").iloc[:, 0]
        out = pd.DataFrame({
            "baltic_dry": s.shift(1),
            "baltic_dry_chg_63d": (s / s.shift(63) - 1.0).shift(1),
        })
        save_features(out, "alternative", "experimental_baltic_dry")
        n += 1

    return n


# Calendar

def step6_calendar() -> int:
    ev = load_clean(CAL_CLEAN / "events.parquet")
    ev = ev.sort_index()
    ev = ev[~ev.index.duplicated(keep="last")]
    cal_cols_timing = [
        "days_since_last_fomc", "days_to_next_fomc",
        "is_fomc_day", "is_fomc_week",
        "is_cpi_week", "is_nfp_week", "is_gdp_week",
        "is_earnings_season", "is_opex_week",
        "is_quad_witching_week", "is_russell_recon_week",
        "is_sp_rebalance_week", "is_election_month",
        "is_ecb_day", "is_boj_week", "is_cn_pmi_week",
    ]
    present = [c for c in cal_cols_timing if c in ev.columns]
    timing = ev[present].copy()
    # shift(1): use flags known at prior close
    timing = timing.shift(1)
    save_features(timing, "calendar", "timing")

    season_cols = ["month_sin", "month_cos", "woy_sin", "woy_cos",
                   "dom_sin", "dom_cos"]
    present = [c for c in season_cols if c in ev.columns]
    # Seasonality is deterministic — no shift needed, but keep consistent:
    seasonality = ev[present].copy()
    save_features(seasonality, "calendar", "seasonality")
    return 2


# Validation

def validate() -> None:
    print("\n=== VALIDATION ===")

    # Cross-asset copper/gold in Mar 2020
    try:
        cg = pd.read_parquet(DATA_DIR / "features/alternative/cross_asset_copper_gold.parquet")
        jan = cg.loc["2020-01":"2020-02", "copper_gold_ratio"].mean()
        mar = cg.loc["2020-03", "copper_gold_ratio"].mean()
        rec = cg.loc["2020-11":"2021-03", "copper_gold_ratio"].mean()
        print(f"[copper/gold] pre-covid={jan:.5f}  mar2020={mar:.5f}  recovery={rec:.5f}  "
              f"drop={'OK' if mar < jan else 'FAIL'}  recover={'OK' if rec > mar else 'FAIL'}")
    except Exception as e:
        print(f"[copper/gold] ERR {e}")

    # FOMC flags vs known 2023 dates (Mar 22, May 3, Jul 26, Nov 1, Dec 13)
    try:
        cal = pd.read_parquet(DATA_DIR / "features/calendar/timing.parquet")
        known = ["2023-03-23", "2023-05-04", "2023-07-27", "2023-11-02", "2023-12-14"]
        # timing uses shift(1): FOMC day T should show in row T+1
        hits = [d for d in known if d in cal.index and cal.loc[d, "is_fomc_day"] == 1.0]
        print(f"[fomc 2023] {len(hits)}/5 known FOMC day flags present (t+1): {hits}")
    except Exception as e:
        print(f"[fomc] ERR {e}")

    # Experimental availability summary
    exp_files = list((DATA_DIR / "features/alternative").glob("experimental_*.parquet"))
    print(f"\n[experimental] {len(exp_files)} files")
    for p in exp_files:
        df = pd.read_parquet(p)
        nan_pct = df.isna().mean().mean() * 100
        var_cols = int((df.std() > 1e-12).sum())
        rng = f"{df.index.min().date()}..{df.index.max().date()}" if len(df) else "empty"
        print(f"  {p.stem:45s} cols={len(df.columns):2d} non_const={var_cols:2d} "
              f"nan={nan_pct:5.1f}%  {rng}")


# Main

def main() -> None:
    total = 0
    total += step1_gtrends(); print(f"[step1] gtrends files written")
    total += step2_wikipedia(); print(f"[step2] wikipedia files written")
    total += step3_activity(); print(f"[step3] activity files written")
    total += step4_cross_asset(); print(f"[step4] cross-asset files written")
    total += step5_experimental(); print(f"[step5] experimental files written")
    total += step6_calendar(); print(f"[step6] calendar files written")
    print(f"\nTotal feature files created: {total}")
    validate()


if __name__ == "__main__":
    main()
