# Data Notes — gotchas and source choices for Phase 4+

Context file for future phases. Each entry below was learned the hard way
during sessions 3.1–3.4. Read before building features off any of these series.

## Gold prices

- **`data/clean/fundamental/sector_gold_london_fix.parquet`** (Macrotrends, id=1333)
  is **inflation-adjusted to current dollars**. The "1915 close = $629" in the
  raw data is real-USD-equivalent, not nominal. Do **not** use for momentum,
  return, or any price-based feature.
- **`data/clean/prices/GLD.parquet`** (Yahoo) is nominal. Use this for all
  return / momentum / volatility features on gold.
- The macrotrends series is only useful as a long-history *real price level*
  reference (e.g. CPI-adjusted regime detection).

## Silver prices

- Same caveat. **`sector_silver_price.parquet`** (Macrotrends id=1470) is
  inflation-adjusted. Use **`data/clean/prices/SLV.parquet`** for nominal features.

## Commodity overlap (avoid duplicate features)

| Commodity | Primary | Extended history | Notes |
|---|---|---|---|
| WTI crude | FRED `DCOILWTICO` (daily, 1986+) | Macrotrends `sector_crude_oil_wti` (1946–) | Macrotrends only useful pre-1986 |
| Natural gas (Henry Hub) | FRED `DHHNGSP` (daily, 1997+) | Macrotrends `sector_natural_gas_henry_hub` (1997–) | Same range — Macrotrends adds nothing; pick one |
| Copper | Macrotrends `sector_copper_price` (daily, 1959+) | FRED `PCOPPUSDM` (monthly) | Macrotrends is the daily one |
| Gold (nominal) | Yahoo `GLD` (2004+) | — | No good free pre-2004 nominal source |
| Silver (nominal) | Yahoo `SLV` (2006+) | — | Same |

**Phase 4 rule:** do not build the same feature (e.g. 21d return) from both
sources for the same commodity. Pick one per series and document the choice
in the feature spec.

## Macrotrends commodity series — frequency mismatch

- The macrotrends parquets for crude / gold / silver / natural gas are
  flagged `frequency=daily` in the catalog but the **actual underlying data
  is monthly** before ~2000 and daily after. Result: ~73% NaN when reindexed
  to a daily trading-day calendar with the default 5-day forward-fill limit.
- Phase 4 should either (a) re-fetch and re-save with `source_freq="monthly"`
  in `align_to_trading_days`, or (b) treat these as month-end series and
  resample.

## Margin debt

- **FINRA margin debt** (the published one) is not free-scrapable —
  `finra.org/.../margin-statistics` is Akamai-blocked, no public CSV.
- **FRED `BOGZ1FL663067003Q`** is the substitute. **Do not assume the levels
  match.** FRED uses Z.1 Flow of Funds methodology and reports ~$500B at the
  2021 peak; FINRA gross debit balances were ~$900B at the same point.
- **Direction is the same.** Z-score before use to eliminate the level
  difference. Don't compare absolute levels across the two series in any
  feature or backtest.

## CBOE put/call ratio

- **Not available from any free source.** All `cdn.cboe.com` PCR endpoints
  return 403; the HTML pages are blocked by both robots.txt and Cloudflare.
- Datashop.cboe.com sells the historical feed. Until that's funded:
  **do not build features that depend on equity or index put/call ratio.**
- Possible future workaround: derive a proxy from per-ETF Yahoo options
  volume (SPY/QQQ/IWM total put vs call open interest). Approximate but free.

## CBOE — what IS available

- SKEW (1990+), VIX/VIX9D/VIX3M/VIX6M (varying starts) all download cleanly
  from `cdn.cboe.com/api/global/us_indices/daily_prices/<X>_History.csv`.
- The derived **VIX/VIX3M term structure** (`cboe_vix_term_structure.parquet`)
  contains the contango/backwardation ratio + spread. Validated signal — see
  below.

## OpenInsider

- **Screener backend currently broken** — every `screener?fdr=...` query
  returns the literal HTML string `ERROR: Unable to select tables for main`.
  This is server-side, not a bot block. Re-test in session 3.7.
- Until then, **`insider_transactions.parquet` contains only the latest ~196
  trades** (preset `/insider-purchases` + `/insider-sales` snapshot). It is
  **not enough data to build features on.** Do not use it in Phase 4.
- Spot check **"net insider buying in March 2020"** — the validated insider-
  panic-buying signal — **could not be performed** because of this. When the
  screener comes back, re-run and verify before trusting historical insider
  features.

## SKEW — known limitation

- SKEW **did NOT spike before the 2008 crash.** It only prices S&P 500
  options tail risk, and S&P options under-priced 2008 in real time.
- SKEW **did spike before the Q4 2018 selloff** (max ~159 in Aug–Oct 2018).
- Useful as a contributing tail-risk signal, **not as a universal crash
  predictor**. Don't build a single-feature SKEW threshold rule and assume
  it would have caught all historical drawdowns.

## VIX term structure — validated signal

- Backwardation (front month VIX > VIX3M, ratio > 1.05) correctly fired
  before / during: COVID Feb–Mar 2020 (peak 1.34), February 2018 volmageddon
  (1.33), August 2015 China devaluation (1.31), and most other major
  vol-spike regimes.
- This is a **validated** regime indicator. Build features on it with
  confidence.

## SIA semiconductor sales

- Headline numbers are scraped from press releases at semiconductors.org.
- Reported figure is a **3-month moving average**, not single-month.
  Use in YoY change form, not absolute level, when comparing across cycles.
- Date assigned is the *month being reported on*, not the publication date
  (which is ~5–6 weeks later — a real-time backtest has to lag the index
  by ~6 weeks to avoid look-ahead bias).

## FINRA Reg SHO daily short volume

- `data/clean/sentiment/short_interest.parquet` is **daily short *volume*
  ratio**, not bi-monthly **short *interest*** (the position-snapshot series).
  These measure different things — short volume is flow, short interest is
  stock.
- Currently spans 2023-01 to today only. Backfill is just a question of
  pushing `START` in `src/data/fetchers/finra_short.py`; files are public
  back to 2009 on `cdn.finra.org/equity/regsho/daily/`.

## Multpl S&P 500 fundamentals

- `sp500_price_to_book` and `sp500_price_to_sales` show ~90% NaN — they're
  actually **quarterly**, not monthly. Catalog says monthly because that's
  the URL slug (`/by-month`); the underlying data isn't. Treat as quarterly
  and resample, or set `source_freq="quarterly"` and re-save.
- Other multpl series (`pe_ratio`, `shiller_cape`, `earnings_yield`,
  `dividend_yield`, `earnings`) really are monthly and span 1871+ — these
  are the longest-history fundamentals we have.

## General gotchas across all HTML scrapers

- **`py` not `python`** on this Windows box.
- Always run long fetchers with **`py -u`** (unbuffered). Without `-u`,
  Python block-buffers stdout when piped, so progress prints don't appear
  for many minutes — looks like the job is hung when it isn't.
- **Akamai-blocked sites** that returned 403 to every header combination we
  tried: `semi.org`, `finra.org` (margin pages only — Reg SHO CDN is fine),
  `etfdb.com`, `etf.com`. Don't waste time retrying with new headers.
- **`urllib.robotparser`** returned `False` for macrotrends.net even though
  the site's actual robots.txt only blocks specific paths. Read the
  `robots.txt` text directly instead of trusting the parser.
- **Reuse a `requests.Session`** for any fetcher making >100 requests to
  the same host — repeated single requests exhaust ephemeral ports on
  Windows (`WinError 10048`).
