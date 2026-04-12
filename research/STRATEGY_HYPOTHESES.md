# Strategy Improvement Hypotheses

**Baseline:** 100% allocation to best 63-day return among {SOXX, QQQ, XLK, VGT, IGV, XLE, GLD, SHY}. Monthly rebalance. 23.0% CAGR vs SPY 14.2%, 2018-2025. Zero negative years.

**Ground rules:** Every hypothesis must be walk-forward testable on available data. Estimated impacts are net of decay haircut (30-50% per McLean & Pontiff 2016). "What it breaks" is mandatory — there is no free lunch.

---

## LOOKBACK & SCORING

### S01: Multi-Period Blended Momentum (VAA-Style)

- **ID:** S01
- **Name:** Replace 63-day return with weighted multi-period momentum score
- **Mechanism:** A single lookback window creates a binary fragility: either the window contains the crash or it doesn't. Blending multiple windows (1m, 3m, 6m, 12m) smooths the signal because short windows recover fast after V-bottoms while long windows provide stability in trends. Keller & Keuning (2017) show this reduces drawdowns by 20-30% vs single-lookback in TAA systems. The weighting scheme `12*R(1m) + 4*R(3m) + 2*R(6m) + 1*R(12m)` overweights recent returns ~40%, allowing faster recovery from crashes without abandoning the medium-term trend signal.
- **Rule change:** Replace `score = R(63d)` with `score = 12*R(21d) + 4*R(63d) + 2*R(126d) + 1*R(252d)`. Rank ETFs by this blended score. Hold top-1 as before. Rebalance monthly.
- **Data needed:** Daily adjusted close prices for all 8 ETFs going back to at least 2017 (252 trading days before Jan 2018). Already in `/data/` — the backtest engine pulls from yfinance or local cache with sufficient history.
- **What it fixes:** W-1.1 (momentum crashes after V-recoveries) and the 2019 problem specifically. In Jan 2019, the 21-day return for QQQ would have turned positive by ~Jan 18, pulling the blended score positive weeks before the 63-day window cleared. Estimated recovery of 8-12% of the 19.5% gap (STRATEGY_WEAKNESSES.md §3.2).
- **What it breaks:** In strong medium-term trends (2022 XLE run), the 12m component dilutes the signal with pre-trend returns, potentially delaying entry by 1-2 weeks vs the current 63-day window. Also adds sensitivity to short-term noise via the 21-day component — a 2-week whipsaw that the current 63-day window ignores could trigger a false rotation.
- **Estimated CAGR impact:** +1-3% CAGR (primarily from recovering 2019-like scenarios; partially offset by slightly later entry in trending years)
- **Walk-forward testable:** Yes
- **Priority:** P1

---

### S02: Volatility-Adjusted Momentum

- **ID:** S02
- **Name:** Rank ETFs by return/realized-vol instead of raw return
- **Mechanism:** Raw 63-day return conflates genuine trend strength with volatility. XLE might have +20% 63-day return with 35% annualized vol (Sharpe ~0.57) while QQQ has +15% with 20% vol (Sharpe ~0.75). The raw signal picks XLE, but QQQ offers better risk-adjusted momentum. van Zundert (2018) shows volatility-adjusted momentum reduces drawdowns by 15-25% with minimal CAGR sacrifice because high-vol winners are disproportionately likely to revert — they are noisy, not trending.
- **Rule change:** Replace `score = R(63d)` with `score = R(63d) / sigma(63d)` where `sigma(63d)` is the annualized realized volatility computed from daily returns over the same 63-day window. Rank and hold top-1.
- **Data needed:** Same daily price data already in `/data/`. Realized vol computed from daily returns — no new data source required.
- **What it fixes:** W-5.6 (no position sizing intelligence) — this is the ranking equivalent of risk-adjusting. Also partially addresses W-1.3 (momentum crowding) because when all 5 tech ETFs have similar returns, the vol-adjustment will differentiate them meaningfully (SOXX is structurally higher vol than QQQ). Additionally helps with W-4.2 (concentration whipsaw) since vol-adjustment dampens noisy high-vol leaders that are likely to revert.
- **What it breaks:** In a genuine high-vol breakout (XLE Feb-Mar 2022 invasion amplification), vol-adjustment penalizes the strongest signal. XLE's 39.4% 63-day return in March 2022 came with ~45% annualized vol — the vol-adjusted score would be lower, potentially losing to a tech ETF with a moderate trend and low vol. Could delay entry to genuine regime shifts by 1-2 months.
- **Estimated CAGR impact:** +0.5-2% CAGR (mainly from avoiding bad rotations into volatile leaders that revert; partially offset by slower entry to genuine high-vol trends)
- **Walk-forward testable:** Yes
- **Priority:** P1

---

### S03: Rolling Sharpe Ranking

- **ID:** S03
- **Name:** Rank ETFs by rolling 63-day Sharpe ratio instead of raw return
- **Mechanism:** Similar to S02 but uses excess return over risk-free rate, making the ranking formally correct as a risk-adjusted measure. When SHY yields 4-5% (as in 2023-2024), a tech ETF needs meaningfully positive returns to beat cash on a Sharpe basis. This creates an implicit absolute momentum filter — ETFs with positive but weak returns relative to cash get penalized. Moskowitz, Ooi & Pedersen (2012) use volatility-scaled returns as the core TSMOM signal precisely because it normalizes across asset classes with different vol profiles.
- **Rule change:** `score = (R(63d) - R_f(63d)) / sigma(63d)` where `R_f` is the cumulative 3-month T-bill return over the same window. Rank and hold top-1.
- **Data needed:** Daily prices (in `/data/`) plus 3-month T-bill rate (^IRX from yfinance, or FRED DGS3MO). T-bill data needs collecting — trivial via yfinance or FRED API, one download.
- **What it fixes:** Same as S02, plus adds an implicit absolute momentum gate that addresses W-1.2 (whipsaw in trendless markets). When all ETFs have negative Sharpe, the ranking naturally favors SHY (whose Sharpe is ~0 by definition), creating an automatic risk-off signal without a separate absolute momentum filter.
- **What it breaks:** Same as S02 — penalizes high-vol breakouts. Additionally, in rising-rate environments, the risk-free hurdle gets higher, making the strategy more conservative than intended. In 2022 H2 when rates were surging, the T-bill hurdle would have been rising, potentially keeping the strategy in SHY too long.
- **Estimated CAGR impact:** +0.5-2% CAGR (overlaps heavily with S02; test both and pick the better performer)
- **Walk-forward testable:** Yes
- **Priority:** P1

---

### S04: Momentum Acceleration Signal

- **ID:** S04
- **Name:** Second derivative of momentum — is the trend strengthening or fading?
- **Mechanism:** A 63-day return of +15% could mean the asset gained 15% steadily, or gained 25% in the first month and lost 10% in the last two. The first case is strong momentum; the second is decelerating momentum likely to revert. Da, Gurun & Warachka (2014) show that "continuous" momentum (many small same-sign returns) is far more persistent than "discrete" momentum (few large jumps). Acceleration = R(21d) - R(21d, lagged 42d). Positive acceleration means the trend is strengthening; negative means it's fading.
- **Rule change:** Compute `accel = R(21d) - R_lagged(21d, offset=42d)` for each ETF. Use as a secondary filter: among ETFs with top-3 momentum scores, prefer the one with highest acceleration. Alternatively, use `composite = 0.7*R(63d) + 0.3*accel_z` where accel_z is the z-scored acceleration signal.
- **Data needed:** Daily prices already in `/data/`. Pure computation on existing data.
- **What it fixes:** W-1.4 (slow regime transitions / boiling frog). Detects fading momentum before the 63-day window fully reflects the decline. Also partially addresses the December 2021 false rotation from XLE to SOXX — XLE's acceleration was positive (trend strengthening) while SOXX had a sharp but decelerating spike.
- **What it breaks:** Acceleration is inherently noisy — it's a second derivative of a noisy time series. In steady trends (the strategy's bread and butter), acceleration hovers near zero and adds noise without information. Could cause premature exits from linear trends where the asset is gaining steadily but not accelerating. Overfitting risk is high since the signal-to-noise ratio of acceleration is much lower than raw momentum.
- **Estimated CAGR impact:** +0-1.5% CAGR (high variance; likely adds value mainly as a filter to avoid fading leaders, not as a primary signal)
- **Walk-forward testable:** Yes
- **Priority:** P1

---

## UNIVERSE

### S05: Add TLT (Long-Duration Treasuries)

- **ID:** S05
- **Name:** Add TLT as a deflationary crash / flight-to-quality weapon
- **Mechanism:** SHY gains 1-3% in a crisis. TLT gained +33% in 2008, +18% in March 2020 (first 2 weeks), and +14% in 2019 as rates were cut. The strategy currently has zero access to the single most powerful crisis alpha asset. In deflationary crashes (2008, COVID initial shock), long bonds are negatively correlated with equities at precisely the moment diversification matters most. This is a structural feature of nominal bonds, not a backtest artifact — central banks cut rates in crises, driving long bond prices up.
- **Rule change:** Add TLT to the universe: {SOXX, QQQ, XLK, VGT, IGV, XLE, GLD, SHY, **TLT**}. TLT competes for allocation on the same momentum score as everything else. No special treatment.
- **Data needed:** TLT daily prices from yfinance. TLT has traded since July 2002 — ample history. Not currently in `/data/`; needs one yfinance download.
- **What it fixes:** W-5.2 (no bond duration exposure). In 2019, TLT returned +14.1%. The strategy missed this because SHY only returned +3.5%. If TLT had ranked #1 in mid-2019 (rate cut expectations), the strategy would have captured much of TLT's run instead of being stuck in SHY. Directly addresses the gap where the strategy has no access to the biggest crisis alpha asset class.
- **What it breaks:** TLT is a double-edged sword. In rising rate environments (2022: TLT -31.2%), TLT's 63-day momentum goes deeply negative, which is fine — the ranking system avoids it. But the risk is a whipsaw: TLT surges in a brief risk-off event, ranks #1, strategy rotates in, then rates resume rising and TLT crashes. This happened in Jan 2023 — TLT rallied 10% on Fed pivot hopes then gave it all back. Adding a volatile defensive asset increases whipsaw frequency by ~1-2 rotations/year.
- **Estimated CAGR impact:** +1-3% CAGR (mainly from capturing deflationary rallies and rate-cut cycles that the strategy currently misses entirely; partially offset by occasional TLT whipsaws)
- **Walk-forward testable:** Yes
- **Priority:** P2

---

### S06: Add Broad Commodity Exposure (DBC or PDBC)

- **ID:** S06
- **Name:** Add a diversified commodity ETF for inflation diversification
- **Mechanism:** XLE provides energy exposure but not broad commodity exposure. In stagflation (rising inflation + weak growth), agriculture, metals, and energy all outperform but in different sequences. DBC holds energy (60%), agriculture (22%), metals (12%), precious metals (6%). Its correlation to XLE is ~0.75 — similar but not identical. Adding DBC provides a second inflation-sensitive option that captures commodity supercycles that aren't purely energy-driven (e.g., 2021 agriculture boom: corn +25%, soybeans +18%). Asness, Moskowitz & Pedersen (2013) show momentum works across commodity classes.
- **Rule change:** Add DBC to the universe: {SOXX, QQQ, XLK, VGT, IGV, XLE, GLD, SHY, **DBC**}. Or use PDBC (Invesco Optimum Yield) which avoids K-1 tax forms. Same momentum ranking as all other ETFs.
- **Data needed:** DBC daily prices from yfinance. DBC has traded since Feb 2006. Not in `/data/`; needs download. PDBC since Nov 2014 — shorter history but still covers backtest period.
- **What it fixes:** W-5.3 (no inflation hedge diversity). Currently the strategy's only inflation play is XLE. In a commodity supercycle where energy lags (e.g., 2021 agriculture), the strategy has no way to participate. DBC also provides partial exposure to precious metals, overlapping with GLD but through a different mechanism (commodity futures vs physical gold).
- **What it breaks:** DBC has structural negative roll yield due to contango in commodity futures — it loses ~2-4% annually to futures rolling costs even when spot prices are flat. This means DBC needs a stronger trend to rank #1 vs equity ETFs. In practice, DBC ranks highly only in strong commodity trends, which limits its utility as a diversifier in normal markets. Also increases universe size, marginally increasing the probability of a noisy ranking picking a suboptimal asset.
- **Estimated CAGR impact:** +0.5-1.5% CAGR (value comes mainly from catching non-energy commodity trends that the strategy currently misses; drag from contango limits upside)
- **Walk-forward testable:** Yes
- **Priority:** P2

---

### S07: Reduce Tech Overlap — Drop XLK/VGT/IGV, Add XLF/XLI/XLV

- **ID:** S07
- **Name:** Replace overlapping tech ETFs with sector diversification
- **Mechanism:** SOXX, QQQ, XLK, VGT, and IGV share enormous overlap in mega-cap tech (AAPL, MSFT, NVDA appear in all five). MECHANISM_ANALYSIS.md §Q4 and STRATEGY_WEAKNESSES.md §5.1 identify this as a key structural vulnerability — it's 5 flavors of the same bet. Replacing XLK/VGT/IGV with XLF (financials), XLI (industrials), and XLV (healthcare) creates genuine sector diversification. These three sectors have low correlation to tech and each responds to different macro regimes: XLF to yield curve steepening, XLI to PMI expansion, XLV to defensive demand. The revised universe covers 6 of the 11 GICS sectors instead of 3.
- **Rule change:** Universe becomes {SOXX, QQQ, **XLF, XLI, XLV**, XLE, GLD, SHY}. Same 8 ETFs, same ranking logic. SOXX stays because semiconductors are sufficiently differentiated from broad tech (more cyclical, supply-chain driven). QQQ stays as the broad growth proxy.
- **Data needed:** XLF, XLI, XLV daily prices from yfinance. All three are SPDR sector ETFs trading since 1998 — ample history. Not in `/data/`; need download.
- **What it fixes:** W-5.1 (universe concentration risk). The current strategy is effectively a 3-sector system (tech/energy/safe haven). The revised universe is a 6-sector system with genuinely different macro sensitivities. In a tech regime change (rate shock, regulation, AI bust), the strategy currently has nowhere to go except XLE/GLD/SHY. With XLF/XLI/XLV, the strategy gains access to late-cycle plays (financials in 2016-2018), early-cycle plays (industrials in recovery), and defensive growth (healthcare in slowdowns).
- **What it breaks:** Backtest CAGR will almost certainly drop. XLK, VGT, and IGV were included because they captured the AI/semiconductor boom 2018-2025. Replacing them with financials, industrials, and healthcare removes the strategy's ability to make leveraged bets on the single strongest trend of the backtest period. In years like 2023-2024 where tech dominance was extreme, having only SOXX+QQQ instead of 5 tech ETFs reduces the probability of holding the best-performing tech variant. The strategy will look worse in backtests but be more robust forward.
- **Estimated CAGR impact:** -1 to +2% CAGR (likely negative in backtest due to reduced tech concentration in a tech-dominant period; positive forward as it improves robustness to regime changes)
- **Walk-forward testable:** Yes
- **Priority:** P2

---

### S08: Canary Universe Crash Detection

- **ID:** S08
- **Name:** Use EEM + AGG momentum as a market-wide risk gate
- **Mechanism:** Keller (2018 DAA) shows that emerging markets (EEM) and aggregate bonds (AGG) act as "canary" assets — their momentum deteriorates 1-2 months before US equity momentum does, because EM and credit are more sensitive to global risk appetite and dollar strength. When both EEM and AGG have negative 63-day momentum, it's a strong signal of global risk-off. The strategy should de-risk regardless of what the US ETF rankings say. This works because global capital flows hit EM and credit first (most risk-sensitive), then propagate to US sectors.
- **Rule change:** Compute `canary_score = R(EEM, 63d) + R(AGG, 63d)`. If both are negative (both EEM and AGG have negative 63-day returns), override the ranking and allocate 100% SHY. If only one is negative, allocate to top-ranked ETF but from defensive subset only {GLD, SHY, TLT if added}. If both positive, rank and allocate normally.
- **Data needed:** EEM and AGG daily prices from yfinance. Both trade since 2003+. Not in `/data/`; need download. These are used only as signals, not held.
- **What it fixes:** W-1.1 (momentum crashes). The canary signal would have fired a warning in Q4 2018 (EEM was negative before US tech), catching the crash 2-4 weeks earlier. Also addresses W-1.4 (boiling frog) — global deterioration shows up in EM/credit before it shows up in US sector momentum. Provides the "early warning" system that STRATEGY_WEAKNESSES.md §2 identifies as a key gap.
- **What it breaks:** False positives. EM and bond momentum can go negative during US-centric rallies (e.g., dollar strength hurts EEM without implying US risk; rising rates hurt AGG without implying equity risk). In 2022 H1, AGG was deeply negative (rate hikes) while XLE was surging — the canary gate would have forced the strategy out of its best trade. Need to calibrate: the gate should override only for "both negative simultaneously," not for one asset. Even then, ~1-2 false positives per year are likely, each costing 2-4% in missed equity returns.
- **Estimated CAGR impact:** +0.5-2% CAGR (mainly from catching 1-2 major drawdowns per decade earlier; partially offset by false positives forcing premature de-risking)
- **Walk-forward testable:** Yes
- **Priority:** P2

---

## POSITION SIZING

### S09: Top-2 Equal Weight

- **ID:** S09
- **Name:** Hold top-2 ranked ETFs at 50% each instead of 100% top-1
- **Mechanism:** 100% concentration means every rotation error costs the maximum amount. Holding top-2 halves the cost of the #1 pick being wrong while keeping the strategy invested in the strongest trends. Diversification across the top-2 is not naive — in a trending market, the #1 and #2 ranked ETFs are usually in the same regime (both tech, or tech + semis), so you maintain regime exposure. In transitional markets, #1 might be the new leader and #2 the old leader — the split provides a natural hedge during transitions. The December 2021 false rotation (XLE → SOXX for one month) would have been halved in cost since XLE was #2.
- **Rule change:** Allocate 50% to rank-1 ETF, 50% to rank-2 ETF. Rebalance monthly. If rank-1 and rank-2 are the same sector (both tech), option to take rank-3 instead for diversification (variant S09b).
- **Data needed:** Same data already used. No new data required.
- **What it fixes:** W-4.2 (concentration whipsaw) — halves the cost of each wrong rotation. W-5.6 (no position sizing intelligence) — moves from binary to graduated. Also reduces tracking error vs SPY by ~30%, addressing the 2019 problem: in Jan 2019, #1 was GLD (+3%) but #2 was likely IGV or QQQ — the 50/50 split would have captured half the growth recovery.
- **What it breaks:** In strong trending years (2021: SOXX +43%, 2022: XLE +53%), the #2 position dilutes returns. The strategy's best year (2021: +39%) would likely have been +30-35% with top-2 allocation since #2 was typically a slightly weaker tech ETF. The 23% CAGR would compress to ~20-21%. This is the fundamental cost of diversification — you reduce extremes on both sides.
- **Estimated CAGR impact:** -1 to -2% CAGR (raw return sacrifice from dilution; offset by ~30% reduction in max drawdown and lower tracking error)
- **Walk-forward testable:** Yes
- **Priority:** P1

---

### S10: Top-3 Inverse-Volatility Weighted

- **ID:** S10
- **Name:** Hold top-3 ETFs weighted inversely to their realized volatility
- **Mechanism:** Inverse-vol weighting equalizes risk contribution: a high-vol ETF (SOXX, ~28% annual vol) gets a smaller weight than a low-vol one (SHY, ~3%). Butler, Philbrick & Gordillo (2012) show that inverse-vol across asset classes delivers comparable returns to equal-weight with 25-35% lower drawdowns. Combined with top-3 selection, this creates a concentrated but risk-balanced portfolio. SOXX at 20% weight + QQQ at 35% weight + GLD at 45% weight is a very different risk profile than SOXX at 33% each.
- **Rule change:** Select top-3 ETFs by momentum score. Compute 63-day realized vol for each. Weight: `w_i = (1/sigma_i) / sum(1/sigma_j)`. Rebalance monthly. If any weight exceeds 60%, cap it and redistribute proportionally.
- **Data needed:** Same daily price data in `/data/`. No new data required.
- **What it fixes:** W-5.6 (no position sizing intelligence) and W-4.2 (concentration whipsaw). The inverse-vol weighting means the strategy naturally takes smaller positions in the noisiest ETFs (which are the most likely to whipsaw) and larger positions in smooth trends. This is mathematically equivalent to equalizing risk, which is the minimal sensible position sizing rule.
- **What it breaks:** In momentum breakouts, the highest-conviction/strongest-return ETF is often also the highest-vol one (XLE in 2022: highest return AND highest vol). Inverse-vol penalizes this signal, underweighting the best trade. The 2022 XLE run would have been captured at ~25% weight instead of 100%, costing roughly 15-20% of that year's alpha. Also adds complexity and rebalancing cost (3 positions instead of 1).
- **Estimated CAGR impact:** -2 to -1% CAGR (significant dilution in trending years; partially offset by much better drawdown profile and Sharpe ratio)
- **Walk-forward testable:** Yes
- **Priority:** P1

---

### S11: Momentum-Score Proportional Weighting

- **ID:** S11
- **Name:** Weight positions proportional to momentum score strength
- **Mechanism:** Binary top-1 selection throws away information: an ETF with 25% 63-day return and one with 10% get the same 100% allocation if they're ranked #1 in their respective months. Proportional weighting uses the signal magnitude: if the #1 ETF's momentum score is 3x the #2's, it gets 3x the weight (capped and normalized). This is the portfolio construction analog of the "continuous TREND signal" from Baltas & Kosowski (2013) — stronger signals deserve larger bets.
- **Rule change:** Select top-3 ETFs by momentum score. Compute weights proportional to positive momentum scores: `w_i = max(score_i, 0) / sum(max(score_j, 0))` for top-3. If all scores negative, 100% SHY. Cap any single weight at 70%.
- **Data needed:** Same data in `/data/`. No new data required.
- **What it fixes:** W-5.6 (no position sizing intelligence). When one ETF has a dominant signal (XLE in March 2022 at +39.4% vs #2 at +5%), the proportional weight keeps it at or near the 70% cap. When signals are close (all tech ETFs within 2-3%), the weight spreads more evenly, reducing concentration whipsaw (W-4.2).
- **What it breaks:** Momentum scores are noisy — small differences in score create weight differences that are just noise, not signal. In months where the top 3 have scores of 12%, 11%, 10%, the weights (34%/33%/33%) are essentially equal weight — the proportionality adds computational complexity for no benefit. In months with extreme divergence, the cap at 70% limits the strategy's ability to go all-in on the strongest signal, which is often when it's most valuable.
- **Estimated CAGR impact:** -0.5 to +1% CAGR (marginal; primarily value is in risk-adjusted terms, not raw return)
- **Walk-forward testable:** Yes
- **Priority:** P1

---

### S12: Kelly Criterion Sizing

- **ID:** S12
- **Name:** Size positions using Kelly criterion with momentum z-score as edge estimate
- **Mechanism:** The Kelly criterion optimally sizes bets given an estimate of edge and odds: `f* = edge / odds`. For this strategy, "edge" = the z-score of the top ETF's momentum relative to the cross-sectional distribution (how strong is this signal historically?), and "odds" = the inverse of realized vol. A z-score of 2.0 (top ETF's momentum is 2 standard deviations above the universe mean) implies high conviction → large position. A z-score of 0.5 implies weak signal → small position. Half-Kelly (f*/2) is standard practice to account for estimation error.
- **Rule change:** Compute `z = (score_top - mean(scores)) / std(scores)` each month. Apply half-Kelly: `position_size = min(0.5 * z / sigma_top, 1.0)`. Remainder goes to SHY. If z < 0.5, go 100% SHY (no edge).
- **Data needed:** Same data in `/data/`. No new data required.
- **What it fixes:** W-5.6 (no position sizing intelligence) and W-1.2 (whipsaw in trendless markets). When all ETFs have similar momentum (low z-score), Kelly naturally de-risks to SHY, avoiding the whipsaw of picking among nearly identical candidates. When one ETF clearly dominates (high z-score), Kelly sizes up, maximizing the best trades.
- **What it breaks:** Kelly estimation is extremely sensitive to the accuracy of edge estimates. Momentum z-scores are noisy and non-stationary — a z-score of 2.0 in a low-dispersion month means something very different than in a high-dispersion month. In practice, half-Kelly will keep the strategy at 50-80% allocation most of the time (since z-scores above 2 are rare), meaning a persistent cash drag of 20-50% that compounds to a significant CAGR reduction. The strategy's best feature (100% allocation to strong trends) gets diluted.
- **Estimated CAGR impact:** -3 to -1% CAGR (substantial cash drag in most months; improved Sharpe ratio but lower raw returns)
- **Walk-forward testable:** Yes
- **Priority:** P2

---

## RISK MANAGEMENT

### S13: Portfolio-Level Trailing Stop

- **ID:** S13
- **Name:** Rotate to SHY if portfolio drawdown from trailing high exceeds threshold
- **Mechanism:** The strategy currently has no intra-month risk management — it rides the full drawdown until the next monthly rebalance. A trailing stop (e.g., if the portfolio drops >8% from its trailing high-water mark over 10 trading days) forces an exit to SHY regardless of the ranking. This addresses the March 2020 problem where SPY fell 35% within a single month and the strategy had no response mechanism. Barroso & Santa-Clara (2015) show that volatility-managed momentum "virtually eliminates" momentum crashes — a trailing stop is a cruder but more transparent implementation of the same idea.
- **Rule change:** Track the portfolio's trailing 252-day high-water mark. If the current portfolio value drops below (1 - threshold) × high_water_mark at any daily close, sell everything and allocate 100% SHY. Stay in SHY until the next scheduled monthly rebalance, at which point re-enter normally. Threshold = 8% (calibrate via walk-forward).
- **Data needed:** Daily portfolio values (computed from existing daily price data in `/data/`). No new external data.
- **What it fixes:** W-5.5 (monthly rebalance timing risk). The current strategy is blind to intra-month drawdowns. Also partially addresses W-1.1 (momentum crashes) by cutting losses before the full crash unfolds.
- **What it breaks:** Trailing stops are whipsaw machines. An 8% intra-month drop that immediately reverses (V-recovery, flash crash, options expiration) triggers the stop and locks in losses. The stop fires and the strategy misses the recovery. In 2018 Q4, a -8% stop would have fired in October, moving to SHY — which was correct. But in February 2018 (VIX spike, -10% drop, immediate recovery), the stop would have fired and missed the bounce. Historically, ~40-50% of -8% drawdowns reverse within 1-2 weeks. Each false trigger costs 3-5% in missed recovery.
- **Estimated CAGR impact:** -1 to +1% CAGR (avoids ~1 major drawdown per 3-5 years but generates 1-2 false stops per year; net effect depends heavily on the specific drawdown distribution encountered)
- **Walk-forward testable:** Yes
- **Priority:** P1

---

### S14: Volatility Targeting

- **ID:** S14
- **Name:** Scale gross exposure to target 10-12% annualized portfolio volatility
- **Mechanism:** Instead of a binary stop, volatility targeting continuously adjusts exposure. When trailing 21-day realized vol is 8% (calm market), the strategy is fully invested. When vol is 20% (stressed market), the strategy reduces to 50-60% allocation with the remainder in SHY. This is the Barroso & Santa-Clara (2015) approach that "virtually eliminates" momentum crashes — not by predicting crashes, but by mechanically reducing exposure when vol is elevated (which is when crashes occur). The mathematical insight: momentum returns per unit of risk are roughly constant, but the risk itself varies enormously. Normalizing risk normalizes returns.
- **Rule change:** Compute `leverage = target_vol / realized_vol(21d)`, capped at [0.5, 1.0]. Allocate `leverage × 100%` to the top-ranked ETF, remainder to SHY. Target_vol = 11% annualized (calibrate via walk-forward). Never exceed 100% gross (no leverage).
- **Data needed:** Daily portfolio returns for trailing vol calculation. Already computable from `/data/`. No new external data.
- **What it fixes:** W-5.6 (no position sizing intelligence) and W-1.1 (momentum crashes). In high-vol environments (when crashes happen), the strategy automatically de-risks. In low-vol environments (when trends are persistent), it stays fully invested. This is a more sophisticated version of S13 that doesn't have a binary trigger.
- **What it breaks:** Volatility clustering means high-vol often precedes the biggest moves — both up and down. In January 2019, vol was declining from the Q4 2018 spike. The vol target would have kept the strategy at 50-70% allocation precisely when re-entering growth was most valuable. In 2022, XLE had elevated vol — the strategy would have been 60-70% XLE + 30-40% SHY instead of 100% XLE, costing ~10-15% of the year's excess return. Persistent cash drag of 10-30% in most periods.
- **Estimated CAGR impact:** -2 to 0% CAGR (Sharpe ratio likely improves by 0.2-0.4; raw CAGR drops due to persistent cash drag; net value is in risk-adjusted terms, not absolute return)
- **Walk-forward testable:** Yes
- **Priority:** P1

---

### S15: Correlation Gate

- **ID:** S15
- **Name:** Force split across top-2 when top-ranked ETF correlates highly with SPY
- **Mechanism:** When the top-ranked ETF has >0.90 rolling 63-day correlation with SPY, the strategy is effectively making a leveraged beta bet, not an alpha bet. The momentum "edge" disappears when the ETF moves in lockstep with the market — you're just picking the highest-beta asset. Forcing a split to top-2 in this case reduces beta exposure and re-introduces some diversification. This is relevant for QQQ and SOXX which frequently correlate >0.90 with SPY.
- **Rule change:** Compute rolling 63-day Pearson correlation between rank-1 ETF and SPY. If corr > 0.90, allocate 50/50 to rank-1 and rank-2. If rank-2 also has corr > 0.90 with SPY, allocate 50/50 to rank-1 and GLD (forced diversification). If corr ≤ 0.90, allocate normally (100% to rank-1).
- **Data needed:** SPY daily prices (likely already in `/data/` or trivial to add). No new external data.
- **What it fixes:** W-1.3 (momentum crowding). When multiple tech ETFs are highly correlated to the market, the strategy is just picking the noisiest beta exposure. The correlation gate reduces this to a more meaningful sector bet. Also partially addresses W-5.1 (universe concentration) by forcing diversification when the ranking is uninformative.
- **What it breaks:** High correlation to SPY is often a feature, not a bug — in bull markets, the highest-correlated ETF captures the most upside. Forcing diversification in a strong bull (2023-2024) would have dragged returns by allocating 50% to a weaker performer. The 0.90 threshold is arbitrary and might fire too often (tech ETFs frequently exceed this) or too rarely (if we set it higher). Also, GLD as the forced diversifier is a specific choice that might not be optimal.
- **Estimated CAGR impact:** -1 to +0.5% CAGR (reduces beta-disguised-as-alpha; costs real alpha in genuine trending periods; value is mainly in Sharpe improvement)
- **Walk-forward testable:** Yes
- **Priority:** P1

---

### S16: VIX Regime Switch for Lookback Length

- **ID:** S16
- **Name:** Shorter lookback in high-vol regimes, longer in low-vol
- **Mechanism:** RegimeFolio (2025) finds that momentum signal importance collapses in high-vol but recovers as vol normalizes. The insight: in high-vol, longer lookback windows are contaminated with crisis returns that don't represent the current regime. In low-vol, longer windows are more reliable because trends persist. VIX below 18 → use 63-day lookback (standard). VIX 18-25 → use 42-day. VIX above 25 → use 21-day. This adapts the signal to the information quality of the environment.
- **Rule change:** Compute VIX level (or proxy: 21-day realized vol of SPY × sqrt(252) if VIX data unavailable). Set lookback: VIX < 18 → L=63, VIX 18-25 → L=42, VIX > 25 → L=21. Rank ETFs by R(L-day). All else unchanged.
- **Data needed:** VIX daily close from yfinance (^VIX). Not currently in `/data/`; needs download. Alternatively, compute from SPY realized vol (no new data needed).
- **What it fixes:** W-1.1 (V-recovery problem / 2019 gap). In January 2019, VIX was ~25 (declining from 36). The 21-day lookback would have picked up the growth recovery 4-6 weeks before the 63-day window cleared. Also addresses W-1.2 (whipsaw in trendless markets) indirectly — when VIX is low, the longer lookback filters out more noise.
- **What it breaks:** The VIX thresholds (18/25) are arbitrary and likely overfit to the 2018-2025 sample. VIX spent most of 2020-2021 between 15-25, meaning the strategy would have oscillated between 42-day and 63-day lookbacks frequently — this adds a meta-level of whipsaw. Shorter lookbacks in high-vol are noisier by definition — you're trading contaminated-but-stable (63d) for clean-but-noisy (21d). In practice, the 21-day lookback in a VIX>25 environment will produce rapid rotations that may themselves whipsaw.
- **Estimated CAGR impact:** +1-3% CAGR (mainly from faster recovery in V-shaped events; partially offset by noisier signals in transitional periods)
- **Walk-forward testable:** Yes
- **Priority:** P2

---

## TIMING

### S17: Weekly Check with High-Threshold Trigger

- **ID:** S17
- **Name:** Check rankings weekly but only switch if new leader exceeds current by >3%
- **Mechanism:** Monthly rebalancing means the strategy is blind for ~22 trading days between checks. Weekly checks (every 5 trading days) give 4x the responsiveness. But more frequent checks also mean more opportunities for noisy rotations. The hysteresis threshold solves this: only switch if the new leader's momentum score exceeds the current holding's score by >3 percentage points. This filters out noise while catching genuine regime changes faster. The December 2021 false rotation (XLE → SOXX for one month, then back) would have been avoided: SOXX's 63-day return exceeded XLE's by only ~3.4% for a brief period — a 3% threshold would have been marginal, and XLE would have reasserted dominance within 1-2 weeks.
- **Rule change:** Evaluate rankings every Friday close. If rank-1 ETF differs from current holding AND `score(new_rank1) - score(current_holding) > 3%`, rotate. Otherwise, hold current position. Monthly forced re-evaluation regardless (to prevent permanent lock-in to a deteriorating position).
- **Data needed:** Same daily price data in `/data/`. No new data — just more frequent computation.
- **What it fixes:** W-5.5 (monthly rebalance timing risk) — catches intra-month crashes 1-3 weeks earlier. W-4.1 (classic whipsaw) — the threshold prevents rotation on noisy signal differences. The Dec 2021 false rotation is the poster child: the strategy correctly held XLE, incorrectly rotated to SOXX for one month, then rotated back — a 3% threshold would have prevented the round-trip.
- **What it breaks:** Weekly checking + 3% threshold still has more turnover than monthly rebalancing. Each additional rotation incurs transaction costs (~10 bps) and tax drag (short-term capital gains). In trending markets, the threshold rarely fires (the current holding maintains its lead), so the cost is just computational. But in choppy markets, the threshold may fire and un-fire within the same month, generating tax events without meaningful portfolio improvement. The 3% threshold needs calibration — too low = more whipsaw, too high = too slow to rotate.
- **Estimated CAGR impact:** +0.5-2% CAGR (faster response to genuine rotations; partially offset by increased transaction costs and occasional threshold-level false signals)
- **Walk-forward testable:** Yes
- **Priority:** P2

---

### S18: Avoid FOMC Week Rebalancing

- **ID:** S18
- **Name:** Defer rebalancing by 5 trading days if it falls in FOMC week
- **Mechanism:** FOMC announcements create short-term volatility spikes and mean-reverting price action. The day before and after FOMC, sector ETFs experience elevated vol and temporary dislocations that can distort momentum rankings. Rebalancing during this window risks rotating based on a transient dislocation rather than a genuine trend. By deferring 5 trading days, the strategy lets the market digest the new information and re-establish trend direction before acting.
- **Rule change:** If the scheduled monthly rebalance date falls within 2 trading days of an FOMC announcement, defer rebalancing to 5 trading days after the announcement. Use the FOMC calendar (published annually by the Fed, 8 meetings per year). All signal calculations use the deferred date.
- **Data needed:** FOMC meeting dates — published by the Federal Reserve, available as a simple list. Needs to be collected and stored (trivial — 8 dates per year). Historical FOMC dates available from the Fed website back to 1990s.
- **What it fixes:** W-4.1 (whipsaw) — FOMC-driven volatility is a specific trigger for false rotations. In months where FOMC falls near month-end (happens ~3-4 times per year), the rankings on rebalance day may reflect Fed-reaction noise rather than genuine momentum.
- **What it breaks:** The deferral itself means the strategy holds its previous position for an extra week, 3-4 times per year. If a genuine rotation signal fires on FOMC day (e.g., Fed pivots to rate cuts, TLT surges), the 5-day deferral delays the correct rotation. In most cases, 5 days of delay costs 0.5-1% of the move — small but non-zero. Also adds calendar-based complexity to an otherwise simple system.
- **Estimated CAGR impact:** +0-0.5% CAGR (avoids ~1-2 FOMC-driven false rotations per year, each costing 1-2%; partially offset by occasional delayed correct rotations)
- **Walk-forward testable:** Yes
- **Priority:** P2

---

### S19: Earnings Season Filter

- **ID:** S19
- **Name:** No rotation during peak earnings reporting weeks
- **Mechanism:** During earnings season peaks (mid-Jan, mid-Apr, mid-Jul, mid-Oct — roughly 2 weeks each), individual stock earnings create sector-level volatility that doesn't reflect genuine momentum shifts. A tech ETF might spike on NVDA earnings then revert as other tech names disappoint. This short-term noise can distort 63-day rankings at month-end if earnings season coincides with the rebalance window. Deferring rotation during these periods avoids acting on incomplete information — wait for the full earnings picture to emerge.
- **Rule change:** If >30% of S&P 500 companies by market cap report earnings in the 5 trading days before or after the scheduled rebalance, defer rebalancing by 5 trading days. Alternatively, use a simpler rule: no rotation in the 3rd week of January, April, July, or October (peak earnings weeks).
- **Data needed:** Earnings calendar data (for the precise rule) or just hardcoded peak-earnings weeks (for the simple rule). Hardcoded weeks need no external data. For the precise rule, earnings calendars are available from various APIs but add data dependency.
- **What it fixes:** W-4.1 (whipsaw) — earnings-driven sector rotation that reverses within 2-3 weeks is a specific whipsaw trigger. When NVDA reports blowout earnings and SOXX spikes 5% in a day, that spike enters the 63-day window and may tip the ranking — but it doesn't represent a sustainable trend.
- **What it breaks:** Same issue as S18: deferral delays correct rotations that genuinely begin during earnings season. The Q4 2021 XLE rotation began building during October earnings season — deferring would have slightly delayed entry. Also, 8 weeks per year of "no rotation" (4 periods × 2 weeks) reduces the strategy's already limited 12 annual rebalance opportunities to effectively 8-9, making it slower to respond.
- **Estimated CAGR impact:** +0-0.5% CAGR (marginal; avoids ~1 earnings-driven false rotation per year but at the cost of 4 weeks of reduced responsiveness)
- **Walk-forward testable:** Yes
- **Priority:** P2

---

## EARLY WARNING / MACRO OVERLAY

### S20: Yield Curve Inversion Gate

- **ID:** S20
- **Name:** Reduce equity exposure when the yield curve has been inverted 3+ months
- **Mechanism:** A persistently inverted yield curve (10Y-2Y < 0 for 3+ consecutive months) has preceded every US recession since 1970 with 1-2 year lead time. While the timing is notoriously variable, the signal is binary and high-conviction when it fires. The strategy should reduce equity exposure (not eliminate it — the lag is too variable) during sustained inversions because the macro backdrop increasingly favors defensive assets. This is not a timing signal but a regime signal: "the environment has shifted toward late-cycle risk."
- **Rule change:** Compute 10Y-2Y Treasury spread daily. If the spread has been continuously negative for 63+ trading days (roughly 3 months), reduce equity allocation to 50% and allocate 50% to top-ranked defensive {GLD, SHY, TLT}. If spread turns positive, return to normal allocation after 21 trading days (confirmation period). This is a slow-moving gate, not a tactical signal.
- **Data needed:** 10-Year Treasury Constant Maturity (DGS10) and 2-Year Treasury Constant Maturity (DGS2) from FRED. Not in `/data/`; needs download via FRED API. Daily data available from 1976.
- **What it fixes:** W-1.4 (boiling frog / slow regime transitions). Yield curve inversion is the slowest-moving but highest-conviction macro signal. It detects late-cycle risk 6-18 months before it manifests in equity momentum. The 2022-2023 inversion began July 2022 and persisted through 2024 — the gate would have maintained defensive allocation throughout, which would have been premature in 2023 but correct in the context of elevated recession risk.
- **What it breaks:** The yield curve has been a terrible timing signal in the 2020s. The curve inverted in July 2022 and stayed inverted for 2+ years without a recession materializing. During that period, SOXX returned +50% and QQQ returned +40%. A 50% reduction to defensive assets would have cost ~20-25% CAGR during the strongest tech rally in the backtest. The signal is high-conviction but variable-lag — acting on it too aggressively destroys returns in the (sometimes very long) gap between inversion and recession.
- **Estimated CAGR impact:** -2 to +1% CAGR (captures rare but severe recession drawdowns; likely net negative in backtests due to premature de-risking during the 2022-2024 inversion without recession. Forward value depends entirely on whether inversions continue to precede recessions with reasonable lag.)
- **Walk-forward testable:** Yes
- **Priority:** P2

---

### S21: Credit Spread Widening Gate

- **ID:** S21
- **Name:** De-risk when HY-IG credit spread z-score exceeds 1.5
- **Mechanism:** High-yield credit spreads widen 1-3 months before equity drawdowns because credit markets are dominated by institutional investors who de-risk earlier than equity markets (Klein 2013). The z-score normalizes: a spread level that's 1.5 standard deviations above its 252-day mean indicates unusual stress. Combined with the direction (widening, not just high level), this creates an early warning signal. STRATEGY_WEAKNESSES.md §2.1 identifies credit spread divergence as a 2-4 month leading indicator for sector rotation, specifically for the 2022 XLE trade.
- **Rule change:** Compute `HY_spread` (ICE BofA HY OAS) and `IG_spread` (ICE BofA IG OAS) daily. `credit_z = (HY_spread - IG_spread - rolling_mean(252d)) / rolling_std(252d)`. If credit_z > 1.5 AND rising (higher than 21 days ago), allocate to defensive subset {GLD, SHY, TLT} regardless of equity momentum rankings. If credit_z ≤ 1.5 or declining, rank normally.
- **Data needed:** ICE BofA HY OAS (BAMLH0A0HYM2) and IG OAS (BAMLC0A0CM) from FRED. Not in `/data/`; need download. Daily data available from 1996.
- **What it fixes:** W-1.4 (boiling frog) and the early-warning gap identified in STRATEGY_WEAKNESSES.md §2. Credit spreads would have flagged stress in Q4 2018 (spreads widened from September), March 2020 (spreads surged in late February), and would have provided an earlier exit signal than equity momentum in most drawdowns.
- **What it breaks:** Credit spreads have false positives — they can widen on technical factors (ETF outflows, dealer inventory shifts) without signaling genuine equity risk. In 2015-2016, HY spreads widened significantly due to energy sector stress, but the broader equity market recovered after a brief selloff. The gate would have forced the strategy out of equities for months during what turned out to be a buying opportunity. Frequency of false positives: ~1-2 per year, each costing 3-5% in missed equity returns.
- **Estimated CAGR impact:** +0.5-2% CAGR (catches major drawdowns 1-3 months early; partially offset by ~1-2 false positives per year)
- **Walk-forward testable:** Yes
- **Priority:** P2

---

### S22: Oil Term Structure for XLE Timing

- **ID:** S22
- **Name:** Use crude oil futures backwardation as an early entry signal for XLE
- **Mechanism:** When crude oil futures are in backwardation (near-month > far-month), it signals tight physical supply — producers can't meet current demand, so spot prices exceed future prices. This structural condition is bullish for energy equities because it implies sustained high prices and strong cash flows for energy companies. STRATEGY_WEAKNESSES.md §2.3 identifies commodity momentum as a 1-3 month leading indicator for XLE. Backwardation is more specific: it's not just "oil is going up" but "the physical market is structurally tight," which is a more persistent signal.
- **Rule change:** Compute `oil_term = CL1 - CL6` (front-month minus 6-month WTI crude futures). If oil_term > 0 (backwardation) for 21+ consecutive trading days, add a +5% bonus to XLE's momentum score. If oil_term < 0 (contango) for 21+ days, add a -3% penalty. This tilts but doesn't override the ranking.
- **Data needed:** WTI crude oil front-month (CL1) and 6-month (CL6) continuous futures prices. Available from yfinance (CL=F for front month) or Quandl. Not in `/data/`; needs collection. Historical data available from ~2000.
- **What it fixes:** The XLE timing problem identified in MECHANISM_ANALYSIS.md §Q3. XLE became #1 ranked in October 2021, but oil was in backwardation from mid-2021 — the term structure signal would have boosted XLE's score 2-3 months earlier, potentially capturing XLE's August-September 2021 move that the strategy missed.
- **What it breaks:** The oil term structure is a commodity-specific signal applied to one ETF in the universe — it breaks the symmetry of treating all ETFs the same way. If we add asset-specific signals for XLE, we should arguably add them for every ETF, which dramatically increases complexity. Also, backwardation can persist for months during supply disruptions without translating to energy equity returns (e.g., if production costs also rise). The +5% bonus is an arbitrary parameter that requires calibration.
- **Estimated CAGR impact:** +0.5-1.5% CAGR (mainly from earlier XLE entry in energy bull markets; limited by the infrequency of strong backwardation regimes — roughly 2-3 periods in the backtest)
- **Walk-forward testable:** Yes
- **Priority:** P2

---

### S23: Growth-Inflation Quadrant Regime

- **ID:** S23
- **Name:** Classify macro regime by CPI trend + PMI trend and tilt sector allocation
- **Mechanism:** CSS Analytics / Varadi (2025) 2x2 growth-inflation model divides the macro environment into 4 regimes based on whether growth (PMI or GDP proxy) and inflation (CPI or breakeven proxy) are trending up or down: (1) Goldilocks (growth up, inflation down) → tech/growth, (2) Reflation (growth up, inflation up) → energy/industrials/financials, (3) Stagflation (growth down, inflation up) → commodities/gold, (4) Deflation (growth down, inflation down) → bonds/defensive. Each regime historically favors specific sectors with statistical significance. The regime classification provides a macro overlay that the pure momentum signal lacks.
- **Rule change:** Monthly, classify the regime: Growth proxy = ISM PMI > 50 AND rising (3-month trend). Inflation proxy = CPI YoY > 2.5% AND rising. Map to 4 quadrants. For each regime, define a "favored" subset of the ETF universe. Apply a +3% momentum score bonus to ETFs in the favored subset, -2% penalty to disfavored ETFs. Let the momentum ranking handle the rest.
- **Data needed:** ISM PMI (monthly, from FRED: NAPM or ISM Manufacturing Index) and CPI YoY (monthly, from FRED: CPIAUCSL). Not in `/data/`; need download. Both available with long history (1948+ for PMI, 1947+ for CPI). Monthly data — lower frequency than daily prices.
- **What it fixes:** W-1.4 (boiling frog / slow regime transitions). The macro regime can shift before momentum catches it — inflation rising + PMI declining = stagflation regime, which favors GLD and XLE, but the 63-day momentum of tech ETFs might still be positive (momentum lags the regime). The quadrant overlay provides a "gravitational pull" toward the correct sector before momentum confirms.
- **What it breaks:** Macro regime classification is inherently backward-looking (PMI and CPI are lagging indicators with 1-2 month publication delays). The regime might shift by the time the data confirms it. Also, the 2x2 model is extremely simplified — the real economy doesn't neatly divide into 4 regimes. Threshold sensitivity (PMI > 50? > 52?) and the arbitrary bonus/penalty magnitudes add parameters to calibrate, increasing overfitting risk. In backtests, the regime overlay will appear to work because we know which sectors performed in which regimes — but out-of-sample, the mapping may not hold.
- **Estimated CAGR impact:** +0.5-2% CAGR (mainly from faster regime-aligned rotation; offset by lagging macro data and occasional regime misclassification)
- **Walk-forward testable:** Yes
- **Priority:** P2

---

## NOVEL (P3)

### S24: Wikipedia Page View Anomaly for Sector Keywords

- **ID:** S24
- **Name:** Use anomalous spikes in Wikipedia page views for sector keywords as a sentiment proxy
- **Mechanism:** Preis, Moat & Stanley (2013) showed that Wikipedia/Google search volume for financial terms precedes market moves. The logic: retail attention spikes before price moves because people research topics before investing. For sector ETFs, monitoring Wikipedia views for keywords like "semiconductor," "crude oil price," "gold price," "artificial intelligence" could detect surging retail interest 1-4 weeks before it fully reflects in sector prices. An anomaly = page views > 2 standard deviations above the 90-day mean.
- **Rule change:** Weekly, pull Wikipedia page views for a keyword set mapped to each ETF (e.g., SOXX → "semiconductor industry," XLE → "price of oil," GLD → "gold as an investment"). Compute z-score relative to 90-day history. If any ETF's keyword z-score > 2.0, add +2% bonus to that ETF's momentum score. If z-score < -1.0 (unusually low attention), add -1% penalty.
- **Data needed:** Wikipedia page view data from the Wikimedia API (pageviews.wmflabs.org). Free, daily data available from July 2015. Not in `/data/`; needs collection via API. Requires keyword-to-ETF mapping definition (manual curation).
- **What it fixes:** Provides a truly orthogonal signal to price-based momentum. All other hypotheses (S01-S23) ultimately derive from price, volume, or macro data. Wikipedia attention is an independent data source that captures a different aspect of market dynamics — investor attention and narrative formation.
- **What it breaks:** Wikipedia page views are extremely noisy. Spikes can be driven by non-financial events (a semiconductor article goes viral due to a news story about chip shortages in cars, not investment interest). The signal-to-noise ratio is likely very low for sector-level investing. Also, the keyword mapping is subjective and fragile — which keywords represent SOXX vs QQQ? In backtests, you can cherry-pick the best keywords; out-of-sample, the mapping may not generalize.
- **Estimated CAGR impact:** +0-1% CAGR (speculative; likely adds information at the margin but with high noise and significant data engineering overhead)
- **Walk-forward testable:** Yes (data available from 2015)
- **Priority:** P3

---

### S25: Options Put/Call Skew per Sector ETF

- **ID:** S25
- **Name:** Use options put/call skew as a positioning signal for each sector ETF
- **Mechanism:** Options skew (the relative price of out-of-the-money puts vs calls) reveals institutional positioning. When puts are expensive relative to calls (high skew), institutions are hedging downside — this can mean either (a) they're long and worried (bearish contrarian signal) or (b) they're positioning for a known risk (event risk). For sector ETFs, a declining skew (puts getting cheaper) signals that institutions are reducing hedges → bullish. A rising skew signals increasing demand for downside protection → bearish. This is a direct window into institutional positioning that price momentum cannot observe.
- **Rule change:** Weekly, compute 25-delta put/call implied vol skew for each ETF with listed options (SOXX, QQQ, XLE, GLD all have liquid options). `skew_z = (current_skew - rolling_mean(63d)) / rolling_std(63d)`. If skew_z < -1.0 (institutions reducing hedges), add +2% bonus. If skew_z > 1.5 (institutions increasing hedges), add -2% penalty.
- **Data needed:** Options implied volatility surface data (25-delta put IV, 25-delta call IV) for each ETF. Available from CBOE DataShop (paid), or approximated from options chain data via yfinance (free but noisy). Not in `/data/`; needs collection. Historical options data going back to 2018 may require a paid data source.
- **What it fixes:** Provides a positioning signal that's orthogonal to price momentum. Addresses the "crowding" concern from W-1.3 — when momentum is crowded, put skew typically rises (hedging activity increases), and the skew signal would penalize the crowded trade.
- **What it breaks:** Options data is noisy and influenced by factors unrelated to directional views (dealer gamma hedging, vol surface dynamics, expiration effects). Skew for sector ETFs is less liquid and less informative than for SPX. The signal may be a lagging indicator of institutional positioning rather than a leading one — by the time puts are expensive, the risk may already be priced. Also, data quality and availability are a significant hurdle.
- **Estimated CAGR impact:** +0-1.5% CAGR (speculative; potentially valuable but data challenges and noise may limit practical utility)
- **Walk-forward testable:** Yes (with appropriate data; quality of backtest depends on data source)
- **Priority:** P3

---

### S26: Cross-Asset Momentum Confirmation for XLE

- **ID:** S26
- **Name:** Require commodity + equity momentum alignment before entering XLE
- **Mechanism:** XLE's returns are driven by oil prices, but the 63-day equity momentum can be distorted by equity-specific factors (fund flows, sector rotation, tax-loss selling). Requiring that crude oil momentum (CL1 futures) AND XLE equity momentum are both positive provides a "confirmation" that the energy trend is genuine and not just equity-market noise. Cross-asset confirmation filters out false signals where XLE rallies on short squeezes or positioning flows rather than fundamental energy strength.
- **Rule change:** XLE can only rank #1 if BOTH conditions are met: (1) XLE's momentum score is the highest in the universe, AND (2) crude oil front-month futures (CL1) have positive 63-day returns. If condition (2) fails, XLE is demoted to rank #2 and the next-highest ETF takes rank #1. This is a confirmation gate, not a score adjustment.
- **Data needed:** WTI crude oil front-month continuous futures prices (CL=F from yfinance or similar). Same as S22 — overlap in data collection. Not in `/data/`; needs download.
- **What it fixes:** Reduces false positive XLE rotations where equity momentum diverges from commodity fundamentals. Partially addresses W-4.1 (whipsaw) for XLE-specific rotations.
- **What it breaks:** Delays legitimate XLE entry when equity markets lead commodity markets (which happens — equity markets are forward-looking and sometimes price in commodity trends before futures confirm). In the 2021 XLE buildup, equity momentum turned positive slightly before crude oil confirmed. The gate would have delayed entry by ~2-4 weeks. Also, asymmetric treatment of one ETF (only XLE has a confirmation requirement) introduces an arbitrary bias.
- **Estimated CAGR impact:** +0-1% CAGR (avoids ~1 false XLE rotation per cycle; small and infrequent benefit)
- **Walk-forward testable:** Yes
- **Priority:** P3

---

### S27: Realized Correlation Regime — Crisis Cash Override

- **ID:** S27
- **Name:** Go to cash when all ETFs correlate >0.85 (crisis correlation = no diversification benefit)
- **Mechanism:** In a financial crisis, all risky assets correlate toward 1.0 — "all correlations go to 1 in a crisis" (Longin & Solnik 2001). When the average pairwise 21-day correlation among the 5 equity ETFs exceeds 0.85, the universe offers no diversification. Momentum is meaningless when everything moves together — the #1 ranked ETF is just the highest-beta, not the best trade. Going to cash (SHY) in this regime avoids being fully invested in what is essentially a single correlated bet during maximum market stress.
- **Rule change:** Compute the average pairwise 21-day rolling correlation among {SOXX, QQQ, XLK, VGT, IGV, XLE} (the equity subset). If avg_corr > 0.85 for 5+ consecutive trading days, override the ranking and allocate 100% to SHY. Hold SHY until avg_corr drops below 0.75 for 5+ days (confirmation of regime change). GLD is excluded from the equity correlation calculation since it's a natural diversifier.
- **Data needed:** Daily returns for all equity ETFs (already in `/data/`). Pure computation — no new external data.
- **What it fixes:** W-1.3 (momentum crowding) and W-4.2 (concentration whipsaw in crisis). When everything is moving together, the momentum signal is noise — you're just picking the highest-beta asset. Going to cash acknowledges that the signal has no edge in this regime.
- **What it breaks:** High correlation doesn't always mean "crisis" — in strong bull markets, all equity sectors rise together (positive correlation) and the strategy should be fully invested. The 2023-2024 AI rally saw high correlation across tech ETFs but produced +50% returns — going to cash would have been catastrophic. The 0.85 threshold needs to distinguish "crisis correlation" from "bull market correlation." Including the direction of returns (all positive vs all negative) would help, but adds complexity. Also, XLE's correlation to tech ETFs is typically lower (~0.3-0.5), so including it in the calculation may prevent the gate from ever firing.
- **Estimated CAGR impact:** -1 to +1% CAGR (avoids rare but severe crisis periods; likely net negative in backtests due to false triggers during coordinated rallies. Forward value depends on the frequency and severity of future crises.)
- **Walk-forward testable:** Yes
- **Priority:** P3

---

## TESTING ORDER

Each group is designed to be testable in a single session: same data, same backtest engine, results from one group inform the next.

### Group 1: Run First — No New Data Needed

**Hypotheses:** S01, S02, S03, S04, S09, S10, S11, S13, S14, S15

**Rationale:** These use only the daily price data already in `/data/`. They modify the scoring function (S01-S04), position sizing (S09-S11), or risk management (S13-S15) without requiring any new tickers or external data. Run them on the current 8-ETF universe with the existing backtest engine.

**Testing protocol:**
1. Establish baseline: current strategy (63d return, top-1, monthly rebalance) with clean walk-forward splits (train 2018-2021, test 2022-2025).
2. Test S01-S04 independently against baseline. Pick the best scoring change.
3. Test S09-S11 independently using the best scoring function from step 2. Pick the best sizing rule.
4. Test S13-S15 as overlays on the best scoring + sizing from steps 2-3.
5. Final Group 1 candidate = best scoring + best sizing + best risk overlay.

**Key metric:** Sharpe ratio first, CAGR second. We're optimizing risk-adjusted returns, not chasing raw CAGR.

**Expected outcome:** 2-5% CAGR improvement with 20-30% drawdown reduction. If Group 1 changes don't improve Sharpe by at least 0.1, stop — the baseline may be near-optimal for its simplicity.

### Group 2: Minimal New Data — New Tickers Only

**Hypotheses:** S05, S06, S07, S08, S16, S17, S18, S19

**Rationale:** These require downloading new ticker data (TLT, DBC, XLF, XLI, XLV, EEM, AGG, VIX) but no external macro data sources. All available from yfinance in a single download session.

**Testing protocol:**
1. Use the best Group 1 configuration as the new baseline.
2. Test universe changes (S05-S07) independently. Each is a different universe composition — they're mutually exclusive alternatives, not additive.
3. Test S08 (canary gate) as an overlay on the best universe from step 2.
4. Test timing changes (S16-S19) as overlays on the best universe + canary configuration.
5. Final Group 2 candidate = Group 1 best + best universe + best timing overlay.

**Key metric:** Sharpe ratio and maximum drawdown. Universe changes should improve diversification (lower max drawdown) without destroying CAGR.

**Expected outcome:** An additional 1-3% CAGR improvement or (more likely) a significant drawdown reduction at similar CAGR.

### Group 3: New Data Required — Macro Data Sources

**Hypotheses:** S20, S21, S22, S23

**Rationale:** These require FRED downloads (yield curve, credit spreads, CPI, PMI) and/or commodity futures data. Each introduces a new data dependency and a macro overlay that operates on a different timescale than price momentum.

**Testing protocol:**
1. Use the best Group 2 configuration as baseline.
2. Test S20 and S21 independently as risk gates (they serve a similar function — early warning of stress).
3. Test S22 as an XLE-specific enhancement — only useful if XLE is still in the universe.
4. Test S23 as a macro regime overlay — this is the most complex and highest-risk-of-overfitting hypothesis.
5. Only add macro overlays that improve out-of-sample Sharpe. Macro signals are inherently low-frequency and prone to overfitting in short samples.

**Key metric:** Out-of-sample hit rate (what % of the time does the macro signal correctly identify the regime?) and false positive rate (what % of defensive triggers are followed by actual drawdowns?).

**Expected outcome:** 0-2% CAGR improvement. Macro signals are slow-moving and the 2018-2025 sample contains only 2-3 regime transitions — statistical significance will be low. The primary value is risk management, not return generation.

### Group 4: Speculative — Test Only if Groups 1-3 Show the Framework Is Improvable

**Hypotheses:** S24, S25, S26, S27

**Rationale:** These are either data-intensive (Wikipedia, options), asset-specific (XLE confirmation), or crisis-specific (correlation regime). They should only be tested if Groups 1-3 demonstrate that the strategy's framework can be improved — i.e., if the Sharpe ratio improves by at least 0.15 from Group 1-3 changes. If the baseline is already near-optimal, these exotic signals will just add noise and overfitting.

**Testing protocol:**
1. Use the best Group 3 configuration as baseline.
2. Test S27 first (simplest, uses existing data). If crisis correlation detection adds value, proceed.
3. Test S26 next (requires commodity data, already collected for S22).
4. Test S24 and S25 only if data collection is feasible and prior results are promising.
5. Apply strict out-of-sample validation — any signal that works in-sample but not out-of-sample is discarded.

**Key metric:** Incremental Sharpe ratio improvement. These signals must clear a higher bar since they add complexity and data dependencies.

**Expected outcome:** 0-1% CAGR improvement, if any. The primary value of Group 4 is intellectual — confirming whether orthogonal data sources add information to price momentum, not generating production signals.

---

## SUMMARY TABLE

| ID | Name | Priority | New Data? | Fixes Weakness | Est. CAGR Impact |
|----|------|----------|-----------|---------------|-----------------|
| S01 | Multi-period blended momentum | P1 | No | W-1.1 (V-recovery) | +1-3% |
| S02 | Volatility-adjusted momentum | P1 | No | W-5.6 (no sizing intelligence) | +0.5-2% |
| S03 | Rolling Sharpe ranking | P1 | Minimal (T-bill rate) | W-1.2 (whipsaw) | +0.5-2% |
| S04 | Acceleration signal | P1 | No | W-1.4 (boiling frog) | +0-1.5% |
| S05 | Add TLT | P2 | TLT prices | W-5.2 (no duration) | +1-3% |
| S06 | Add DBC/PDBC | P2 | DBC prices | W-5.3 (no inflation diversity) | +0.5-1.5% |
| S07 | Replace tech overlap | P2 | XLF/XLI/XLV prices | W-5.1 (universe concentration) | -1 to +2% |
| S08 | Canary universe | P2 | EEM/AGG prices | W-1.1 (momentum crashes) | +0.5-2% |
| S09 | Top-2 equal weight | P1 | No | W-4.2 (concentration whipsaw) | -1 to -2% |
| S10 | Top-3 inverse-vol | P1 | No | W-5.6, W-4.2 | -2 to -1% |
| S11 | Score-proportional weight | P1 | No | W-5.6 | -0.5 to +1% |
| S12 | Kelly criterion sizing | P2 | No | W-5.6, W-1.2 | -3 to -1% |
| S13 | Portfolio trailing stop | P1 | No | W-5.5 (timing risk) | -1 to +1% |
| S14 | Volatility targeting | P1 | No | W-5.6, W-1.1 | -2 to 0% |
| S15 | Correlation gate | P1 | SPY prices | W-1.3 (crowding) | -1 to +0.5% |
| S16 | VIX regime lookback | P2 | VIX data | W-1.1 (V-recovery) | +1-3% |
| S17 | Weekly check + threshold | P2 | No | W-5.5, W-4.1 | +0.5-2% |
| S18 | FOMC week avoidance | P2 | FOMC calendar | W-4.1 (whipsaw) | +0-0.5% |
| S19 | Earnings season filter | P2 | Earnings calendar | W-4.1 (whipsaw) | +0-0.5% |
| S20 | Yield curve gate | P2 | FRED (DGS10/DGS2) | W-1.4 (boiling frog) | -2 to +1% |
| S21 | Credit spread gate | P2 | FRED (HY/IG OAS) | W-1.4 (boiling frog) | +0.5-2% |
| S22 | Oil term structure | P2 | Crude futures | XLE timing gap | +0.5-1.5% |
| S23 | Growth-inflation quadrant | P2 | FRED (PMI/CPI) | W-1.4 (boiling frog) | +0.5-2% |
| S24 | Wikipedia page views | P3 | Wikimedia API | Orthogonal signal | +0-1% |
| S25 | Options skew | P3 | Options data | W-1.3 (crowding) | +0-1.5% |
| S26 | Cross-asset XLE confirm | P3 | Crude futures | XLE false positives | +0-1% |
| S27 | Crisis correlation override | P3 | No | W-1.3 (crowding) | -1 to +1% |
