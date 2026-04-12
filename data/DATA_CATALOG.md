# Data Catalog

| Source | Series | Frequency | Date Range | File Path | Status | Notes |
|--------|--------|-----------|------------|-----------|--------|-------|
| data.bts.gov | airline_passengers | monthly | 2000-01-03..2025-12-01 | data/clean/alternative/airline_passengers.parquet | OK | BTS Monthly Transportation Statistics crem-w557 � US airline passengers (travel demand proxy) |
| yahoo_v8 | BDRY | daily | 2018-03-22..2026-04-10 | data/clean/alternative/baltic_dry.parquet | OK | BDRY ETF (Breakwave Dry Bulk Shipping) via Yahoo v8 chart API as BDI proxy. Inception 2018-03. |
| derived | copper_gold_ratio | daily | 2005-01-03..2026-04-10 | data/clean/alternative/copper_gold_ratio.parquet | OK | copper_price / GLD close (risk appetite indicator) |
| eia | eia_crude_oil_inventory | weekly | 1982-08-20..2026-04-02 | data/clean/alternative/eia_crude_oil_inventory.parquet | OK |  |
| eia | eia_electricity_generation | monthly | 2001-01-02..2025-12-31 | data/clean/alternative/eia_electricity_generation.parquet | OK |  |
| eia | eia_electricity_sales | monthly | 2001-01-02..2025-12-31 | data/clean/alternative/eia_electricity_sales.parquet | OK |  |
| eia | eia_gasoline_demand | weekly | 1991-02-08..2026-04-02 | data/clean/alternative/eia_gasoline_demand.parquet | OK |  |
| eia | eia_gasoline_inventory | weekly | 1990-01-05..2026-04-02 | data/clean/alternative/eia_gasoline_inventory.parquet | OK |  |
| eia | eia_natgas_storage | weekly | 2010-01-04..2026-04-02 | data/clean/alternative/eia_natgas_storage.parquet | OK |  |
| eia | eia_refinery_utilization | weekly | 1990-11-02..2026-04-02 | data/clean/alternative/eia_refinery_utilization.parquet | OK |  |
| finra | finra_darkpool | weekly | 2023-11-27..2023-12-11 | data/clean/alternative/finra_darkpool.parquet | STUB | only 11 rows from public ATS summary endpoint; full archive requires FINRA OTC account |
| github | github_amd | weekly | 2025-04-21..2026-04-10 | data/clean/alternative/github_amd.parquet | SHORT | history capped at 52 weeks by GitHub API |
| github | github_apple | weekly | 2025-04-21..2026-04-10 | data/clean/alternative/github_apple.parquet | SHORT | history capped at 52 weeks by GitHub API |
| github | github_google | weekly | 2025-04-21..2026-04-10 | data/clean/alternative/github_google.parquet | SHORT | history capped at 52 weeks by GitHub API |
| github | github_meta | weekly | 2025-04-21..2026-04-10 | data/clean/alternative/github_meta.parquet | SHORT | history capped at 52 weeks by GitHub API |
| github | github_microsoft | weekly | 2025-04-21..2026-04-10 | data/clean/alternative/github_microsoft.parquet | SHORT | history capped at 52 weeks by GitHub API |
| github | github_nvidia | weekly | 2025-04-21..2026-04-10 | data/clean/alternative/github_nvidia.parquet | SHORT | history capped at 52 weeks by GitHub API |
| google_trends | gtrends_ai_stocks | weekly | 2010-01-04..2026-04-01 | data/clean/alternative/gtrends_ai_stocks.parquet | OK | relative search interest (0-100) for 'AI stocks' |
| google_trends | gtrends_bank_run | weekly | 2010-01-04..2026-04-01 | data/clean/alternative/gtrends_bank_run.parquet | OK | relative search interest (0-100) for 'bank run' |
| google_trends | gtrends_bankruptcy | weekly | 2010-01-04..2026-04-01 | data/clean/alternative/gtrends_bankruptcy.parquet | OK | relative search interest (0-100) for 'bankruptcy' |
| google_trends | gtrends_bear_market | weekly | 2010-01-04..2026-04-01 | data/clean/alternative/gtrends_bear_market.parquet | OK | relative search interest (0-100) for 'bear market' |
| google_trends | gtrends_bitcoin_price | weekly | 2010-01-04..2026-04-01 | data/clean/alternative/gtrends_bitcoin_price.parquet | OK | relative search interest (0-100) for 'bitcoin price' |
| google_trends | gtrends_bull_market | weekly | 2010-01-04..2026-04-01 | data/clean/alternative/gtrends_bull_market.parquet | OK | relative search interest (0-100) for 'bull market' |
| google_trends | gtrends_buy_gold | weekly | 2010-01-04..2026-04-01 | data/clean/alternative/gtrends_buy_gold.parquet | OK | relative search interest (0-100) for 'buy gold' |
| google_trends | gtrends_energy_crisis | weekly | 2010-01-04..2026-04-01 | data/clean/alternative/gtrends_energy_crisis.parquet | OK | relative search interest (0-100) for 'energy crisis' |
| google_trends | gtrends_gold_buy | weekly | 2010-01-04..2026-04-01 | data/clean/alternative/gtrends_gold_buy.parquet | OK | relative search interest (0-100) for 'gold buy' |
| google_trends | gtrends_housing_crash | weekly | 2010-01-04..2026-04-01 | data/clean/alternative/gtrends_housing_crash.parquet | OK | relative search interest (0-100) for 'housing crash' |
| google_trends | gtrends_inflation | weekly | 2010-01-04..2026-04-01 | data/clean/alternative/gtrends_inflation.parquet | OK | relative search interest (0-100) for 'inflation' |
| google_trends | gtrends_interest_rates | weekly | 2010-01-04..2026-04-01 | data/clean/alternative/gtrends_interest_rates.parquet | OK | relative search interest (0-100) for 'interest rates' |
| google_trends | gtrends_layoffs | weekly | 2010-01-04..2026-04-01 | data/clean/alternative/gtrends_layoffs.parquet | OK | relative search interest (0-100) for 'layoffs' |
| google_trends | gtrends_oil_price | weekly | 2010-01-04..2026-04-01 | data/clean/alternative/gtrends_oil_price.parquet | OK | relative search interest (0-100) for 'oil price' |
| google_trends | gtrends_recession | weekly | 2010-01-04..2026-04-01 | data/clean/alternative/gtrends_recession.parquet | OK | relative search interest (0-100) for 'recession' |
| google_trends | gtrends_semiconductor_shortage | weekly | 2010-01-04..2026-04-01 | data/clean/alternative/gtrends_semiconductor_shortage.parquet | OK | relative search interest (0-100) for 'semiconductor shortage' |
| google_trends | gtrends_stock_market_crash | weekly | 2010-01-04..2026-04-01 | data/clean/alternative/gtrends_stock_market_crash.parquet | OK | relative search interest (0-100) for 'stock market crash' |
| google_trends | gtrends_tech_stocks | weekly | 2010-01-04..2026-04-01 | data/clean/alternative/gtrends_tech_stocks.parquet | OK | relative search interest (0-100) for 'tech stocks' |
| google_trends | gtrends_unemployment | weekly | 2010-01-04..2026-04-01 | data/clean/alternative/gtrends_unemployment.parquet | OK | relative search interest (0-100) for 'unemployment' |
| derived | lumber_gold_ratio | monthly | 1926-02-01..2025-12-01 | data/clean/alternative/lumber_gold_ratio.parquet | OK | FRED WPU081 lumber PPI / gold london fix (housing/construction sentiment) |
| fred | MMMFFAQ027S | quarterly | 1945-10-01..2025-10-01 | data/clean/alternative/money_market_assets.parquet | OK | Money market fund total financial assets (risk aversion proxy) |
| data.lacity.org | port_la_teu | monthly | 2009-02-02..2016-09-30 | data/clean/alternative/port_la_containers.parquet | OK | Port of LA monthly TEU counts via LA City socrata (tsuv-4rgh). Trade activity proxy. |
| arctic-shift | reddit_economics | daily | 2018-01-02..2026-04-08 | data/clean/alternative/reddit_economics.parquet | OK | Arctic Shift daily post count for r/economics + 21d spike ratio |
| arctic-shift | reddit_investing | daily | 2018-01-02..2026-04-08 | data/clean/alternative/reddit_investing.parquet | OK | Arctic Shift daily post count for r/investing + 21d spike ratio |
| arctic-shift | reddit_stocks | daily | 2018-01-02..2026-04-08 | data/clean/alternative/reddit_stocks.parquet | OK | Arctic Shift daily post count for r/stocks + 21d spike ratio |
| arctic-shift | reddit_wallstreetbets | daily | 2018-01-02..2026-04-08 | data/clean/alternative/reddit_wallstreetbets.parquet | OK | Arctic Shift daily post count for r/wallstreetbets + 21d spike ratio |
| tsa | tsa_passengers | daily | 2026-01-02..2026-04-09 | data/clean/alternative/tsa_passengers.parquet | OK | TSA checkpoint daily throughput (travel demand proxy). Only ~3mo history � TSA page now shows rolling window only. |
| wikipedia | wikipedia_artificial_intelligence | daily | 2015-07-01..2026-04-10 | data/clean/alternative/wikipedia_artificial_intelligence.parquet | OK | Artificial_intelligence |
| wikipedia | wikipedia_bank_run | daily | 2015-07-01..2026-04-10 | data/clean/alternative/wikipedia_bank_run.parquet | OK | Bank_run |
| wikipedia | wikipedia_bear_market | daily | 2015-07-01..2026-04-10 | data/clean/alternative/wikipedia_bear_market.parquet | OK | Bear_market |
| wikipedia | wikipedia_bitcoin | daily | 2015-07-01..2026-04-10 | data/clean/alternative/wikipedia_bitcoin.parquet | OK | Bitcoin |
| wikipedia | wikipedia_cryptocurrency | daily | 2015-07-01..2026-04-10 | data/clean/alternative/wikipedia_cryptocurrency.parquet | OK | Cryptocurrency |
| wikipedia | wikipedia_dot_com_bubble | daily | 2015-07-01..2026-04-10 | data/clean/alternative/wikipedia_dot_com_bubble.parquet | OK | Dot-com_bubble |
| wikipedia | wikipedia_federal_reserve | daily | 2015-07-01..2026-04-10 | data/clean/alternative/wikipedia_federal_reserve.parquet | OK | Federal_Reserve |
| wikipedia | wikipedia_gold_as_an_investment | daily | 2015-07-01..2026-04-10 | data/clean/alternative/wikipedia_gold_as_an_investment.parquet | OK | Gold_as_an_investment |
| wikipedia | wikipedia_inflation | daily | 2015-07-01..2026-04-10 | data/clean/alternative/wikipedia_inflation.parquet | OK | Inflation |
| wikipedia | wikipedia_margin_finance | daily | 2015-07-01..2026-04-10 | data/clean/alternative/wikipedia_margin_finance.parquet | OK | Margin_(finance) |
| wikipedia | wikipedia_nasdaq_100 | daily | 2015-07-01..2026-04-10 | data/clean/alternative/wikipedia_nasdaq_100.parquet | OK | NASDAQ-100 |
| wikipedia | wikipedia_nvidia | daily | 2015-07-01..2026-04-10 | data/clean/alternative/wikipedia_nvidia.parquet | OK | NVIDIA |
| wikipedia | wikipedia_oil_crisis | daily | 2015-07-01..2026-04-10 | data/clean/alternative/wikipedia_oil_crisis.parquet | OK | Oil_crisis |
| wikipedia | wikipedia_quantitative_easing | daily | 2015-07-01..2026-04-10 | data/clean/alternative/wikipedia_quantitative_easing.parquet | OK | Quantitative_easing |
| wikipedia | wikipedia_recession | daily | 2015-07-01..2026-04-10 | data/clean/alternative/wikipedia_recession.parquet | OK | Recession |
| wikipedia | wikipedia_s_p_500 | daily | 2015-07-01..2026-04-10 | data/clean/alternative/wikipedia_s_p_500.parquet | OK | S%26P_500 |
| wikipedia | wikipedia_semiconductor | daily | 2015-07-01..2026-04-10 | data/clean/alternative/wikipedia_semiconductor.parquet | OK | Semiconductor |
| wikipedia | wikipedia_short_selling | daily | 2015-07-01..2026-04-10 | data/clean/alternative/wikipedia_short_selling.parquet | OK | Short_selling |
| wikipedia | wikipedia_stagflation | daily | 2015-07-01..2026-04-10 | data/clean/alternative/wikipedia_stagflation.parquet | OK | Stagflation |
| wikipedia | wikipedia_stock_market_crash | daily | 2015-07-01..2026-04-10 | data/clean/alternative/wikipedia_stock_market_crash.parquet | OK | Stock_market_crash |
| wikipedia | wikipedia_subprime_mortgage_crisis | daily | 2015-07-01..2026-04-10 | data/clean/alternative/wikipedia_subprime_mortgage_crisis.parquet | OK | Subprime_mortgage_crisis |
| wikipedia | wikipedia_trade_war | daily | 2015-07-01..2026-04-10 | data/clean/alternative/wikipedia_trade_war.parquet | OK | Trade_war |
| wikipedia | wikipedia_unemployment | daily | 2015-07-01..2026-04-10 | data/clean/alternative/wikipedia_unemployment.parquet | OK | Unemployment |
| wikipedia | wikipedia_yield_curve | daily | 2015-07-01..2026-04-10 | data/clean/alternative/wikipedia_yield_curve.parquet | OK | Yield_curve |
| rule-based | calendar_events | daily | 2005-01-03..2027-12-31 | data/clean/calendar/events.parquet | OK | 22 flags: FOMC/CPI/NFP/GDP/OpEx/quad/Russell/election/ECB/BOJ/cyclical encodings |
| macrotrends | sector_copper_price | daily | 1959-07-02..2026-04-10 | data/clean/fundamental/sector_copper_price.parquet | OK | id=1476; genuinely daily; longer history than FRED PCOPPUSDM (monthly 2000-). |
| macrotrends | sector_crude_oil_wti | monthly | 1946-01-02..2026-04-01 | data/clean/fundamental/sector_crude_oil_wti.parquet | REDUNDANT | id=1369; monthly (re-aligned 2026-04-12, was incorrectly daily). REDUNDANT with FRED DCOILWTICO (daily, 2000-). Keep for pre-2000 history only. |
| macrotrends | sector_gold_london_fix | monthly | 1915-01-02..2026-04-01 | data/clean/fundamental/sector_gold_london_fix.parquet | OK | id=1333; monthly (re-aligned 2026-04-12). Inflation-adjusted series (macrotrends historical-gold-prices-100-year-chart). No FRED equivalent (GOLDAMGBD228NLBM discontinued). |
| macrotrends | sector_natural_gas_henry_hub | monthly | 1997-01-02..2026-04-01 | data/clean/fundamental/sector_natural_gas_henry_hub.parquet | REDUNDANT | id=2478; monthly (re-aligned 2026-04-12, was incorrectly daily). REDUNDANT with FRED DHHNGSP (daily, 2000-). Keep for 1997-2000 history only. |
| macrotrends | sector_silver_price | monthly | 1915-01-02..2026-04-01 | data/clean/fundamental/sector_silver_price.parquet | OK | id=1470; monthly (re-aligned 2026-04-12). No free FRED equivalent. |
| macrotrends | sector_sp500_pe_ratio | monthly | 1927-12-01..2026-02-27 | data/clean/fundamental/sector_sp500_pe_ratio.parquet | OK | chart_iframe_comp id=2577 |
| sia | sia_semiconductor_sales | monthly | 2005-08-31..2026-02-27 | data/clean/fundamental/sia_semiconductor_sales.parquet | OK | scraped from press release headlines (3-month moving average) |
| multpl | sp500_dividend_yield | monthly | 1871-01-31..2026-04-10 | data/clean/fundamental/sp500_dividend_yield.parquet | OK | monthly S&P 500 fundamentals |
| multpl | sp500_earnings | monthly | 1871-01-31..2025-09-30 | data/clean/fundamental/sp500_earnings.parquet | OK | monthly S&P 500 fundamentals |
| multpl | sp500_earnings_yield | monthly | 1871-01-02..2026-04-10 | data/clean/fundamental/sp500_earnings_yield.parquet | OK | monthly S&P 500 fundamentals |
| multpl | sp500_pe_ratio | monthly | 1871-01-02..2026-04-10 | data/clean/fundamental/sp500_pe_ratio.parquet | OK | monthly S&P 500 fundamentals |
| multpl | sp500_price_to_book | monthly | 1999-12-31..2026-04-10 | data/clean/fundamental/sp500_price_to_book.parquet | OK | monthly S&P 500 fundamentals |
| multpl | sp500_price_to_sales | monthly | 2001-01-02..2026-04-10 | data/clean/fundamental/sp500_price_to_sales.parquet | OK | monthly S&P 500 fundamentals |
| multpl | sp500_shiller_cape | monthly | 1871-02-01..2026-04-10 | data/clean/fundamental/sp500_shiller_cape.parquet | OK | monthly S&P 500 fundamentals |
| fred | PALUMUSDM | monthly | 2000-02-01..2026-01-02 | data/clean/macro/aluminum_price.parquet | OK |  |
| fred | DRALACBN | quarterly | 2001-10-01..2025-10-01 | data/clean/macro/auto_loan_delinq.parquet | OK |  |
| fred | CES0500000003 | monthly | 2006-03-01..2026-01-02 | data/clean/macro/avg_hourly_earnings.parquet | OK |  |
| fred | avg_hourly_earnings_yoy | monthly | 2007-05-31..2026-01-30 | data/clean/macro/avg_hourly_earnings_yoy.parquet | OK | derived; CES0500000003 12m % change |
| fred | BAMLC0A4CBBB | daily | 2000-01-03..2026-04-09 | data/clean/macro/bbb_oas.parquet | OK |  |
| fred | breakeven10_minus_cpi_yoy | daily | 2003-01-02..2026-01-30 | data/clean/macro/breakeven10_minus_cpi_yoy.parquet | OK | derived; T10YIE - CPI YoY |
| fred | breakeven5_minus_cpi_yoy | daily | 2003-01-02..2026-01-30 | data/clean/macro/breakeven5_minus_cpi_yoy.parquet | OK | derived; T5YIE - CPI YoY |
| fred | T10YIE | daily | 2003-01-02..2026-04-10 | data/clean/macro/breakeven_10y.parquet | OK |  |
| fred | T5YIE | daily | 2003-01-02..2026-04-10 | data/clean/macro/breakeven_5y.parquet | OK |  |
| fred | DCOILBRENTEU | daily | 2000-01-04..2026-04-02 | data/clean/macro/brent_crude.parquet | OK |  |
| fred | PERMIT | monthly | 2000-02-01..2025-12-31 | data/clean/macro/building_permits.parquet | OK |  |
| fred | TCU | monthly | 2000-02-01..2026-01-02 | data/clean/macro/capacity_utilization.parquet | OK |  |
| fred | CSUSHPINSA | monthly | 2000-02-01..2025-12-31 | data/clean/macro/case_shiller_hpi.parquet | OK |  |
| fred | DEXCHUS | daily | 2000-01-03..2026-04-02 | data/clean/macro/cny_usd.parquet | OK |  |
| fred | CPFF | daily | 2000-01-03..2026-04-09 | data/clean/macro/commercial_paper_rate.parquet | OK |  |
| fred | CONCCONF | monthly | 2000-02-01..2026-01-02 | data/clean/macro/conference_board_conf.parquet | OK | alt:UMCSENT |
| fred | TOTALSL | monthly | 2000-02-01..2026-01-02 | data/clean/macro/consumer_credit_total.parquet | OK |  |
| fred | CCSA | weekly | 1967-01-09..2026-03-27 | data/clean/macro/continuing_claims.parquet | OK | re-fetched 2026-04-12; was empty/sparse |
| fred | PCOPPUSDM | monthly | 2000-02-01..2026-01-02 | data/clean/macro/copper_price.parquet | OK |  |
| fred | CPIAUCSL | monthly | 2000-02-01..2026-01-02 | data/clean/macro/cpi_all_urban.parquet | OK |  |
| fred | CPILFESL | monthly | 2000-02-01..2026-01-02 | data/clean/macro/cpi_core.parquet | OK |  |
| fred | cpi_core_yoy | monthly | 2001-02-28..2026-01-30 | data/clean/macro/cpi_core_yoy.parquet | OK | derived; CPILFESL 12m % change |
| fred | cpi_mom | monthly | 2000-03-31..2025-10-30 | data/clean/macro/cpi_mom.parquet | OK | derived; CPIAUCSL 1m % change |
| fred | cpi_yoy | monthly | 2001-02-28..2026-01-30 | data/clean/macro/cpi_yoy.parquet | OK | derived; CPIAUCSL 12m % change |
| fred | DRCCLACBS | quarterly | 2001-10-01..2025-10-01 | data/clean/macro/credit_card_delinq.parquet | OK |  |
| fred | DGORDER | monthly | 2000-02-01..2026-01-02 | data/clean/macro/durable_goods_orders.parquet | OK |  |
| fred | EXHOSLUSM495S | monthly | 2025-04-01..2026-01-02 | data/clean/macro/existing_home_sales.parquet | SHORT | history=0.8y |
| fred | EXPGS | quarterly | 2001-10-01..2025-10-01 | data/clean/macro/exports_gs.parquet | OK |  |
| fred | WALCL | weekly | 2002-12-18..2026-04-08 | data/clean/macro/fed_balance_sheet.parquet | OK |  |
| fred | DFF | daily | 2000-01-03..2026-04-09 | data/clean/macro/fed_funds_daily.parquet | OK |  |
| fred | FEDFUNDS | monthly | 2000-02-01..2026-01-02 | data/clean/macro/fed_funds_rate.parquet | OK |  |
| fred | GDP | quarterly | 2001-10-01..2025-10-01 | data/clean/macro/gdp_nominal.parquet | OK |  |
| fred | GDPC1 | quarterly | 2001-10-01..2025-10-01 | data/clean/macro/gdp_real.parquet | OK |  |
| fred | A191RL1Q225SBEA | quarterly | 1947-04-01..2025-10-01 | data/clean/macro/gdp_real_growth_annualized.parquet | OK | re-fetched 2026-04-12; was empty/sparse |
| fred | DHHNGSP | daily | 2000-01-04..2026-04-06 | data/clean/macro/henry_hub_natgas.parquet | OK |  |
| fred | HOUST | monthly | 2000-02-01..2025-12-31 | data/clean/macro/housing_starts.parquet | OK |  |
| fred | BAMLH0A0HYM2 | daily | 2000-01-03..2026-04-09 | data/clean/macro/hy_oas.parquet | OK |  |
| fred | IMPGS | quarterly | 2001-10-01..2025-10-01 | data/clean/macro/imports_gs.parquet | OK |  |
| fred | INDPRO | monthly | 2000-02-01..2026-01-02 | data/clean/macro/industrial_production.parquet | OK |  |
| fred | ICSA | weekly | 1967-01-09..2026-04-02 | data/clean/macro/initial_claims.parquet | OK | re-fetched 2026-04-12; was empty/sparse |
| fred | ism_manufacturing_pmi | monthly | 2002-04-30..2025-12-31 | data/clean/macro/ism_manufacturing_pmi.parquet | PROXY | PROXY: z-score composite of INDPRO 12m log-change + TCU level dev, rescaled to PMI-like 50-center. Not the actual ISM series. |
| fred | ism_services_pmi | monthly | 2002-04-30..2025-12-31 | data/clean/macro/ism_services_pmi.parquet | PROXY | PROXY: same INDPRO+TCU composite as manufacturing proxy. No free services-specific proxy available; treat with caution. |
| fred | JTSJOL | monthly | 2000-12-01..2026-01-02 | data/clean/macro/jolts_job_openings.parquet | OK |  |
| fred | DEXJPUS | daily | 2000-01-03..2026-04-02 | data/clean/macro/jpy_usd.parquet | OK |  |
| fred | KCFSI | monthly | 2000-02-01..2026-01-02 | data/clean/macro/kcfsi.parquet | OK |  |
| fred | CIVPART | monthly | 2000-02-01..2026-01-02 | data/clean/macro/labor_force_partic.parquet | OK |  |
| fred | USSLIND | monthly | 2000-02-01..2019-12-04 | data/clean/macro/leading_econ_index.parquet | OK |  |
| fred | M1SL | monthly | 2000-02-01..2026-01-02 | data/clean/macro/m1_money_supply.parquet | OK |  |
| fred | M2SL | monthly | 2000-02-01..2026-01-02 | data/clean/macro/m2_money_supply.parquet | OK |  |
| fred | m2_yoy | monthly | 2001-02-28..2026-01-30 | data/clean/macro/m2_yoy.parquet | OK | derived; M2SL 12m % change |
| fred | BOGMBASE | monthly | 2000-02-01..2026-01-02 | data/clean/macro/monetary_base.parquet | OK |  |
| fred | DAAA | daily | 1983-01-03..2026-04-09 | data/clean/macro/moodys_aaa.parquet | OK | re-fetched 2026-04-12; was empty/sparse |
| fred | DBAA | daily | 1986-01-02..2026-04-09 | data/clean/macro/moodys_baa.parquet | OK | re-fetched 2026-04-12; was empty/sparse |
| fred | MORTGAGE30US | weekly | 2000-01-07..2026-04-09 | data/clean/macro/mortgage_30y.parquet | OK |  |
| fred | NFCI | weekly | 2000-01-07..2026-04-02 | data/clean/macro/nfci.parquet | OK |  |
| fred | PAYEMS | monthly | 2000-02-01..2026-01-02 | data/clean/macro/nonfarm_payrolls.parquet | OK |  |
| fred | USALOLITONOSTSAM | monthly | 2000-02-01..2023-12-29 | data/clean/macro/oecd_cli_us.parquet | OK |  |
| fred | CSCICP03USM665S | monthly | 2000-02-01..2023-12-29 | data/clean/macro/oecd_consumer_conf_us.parquet | OK |  |
| fred | RRPONTSYD | daily | 2003-02-07..2026-04-10 | data/clean/macro/overnight_repo.parquet | OK |  |
| fred | payems_mom | monthly | 2000-03-31..2025-12-03 | data/clean/macro/payems_mom.parquet | OK | derived; PAYEMS 1m diff (thousands) |
| fred | PCEPILFE | monthly | 2000-02-01..2026-01-02 | data/clean/macro/pce_core.parquet | OK |  |
| fred | PCEPI | monthly | 2000-02-01..2026-01-02 | data/clean/macro/pce_price_index.parquet | OK |  |
| fred | PCE | monthly | 2000-02-01..2026-01-02 | data/clean/macro/personal_consumption.parquet | OK |  |
| fred | PSAVERT | monthly | 2000-02-01..2026-01-02 | data/clean/macro/personal_savings_rate.parquet | OK |  |
| fred | WPU10250105 | monthly | 2003-12-01..2023-09-01 | data/clean/macro/platinum_ppi.parquet | OK |  |
| fred | PPIACO | monthly | 2000-02-01..2026-01-02 | data/clean/macro/ppi_all_commodities.parquet | OK |  |
| fred | RSXFS | monthly | 2000-02-01..2026-01-02 | data/clean/macro/retail_sales_ex_food.parquet | OK |  |
| fred | spread_10y_2y | daily | 2000-01-03..2026-04-09 | data/clean/macro/spread_10y_2y.parquet | OK | derived; DGS10 - DGS2 |
| fred | spread_10y_3m | daily | 2000-01-03..2026-04-09 | data/clean/macro/spread_10y_3m.parquet | OK | derived; DGS10 - DGS3MO |
| fred | spread_baa_aaa | daily | 1986-01-02..2026-04-09 | data/clean/macro/spread_baa_aaa.parquet | OK | derived; DBAA - DAAA (daily) |
| fred | STLFSI2 | weekly | 2000-01-07..2022-01-07 | data/clean/macro/stlfsi.parquet | OK |  |
| fred | STLFSI4 | weekly | 2000-01-07..2026-04-02 | data/clean/macro/stlfsi4.parquet | OK | replacement for discontinued STLFSI2 |
| fred | BOGZ1FL073164003Q | quarterly | 2001-10-01..2025-10-01 | data/clean/macro/student_loan_delinq.parquet | OK |  |
| fred | TEDRATE | daily | 2000-01-04..2022-01-21 | data/clean/macro/ted_spread.parquet | OK |  |
| fred | BOPGSTB | monthly | 2000-02-01..2026-01-02 | data/clean/macro/trade_balance.parquet | OK |  |
| fred | DGS10 | daily | 2000-01-03..2026-04-09 | data/clean/macro/treasury_10y.parquet | OK |  |
| fred | DGS2 | daily | 2000-01-03..2026-04-09 | data/clean/macro/treasury_2y.parquet | OK |  |
| fred | DGS30 | daily | 2000-01-03..2026-04-09 | data/clean/macro/treasury_30y.parquet | OK |  |
| fred | DGS3MO | daily | 2000-01-03..2026-04-09 | data/clean/macro/treasury_3m.parquet | OK |  |
| fred | DGS5 | daily | 2000-01-03..2026-04-09 | data/clean/macro/treasury_5y.parquet | OK |  |
| treasury | treasury_auctions | event | 1997-01-29..2026-03-24 | data/clean/macro/treasury_auctions.parquet | OK | bid-to-cover for 2y/10y/30y from FiscalData |
| fred | UMCSENT | monthly | 2000-02-01..2026-01-02 | data/clean/macro/umich_sentiment.parquet | OK |  |
| fred | UNRATE | monthly | 2000-02-01..2026-01-02 | data/clean/macro/unemployment_rate.parquet | OK |  |
| fred | DTWEXBGS | daily | 2006-01-03..2026-04-02 | data/clean/macro/usd_broad.parquet | OK |  |
| fred | DEXUSEU | daily | 2000-01-03..2026-04-02 | data/clean/macro/usd_eur.parquet | OK |  |
| fred | TOTALSA | monthly | 2000-02-01..2026-01-02 | data/clean/macro/vehicle_sales.parquet | OK |  |
| fred | DCOILWTICO | daily | 2000-01-04..2026-04-06 | data/clean/macro/wti_crude.parquet | OK |  |
| yahoo | AGG | daily | 2005-01-03..2026-04-10 | data/clean/prices/AGG.parquet | OK |  |
| yahoo | ARKK | daily | 2014-10-31..2026-04-10 | data/clean/prices/ARKK.parquet | OK |  |
| yahoo | BITO | daily | 2021-10-20..2026-04-10 | data/clean/prices/BITO.parquet | OK |  |
| yahoo | BND | daily | 2007-04-10..2026-04-10 | data/clean/prices/BND.parquet | OK |  |
| yahoo | COPX | daily | 2010-04-20..2026-04-10 | data/clean/prices/COPX.parquet | OK |  |
| yahoo | CORN | daily | 2010-06-09..2026-04-10 | data/clean/prices/CORN.parquet | OK |  |
| yahoo | DBA | daily | 2007-01-05..2026-04-10 | data/clean/prices/DBA.parquet | OK |  |
| yahoo | DBC | daily | 2006-02-06..2026-04-10 | data/clean/prices/DBC.parquet | OK |  |
| yahoo | EEM | daily | 2005-01-03..2026-04-10 | data/clean/prices/EEM.parquet | OK |  |
| yahoo | EFA | daily | 2005-01-03..2026-04-10 | data/clean/prices/EFA.parquet | OK |  |
| yahoo | EWG | daily | 2005-01-03..2026-04-10 | data/clean/prices/EWG.parquet | OK |  |
| yahoo | EWJ | daily | 2005-01-03..2026-04-10 | data/clean/prices/EWJ.parquet | OK |  |
| yahoo | EWZ | daily | 2005-01-03..2026-04-10 | data/clean/prices/EWZ.parquet | OK |  |
| yahoo | FXA | daily | 2006-06-26..2026-04-10 | data/clean/prices/FXA.parquet | OK |  |
| yahoo | FXE | daily | 2005-12-12..2026-04-10 | data/clean/prices/FXE.parquet | OK |  |
| yahoo | FXI | daily | 2005-01-03..2026-04-10 | data/clean/prices/FXI.parquet | OK |  |
| yahoo | FXY | daily | 2007-02-13..2026-04-10 | data/clean/prices/FXY.parquet | OK |  |
| yahoo | GBTC | daily | 2015-05-11..2026-04-10 | data/clean/prices/GBTC.parquet | OK |  |
| yahoo | GDX | daily | 2006-05-22..2026-04-10 | data/clean/prices/GDX.parquet | OK |  |
| yahoo | GLD | daily | 2005-01-03..2026-04-10 | data/clean/prices/GLD.parquet | OK |  |
| yahoo | HACK | daily | 2014-11-12..2026-04-10 | data/clean/prices/HACK.parquet | OK |  |
| yahoo | HYG | daily | 2007-04-11..2026-04-10 | data/clean/prices/HYG.parquet | OK |  |
| yahoo | IBB | daily | 2005-01-03..2026-04-10 | data/clean/prices/IBB.parquet | OK |  |
| yahoo | ICLN | daily | 2008-06-25..2026-04-10 | data/clean/prices/ICLN.parquet | OK |  |
| yahoo | IEF | daily | 2005-01-03..2026-04-10 | data/clean/prices/IEF.parquet | OK |  |
| yahoo | IEI | daily | 2007-01-11..2026-04-10 | data/clean/prices/IEI.parquet | OK |  |
| yahoo | IGV | daily | 2005-01-03..2026-04-10 | data/clean/prices/IGV.parquet | OK |  |
| yahoo | IWM | daily | 2005-01-03..2026-04-10 | data/clean/prices/IWM.parquet | OK |  |
| yahoo | IYR | daily | 2005-01-03..2026-04-10 | data/clean/prices/IYR.parquet | OK |  |
| yahoo | JETS | daily | 2015-04-30..2026-04-10 | data/clean/prices/JETS.parquet | OK |  |
| yahoo | KWEB | daily | 2013-08-01..2026-04-10 | data/clean/prices/KWEB.parquet | OK |  |
| yahoo | LIT | daily | 2010-07-23..2026-04-10 | data/clean/prices/LIT.parquet | OK |  |
| yahoo | LQD | daily | 2005-01-03..2026-04-10 | data/clean/prices/LQD.parquet | OK |  |
| yahoo | MTUM | daily | 2013-04-18..2026-04-10 | data/clean/prices/MTUM.parquet | OK |  |
| yahoo | PDBC | daily | 2014-11-07..2026-04-10 | data/clean/prices/PDBC.parquet | OK |  |
| yahoo | PPLT | daily | 2010-01-08..2026-04-10 | data/clean/prices/PPLT.parquet | OK |  |
| yahoo | QQQ | daily | 2005-01-03..2026-04-10 | data/clean/prices/QQQ.parquet | OK |  |
| yahoo | QUAL | daily | 2013-07-18..2026-04-10 | data/clean/prices/QUAL.parquet | OK |  |
| yahoo | SHV | daily | 2007-01-11..2026-04-10 | data/clean/prices/SHV.parquet | OK |  |
| yahoo | SHY | daily | 2005-01-03..2026-04-10 | data/clean/prices/SHY.parquet | OK |  |
| yahoo | SIZE | daily | 2013-04-18..2026-04-10 | data/clean/prices/SIZE.parquet | OK |  |
| yahoo | SLV | daily | 2006-04-28..2026-04-10 | data/clean/prices/SLV.parquet | OK |  |
| yahoo | SMH | daily | 2005-01-03..2026-04-10 | data/clean/prices/SMH.parquet | OK |  |
| yahoo | SOXX | daily | 2005-01-03..2026-04-10 | data/clean/prices/SOXX.parquet | OK |  |
| yahoo | SPY | daily | 2005-01-03..2026-04-10 | data/clean/prices/SPY.parquet | OK |  |
| yahoo | TAN | daily | 2008-04-15..2026-04-10 | data/clean/prices/TAN.parquet | OK |  |
| yahoo | TIP | daily | 2005-01-03..2026-04-10 | data/clean/prices/TIP.parquet | OK |  |
| yahoo | TLT | daily | 2005-01-03..2026-04-10 | data/clean/prices/TLT.parquet | OK |  |
| yahoo | UNG | daily | 2007-04-18..2026-04-10 | data/clean/prices/UNG.parquet | OK |  |
| yahoo | USMV | daily | 2011-10-20..2026-04-10 | data/clean/prices/USMV.parquet | OK |  |
| yahoo | USO | daily | 2006-04-10..2026-04-10 | data/clean/prices/USO.parquet | OK |  |
| yahoo | UUP | daily | 2007-03-01..2026-04-10 | data/clean/prices/UUP.parquet | OK |  |
| yahoo | UVXY | daily | 2011-10-04..2026-04-10 | data/clean/prices/UVXY.parquet | OK |  |
| yahoo | VGT | daily | 2005-01-03..2026-04-10 | data/clean/prices/VGT.parquet | OK |  |
| yahoo | VIXY | daily | 2011-01-04..2026-04-10 | data/clean/prices/VIXY.parquet | OK |  |
| yahoo | VLUE | daily | 2013-04-18..2026-04-10 | data/clean/prices/VLUE.parquet | OK |  |
| yahoo | VNQ | daily | 2005-01-03..2026-04-10 | data/clean/prices/VNQ.parquet | OK |  |
| yahoo | WEAT | daily | 2011-09-19..2026-04-10 | data/clean/prices/WEAT.parquet | OK |  |
| yahoo | XBI | daily | 2006-02-06..2026-04-10 | data/clean/prices/XBI.parquet | OK |  |
| yahoo | XLB | daily | 2005-01-03..2026-04-10 | data/clean/prices/XLB.parquet | OK |  |
| yahoo | XLE | daily | 2005-01-03..2026-04-10 | data/clean/prices/XLE.parquet | OK |  |
| yahoo | XLF | daily | 2005-01-03..2026-04-10 | data/clean/prices/XLF.parquet | OK |  |
| yahoo | XLI | daily | 2005-01-03..2026-04-10 | data/clean/prices/XLI.parquet | OK |  |
| yahoo | XLK | daily | 2005-01-03..2026-04-10 | data/clean/prices/XLK.parquet | OK |  |
| yahoo | XLP | daily | 2005-01-03..2026-04-10 | data/clean/prices/XLP.parquet | OK |  |
| yahoo | XLRE | daily | 2015-10-08..2026-04-10 | data/clean/prices/XLRE.parquet | OK |  |
| yahoo | XLU | daily | 2005-01-03..2026-04-10 | data/clean/prices/XLU.parquet | OK |  |
| yahoo | XLV | daily | 2005-01-03..2026-04-10 | data/clean/prices/XLV.parquet | OK |  |
| yahoo | ^VIX | daily | 2005-01-03..2026-04-10 | data/clean/prices/_VIX.parquet | OK |  |
| aaii | aaii_sentiment | weekly | 1987-07-24..2023-12-28 | data/clean/sentiment/aaii_sentiment.parquet | OK | bull/bear/neutral % + spread |
| cboe | cboe_skew | daily | 1990-01-02..2026-04-10 | data/clean/sentiment/cboe_skew.parquet | OK | from cdn.cboe.com |
| cboe | cboe_vix | daily | 1990-01-02..2026-04-10 | data/clean/sentiment/cboe_vix.parquet | OK | from cdn.cboe.com |
| cboe | cboe_vix3m | daily | 2009-09-18..2026-04-10 | data/clean/sentiment/cboe_vix3m.parquet | OK | from cdn.cboe.com |
| cboe | cboe_vix6m | daily | 2008-01-02..2026-04-10 | data/clean/sentiment/cboe_vix6m.parquet | OK | from cdn.cboe.com |
| cboe | cboe_vix9d | daily | 2011-01-04..2026-04-10 | data/clean/sentiment/cboe_vix9d.parquet | OK | from cdn.cboe.com |
| cboe | cboe_vix_term_structure | daily | 2009-09-18..2026-04-10 | data/clean/sentiment/cboe_vix_term_structure.parquet | OK | VIX/VIX3M ratio and spread (derived) |
| cnn | cnn_fear_greed | daily | 2025-04-14..2026-04-10 | data/clean/sentiment/cnn_fear_greed.parquet | OK | CNN Fear & Greed Index (0-100); ~3y history from undocumented API |
| cftc | cot_copper | weekly | 2010-01-05..2026-04-07 | data/clean/sentiment/cot_copper.parquet | OK | Copper |
| cftc | cot_crude_oil_wti | weekly | 2010-01-05..2026-04-07 | data/clean/sentiment/cot_crude_oil_wti.parquet | OK | WTI Crude Oil |
| cftc | cot_gold | weekly | 2010-01-05..2026-04-07 | data/clean/sentiment/cot_gold.parquet | OK | Gold |
| cftc | cot_nasdaq_emini | weekly | 2010-07-20..2026-04-07 | data/clean/sentiment/cot_nasdaq_emini.parquet | OK | Nasdaq 100 E-mini |
| cftc | cot_silver | weekly | 2010-01-05..2026-04-07 | data/clean/sentiment/cot_silver.parquet | OK | Silver |
| cftc | cot_sp500_emini | weekly | 2010-07-20..2026-04-07 | data/clean/sentiment/cot_sp500_emini.parquet | OK | S&P 500 E-mini |
| cftc | cot_usd_index | weekly | 2010-07-20..2026-04-07 | data/clean/sentiment/cot_usd_index.parquet | OK | USD Index |
| cftc | cot_ust_10y | weekly | 2010-07-20..2026-04-07 | data/clean/sentiment/cot_ust_10y.parquet | OK | UST 10Y Note |
| reconstructed | fear_greed_reconstructed | daily | 2000-03-28..2026-04-10 | data/clean/sentiment/fear_greed_reconstructed.parquet | OK | 6-component reconstruction; pearson_vs_cnn=0.875 |
| openinsider | insider_transactions | daily | 2025-06-27..2026-04-08 | data/clean/sentiment/insider_transactions.parquet | OK | buy/sell counts, dollar value, 21d sentiment from openinsider screener |
| fred | BOGZ1FL663067003Q | quarterly | 2000-01-03..2025-10-01 | data/clean/sentiment/margin_debt_fred.parquet | OK | margin debt; substitute for FINRA (Akamai-blocked) |
| naaim | naaim_exposure | weekly | 2006-07-05..2026-04-08 | data/clean/sentiment/naaim_exposure.parquet | OK | NAAIM mean active-manager exposure (weekly) |
| news_vader | news_sentiment_crypto | daily | 2026-03-30..2026-04-10 | data/clean/sentiment/news_sentiment_crypto.parquet | OK | VADER crypto-topic daily headline sentiment |
| news_vader | news_sentiment_energy | daily | 2026-01-12..2026-04-10 | data/clean/sentiment/news_sentiment_energy.parquet | OK | VADER energy-topic daily headline sentiment |
| news_vader | news_sentiment_gold | daily | 2025-12-16..2026-04-10 | data/clean/sentiment/news_sentiment_gold.parquet | OK | VADER gold-topic daily headline sentiment |
| news_vader | news_sentiment_housing | daily | 2025-07-16..2026-04-10 | data/clean/sentiment/news_sentiment_housing.parquet | OK | VADER housing-topic daily headline sentiment |
| news_vader | news_sentiment_inflation | daily | 2024-07-31..2026-04-10 | data/clean/sentiment/news_sentiment_inflation.parquet | OK | VADER inflation-topic daily headline sentiment |
| news_vader | news_sentiment_market | daily | 2024-07-19..2026-04-10 | data/clean/sentiment/news_sentiment_market.parquet | OK | VADER market-topic daily headline sentiment |
| news_vader | news_sentiment_overall | daily | 2024-02-13..2026-04-10 | data/clean/sentiment/news_sentiment_overall.parquet | OK | VADER overall daily headline sentiment |
| news_vader | news_sentiment_recession | daily | 2025-11-13..2026-04-10 | data/clean/sentiment/news_sentiment_recession.parquet | OK | VADER recession-topic daily headline sentiment |
| news_vader | news_sentiment_tech | daily | 2024-09-12..2026-04-10 | data/clean/sentiment/news_sentiment_tech.parquet | OK | VADER tech-topic daily headline sentiment |
| finra | short_interest | daily | 2023-01-03..2026-04-10 | data/clean/sentiment/short_interest.parquet | OK | market-wide Reg SHO daily short volume aggregate |
| news_vader | news_sentiment_overall | daily | 2010-01-04..2026-04-10 | data/clean/sentiment/news_sentiment_overall.parquet | OK | VADER overall daily headline sentiment |
| news_vader | news_sentiment_tech | daily | 2010-01-21..2026-04-10 | data/clean/sentiment/news_sentiment_tech.parquet | OK | VADER tech-topic daily headline sentiment |
| news_vader | news_sentiment_energy | daily | 2010-01-04..2026-04-10 | data/clean/sentiment/news_sentiment_energy.parquet | OK | VADER energy-topic daily headline sentiment |
| news_vader | news_sentiment_inflation | daily | 2010-01-04..2026-04-10 | data/clean/sentiment/news_sentiment_inflation.parquet | OK | VADER inflation-topic daily headline sentiment |
| news_vader | news_sentiment_recession | daily | 2010-01-11..2026-04-10 | data/clean/sentiment/news_sentiment_recession.parquet | OK | VADER recession-topic daily headline sentiment |
| news_vader | news_sentiment_market | daily | 2010-01-04..2026-04-10 | data/clean/sentiment/news_sentiment_market.parquet | OK | VADER market-topic daily headline sentiment |
| news_vader | news_sentiment_gold | daily | 2010-01-05..2026-04-10 | data/clean/sentiment/news_sentiment_gold.parquet | OK | VADER gold-topic daily headline sentiment |
| news_vader | news_sentiment_housing | daily | 2010-01-04..2026-04-10 | data/clean/sentiment/news_sentiment_housing.parquet | OK | VADER housing-topic daily headline sentiment |
| news_vader | news_sentiment_crypto | daily | 2013-03-14..2026-04-10 | data/clean/sentiment/news_sentiment_crypto.parquet | OK | VADER crypto-topic daily headline sentiment |
| news_vader | news_sentiment_overall | daily | 2010-01-04..2026-04-10 | data/clean/sentiment/news_sentiment_overall.parquet | OK | VADER overall daily headline sentiment |
| news_vader | news_sentiment_tech | daily | 2010-01-21..2026-04-10 | data/clean/sentiment/news_sentiment_tech.parquet | OK | VADER tech-topic daily headline sentiment |
| news_vader | news_sentiment_energy | daily | 2010-01-04..2026-04-10 | data/clean/sentiment/news_sentiment_energy.parquet | OK | VADER energy-topic daily headline sentiment |
| news_vader | news_sentiment_inflation | daily | 2010-01-04..2026-04-10 | data/clean/sentiment/news_sentiment_inflation.parquet | OK | VADER inflation-topic daily headline sentiment |
| news_vader | news_sentiment_recession | daily | 2010-01-11..2026-04-10 | data/clean/sentiment/news_sentiment_recession.parquet | OK | VADER recession-topic daily headline sentiment |
| news_vader | news_sentiment_market | daily | 2010-01-04..2026-04-10 | data/clean/sentiment/news_sentiment_market.parquet | OK | VADER market-topic daily headline sentiment |
| news_vader | news_sentiment_gold | daily | 2010-01-05..2026-04-10 | data/clean/sentiment/news_sentiment_gold.parquet | OK | VADER gold-topic daily headline sentiment |
| news_vader | news_sentiment_housing | daily | 2010-01-04..2026-04-10 | data/clean/sentiment/news_sentiment_housing.parquet | OK | VADER housing-topic daily headline sentiment |
| news_vader | news_sentiment_crypto | daily | 2013-03-14..2026-04-10 | data/clean/sentiment/news_sentiment_crypto.parquet | OK | VADER crypto-topic daily headline sentiment |
| cboe | putcall_total | daily | 2003-10-17..2019-10-04 | data/clean/sentiment/cboe_putcall_total.parquet | OK | cdn.cboe.com with Referer header |
| cboe | putcall_equity | daily | 2003-10-17..2019-10-04 | data/clean/sentiment/cboe_putcall_equity.parquet | OK | cdn.cboe.com with Referer header |
| cboe | putcall_index | daily | 2003-10-17..2019-10-04 | data/clean/sentiment/cboe_putcall_index.parquet | OK | cdn.cboe.com with Referer header |
| fred | BOGZ1FA106121075Q | quarterly | 1946-10-01..2025-10-01 | data/clean/fundamental/sp500_buyback_yield.parquet | OK | proxy for SP500 buyback yield; aggregate US nonfinancial corp net equity issuance |
| fred | RAILFRTCARLOADSD11 | monthly | 2000-01-03..2025-12-31 | data/clean/alternative/rail_traffic.parquet | OK | substitute for AAR weekly rail (AAR is PDF-only) |
| fred | NCBDBIQ027S | quarterly | 1945-10-01..2025-10-01 | data/clean/fundamental/corp_bond_issuance.parquet | OK | substitute for SIFMA corp bond issuance (HubSpot form-gated); Z.1 net flow |
| fred | DRBLACBS | quarterly | 1987-01-02..2025-10-01 | data/clean/alternative/bankruptcy_filings.parquet | OK | proxy for bankruptcy filings; BLS/ABI bankruptcy counts not free-downloadable |
| cboe+proxy | putcall_total_spliced | daily | 2003-10-17..2026-04-10 | data/clean/sentiment/cboe_putcall_total_spliced.parquet | OK | splice_date=2019-10-04 R2=0.248 regressors=+spy |
| cboe+proxy | putcall_equity_spliced | daily | 2003-10-17..2026-04-10 | data/clean/sentiment/cboe_putcall_equity_spliced.parquet | OK | splice_date=2019-10-04 R2=0.347 regressors=+spy |
| cboe+proxy | putcall_index_spliced | n/a | dropped | - | DROPPED | R2=0.022 on overlap; VIX/SPY do not explain index PCR. Use real 2003-2019 file only. |
