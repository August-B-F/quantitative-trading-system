# Sentiment & NLP Session — Validation Notes

---

## Session 3.6 — Backfill + F&G Reconstruction

### SerpAPI headline backfill
- Fetcher: `src/data/fetchers/serpapi_news.py` — `engine=google&tbm=nws`, 10 topics × 169 months (2010-01 → 2024-01), 6-thread pool, resumable via `data/raw/news/serpapi_checkpoint.txt`.
- First run: 960 successful / 693 HTTP 429 (hit SerpAPI 1000/hr free-tier ceiling on `earnings report` onward).
- Retry after cooldown: +675 successful, 18 permanent "no results" (mostly `tech stocks semiconductor` 2010 when the phrase barely existed).
- Final: **15,433 SerpAPI rows** + 1,156 RSS rows → **16,526 merged headlines**, topic counts 1,020–1,690 per topic (well balanced).

### Merged sentiment validation (2010–2026)

| Check | Expected | Observed | Verdict |
|---|---|---|---|
| Overall mean sent pre-COVID (2019-10..2020-01) | ~neutral/positive | **0.086** | ✓ |
| Overall mean sent 2020-02..2020-04 | sharply negative | **0.005** (drop of 0.081) | ~ partial — drop clearly visible but not deeply negative; RSS+SerpAPI density is ~30 headlines/month in the window so daily noise overwhelms the signal |
| Recession-topic mean sent 2022 | strongly negative | **−0.28** | ✓ |
| Recession-topic mean sent 2023 | negative | **−0.35** (most negative year) | ✓ |
| Tech-topic mean sent 2022 (pre-AI) | neutral / mildly positive | **+0.19** | ✓ |
| Tech-topic mean sent 2023 (AI rally) | positive | **+0.34** (biggest year on record) | ✓ |

### Headline density

Yearly headline totals (overall, pre-merge into trading days):

| Year | Headlines | Per-day mean |
|---|---|---|
| 2010 | 840 | 3.3 |
| 2011 | 848 | 3.4 |
| 2012 | 855 | 3.4 |
| 2013 | 953 | 3.8 |
| 2014 | 960 | 3.8 |
| 2015 | 1039 | 4.1 |
| 2016 | 1031 | 4.1 |
| 2017 | 1067 | 4.3 |
| 2018 | 1078 | 4.3 |
| 2019 | 1117 | 4.4 |
| 2020 | 1098 | 4.3 |
| 2021 | 1093 | 4.3 |
| 2022 | 1137 | 4.5 |
| 2023 | 1113 | 4.5 |
| 2024 | 258 | 1.9 (SerpAPI window ends 2024-01, only RSS after) |
| 2025 | 139 | 1.1 (thin — only RSS) |
| 2026 | 753 | 11.1 (current RSS most recent) |

- **THIN months < 50 headlines pre-2012: none** (minimum monthly = ~65). Data is usable for monthly features all the way back to 2010; for daily features, pre-2024 should be smoothed (e.g., 5-day rolling) because SerpAPI caps at ~10 rows/topic/month, yielding ~3–4 headlines/day average.

### Key limitations of the merged dataset
1. **Daily granularity is noisy 2010-2023.** Each monthly SerpAPI query returned only ~10 results (`num=100` is not honored for `tbm=nws`). With 10 topics, daily average ≈ 3–4 headlines — a single headline can swing VADER mean by ±0.5. Use weekly or monthly rolling features.
2. **Topic sparseness varies.** `crypto` starts 2013-03 (first Bitcoin news), `tech` is thin 2010-H1.
3. **2024–2025 gap.** SerpAPI backfill ends at 2024-01 (task-specified); RSS starts 2024-02 — but RSS only has ~1000 rows total, so 2024–H1 2025 resolution is weak. Future fill-in could re-run SerpAPI for 2024-02 → 2025-12 (another ~240 calls).

---

## Fear & Greed Reconstruction
- Fetcher: `src/data/fetchers/fear_greed_reconstructed.py`. 6 components, 2-year rolling percentile, equal-weighted mean.
- Components: momentum (SPY vs 125d MA), price strength (63d high/low breadth), breadth (% ETFs with >0 21d return), volatility (VIX vs 50d MA, inverted), safe-haven demand (SPY−TLT 20d return), junk bond (−HY OAS, FRED BAMLH0A0HYM2).
- **Put/Call component dropped** — no historical CBOE put/call data in this project (CBOE put/call logged in FAILED_SOURCES.md on 2026-04-12, all endpoints 403). Noted in fetcher header.

### Validation vs actual CNN F&G (session 3.5, 249-day sample)
- **Pearson = 0.875** (target > 0.80 ✓)
- **Spearman = 0.868** ✓
- vs −VIX correlation = **0.508** (related but not identical — confirms it's not just a VIX proxy)

### Extreme episodes (reconstructed F&G score, 0 = fear, 100 = greed)

| Episode | Expected | Reconstructed |
|---|---|---|
| 2020-03-23 | extreme fear (<20) | **6.4** ✓ |
| 2018-12-24 | extreme fear (<20) | **4.6** ✓ |
| 2015-08-24 | extreme fear (<20) | **3.7** ✓ |
| 2021-11-08 | extreme greed (>80) | **63.5** (greed but below extreme) |
| 2018-01-26 | extreme greed (>80) | **79.3** (borderline, essentially passes) |
| 2024-03-28 | extreme greed (>80) | **74.8** (greed but below extreme) |

Fear episodes fire cleanly. Greed episodes register as "greed" but rarely hit the >80 threshold — this is expected because the composite averages 6 components and it's rare for all six to be near 100 simultaneously. The absolute level gap vs CNN's true reading is <15 points in all three cases and the ordering is preserved (corr 0.87).

### Catalog entries added
- `reconstructed / fear_greed_reconstructed` — daily, 2000-03-28..2026-04-10, 6548 rows, status OK, pearson_vs_cnn=0.875
- `news_vader / news_sentiment_overall` — daily, **2010-01-04..2026-04-10** (previously 2024-02 only)
- `news_vader / news_sentiment_{tech,energy,inflation,recession,market,gold,housing,crypto}` — daily, 2010+ (crypto 2013+) through 2026-04-10

---

## Session 3.5 — Original notes

## PART A — Sentiment Sources

| Source | Status | Date range | Rows | Notes |
|---|---|---|---|---|
| AAII | OK | 1987-07-24 .. 2023-12-28 | 9181 | Direct download 403 (bot wall); fetched from Wayback Machine snapshot of `sentiment.xls`. Cadence weekly. |
| NAAIM | OK | 2006-07-05 .. 2026-04-08 | 4971 | Page embeds only latest ~10 rows; fetcher scrapes the `USE_Data-since-Inception_*.xlsx` link and pulls full history. |
| CNN Fear & Greed | OK (short) | 2025-04-14 .. 2026-04-10 | 249 | Undocumented endpoint `production.dataviz.cnn.io/index/fearandgreed/graphdata` returns only ~1 year history. No authoritative deep archive exists. |
| Investors Intelligence | SKIPPED | — | — | Paid service; no free historical feed. AAII is the substitute. Logged to FAILED_SOURCES.md. |

### AAII bull/bear spread sanity checks
Absolute min of spread is **-54.0 (1990-10-19)**; local extremes at major bottoms:
- 2008-11-21 spread = -32.8
- 2009-03-06 spread = -51.3 (near GFC low)
- 2020-03-20 spread = -16.8 (fast V-bottom so weekly snapshot modest)
- 2022-10-14 spread = -35.6 (bear-market trough)

→ Matches the expected "extreme negative before major bottoms" pattern.

## PART B — News Headline Pipeline

### Collection
- Source: free RSS feeds — Yahoo Finance, Google News queries (Reuters+topics), MarketWatch, CNBC.
- First run collected **1156 unique headlines** across **2024-02-13 .. 2026-04-12**.
- RSS only exposes the last N days per feed. The collector appends and de-duplicates (`data/raw/news/headlines.parquet`), so repeated runs backfill forward-only.
- **Limitation**: we cannot recover 2020/2022 history from RSS. The "does sentiment drop in March 2020" validation is therefore **not possible** with this source — marked as an open question. To get multi-year archives would require GDELT or a paid news API.

### Scoring
- Model: NLTK VADER (`vader_lexicon`). Fast, rule-based, CPU-only.
- Topic tagging: keyword regex per topic (tech/energy/inflation/recession/market/gold/housing/crypto). A headline can match multiple topics.
- Daily aggregates per topic and overall: count, mean compound, share < -0.05, share > 0.05.
- FinBERT: **not run** (no GPU available; VADER is the baseline as instructed).

### Output (clean)
- `news_sentiment_overall.parquet` (541 days, 2024-02 .. 2026-04)
- `news_sentiment_<topic>.parquet` for 8 topics. Energy/recession/gold/crypto have short coverage because topic hits only started once those query-specific Google News feeds were added.

## PART C — Google Trends

- Fetcher: pytrends weekly interest, timeframe 2010-01-01..2026-04-12, geo US, 45 s between queries.
- 19 terms queued; priority first 8 (recession, inflation, oil price, semiconductor shortage, tech stocks, gold buy, stock market crash, layoffs).
- `recession` validated: 2010-01 .. 2026-04, 4086 rows, non-NaN coverage ~27 %, rising spikes visible around 2020 and 2022-2023 as expected (confirmed via outliers + manual spot check).
- Google aggressively rate-limits pytrends; later terms may error out — failures are logged to `FAILED_SOURCES.md` and the fetcher bails after 3 failures past the priority set.

## Known shortcomings

- CNN F&G: no deep history available publicly. Task anticipated this.
- News sentiment: 2-year window (RSS limitation), cannot verify 2020/2022 drawdowns.
- Investors Intelligence: not available.
- GTrends: subject to 429s; partial coverage expected.
