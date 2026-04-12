"""Phase 4 sentiment + fundamental feature builder.

Reads /data/clean/sentiment and /data/clean/fundamental, applies publication-lag
shifts, reindexes onto the NYSE trading calendar, then writes one parquet per
signal under /data/features/{sentiment,fundamental}/.

Only sources whose Phase-3 cleans landed in /data/clean/ are touched. Sources
listed as failed in FAILED_SOURCES.md (investors_intelligence, etf_flow,
dark_pool, IPO data, sector PE per-industry, insider_transactions ≤ 196 rows)
are skipped — see SKIPPED at bottom.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from src.data.utils import DATA_DIR, align_to_trading_days, load_clean
from src.features.engineer import save_features, load_prices

CLEAN_SENT = DATA_DIR / "clean" / "sentiment"
CLEAN_FUND = DATA_DIR / "clean" / "fundamental"

# Publication-lag map (calendar days). Conservative — Tuesday COT positions
# only become public Friday afternoon, so we use 4 to land on the next Monday.
LAG_DAYS = {
    "aaii": 1,
    "naaim": 1,
    "fear_greed": 1,
    "cot": 4,
    "putcall": 1,
    "margin_debt": 30,
    "short_interest": 1,
    "news": 1,
    "sp500_daily": 1,
    "shiller": 30,
    "buyback": 60,
    "sia": 45,
}

START = "2003-01-01"
END = "2026-04-12"


def _load_clean(rel: Path, lag_key: str, freq: str = "daily") -> pd.DataFrame:
    df = load_clean(CLEAN_SENT / rel) if (CLEAN_SENT / rel).exists() else load_clean(CLEAN_FUND / rel)
    df = df.sort_index()
    df = df[~df.index.duplicated(keep="last")]
    df.index = df.index + pd.Timedelta(days=LAG_DAYS[lag_key])
    return align_to_trading_days(df, method="ffill", source_freq=freq, start=START, end=END)


def _zscore(s: pd.Series, window: int) -> pd.Series:
    m = s.rolling(window, min_periods=max(20, window // 4)).mean()
    sd = s.rolling(window, min_periods=max(20, window // 4)).std()
    return (s - m) / sd.replace(0, np.nan)


def _save(df: pd.DataFrame, category: str, name: str) -> None:
    save_features(df, category, name)


# ============================ STEP 1: SURVEY ============================

def step1_survey() -> int:
    n = 0

    # AAII
    aaii_path = CLEAN_SENT / "aaii_sentiment.parquet"
    if aaii_path.exists():
        a = _load_clean(Path("aaii_sentiment.parquet"), "aaii", freq="weekly")
        spread = a["bull_bear_spread"].astype(float)
        _save(spread.to_frame("aaii_spread"), "sentiment", "survey_aaii_spread"); n += 1
        _save(spread.rolling(20).mean().to_frame("aaii_spread_4w_ma"),
              "sentiment", "survey_aaii_spread_4w_ma"); n += 1
        _save(_zscore(spread, 252).to_frame("aaii_spread_z52w"),
              "sentiment", "survey_aaii_spread_z52w"); n += 1
        _save((spread < -20).astype(float).to_frame("aaii_extreme_pessimism"),
              "sentiment", "survey_aaii_extreme_pessimism"); n += 1
        _save((spread > 30).astype(float).to_frame("aaii_extreme_bullish"),
              "sentiment", "survey_aaii_extreme_bullish"); n += 1

    # NAAIM
    naaim_path = CLEAN_SENT / "naaim_exposure.parquet"
    if naaim_path.exists():
        nm = _load_clean(Path("naaim_exposure.parquet"), "naaim", freq="weekly")
        exp = nm["naaim_exposure"].astype(float)
        _save(exp.to_frame("naaim_exposure"), "sentiment", "survey_naaim_exposure"); n += 1
        _save(exp.rolling(20).mean().to_frame("naaim_exposure_4w_ma"),
              "sentiment", "survey_naaim_exposure_4w_ma"); n += 1
        _save(_zscore(exp, 252).to_frame("naaim_z52w"),
              "sentiment", "survey_naaim_z52w"); n += 1
        _save((exp < 40).astype(float).to_frame("naaim_low_flag"),
              "sentiment", "survey_naaim_low_flag"); n += 1

    # CNN Fear & Greed — only the *reconstructed* file has long history.
    fg_path = CLEAN_SENT / "fear_greed_reconstructed.parquet"
    if fg_path.exists():
        fg = _load_clean(Path("fear_greed_reconstructed.parquet"), "fear_greed", freq="daily")
        lvl = fg["fear_greed_reconstructed"].astype(float)
        _save(lvl.to_frame("fear_greed_level"), "sentiment", "survey_fg_level"); n += 1
        _save(lvl.rolling(21).mean().to_frame("fear_greed_21d_ma"),
              "sentiment", "survey_fg_21d_ma"); n += 1
        _save((lvl < 20).astype(float).to_frame("fear_greed_extreme_fear"),
              "sentiment", "survey_fg_extreme_fear"); n += 1
        _save((lvl > 80).astype(float).to_frame("fear_greed_extreme_greed"),
              "sentiment", "survey_fg_extreme_greed"); n += 1

    return n


# ============================ STEP 2: POSITIONING ============================

COT_CONTRACTS = {
    "crude": "cot_crude_oil_wti.parquet",
    "gold": "cot_gold.parquet",
    "sp500": "cot_sp500_emini.parquet",
    "nasdaq": "cot_nasdaq_emini.parquet",
    "ust10y": "cot_ust_10y.parquet",
    "usd": "cot_usd_index.parquet",
}


def step2_positioning() -> int:
    n = 0

    # COT
    for label, fname in COT_CONTRACTS.items():
        p = CLEAN_SENT / fname
        if not p.exists():
            continue
        c = _load_clean(Path(fname), "cot", freq="weekly")
        mm_net = c["managed_money_net"].astype(float)
        comm_net = c["commercial_net"].astype(float)
        z = c["mm_net_zscore_52w"].astype(float) if "mm_net_zscore_52w" in c.columns else _zscore(mm_net, 260)
        _save(mm_net.to_frame(f"cot_{label}_mm_net"),
              "sentiment", f"positioning_cot_{label}_mm_net"); n += 1
        _save(z.to_frame(f"cot_{label}_mm_net_z52w"),
              "sentiment", f"positioning_cot_{label}_mm_net_z52w"); n += 1
        _save(mm_net.diff(20).to_frame(f"cot_{label}_mm_net_4w_chg"),
              "sentiment", f"positioning_cot_{label}_mm_net_4w_chg"); n += 1
        _save((z > 1.5).astype(float).to_frame(f"cot_{label}_extreme_long"),
              "sentiment", f"positioning_cot_{label}_extreme_long"); n += 1
        _save((z < -1.5).astype(float).to_frame(f"cot_{label}_extreme_short"),
              "sentiment", f"positioning_cot_{label}_extreme_short"); n += 1
        _save((comm_net - mm_net).to_frame(f"cot_{label}_comm_vs_spec"),
              "sentiment", f"positioning_cot_{label}_comm_vs_spec"); n += 1

    # Put/Call ratios — spliced files exist, but post-2019 portion is a weak
    # VIX proxy (per FEATURE_CATALOG fold note). Build features only on the
    # native CBOE window 2003-10-17..2019-10-04. Phase-4 fold logic gates the
    # post-2019 portion separately.
    for col, fname, tag in [
        ("cboe_putcall_equity", "cboe_putcall_equity.parquet", "equity"),
        ("cboe_putcall_total", "cboe_putcall_total.parquet", "total"),
        ("cboe_putcall_index", "cboe_putcall_index.parquet", "index"),
    ]:
        p = CLEAN_SENT / fname
        if not p.exists():
            continue
        d = _load_clean(Path(fname), "putcall", freq="daily")
        s = d[col].astype(float)
        _save(s.rolling(5).mean().to_frame(f"pcr_{tag}_5d_ma"),
              "sentiment", f"positioning_pcr_{tag}_5d_ma"); n += 1
        _save(s.rolling(21).mean().to_frame(f"pcr_{tag}_21d_ma"),
              "sentiment", f"positioning_pcr_{tag}_21d_ma"); n += 1
        _save(_zscore(s, 252).to_frame(f"pcr_{tag}_z252d"),
              "sentiment", f"positioning_pcr_{tag}_z252d"); n += 1
        if tag == "equity":
            _save((s.rolling(5).mean() > 1.2).astype(float).to_frame("pcr_equity_extreme_put"),
                  "sentiment", "positioning_pcr_equity_extreme_put"); n += 1
            _save((s.rolling(5).mean() < 0.6).astype(float).to_frame("pcr_equity_extreme_call"),
                  "sentiment", "positioning_pcr_equity_extreme_call"); n += 1

    # Margin debt (FRED, monthly)
    md_path = CLEAN_SENT / "margin_debt_fred.parquet"
    if md_path.exists():
        md = _load_clean(Path("margin_debt_fred.parquet"), "margin_debt", freq="monthly")
        s = md["margin_debt_fred"].astype(float)
        _save(s.to_frame("margin_debt"), "sentiment", "positioning_margin_debt"); n += 1
        _save(s.pct_change(63).to_frame("margin_debt_3m_chg"),
              "sentiment", "positioning_margin_debt_3m_chg"); n += 1
        # % of SPY market cap proxy via SPY close (cap not available; use price-relative)
        try:
            spy = load_clean(DATA_DIR / "clean" / "prices" / "SPY.parquet")["adj_close"]
            spy = align_to_trading_days(spy.to_frame("c"), source_freq="daily",
                                        start=START, end=END)["c"]
            ratio = (s / spy).replace([np.inf, -np.inf], np.nan)
            _save(ratio.to_frame("margin_debt_per_spy_px"),
                  "sentiment", "positioning_margin_debt_per_spy_px"); n += 1
        except Exception:
            pass

    # Short interest (FINRA short volume — daily)
    si_path = CLEAN_SENT / "short_interest.parquet"
    if si_path.exists():
        si = _load_clean(Path("short_interest.parquet"), "short_interest", freq="daily")
        s = si["short_volume_ratio_21d"].astype(float)
        _save(s.to_frame("short_volume_ratio_21d"),
              "sentiment", "positioning_short_volume_ratio_21d"); n += 1
        _save(s.diff(10).to_frame("short_volume_ratio_2w_chg"),
              "sentiment", "positioning_short_volume_ratio_2w_chg"); n += 1

    return n


# ============================ STEP 3: NEWS ============================

NEWS_TOPICS = ["tech", "energy", "inflation", "recession", "market", "gold"]


def step3_news() -> int:
    n = 0
    sentiments: dict[str, pd.Series] = {}
    counts: dict[str, pd.Series] = {}
    for topic in NEWS_TOPICS:
        p = CLEAN_SENT / f"news_sentiment_{topic}.parquet"
        if not p.exists():
            continue
        d = _load_clean(Path(f"news_sentiment_{topic}.parquet"), "news", freq="daily")
        mean_col = f"{topic}_mean_sent"
        neg_col = f"{topic}_neg_share"
        cnt_col = f"{topic}_count"
        if mean_col not in d.columns:
            continue
        sent = d[mean_col].astype(float)
        sentiments[topic] = sent
        counts[topic] = d[cnt_col].astype(float)

        s21 = sent.rolling(21, min_periods=5).mean()
        s63 = sent.rolling(63, min_periods=10).mean()
        _save(s21.to_frame(f"news_{topic}_sent_21d_ma"),
              "sentiment", f"news_{topic}_sent_21d_ma"); n += 1
        _save(s63.to_frame(f"news_{topic}_sent_63d_ma"),
              "sentiment", f"news_{topic}_sent_63d_ma"); n += 1
        _save((s21 - s63).to_frame(f"news_{topic}_sent_accel"),
              "sentiment", f"news_{topic}_sent_accel"); n += 1
        neg5 = d[neg_col].astype(float).rolling(5, min_periods=2).mean()
        _save((neg5 > 0.6).astype(float).to_frame(f"news_{topic}_neg_spike"),
              "sentiment", f"news_{topic}_neg_spike"); n += 1
        cnt = d[cnt_col].astype(float)
        cnt_z = _zscore(cnt, 252)
        _save((cnt_z > 2).astype(float).to_frame(f"news_{topic}_volume_spike"),
              "sentiment", f"news_{topic}_volume_spike"); n += 1

    # Sentiment-vs-price divergence: SOXX vs tech, XLE vs energy
    try:
        prices = load_prices(["SOXX", "XLE"])
        for ticker, topic in [("SOXX", "tech"), ("XLE", "energy")]:
            if topic not in sentiments:
                continue
            px = prices[ticker]["adj_close"]
            mom21 = px.pct_change(21).shift(1)
            mom21 = align_to_trading_days(mom21.to_frame("m"), source_freq="daily",
                                          start=START, end=END)["m"]
            sent21 = sentiments[topic].rolling(21, min_periods=5).mean()
            both = pd.concat([mom21, sent21], axis=1).dropna()
            div = (np.sign(both.iloc[:, 0]) - np.sign(both.iloc[:, 1])).reindex(mom21.index)
            _save(div.to_frame(f"news_div_{ticker}_{topic}"),
                  "sentiment", f"news_div_{ticker}_{topic}"); n += 1
    except Exception as e:
        print("[news div skipped]", e)

    return n


# ============================ STEP 4: FUNDAMENTAL ============================

def step4_fundamental() -> int:
    n = 0

    pe_path = CLEAN_FUND / "sp500_pe_ratio.parquet"
    if pe_path.exists():
        pe = _load_clean(Path("sp500_pe_ratio.parquet"), "sp500_daily", freq="daily")
        s = pe["pe_ratio"].astype(float)
        _save(s.to_frame("sp500_pe"), "fundamental", "sp500_pe"); n += 1
        _save(s.rolling(2520, min_periods=252).rank(pct=True).to_frame("sp500_pe_pct_10y"),
              "fundamental", "sp500_pe_pct_10y"); n += 1

    ey_path = CLEAN_FUND / "sp500_earnings_yield.parquet"
    if ey_path.exists():
        ey = _load_clean(Path("sp500_earnings_yield.parquet"), "sp500_daily", freq="daily")
        s = ey["earnings_yield"].astype(float)
        _save(s.to_frame("sp500_earnings_yield"),
              "fundamental", "sp500_earnings_yield"); n += 1
        # Equity risk premium proxy: earnings yield − 10Y treasury
        try:
            tnx = load_clean(DATA_DIR / "clean" / "macro" / "treasury_10y.parquet")
            tnx_col = tnx.columns[0]
            tnx_s = align_to_trading_days(tnx, source_freq="daily",
                                          start=START, end=END)[tnx_col].astype(float)
            erp = (s - tnx_s).to_frame("sp500_erp_proxy")
            _save(erp, "fundamental", "sp500_erp_proxy"); n += 1
        except Exception as e:
            print("[ERP skipped]", e)

    dy_path = CLEAN_FUND / "sp500_dividend_yield.parquet"
    if dy_path.exists():
        dy = _load_clean(Path("sp500_dividend_yield.parquet"), "sp500_daily", freq="daily")
        _save(dy["dividend_yield"].astype(float).to_frame("sp500_div_yield"),
              "fundamental", "sp500_div_yield"); n += 1

    cape_path = CLEAN_FUND / "sp500_shiller_cape.parquet"
    if cape_path.exists():
        cape = _load_clean(Path("sp500_shiller_cape.parquet"), "shiller", freq="monthly")
        s = cape["shiller_cape"].astype(float)
        _save(s.to_frame("sp500_cape"), "fundamental", "sp500_cape"); n += 1
        _save(s.rolling(2520, min_periods=252).rank(pct=True).to_frame("sp500_cape_pct_10y"),
              "fundamental", "sp500_cape_pct_10y"); n += 1

    bb_path = CLEAN_FUND / "sp500_buyback_yield.parquet"
    if bb_path.exists():
        bb = _load_clean(Path("sp500_buyback_yield.parquet"), "buyback", freq="quarterly")
        _save(bb["sp500_buyback_yield"].astype(float).to_frame("sp500_buyback_yield"),
              "fundamental", "sp500_buyback_yield"); n += 1

    sia_path = CLEAN_FUND / "sia_semiconductor_sales.parquet"
    if sia_path.exists():
        sia = _load_clean(Path("sia_semiconductor_sales.parquet"), "sia", freq="monthly")
        _save(sia["sales_usd_bn"].astype(float).to_frame("sia_semi_sales"),
              "fundamental", "sia_semi_sales"); n += 1
        _save(sia["yoy_pct"].astype(float).to_frame("sia_semi_yoy"),
              "fundamental", "sia_semi_yoy"); n += 1
        # 3-month trend = 3m diff of yoy
        _save(sia["yoy_pct"].astype(float).diff(63).to_frame("sia_semi_yoy_3m_chg"),
              "fundamental", "sia_semi_yoy_3m_chg"); n += 1

    return n


# ============================ VALIDATION ============================

def validate() -> None:
    print("\n=== VALIDATION ===")

    # AAII extreme pessimism around Mar 2020 + Oct 2022
    p = DATA_DIR / "features" / "sentiment" / "survey_aaii_extreme_pessimism.parquet"
    if p.exists():
        f = pd.read_parquet(p)
        m20 = f.loc["2020-03-01":"2020-04-15"].sum().iloc[0]
        m22 = f.loc["2022-09-15":"2022-11-15"].sum().iloc[0]
        print(f"[AAII] extreme pessimism days Mar2020={int(m20)}, Oct2022={int(m22)}")

    # COT crude — speculators net long before 2022 oil rally (early 2022)
    p = DATA_DIR / "features" / "sentiment" / "positioning_cot_crude_mm_net.parquet"
    if p.exists():
        f = pd.read_parquet(p)
        early22 = f.loc["2022-01-01":"2022-02-28"].mean().iloc[0]
        print(f"[COT crude] mean MM net Jan-Feb 2022 = {early22:.0f} (>0 = net long)")

    # News energy sentiment turning positive late 2021
    p = DATA_DIR / "features" / "sentiment" / "news_energy_sent_21d_ma.parquet"
    if p.exists():
        f = pd.read_parquet(p)
        q4 = f.loc["2021-10-01":"2021-12-31"].mean().iloc[0]
        q1 = f.loc["2021-01-01":"2021-03-31"].mean().iloc[0]
        print(f"[news energy] sent_21d_ma Q1-2021={q1:.3f}  Q4-2021={q4:.3f}")

    # Count features
    sent_dir = DATA_DIR / "features" / "sentiment"
    fund_dir = DATA_DIR / "features" / "fundamental"
    sn = len(list(sent_dir.glob("*.parquet"))) if sent_dir.exists() else 0
    fn = len(list(fund_dir.glob("*.parquet"))) if fund_dir.exists() else 0
    print(f"[counts] sentiment files = {sn}, fundamental files = {fn}")

    # Orphan check: ensure no features reference failed sources
    forbidden = ["investors_intel", "etf_flow", "darkpool", "ipo_volume",
                 "tech_sector_pe", "energy_sector_earn", "insider_"]
    orphans = []
    for d in [sent_dir, fund_dir]:
        if not d.exists():
            continue
        for f in d.glob("*.parquet"):
            for tok in forbidden:
                if tok in f.name.lower():
                    orphans.append(f.name)
    print(f"[orphan check] {len(orphans)} orphan features (should be 0)")
    if orphans:
        for o in orphans:
            print(" ", o)


# ============================ MAIN ============================

def main() -> None:
    print(f"Building Phase-4 sentiment + fundamental features ({START}..{END})")
    n1 = step1_survey();      print(f"  step1 survey:       {n1} files")
    n2 = step2_positioning(); print(f"  step2 positioning:  {n2} files")
    n3 = step3_news();        print(f"  step3 news:         {n3} files")
    n4 = step4_fundamental(); print(f"  step4 fundamental:  {n4} files")
    print(f"  TOTAL:              {n1+n2+n3+n4} files")
    validate()


if __name__ == "__main__":
    main()
