# Failed Sources

| Date | Source | Attempted | Reason | Status |
|------|--------|-----------|--------|--------|
| 2026-04-12 | fred:NAPM | MANEMP, NAPMPI, ISM, ISMPMI (all 404); scrape sources brittle | ISM PMI no longer free on FRED (licensing) | RESOLVED: replaced by ism_manufacturing_pmi proxy from INDPRO+TCU z-scores |
| 2026-04-12 | fred:NMFBAI | NMFBAI, ISMNONMFG, NMFCI all 404 | ISM Services PMI no longer free on FRED | RESOLVED: replaced by ism_services_pmi proxy (same INDPRO+TCU composite) |
| 2026-04-12 | fred:NAPMNOI | CSV 404 | ISM new orders no longer free on FRED | COVERED: not needed; PMI proxy and DGORDER cover orders signal |
| 2026-04-12 | fred:TRIMMEDMEANPCE | CSV 404 | series ID changed | COVERED: CPIAUCSL, CPILFESL, PCEPI, PCEPILFE, T5YIE, T10YIE provide four inflation measures |
| 2026-04-12 | fred:GOLDAMGBD228NLBM | GOLDPMGBD228NLBM also 404 | London Fix series discontinued on FRED | COVERED: GLD ETF in prices |
| 2026-04-12 | fred:SLVPRUSD | CSV 404 | series ID wrong / discontinued | COVERED: SLV ETF in prices |
| 2026-04-12 | fred:TEDRATE | n/a | discontinued 2022-01 with LIBOR sunset | PERMANENT: not coming back; NFCI/STLFSI4/hy_oas cover stress signal |
| 2026-04-12 | fred:STLFSI2 | n/a | discontinued 2022-01 | RESOLVED: STLFSI4 is the replacement, now downloaded |
| 2026-04-12 | cftc:* (initial) | wrong TFF URL pattern (fin_fut_txt) and stale contract substring matches | first attempt only got 2010-2012 commodities and no financials | RESOLVED: TFF URL is fut_fin_txt; contract names changed in 2022 (E-MINI S&P 500 STOCK INDEX -> E-MINI S&P 500); both old/new patterns now matched. All 8 contracts now span 2010-2026. |
| 2026-04-12 | treasury:auctions (initial) | wrong FiscalData path securities_auctions | HTTP 404 | RESOLVED: correct path is v1/accounting/od/auctions_query; now spans 1997-2026. |
| 2026-04-12 | eia:* (all 7 series) | api.eia.gov v2 | EIA_API_KEY env var not set | RESOLVED: key supplied; all 7 series now downloaded. gasoline_demand route corrected from petroleum/sum/snd to petroleum/cons/wpsup. Histories range 1982-2026 (crude inventory) to 2010-2026 (natgas storage). |
| 2026-04-12 | uspto:* (all 9 companies) | https://search.patentsview.org/api/v1/patent/ | PATENTSVIEW_API_KEY env var not set | BLOCKED: requires free key from https://patentsview.org/apis/keyrequest; set PATENTSVIEW_API_KEY then re-run `py scripts/phase2_download.py --only uspto`. Patent data is a low-priority long-horizon signal so backlog is acceptable. |
| 2026-04-12 | aar:rail_traffic | https://www.aar.org/data-center/ | AAR weekly rail traffic is published only as PDF press releases; no structured download or public API. HTML/PDF scraping not in scope. | PERMANENT: alternative coverage via FRED RAILFRTCARLOADSD11 could be added in a later phase. |
| 2026-04-12 | finra:darkpool | https://api.finra.org/data/group/otcMarket/name/weeklySummary | endpoint accepts request but returns ATS-summary slice that aggregates to only 11 distinct weekly rows; no historical archive without registered FINRA OTC Transparency account | PARTIAL: tiny sample saved as finra_darkpool.parquet for reference. For real coverage, register at otctransparency.finra.org and use authenticated bulk export. |
| 2026-04-12 | github:* (all companies) | /repos/{owner}/{repo}/stats/participation | endpoint only returns 52 weeks of history | PERMANENT API LIMITATION: marked SHORT in catalog. Longer history would require GH Archive (archive.org) ingestion. |
| 2026-04-12 | cboe:put_call | 403:PCRATIO_History.csv; 403:totalpc.csv; 403:indexpc.csv; 403:equitypc.csv | all CDN put/call endpoints 403; HTML pages blocked by robots+WAF; register at datashop.cboe.com for historical PCR feeds |
| 2026-04-12 | macrotrends:tech_sector_pe | search bypass not attempted | no stable chart_iframe_comp ID known; would require site search (disallowed by robots /search/) |
| 2026-04-12 | macrotrends:energy_sector_earnings | search bypass not attempted | no stable chart_iframe_comp ID known; would require site search (disallowed by robots /search/) |
| 2026-04-12 | macrotrends:sp500_profit_margin | search bypass not attempted | no stable chart_iframe_comp ID known; would require site search (disallowed by robots /search/) |
| 2026-04-12 | macrotrends:sp500_buyback_yield | search bypass not attempted | no stable chart_iframe_comp ID known; would require site search (disallowed by robots /search/) |
| 2026-04-12 | finra:margin_debt | 403:est/advanced-investing/margin-statistics; 403:ta/browse-catalog/margin-statistics/data; 403:ult/files/2024-02/margin-statistics.xlsx | Akamai bot block (HTTP 403) on all FINRA margin URLs; no public CSV. | RESOLVED: replaced by FRED BOGZ1FL663067003Q (Z.1 Margin Accounts at Brokers/Dealers, quarterly) -> data/clean/sentiment/margin_debt_fred.parquet. Note: Z.1 series differs in magnitude from FINRA gross debit balances (methodology differs) but tracks the same phenomenon. |
| 2026-04-12 | etf:flows | SPY:403:etfdb.com; SPY:403:www.etf.com; QQQ:403:etfdb.com; QQQ:403:www.etf.com; HYG:403:etfdb.com; HYG:403:www.etf.com... | etfdb.com and etf.com both 403; ICI Stats no public CSV. Recommended substitute: derive flows from yahoo shares-outstanding deltas (modules=defaultKeyStatistics) once a yahoo crumb session is built, or pay for ETF.com PRO / etfdb API. |
| 2026-04-12 | semi:book_to_bill | 403; 403; 403 | semi.org Akamai-blocked (403 all endpoints); SEMI book-to-bill discontinued for public release in 2017, member-only since. No fallback. |
| 2026-04-12 | openinsider | screener | no data fetched |
| 2026-04-12 | openinsider | screener | no data fetched |
| 2026-04-12 | openinsider:screener | screener?fdr=...&xp=1&xs=1 | screener backend returns 'ERROR: Unable to select tables for main' for any fdr date-range query (server-side bug, not a block). Falling back to /insider-purchases + /insider-sales preset snapshots (latest ~100 rows each, no historical depth). | PENDING: do not build features on the 196 recent trades (too short). Retry in session 3.7 if screener?fdr= endpoint starts returning data; backfill multi-year history then. |
| 2026-04-12 | aaii | https://www.aaii.com/files/surveys/sentiment.xls | parse empty |
| 2026-04-12 | aaii | https://www.aaii.com/files/surveys/sentiment.xls | parse empty |
| 2026-04-12 | aaii | https://www.aaii.com/files/surveys/sentiment.xls | parse empty |
| 2026-04-12 | aaii | https://www.aaii.com/files/surveys/sentiment.xls | parse empty |
| 2026-04-12 | aaii | https://web.archive.org/web/2025im_/https://www.aaii.com/files/surveys/sentiment.xls | parse empty |
| 2026-04-12 | naaim | https://www.naaim.org/programs/naaim-exposure-index/ | no parseable table |
| 2026-04-12 | investors_intelligence | investorsintelligence.com / yardeni.com | paid service; no free historical feed discovered |
| 2026-04-12 | serpapi:tech stocks semiconductor|2010-05 | tech stocks semiconductor|2010-05 | api error: Google hasn't returned any results for this query. |
| 2026-04-12 | serpapi:tech stocks semiconductor|2010-02 | tech stocks semiconductor|2010-02 | api error: Google hasn't returned any results for this query. |
| 2026-04-12 | serpapi:tech stocks semiconductor|2010-04 | tech stocks semiconductor|2010-04 | api error: Google hasn't returned any results for this query. |
| 2026-04-12 | serpapi:tech stocks semiconductor|2010-08 | tech stocks semiconductor|2010-08 | api error: Google hasn't returned any results for this query. |
| 2026-04-12 | serpapi:tech stocks semiconductor|2010-03 | tech stocks semiconductor|2010-03 | api error: Google hasn't returned any results for this query. |
| 2026-04-12 | serpapi:tech stocks semiconductor|2010-07 | tech stocks semiconductor|2010-07 | api error: Google hasn't returned any results for this query. |
| 2026-04-12 | serpapi:tech stocks semiconductor|2010-10 | tech stocks semiconductor|2010-10 | api error: Google hasn't returned any results for this query. |
| 2026-04-12 | serpapi:tech stocks semiconductor|2011-03 | tech stocks semiconductor|2011-03 | api error: Google hasn't returned any results for this query. |
| 2026-04-12 | serpapi:tech stocks semiconductor|2011-08 | tech stocks semiconductor|2011-08 | api error: Google hasn't returned any results for this query. |
| 2026-04-12 | serpapi:tech stocks semiconductor|2010-06 | tech stocks semiconductor|2010-06 | api error: Google hasn't returned any results for this query. |
| 2026-04-12 | serpapi:tech stocks semiconductor|2012-01 | tech stocks semiconductor|2012-01 | api error: Google hasn't returned any results for this query. |
| 2026-04-12 | serpapi:tech stocks semiconductor|2012-05 | tech stocks semiconductor|2012-05 | api error: Google hasn't returned any results for this query. |
| 2026-04-12 | serpapi:tech stocks semiconductor|2012-03 | tech stocks semiconductor|2012-03 | api error: Google hasn't returned any results for this query. |
| 2026-04-12 | serpapi:tech stocks semiconductor|2012-04 | tech stocks semiconductor|2012-04 | api error: Google hasn't returned any results for this query. |
| 2026-04-12 | serpapi:tech stocks semiconductor|2013-01 | tech stocks semiconductor|2013-01 | api error: Google hasn't returned any results for this query. |
| 2026-04-12 | serpapi:tech stocks semiconductor|2013-02 | tech stocks semiconductor|2013-02 | api error: Google hasn't returned any results for this query. |
| 2026-04-12 | serpapi:tech stocks semiconductor|2011-11 | tech stocks semiconductor|2011-11 | api error: Google hasn't returned any results for this query. |
| 2026-04-12 | serpapi:tech stocks semiconductor|2013-05 | tech stocks semiconductor|2013-05 | api error: Google hasn't returned any results for this query. |
| 2026-04-12 | serpapi:tech stocks semiconductor|2014-07 | tech stocks semiconductor|2014-07 | api error: Google hasn't returned any results for this query. |
| 2026-04-12 | serpapi:tech stocks semiconductor|2014-09 | tech stocks semiconductor|2014-09 | api error: Google hasn't returned any results for this query. |
| 2026-04-12 | serpapi:tech stocks semiconductor|2023-06 | tech stocks semiconductor|2023-06 | api error: Google hasn't returned any results for this query. |
| 2026-04-12 | serpapi:recession economy|2024-01 | recession economy|2024-01 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2010-01 | gold prices|2010-01 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2010-02 | gold prices|2010-02 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2010-03 | gold prices|2010-03 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2010-04 | gold prices|2010-04 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2010-05 | gold prices|2010-05 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2010-06 | gold prices|2010-06 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2010-08 | gold prices|2010-08 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2010-07 | gold prices|2010-07 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2010-12 | gold prices|2010-12 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2011-01 | gold prices|2011-01 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2011-02 | gold prices|2011-02 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2011-03 | gold prices|2011-03 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2011-04 | gold prices|2011-04 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2011-05 | gold prices|2011-05 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2011-06 | gold prices|2011-06 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2011-07 | gold prices|2011-07 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2011-08 | gold prices|2011-08 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2011-09 | gold prices|2011-09 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2011-10 | gold prices|2011-10 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2011-12 | gold prices|2011-12 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2012-01 | gold prices|2012-01 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2011-11 | gold prices|2011-11 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2012-04 | gold prices|2012-04 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2012-02 | gold prices|2012-02 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2012-03 | gold prices|2012-03 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2012-05 | gold prices|2012-05 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2012-06 | gold prices|2012-06 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2012-07 | gold prices|2012-07 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2012-08 | gold prices|2012-08 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2012-09 | gold prices|2012-09 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2012-11 | gold prices|2012-11 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2012-10 | gold prices|2012-10 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2012-12 | gold prices|2012-12 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2013-01 | gold prices|2013-01 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2013-02 | gold prices|2013-02 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2013-03 | gold prices|2013-03 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2013-04 | gold prices|2013-04 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2013-05 | gold prices|2013-05 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2013-06 | gold prices|2013-06 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2013-08 | gold prices|2013-08 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2013-07 | gold prices|2013-07 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2013-09 | gold prices|2013-09 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2013-10 | gold prices|2013-10 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2013-11 | gold prices|2013-11 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2013-12 | gold prices|2013-12 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2014-02 | gold prices|2014-02 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2014-01 | gold prices|2014-01 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2014-03 | gold prices|2014-03 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2014-04 | gold prices|2014-04 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2014-05 | gold prices|2014-05 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2014-06 | gold prices|2014-06 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2014-07 | gold prices|2014-07 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2014-08 | gold prices|2014-08 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2014-10 | gold prices|2014-10 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2014-11 | gold prices|2014-11 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2014-09 | gold prices|2014-09 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2014-12 | gold prices|2014-12 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2015-01 | gold prices|2015-01 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2015-03 | gold prices|2015-03 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2015-02 | gold prices|2015-02 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2015-04 | gold prices|2015-04 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2015-05 | gold prices|2015-05 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2015-06 | gold prices|2015-06 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2015-07 | gold prices|2015-07 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2015-08 | gold prices|2015-08 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2015-09 | gold prices|2015-09 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2015-11 | gold prices|2015-11 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2015-10 | gold prices|2015-10 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2015-12 | gold prices|2015-12 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2016-02 | gold prices|2016-02 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2016-03 | gold prices|2016-03 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2016-04 | gold prices|2016-04 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2016-05 | gold prices|2016-05 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2016-07 | gold prices|2016-07 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2016-08 | gold prices|2016-08 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2016-09 | gold prices|2016-09 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2016-10 | gold prices|2016-10 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2016-11 | gold prices|2016-11 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2016-12 | gold prices|2016-12 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2017-01 | gold prices|2017-01 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2017-02 | gold prices|2017-02 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2017-03 | gold prices|2017-03 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2017-04 | gold prices|2017-04 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2017-05 | gold prices|2017-05 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2017-06 | gold prices|2017-06 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2017-07 | gold prices|2017-07 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2017-08 | gold prices|2017-08 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2017-09 | gold prices|2017-09 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2017-10 | gold prices|2017-10 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2017-11 | gold prices|2017-11 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2017-12 | gold prices|2017-12 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2018-03 | gold prices|2018-03 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2018-02 | gold prices|2018-02 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2018-01 | gold prices|2018-01 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2018-04 | gold prices|2018-04 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2018-05 | gold prices|2018-05 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2018-06 | gold prices|2018-06 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2018-08 | gold prices|2018-08 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2018-09 | gold prices|2018-09 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2018-07 | gold prices|2018-07 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2018-10 | gold prices|2018-10 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2018-11 | gold prices|2018-11 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2018-12 | gold prices|2018-12 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2019-01 | gold prices|2019-01 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2019-02 | gold prices|2019-02 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2019-03 | gold prices|2019-03 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2019-04 | gold prices|2019-04 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2019-05 | gold prices|2019-05 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2019-06 | gold prices|2019-06 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2019-07 | gold prices|2019-07 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2019-08 | gold prices|2019-08 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2019-09 | gold prices|2019-09 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2019-10 | gold prices|2019-10 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2019-11 | gold prices|2019-11 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2020-01 | gold prices|2020-01 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2019-12 | gold prices|2019-12 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2020-02 | gold prices|2020-02 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2020-03 | gold prices|2020-03 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2020-04 | gold prices|2020-04 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2020-05 | gold prices|2020-05 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2020-06 | gold prices|2020-06 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2020-07 | gold prices|2020-07 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2020-08 | gold prices|2020-08 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2020-09 | gold prices|2020-09 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2020-10 | gold prices|2020-10 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2020-11 | gold prices|2020-11 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2020-12 | gold prices|2020-12 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2021-01 | gold prices|2021-01 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2021-02 | gold prices|2021-02 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2021-04 | gold prices|2021-04 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2021-03 | gold prices|2021-03 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2021-05 | gold prices|2021-05 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2021-06 | gold prices|2021-06 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2021-07 | gold prices|2021-07 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2021-09 | gold prices|2021-09 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2021-10 | gold prices|2021-10 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2021-11 | gold prices|2021-11 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2021-12 | gold prices|2021-12 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2022-01 | gold prices|2022-01 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2021-08 | gold prices|2021-08 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2022-02 | gold prices|2022-02 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2022-04 | gold prices|2022-04 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2022-03 | gold prices|2022-03 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2022-05 | gold prices|2022-05 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2022-06 | gold prices|2022-06 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2022-07 | gold prices|2022-07 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2022-08 | gold prices|2022-08 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2022-09 | gold prices|2022-09 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2022-10 | gold prices|2022-10 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2022-11 | gold prices|2022-11 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2022-12 | gold prices|2022-12 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2023-01 | gold prices|2023-01 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2023-02 | gold prices|2023-02 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2023-04 | gold prices|2023-04 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2023-05 | gold prices|2023-05 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2023-03 | gold prices|2023-03 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2023-06 | gold prices|2023-06 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2023-07 | gold prices|2023-07 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2023-08 | gold prices|2023-08 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2023-11 | gold prices|2023-11 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2023-10 | gold prices|2023-10 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2023-09 | gold prices|2023-09 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2023-12 | gold prices|2023-12 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2010-01 | housing market|2010-01 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:gold prices|2024-01 | gold prices|2024-01 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2010-02 | housing market|2010-02 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2010-03 | housing market|2010-03 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2010-04 | housing market|2010-04 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2010-05 | housing market|2010-05 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2010-07 | housing market|2010-07 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2010-06 | housing market|2010-06 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2010-09 | housing market|2010-09 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2010-10 | housing market|2010-10 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2010-08 | housing market|2010-08 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2010-11 | housing market|2010-11 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2010-12 | housing market|2010-12 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2011-01 | housing market|2011-01 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2011-02 | housing market|2011-02 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2011-03 | housing market|2011-03 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2011-04 | housing market|2011-04 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2011-05 | housing market|2011-05 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2011-06 | housing market|2011-06 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2011-07 | housing market|2011-07 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2011-08 | housing market|2011-08 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2011-09 | housing market|2011-09 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2011-10 | housing market|2011-10 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2012-01 | housing market|2012-01 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2011-12 | housing market|2011-12 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2011-11 | housing market|2011-11 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2012-02 | housing market|2012-02 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2012-03 | housing market|2012-03 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2012-04 | housing market|2012-04 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2012-06 | housing market|2012-06 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2012-05 | housing market|2012-05 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | 1_tsa | phase2_alt | RuntimeError: parsed 0 rows |
| 2026-04-12 | serpapi:housing market|2012-07 | housing market|2012-07 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2012-08 | housing market|2012-08 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2012-09 | housing market|2012-09 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2012-10 | housing market|2012-10 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2012-12 | housing market|2012-12 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2012-11 | housing market|2012-11 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2013-01 | housing market|2013-01 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2013-02 | housing market|2013-02 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2013-03 | housing market|2013-03 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2013-04 | housing market|2013-04 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2013-05 | housing market|2013-05 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2013-06 | housing market|2013-06 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2013-07 | housing market|2013-07 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2013-09 | housing market|2013-09 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2013-08 | housing market|2013-08 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2013-10 | housing market|2013-10 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2013-11 | housing market|2013-11 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2013-12 | housing market|2013-12 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2014-01 | housing market|2014-01 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2014-02 | housing market|2014-02 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2014-03 | housing market|2014-03 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2014-04 | housing market|2014-04 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2014-05 | housing market|2014-05 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2014-06 | housing market|2014-06 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2014-07 | housing market|2014-07 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2014-08 | housing market|2014-08 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2014-09 | housing market|2014-09 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2014-10 | housing market|2014-10 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2014-11 | housing market|2014-11 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2014-12 | housing market|2014-12 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2015-01 | housing market|2015-01 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2015-03 | housing market|2015-03 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2015-02 | housing market|2015-02 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2015-04 | housing market|2015-04 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2015-05 | housing market|2015-05 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2015-06 | housing market|2015-06 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2015-07 | housing market|2015-07 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2015-09 | housing market|2015-09 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2015-08 | housing market|2015-08 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2015-10 | housing market|2015-10 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2015-12 | housing market|2015-12 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2015-11 | housing market|2015-11 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2016-01 | housing market|2016-01 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2016-02 | housing market|2016-02 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2016-04 | housing market|2016-04 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2016-03 | housing market|2016-03 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2016-05 | housing market|2016-05 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2016-06 | housing market|2016-06 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2016-08 | housing market|2016-08 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2016-07 | housing market|2016-07 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2016-09 | housing market|2016-09 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2016-10 | housing market|2016-10 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2016-12 | housing market|2016-12 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2016-11 | housing market|2016-11 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2017-01 | housing market|2017-01 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2017-02 | housing market|2017-02 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2017-03 | housing market|2017-03 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2017-05 | housing market|2017-05 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2017-06 | housing market|2017-06 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2017-07 | housing market|2017-07 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2017-08 | housing market|2017-08 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2017-09 | housing market|2017-09 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2017-04 | housing market|2017-04 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2017-10 | housing market|2017-10 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | 2_port_la | phase2_alt | RuntimeError: tables found but structure ambiguous — full parse skipped per time budget |
| 2026-04-12 | 4_bts_airline | phase2_alt | RuntimeError: BTS TranStats requires ZIP form submission, not scrapeable in budget |
| 2026-04-12 | serpapi:housing market|2017-11 | housing market|2017-11 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2018-01 | housing market|2018-01 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2017-12 | housing market|2017-12 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2018-02 | housing market|2018-02 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2018-03 | housing market|2018-03 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2018-04 | housing market|2018-04 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2018-05 | housing market|2018-05 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2018-07 | housing market|2018-07 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2018-06 | housing market|2018-06 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2018-08 | housing market|2018-08 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2018-09 | housing market|2018-09 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2018-10 | housing market|2018-10 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2018-11 | housing market|2018-11 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2018-12 | housing market|2018-12 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2019-01 | housing market|2019-01 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2019-02 | housing market|2019-02 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2019-03 | housing market|2019-03 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2019-04 | housing market|2019-04 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2019-05 | housing market|2019-05 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2019-06 | housing market|2019-06 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2019-07 | housing market|2019-07 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2019-08 | housing market|2019-08 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2019-10 | housing market|2019-10 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2019-09 | housing market|2019-09 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2019-12 | housing market|2019-12 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2020-01 | housing market|2020-01 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2019-11 | housing market|2019-11 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2020-02 | housing market|2020-02 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2020-03 | housing market|2020-03 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2020-04 | housing market|2020-04 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2020-06 | housing market|2020-06 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2020-07 | housing market|2020-07 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2020-05 | housing market|2020-05 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2020-08 | housing market|2020-08 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | 5_reddit | phase2_alt | RuntimeError: pushshift unreachable: HTTP Error 403: Forbidden |
| 2026-04-12 | serpapi:housing market|2020-10 | housing market|2020-10 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2020-09 | housing market|2020-09 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2020-11 | housing market|2020-11 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2021-01 | housing market|2021-01 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2020-12 | housing market|2020-12 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2021-02 | housing market|2021-02 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2021-03 | housing market|2021-03 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2021-04 | housing market|2021-04 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2021-05 | housing market|2021-05 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2021-07 | housing market|2021-07 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2021-08 | housing market|2021-08 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2021-06 | housing market|2021-06 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2021-09 | housing market|2021-09 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2021-10 | housing market|2021-10 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2021-11 | housing market|2021-11 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2021-12 | housing market|2021-12 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2022-01 | housing market|2022-01 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2022-02 | housing market|2022-02 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2022-03 | housing market|2022-03 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2022-04 | housing market|2022-04 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2022-05 | housing market|2022-05 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2022-07 | housing market|2022-07 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2022-06 | housing market|2022-06 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2022-08 | housing market|2022-08 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2022-09 | housing market|2022-09 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2022-10 | housing market|2022-10 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2022-11 | housing market|2022-11 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2022-12 | housing market|2022-12 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2023-01 | housing market|2023-01 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2023-02 | housing market|2023-02 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2023-03 | housing market|2023-03 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2023-04 | housing market|2023-04 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2023-05 | housing market|2023-05 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2023-07 | housing market|2023-07 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2023-06 | housing market|2023-06 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2023-08 | housing market|2023-08 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2023-10 | housing market|2023-10 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2023-09 | housing market|2023-09 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2023-11 | housing market|2023-11 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2024-01 | housing market|2024-01 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:housing market|2023-12 | housing market|2023-12 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2010-01 | federal reserve|2010-01 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2010-02 | federal reserve|2010-02 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2010-03 | federal reserve|2010-03 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2010-04 | federal reserve|2010-04 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2010-05 | federal reserve|2010-05 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2010-06 | federal reserve|2010-06 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2010-07 | federal reserve|2010-07 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2010-08 | federal reserve|2010-08 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2010-09 | federal reserve|2010-09 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2010-10 | federal reserve|2010-10 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2010-11 | federal reserve|2010-11 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2010-12 | federal reserve|2010-12 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2011-01 | federal reserve|2011-01 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2011-02 | federal reserve|2011-02 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2011-03 | federal reserve|2011-03 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2011-04 | federal reserve|2011-04 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2011-06 | federal reserve|2011-06 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2011-05 | federal reserve|2011-05 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2011-07 | federal reserve|2011-07 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2011-10 | federal reserve|2011-10 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2011-08 | federal reserve|2011-08 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2011-09 | federal reserve|2011-09 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2011-11 | federal reserve|2011-11 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2011-12 | federal reserve|2011-12 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2012-01 | federal reserve|2012-01 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2012-02 | federal reserve|2012-02 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2012-03 | federal reserve|2012-03 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2012-04 | federal reserve|2012-04 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2012-05 | federal reserve|2012-05 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2012-07 | federal reserve|2012-07 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2012-06 | federal reserve|2012-06 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2012-08 | federal reserve|2012-08 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2012-09 | federal reserve|2012-09 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2012-11 | federal reserve|2012-11 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2012-10 | federal reserve|2012-10 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2012-12 | federal reserve|2012-12 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2013-01 | federal reserve|2013-01 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2013-02 | federal reserve|2013-02 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2013-04 | federal reserve|2013-04 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2013-05 | federal reserve|2013-05 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2013-06 | federal reserve|2013-06 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2013-03 | federal reserve|2013-03 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2013-07 | federal reserve|2013-07 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2013-09 | federal reserve|2013-09 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2013-12 | federal reserve|2013-12 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2013-08 | federal reserve|2013-08 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2013-10 | federal reserve|2013-10 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2014-01 | federal reserve|2014-01 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2013-11 | federal reserve|2013-11 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | 7_sifma_corp_bond | phase2_alt | RuntimeError: SIFMA publishes XLSX behind JS page; no stable direct URL |
| 2026-04-12 | 8_bankruptcy | phase2_alt | RuntimeError: uscourts.gov publishes PDFs + HTML tables per quarter; no single stable CSV |
| 2026-04-12 | 9_steel | phase2_alt | RuntimeError: worldsteel.org members-only data; press releases only in PDF |
| 2026-04-12 | 10_jobs | phase2_alt | RuntimeError: Glassdoor/Indeed blocked; enterprise-only API |
| 2026-04-12 | 11_appstore | phase2_alt | RuntimeError: iTunes RSS only gives recent reviews; Play Store blocked |
| 2026-04-12 | serpapi:federal reserve|2014-04 | federal reserve|2014-04 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2014-03 | federal reserve|2014-03 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2014-07 | federal reserve|2014-07 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2014-06 | federal reserve|2014-06 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2014-05 | federal reserve|2014-05 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2014-02 | federal reserve|2014-02 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2014-09 | federal reserve|2014-09 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2014-11 | federal reserve|2014-11 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2014-10 | federal reserve|2014-10 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2015-01 | federal reserve|2015-01 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2014-12 | federal reserve|2014-12 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2015-02 | federal reserve|2015-02 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2015-03 | federal reserve|2015-03 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2015-04 | federal reserve|2015-04 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2015-05 | federal reserve|2015-05 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2015-06 | federal reserve|2015-06 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2014-08 | federal reserve|2014-08 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2015-08 | federal reserve|2015-08 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2015-07 | federal reserve|2015-07 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2015-11 | federal reserve|2015-11 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2015-09 | federal reserve|2015-09 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2015-10 | federal reserve|2015-10 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2015-12 | federal reserve|2015-12 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2016-01 | federal reserve|2016-01 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2016-02 | federal reserve|2016-02 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2016-03 | federal reserve|2016-03 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2016-04 | federal reserve|2016-04 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2016-05 | federal reserve|2016-05 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2016-06 | federal reserve|2016-06 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2016-08 | federal reserve|2016-08 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2016-09 | federal reserve|2016-09 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2016-07 | federal reserve|2016-07 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2016-10 | federal reserve|2016-10 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2016-11 | federal reserve|2016-11 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2016-12 | federal reserve|2016-12 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2017-01 | federal reserve|2017-01 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2017-02 | federal reserve|2017-02 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2017-03 | federal reserve|2017-03 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2017-04 | federal reserve|2017-04 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2017-05 | federal reserve|2017-05 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2017-06 | federal reserve|2017-06 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2017-07 | federal reserve|2017-07 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2017-08 | federal reserve|2017-08 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2017-09 | federal reserve|2017-09 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2017-10 | federal reserve|2017-10 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2017-11 | federal reserve|2017-11 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2017-12 | federal reserve|2017-12 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2018-02 | federal reserve|2018-02 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2018-01 | federal reserve|2018-01 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2018-03 | federal reserve|2018-03 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2018-04 | federal reserve|2018-04 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2018-05 | federal reserve|2018-05 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2018-06 | federal reserve|2018-06 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2018-08 | federal reserve|2018-08 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2018-07 | federal reserve|2018-07 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2018-09 | federal reserve|2018-09 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2018-10 | federal reserve|2018-10 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2018-12 | federal reserve|2018-12 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2018-11 | federal reserve|2018-11 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2019-01 | federal reserve|2019-01 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2019-02 | federal reserve|2019-02 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2019-03 | federal reserve|2019-03 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2019-04 | federal reserve|2019-04 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2019-06 | federal reserve|2019-06 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2019-05 | federal reserve|2019-05 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2019-08 | federal reserve|2019-08 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2019-09 | federal reserve|2019-09 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2019-07 | federal reserve|2019-07 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2019-11 | federal reserve|2019-11 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | 15_opentable | phase2_alt | RuntimeError: OpenTable State-of-Industry dataset ended 2022; no public feed |
| 2026-04-12 | serpapi:federal reserve|2019-12 | federal reserve|2019-12 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2020-01 | federal reserve|2020-01 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2020-02 | federal reserve|2020-02 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2020-03 | federal reserve|2020-03 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2020-05 | federal reserve|2020-05 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2020-04 | federal reserve|2020-04 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2020-06 | federal reserve|2020-06 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2020-07 | federal reserve|2020-07 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2020-08 | federal reserve|2020-08 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2020-09 | federal reserve|2020-09 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2020-10 | federal reserve|2020-10 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2020-12 | federal reserve|2020-12 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2020-11 | federal reserve|2020-11 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | 16_baltic_dry | phase2_alt | RuntimeError: no source returned data (stooq variants failed) |
| 2026-04-12 | 17_twitter | phase2_alt | RuntimeError: X API requires paid tier; historical search not available |
| 2026-04-12 | serpapi:federal reserve|2021-01 | federal reserve|2021-01 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2021-03 | federal reserve|2021-03 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2021-02 | federal reserve|2021-02 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2021-05 | federal reserve|2021-05 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2021-04 | federal reserve|2021-04 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2021-06 | federal reserve|2021-06 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2021-08 | federal reserve|2021-08 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2021-07 | federal reserve|2021-07 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2021-10 | federal reserve|2021-10 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2021-09 | federal reserve|2021-09 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2021-11 | federal reserve|2021-11 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2021-12 | federal reserve|2021-12 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2022-01 | federal reserve|2022-01 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2022-02 | federal reserve|2022-02 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2022-03 | federal reserve|2022-03 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2022-04 | federal reserve|2022-04 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2022-06 | federal reserve|2022-06 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2022-05 | federal reserve|2022-05 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2022-07 | federal reserve|2022-07 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2022-08 | federal reserve|2022-08 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2022-09 | federal reserve|2022-09 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2022-10 | federal reserve|2022-10 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2022-11 | federal reserve|2022-11 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2022-12 | federal reserve|2022-12 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2023-01 | federal reserve|2023-01 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2023-02 | federal reserve|2023-02 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2023-04 | federal reserve|2023-04 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2023-05 | federal reserve|2023-05 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2023-03 | federal reserve|2023-03 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2023-06 | federal reserve|2023-06 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2023-07 | federal reserve|2023-07 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2023-08 | federal reserve|2023-08 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2023-09 | federal reserve|2023-09 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2023-10 | federal reserve|2023-10 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2023-11 | federal reserve|2023-11 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2023-12 | federal reserve|2023-12 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2024-01 | federal reserve|2024-01 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2010-01 | earnings report|2010-01 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2010-02 | earnings report|2010-02 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2010-03 | earnings report|2010-03 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2010-04 | earnings report|2010-04 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2010-05 | earnings report|2010-05 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2010-06 | earnings report|2010-06 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2010-07 | earnings report|2010-07 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2010-08 | earnings report|2010-08 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2010-09 | earnings report|2010-09 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2010-10 | earnings report|2010-10 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2010-12 | earnings report|2010-12 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2010-11 | earnings report|2010-11 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2011-02 | earnings report|2011-02 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2011-01 | earnings report|2011-01 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2011-03 | earnings report|2011-03 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2011-04 | earnings report|2011-04 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2011-05 | earnings report|2011-05 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2011-06 | earnings report|2011-06 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2011-07 | earnings report|2011-07 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2011-08 | earnings report|2011-08 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2011-10 | earnings report|2011-10 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2011-11 | earnings report|2011-11 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2011-09 | earnings report|2011-09 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2011-12 | earnings report|2011-12 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2012-01 | earnings report|2012-01 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2012-02 | earnings report|2012-02 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2012-03 | earnings report|2012-03 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2012-04 | earnings report|2012-04 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2012-05 | earnings report|2012-05 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2012-06 | earnings report|2012-06 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2012-07 | earnings report|2012-07 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2012-08 | earnings report|2012-08 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2012-09 | earnings report|2012-09 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2012-10 | earnings report|2012-10 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2012-11 | earnings report|2012-11 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2012-12 | earnings report|2012-12 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2013-01 | earnings report|2013-01 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2013-02 | earnings report|2013-02 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2013-03 | earnings report|2013-03 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2013-04 | earnings report|2013-04 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2013-05 | earnings report|2013-05 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2013-06 | earnings report|2013-06 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2013-07 | earnings report|2013-07 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2013-08 | earnings report|2013-08 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2013-10 | earnings report|2013-10 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2013-09 | earnings report|2013-09 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2013-11 | earnings report|2013-11 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2013-12 | earnings report|2013-12 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2014-01 | earnings report|2014-01 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2014-02 | earnings report|2014-02 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2014-03 | earnings report|2014-03 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2014-05 | earnings report|2014-05 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2014-04 | earnings report|2014-04 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2014-06 | earnings report|2014-06 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2014-07 | earnings report|2014-07 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2014-08 | earnings report|2014-08 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2014-10 | earnings report|2014-10 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2014-09 | earnings report|2014-09 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2014-11 | earnings report|2014-11 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2015-01 | earnings report|2015-01 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2014-12 | earnings report|2014-12 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2015-03 | earnings report|2015-03 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2015-02 | earnings report|2015-02 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2015-04 | earnings report|2015-04 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2015-05 | earnings report|2015-05 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2015-08 | earnings report|2015-08 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2015-07 | earnings report|2015-07 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2015-06 | earnings report|2015-06 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2015-09 | earnings report|2015-09 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:federal reserve|2019-10 | federal reserve|2019-10 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2015-11 | earnings report|2015-11 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2015-12 | earnings report|2015-12 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2016-01 | earnings report|2016-01 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2015-10 | earnings report|2015-10 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2016-02 | earnings report|2016-02 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2016-03 | earnings report|2016-03 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2016-04 | earnings report|2016-04 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2016-05 | earnings report|2016-05 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2016-06 | earnings report|2016-06 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2016-07 | earnings report|2016-07 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2016-08 | earnings report|2016-08 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2016-10 | earnings report|2016-10 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2016-11 | earnings report|2016-11 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2016-12 | earnings report|2016-12 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2017-01 | earnings report|2017-01 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2017-02 | earnings report|2017-02 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2017-03 | earnings report|2017-03 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2016-09 | earnings report|2016-09 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2017-04 | earnings report|2017-04 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2017-06 | earnings report|2017-06 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2017-05 | earnings report|2017-05 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2017-07 | earnings report|2017-07 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2017-08 | earnings report|2017-08 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2017-09 | earnings report|2017-09 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2017-10 | earnings report|2017-10 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2017-11 | earnings report|2017-11 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2017-12 | earnings report|2017-12 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2018-01 | earnings report|2018-01 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2018-02 | earnings report|2018-02 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2018-03 | earnings report|2018-03 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2018-04 | earnings report|2018-04 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2018-06 | earnings report|2018-06 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2018-05 | earnings report|2018-05 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2018-07 | earnings report|2018-07 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2018-08 | earnings report|2018-08 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2018-09 | earnings report|2018-09 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2018-11 | earnings report|2018-11 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2018-10 | earnings report|2018-10 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2018-12 | earnings report|2018-12 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2019-01 | earnings report|2019-01 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2019-02 | earnings report|2019-02 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2019-04 | earnings report|2019-04 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2019-03 | earnings report|2019-03 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2019-05 | earnings report|2019-05 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2019-06 | earnings report|2019-06 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2019-07 | earnings report|2019-07 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2019-08 | earnings report|2019-08 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2019-09 | earnings report|2019-09 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2019-11 | earnings report|2019-11 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2019-10 | earnings report|2019-10 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2020-01 | earnings report|2020-01 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2019-12 | earnings report|2019-12 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2020-02 | earnings report|2020-02 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2020-03 | earnings report|2020-03 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2020-04 | earnings report|2020-04 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2020-05 | earnings report|2020-05 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2020-07 | earnings report|2020-07 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2020-06 | earnings report|2020-06 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2020-08 | earnings report|2020-08 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2020-09 | earnings report|2020-09 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2020-10 | earnings report|2020-10 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2020-11 | earnings report|2020-11 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2020-12 | earnings report|2020-12 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2021-01 | earnings report|2021-01 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2021-02 | earnings report|2021-02 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2021-03 | earnings report|2021-03 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2021-04 | earnings report|2021-04 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2021-05 | earnings report|2021-05 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2021-06 | earnings report|2021-06 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2021-07 | earnings report|2021-07 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2021-09 | earnings report|2021-09 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2021-08 | earnings report|2021-08 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2021-10 | earnings report|2021-10 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2022-01 | earnings report|2022-01 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2021-11 | earnings report|2021-11 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2021-12 | earnings report|2021-12 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2022-02 | earnings report|2022-02 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2022-03 | earnings report|2022-03 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2022-04 | earnings report|2022-04 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2022-05 | earnings report|2022-05 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2022-07 | earnings report|2022-07 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2022-06 | earnings report|2022-06 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2022-08 | earnings report|2022-08 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2022-10 | earnings report|2022-10 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2022-09 | earnings report|2022-09 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2022-11 | earnings report|2022-11 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2023-01 | earnings report|2023-01 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2022-12 | earnings report|2022-12 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2023-03 | earnings report|2023-03 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2023-02 | earnings report|2023-02 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2023-04 | earnings report|2023-04 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2023-06 | earnings report|2023-06 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2023-05 | earnings report|2023-05 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2023-07 | earnings report|2023-07 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2023-09 | earnings report|2023-09 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2023-10 | earnings report|2023-10 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2023-08 | earnings report|2023-08 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2023-11 | earnings report|2023-11 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2023-12 | earnings report|2023-12 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | serpapi:earnings report|2024-01 | earnings report|2024-01 | HTTP 429: {
  "error": "Your account has been throttled. You are exceeding 1,000 searches per hour. Please upgrade your plan, spread out your searches |
| 2026-04-12 | 2_port_la | https://www.portoflosangeles.org/business/statistics/container-statistics | HTML page contains tables but structure ambiguous; TEU data served via dynamic widget. Skipped per time budget. |
| 2026-04-12 | 4_bts_airline | https://www.transtats.bts.gov/ | TranStats requires interactive form submission returning a ZIP; no stable direct CSV URL. |
| 2026-04-12 | 5_reddit | https://api.pushshift.io | HTTP 403 Forbidden; Pushshift public API has been locked since 2023. Reddit native API requires OAuth and aggressive rate limits. |
| 2026-04-12 | 7_sifma_corp_bond | https://www.sifma.org/resources/research/us-corporate-bond-issuance/ | XLSX served behind JS-rendered page; no stable direct URL. Would need headless browser. |
| 2026-04-12 | 8_bankruptcy | https://www.uscourts.gov/statistics/table/f/bankruptcy-filings | Tables published per-quarter across individual HTML pages + PDF; no consolidated CSV feed. |
| 2026-04-12 | 9_steel | https://worldsteel.org/ | Members-only; public access is headline PDFs only. No historical series. |
| 2026-04-12 | 10_glassdoor_indeed | glassdoor.com / indeed.com | Both require enterprise partnerships; public site blocks scraping. |
| 2026-04-12 | 11_appstore | itunes.apple.com / play.google.com | iTunes RSS exposes only most-recent ~50 reviews; Play Store has no public ratings API. |
| 2026-04-12 | 15_opentable | opentable.com state-of-industry | OpenTable discontinued public State-of-Industry dataset in 2022. |
| 2026-04-12 | 16_baltic_dry | stooq ^bdi / tradingeconomics / investing.com | stooq CSV now requires api key; tradingeconomics/investing WAF-blocked; no free BDI feed discovered. |
| 2026-04-12 | 17_twitter | api.twitter.com / x.com | Free tier removed historical search; Enterprise archive requires paid Academic/Enterprise access. |
| 2026-04-12 | 7_sifma_corp_bond | https://www.sifma.org/research/statistics/us-corporate-bonds-statistics | XLS link redirects to share.hsforms.com HubSpot gate; requires email form submission. No free direct XLSX. Closest FRED substitute is corporate bond outstanding totals (BOGZ1 flow-of-funds) but not issuance-flow specifically. |
| 2026-04-12 | 8_bankruptcy | uscourts.gov/abi.org/epiq | Total US bankruptcy filings: uscourts publishes quarterly XLSX with version-specific URLs per release (not stable); Epiq/AACER is commercial; ABI statistics page is JS-rendered chart with no CSV. Free substitute: FRED has delinquency/charge-off series (already in macro). |
| 2026-04-12 | serpapi:tech stocks semiconductor|2010-05 | tech stocks semiconductor|2010-05 | api error: Google hasn't returned any results for this query. |
| 2026-04-12 | serpapi:tech stocks semiconductor|2010-03 | tech stocks semiconductor|2010-03 | api error: Google hasn't returned any results for this query. |
| 2026-04-12 | serpapi:tech stocks semiconductor|2010-04 | tech stocks semiconductor|2010-04 | api error: Google hasn't returned any results for this query. |
| 2026-04-12 | serpapi:tech stocks semiconductor|2010-02 | tech stocks semiconductor|2010-02 | api error: Google hasn't returned any results for this query. |
| 2026-04-12 | serpapi:tech stocks semiconductor|2010-06 | tech stocks semiconductor|2010-06 | api error: Google hasn't returned any results for this query. |
| 2026-04-12 | serpapi:tech stocks semiconductor|2010-10 | tech stocks semiconductor|2010-10 | api error: Google hasn't returned any results for this query. |
| 2026-04-12 | serpapi:tech stocks semiconductor|2011-03 | tech stocks semiconductor|2011-03 | api error: Google hasn't returned any results for this query. |
| 2026-04-12 | serpapi:tech stocks semiconductor|2010-07 | tech stocks semiconductor|2010-07 | api error: Google hasn't returned any results for this query. |
| 2026-04-12 | serpapi:tech stocks semiconductor|2012-03 | tech stocks semiconductor|2012-03 | api error: Google hasn't returned any results for this query. |
| 2026-04-12 | serpapi:tech stocks semiconductor|2012-05 | tech stocks semiconductor|2012-05 | api error: Google hasn't returned any results for this query. |
| 2026-04-12 | serpapi:tech stocks semiconductor|2011-08 | tech stocks semiconductor|2011-08 | api error: Google hasn't returned any results for this query. |
| 2026-04-12 | serpapi:tech stocks semiconductor|2010-08 | tech stocks semiconductor|2010-08 | api error: Google hasn't returned any results for this query. |
| 2026-04-12 | serpapi:tech stocks semiconductor|2012-04 | tech stocks semiconductor|2012-04 | api error: Google hasn't returned any results for this query. |
| 2026-04-12 | serpapi:tech stocks semiconductor|2013-02 | tech stocks semiconductor|2013-02 | api error: Google hasn't returned any results for this query. |
| 2026-04-12 | serpapi:tech stocks semiconductor|2011-11 | tech stocks semiconductor|2011-11 | api error: Google hasn't returned any results for this query. |
| 2026-04-12 | serpapi:tech stocks semiconductor|2014-09 | tech stocks semiconductor|2014-09 | api error: Google hasn't returned any results for this query. |
| 2026-04-12 | serpapi:tech stocks semiconductor|2013-01 | tech stocks semiconductor|2013-01 | api error: Google hasn't returned any results for this query. |
| 2026-04-12 | serpapi:tech stocks semiconductor|2014-07 | tech stocks semiconductor|2014-07 | api error: Google hasn't returned any results for this query. |
| 2026-04-12 | serpapi:tech stocks semiconductor|2010-04 | tech stocks semiconductor|2010-04 | api error: Google hasn't returned any results for this query. |
| 2026-04-12 | serpapi:tech stocks semiconductor|2010-05 | tech stocks semiconductor|2010-05 | api error: Google hasn't returned any results for this query. |
| 2026-04-12 | serpapi:tech stocks semiconductor|2010-02 | tech stocks semiconductor|2010-02 | api error: Google hasn't returned any results for this query. |
| 2026-04-12 | serpapi:tech stocks semiconductor|2010-06 | tech stocks semiconductor|2010-06 | api error: Google hasn't returned any results for this query. |
| 2026-04-12 | serpapi:tech stocks semiconductor|2010-07 | tech stocks semiconductor|2010-07 | api error: Google hasn't returned any results for this query. |
| 2026-04-12 | serpapi:tech stocks semiconductor|2010-03 | tech stocks semiconductor|2010-03 | api error: Google hasn't returned any results for this query. |
| 2026-04-12 | serpapi:tech stocks semiconductor|2010-08 | tech stocks semiconductor|2010-08 | api error: Google hasn't returned any results for this query. |
| 2026-04-12 | serpapi:tech stocks semiconductor|2011-03 | tech stocks semiconductor|2011-03 | api error: Google hasn't returned any results for this query. |
| 2026-04-12 | serpapi:tech stocks semiconductor|2011-08 | tech stocks semiconductor|2011-08 | api error: Google hasn't returned any results for this query. |
| 2026-04-12 | serpapi:tech stocks semiconductor|2011-11 | tech stocks semiconductor|2011-11 | api error: Google hasn't returned any results for this query. |
| 2026-04-12 | serpapi:tech stocks semiconductor|2010-10 | tech stocks semiconductor|2010-10 | api error: Google hasn't returned any results for this query. |
| 2026-04-12 | serpapi:tech stocks semiconductor|2012-04 | tech stocks semiconductor|2012-04 | api error: Google hasn't returned any results for this query. |
| 2026-04-12 | serpapi:tech stocks semiconductor|2012-03 | tech stocks semiconductor|2012-03 | api error: Google hasn't returned any results for this query. |
| 2026-04-12 | serpapi:tech stocks semiconductor|2012-05 | tech stocks semiconductor|2012-05 | api error: Google hasn't returned any results for this query. |
| 2026-04-12 | serpapi:tech stocks semiconductor|2013-01 | tech stocks semiconductor|2013-01 | api error: Google hasn't returned any results for this query. |
| 2026-04-12 | serpapi:tech stocks semiconductor|2013-02 | tech stocks semiconductor|2013-02 | api error: Google hasn't returned any results for this query. |
| 2026-04-12 | serpapi:tech stocks semiconductor|2014-09 | tech stocks semiconductor|2014-09 | api error: Google hasn't returned any results for this query. |
| 2026-04-12 | serpapi:tech stocks semiconductor|2014-07 | tech stocks semiconductor|2014-07 | api error: Google hasn't returned any results for this query. |
| 2026-04-12 | cboe:put_call | cdn.cboe.com/resources/options/volume_and_call_put_ratios/*.csv with Referer header | PARTIAL: total/equity/index 2003-10-17..2019-10-04 saved to data/clean/sentiment/cboe_putcall_{total,equity,index}.parquet (4019 rows each). No free source covers post-2019-10; CBOE moved ongoing PCR to paid DataShop. |
| 2026-04-12 | openinsider:screener (retry 3.5) | screener?fdr=...&xp=1&xs=1 various date ranges; preset /insider-purchases, /insider-sales, /latest-insider-trading | PERMANENTLY_FAILED: screener backend still returns 'ERROR: Unable to select tables for main' for any xp/xs query (server-side bug from 3.4 unresolved). Preset pages return only ~100 rows each with no historical depth. Use existing short file; no historical backfill possible. |
| 2026-04-12 | sp500:buyback_yield (retry 3.5) | yardeni PDF, macrotrends (search disallowed by robots) | RESOLVED: replaced by FRED BOGZ1FA106121075Q (nonfinancial corp net equity issuance, Z.1 quarterly 1946-2025) -> data/clean/fundamental/sp500_buyback_yield.parquet. Negative values = net buybacks. |
| 2026-04-12 | aar:rail_traffic (retry 3.5) | aar.org PDF press releases | RESOLVED: replaced by FRED RAILFRTCARLOADSD11 (Rail Freight Carloads monthly SA index 2000-2025) -> data/clean/alternative/rail_traffic.parquet. |
| 2026-04-12 | sifma:corp_bond_issuance (retry 3.5) | sifma.org HubSpot form gate; wayback machine | RESOLVED: replaced by FRED NCBDBIQ027S (Z.1 nonfinancial corp debt securities liability transactions, quarterly 1945-2025) -> data/clean/fundamental/corp_bond_issuance.parquet. |
| 2026-04-12 | bankruptcy:us_filings (retry 3.5) | FRED BKCOMN/BKFTTL/TNBFUSQ (all 404); uscourts.gov XLSX; ABI | PARTIAL: no free direct count series found. Saved FRED DRBLACBS (business loan delinquency rate 1987-2025) as proxy -> data/clean/alternative/bankruptcy_filings.parquet. Captures credit stress, not filing counts. |
