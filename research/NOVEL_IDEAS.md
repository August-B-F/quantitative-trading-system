# Novel Hypotheses

30 experimental ideas not well-covered in the literature. Cross-domain, speculative, and intentionally diverse. Each includes the idea, data, modification type, rationale, and risk.

---

## N1: OPTION-IMPLIED SECTOR ROTATION SIGNAL
**Idea:** Compare 30-day implied volatility vs 60-day realized volatility for each ETF. When IV/RV ratio drops below 0.8 (the market is underpricing future risk), this ETF is "cheap insurance" and likely trending smoothly — overweight. When IV/RV > 1.3 (market overpaying for protection), the ETF is likely to mean-revert — underweight.
**Data:** Option chain data for each ETF (available from CBOE, Yahoo Finance options).
**Modification:** Signal modifier — IV/RV ratio adjusts momentum score.
**Why it should work:** The volatility risk premium (VRP) is one of the most robust risk premia in finance. When the market underprices risk for a sector, it's a sign of complacency that benefits trend-followers. When it overprices risk, mean-reversion is more likely — bad for momentum.
**Risk it doesn't work:** Option markets for sector ETFs are less liquid than SPY; IV data may be noisy. VRP is priced in by professional vol traders.

---

## N2: SEMICONDUCTOR CYCLE AS LEADING INDICATOR FOR TECH ETFs
**Idea:** Track the Philadelphia Semiconductor Index (SOX) book-to-bill ratio and DRAM spot prices. When B/B > 1.0 and DRAM prices rising, overweight SOXX. When B/B < 0.9 and DRAM falling, underweight ALL tech ETFs (SOXX, QQQ, XLK, VGT, IGV have substantial semiconductor weight).
**Data:** SIA monthly B/B ratio (free publication), DRAM spot (DRAMeXchange/TrendForce).
**Modification:** Signal filter — semiconductor cycle gates tech ETF eligibility.
**Why it should work:** Semiconductors are the most cyclical sub-sector of tech and lead the broader tech cycle by 3-6 months. SOXX led QQQ in both the 2020 breakout and the 2022 breakdown. Physical supply chain metrics (B/B, memory prices) lead equity prices because they reflect actual demand before earnings reports.
**Risk it doesn't work:** AI demand may have structurally changed the semiconductor cycle (NVDA defying traditional cyclicality). B/B ratio publication may lag actual conditions.

---

## N3: ENERGY SPREAD STRUCTURE AS XLE TIMING SIGNAL
**Idea:** Monitor crude oil futures term structure (front-month vs 12-month contract). Backwardation (front > back) = tight supply = bullish energy. Contango (front < back) = surplus = bearish. When curve flips from contango to backwardation, begin rotating toward XLE even if price momentum hasn't caught up.
**Data:** CL1-CL12 futures spread (free from CME via Yahoo Finance or Quandl).
**Modification:** Signal filter — term structure conditions XLE eligibility.
**Why it should work:** Futures curve structure reflects physical supply/demand fundamentals that PRECEDE equity price movements. The 2021-2022 shift to deep backwardation occurred months before XLE broke out. This is a FORWARD-LOOKING signal while momentum is BACKWARD-LOOKING.
**Risk it doesn't work:** Futures curve is itself volatile and can oscillate. Geopolitical premium can create artificial backwardation that reverses.

---

## N4: CROSS-ASSET VOLATILITY SURFACE REGIME DETECTION
**Idea:** Build a composite "volatility surface health" indicator: combine VIX term structure slope (VIX-VIX3M), MOVE index (bond vol), OVX (oil vol), and GVZ (gold vol). When 3+ of these are in contango (calm, normal), momentum regime. When 2+ are in backwardation (panic), defensive regime.
**Data:** VIX, VIX3M, MOVE, OVX, GVZ (all free from CBOE/FRED).
**Modification:** Regime overlay — multi-asset vol surface determines regime.
**Why it should work:** Single-asset vol (VIX) gives false signals during sector rotations. Multi-asset vol captures systemic stress more accurately. When ALL vol surfaces invert simultaneously, it's a genuine cross-market risk-off event. When only one inverts, it's sector-specific.
**Risk it doesn't work:** Some of these indices have short histories. Correlation between vol surfaces may be unstable.

---

## N5: DARK POOL ACTIVITY RATIO AS INSTITUTIONAL POSITIONING SIGNAL
**Idea:** Track the ratio of dark pool volume to total volume for each ETF. Rising dark pool share = institutional accumulation (positive for future returns). Falling = institutional distribution.
**Data:** FINRA ADF/TRF dark pool volume data (free via FINRA website, 2-week delay).
**Modification:** Signal modifier — dark pool ratio trend adjusts momentum conviction.
**Why it should work:** Institutions use dark pools to build large positions without moving the market. A systematic shift toward dark pool execution in a specific ETF signals informed accumulation that hasn't yet reflected in price. This is the closest retail investors can get to seeing institutional order flow.
**Risk it doesn't work:** 2-week publication delay may be too slow. Dark pool usage is influenced by regulatory changes and market structure, not just positioning. Signal has not been validated for ETF rotation.

---

## N6: PATENT FILING VELOCITY AS TECH SECTOR LEADING INDICATOR
**Idea:** Track the 6-month rolling count of AI/semiconductor/software patent filings by sector-leading companies. Accelerating patent activity = innovation cycle accelerating = favor tech ETFs. Decelerating = cycle peaking.
**Data:** USPTO bulk data (free), Google Patents API.
**Modification:** Signal filter — technology innovation cycle indicator.
**Why it should work:** Patent filing velocity leads R&D spending which leads revenue which leads stock prices. The lag chain is 12-24 months. A sustained acceleration in AI patent filings in 2022-2023 preceded the AI equity boom by ~6 months.
**Risk it doesn't work:** Patent filings are noisy, strategically timed, and may not reflect commercial viability. Very long lead time makes it hard to use for monthly rotation. Purely speculative signal.

---

## N7: ELECTRICITY DEMAND AS REAL-TIME ECONOMIC ACTIVITY PROXY
**Idea:** Track US industrial electricity consumption (from EIA weekly data). Deviation from seasonal norm: positive deviation = strong industrial activity = overweight cyclicals (SOXX, XLE). Negative deviation = weakening activity = underweight.
**Data:** EIA weekly electricity data (free from eia.gov).
**Modification:** Macro signal — real-time economic activity proxy.
**Why it should work:** Electricity demand is nearly impossible to manipulate, is available weekly (vs quarterly GDP), and directly measures physical economic activity. It correlates with manufacturing, data center demand (relevant for tech), and energy consumption. China's electricity data has been used as an alternative GDP proxy for decades.
**Risk it doesn't work:** US electricity data is influenced by weather (AC in summer, heating in winter). Seasonal adjustment is imperfect. Signal-to-noise ratio for monthly ETF rotation may be too low.

---

## N8: FED FUNDS FUTURES IMPLIED PATH AS RATE REGIME SIGNAL
**Idea:** Compute the implied rate change over the next 6 months from Fed Funds futures. When the market prices >75 bps of CUTS, favor growth/duration (QQQ, TLT). When pricing >75 bps of HIKES, favor energy/commodities (XLE, GLD). When neutral, use pure momentum.
**Data:** Fed Funds futures (CME, available via Yahoo Finance or Fred).
**Modification:** Regime overlay — rate expectations condition the ETF universe.
**Why it should work:** Rate expectations drive sector rotation mechanically: falling rates compress discount rates (tech benefits), rising rates benefit commodity producers and hurt duration. The futures market prices this BEFORE it happens, unlike trailing momentum which catches it after.
**Risk it doesn't work:** Rate expectations are often wrong (2023: market priced 6 cuts, got zero). The signal may be a consensus view that's already reflected in equity prices.

---

## N9: EARNINGS REVISION BREADTH BY SECTOR
**Idea:** Track the ratio of upward to downward analyst earnings revisions for the constituents of each ETF. Rising revision breadth = improving fundamentals = overweight. Falling = deteriorating = underweight.
**Data:** IBES earnings estimates via Refinitiv/Bloomberg (not free), or approximate with free sources (Zacks revision data).
**Modification:** Signal modifier — earnings revision breadth adjusts momentum score.
**Why it should work:** Earnings revisions are the single strongest predictor of forward sector returns in institutional research. They capture analyst information processing, which leads stock prices by 1-3 months. Breadth (ratio of up to down) is more robust than level.
**Risk it doesn't work:** Free earnings revision data is limited and delayed. Revisions for broad ETFs may wash out (tech has 100+ stocks). Analyst consensus is a lagging indicator in rapid regime shifts.

---

## N10: INSIDER TRANSACTION AGGREGATE BY SECTOR
**Idea:** Aggregate insider buying/selling dollar volume for the top 10 holdings of each ETF. Net insider buying = overweight. Net selling = underweight. Use as a 3-month leading indicator.
**Data:** SEC Form 4 filings (free via SEC EDGAR, OpenInsider).
**Modification:** Signal filter — insider sentiment conditions ETF eligibility.
**Why it should work:** Corporate insiders have the best information about their companies' prospects. Aggregate insider behavior at the sector level smooths out individual noise. Documented to predict sector returns 3-6 months ahead.
**Risk it doesn't work:** Insider transactions are driven by personal liquidity needs, not just information. Stock option exercises create systematic selling that's uninformative. Aggregate signal may be noisy at the ETF level.

---

## N11: CROSS-SECTOR MOMENTUM DIFFUSION MAP
**Idea:** Build a directed graph of 1-month lead-lag relationships between sectors. Identify which sectors are "momentum transmitters" (lead others) and which are "receivers" (lag). When a transmitter sector's momentum turns, pre-emptively rotate into the receiver sectors that historically follow.
**Data:** Daily sector ETF returns (already available).
**Modification:** Signal generation — predictive lead-lag rotation.
**Why it should work:** Hong, Torous, Valkanov (2007) show sector returns contain predictive information for each other. Information diffusion is slow across sector boundaries. Energy and materials often lead by 1-2 months. Transfer entropy analysis could quantify the directional flow.
**Risk it doesn't work:** Lead-lag relationships are unstable over time. The relationship may reverse during crises. Overfitting to historical patterns that don't persist.

---

## N12: MEAN-REVERSION LAYER AFTER MOMENTUM OVERSHOOT
**Idea:** When the current momentum leader has a 63-day return > 2 standard deviations above its own 3-year average 63-day return, REDUCE allocation from 100% to 70% and put 30% in the #2 ETF. The idea: extreme momentum is more likely to revert.
**Data:** Same daily prices (need historical return distribution).
**Modification:** Position sizing — mean-reversion conditional on momentum extremity.
**Why it should work:** JBF (2010) shows combining momentum with mean-reversion produces higher Sharpe than either alone. Extreme returns have documented tendencies to revert. SOXX returning 50%+ in 63 days is an outlier that often partially reverses.
**Risk it doesn't work:** In genuine breakout regimes (AI boom 2023), "extreme" momentum persists for quarters. Triggering mean-reversion too early leaves returns on the table.

---

## N13: CALENDAR-BASED SEASONALITY OVERLAY
**Idea:** ETFs have documented seasonal patterns. Energy tends to outperform November-April (winter demand). Tech tends to outperform Q4-Q1 (product cycles, earnings). When the seasonal tilt AGREES with momentum, increase conviction. When it disagrees, reduce allocation by 20%.
**Data:** Historical monthly returns by ETF (already available).
**Modification:** Signal modifier — seasonal pattern adjusts conviction.
**Why it should work:** Seasonal patterns in equity sectors are well-documented (Jacobsen et al., "Sell in May"). The mechanism is behavioral (fund flows, earnings timing, commodity demand cycles) and somewhat structural. Agreement between momentum and seasonality is a confluence signal.
**Risk it doesn't work:** Seasonality is one of the most overfit signals in finance. Post-publication decay is severe. Sample sizes per month are small (8 years = 8 January observations). Calendar effects have weakened significantly.

---

## N14: SUPPLY CHAIN STRESS AS TECH/ENERGY ROTATION SIGNAL
**Idea:** Use the NY Fed Global Supply Chain Pressure Index (GSCPI). When GSCPI is elevated and rising, favor energy (supply constraints benefit producers) and avoid tech (supply disruptions hurt manufacturers). When GSCPI is low and falling, favor tech.
**Data:** NY Fed GSCPI (free, monthly).
**Modification:** Regime overlay — supply chain conditions affect ETF eligibility.
**Why it should work:** The 2021-2022 supply chain crisis simultaneously hurt tech (semiconductor shortages) and benefited energy (supply constraints). GSCPI spiked months before equity prices reflected this divergence. Novel because it's not a standard financial signal.
**Risk it doesn't work:** GSCPI is published monthly with revision risk. The 2021-2022 episode may be a one-time event (pandemic-specific) that doesn't generalize.

---

## N15: REALIZED CORRELATION REGIME FOR DIVERSIFICATION GATING
**Idea:** Compute 60-day rolling average pairwise correlation among the 5 tech ETFs (SOXX, QQQ, XLK, VGT, IGV). When average correlation > 0.92 (moving in lockstep), cap tech allocation at 50% max and put remainder in an uncorrelated asset (GLD or XLE if their momentum is positive, else SHY).
**Data:** Daily returns (already available).
**Modification:** Risk filter — correlation-based diversification enforcement.
**Why it should work:** When the 5 tech ETFs are highly correlated, the strategy's apparent 8-ETF diversification is an illusion. A single tech reversal would hit all five. This rule forces genuine diversification when it's needed most. Related to the comomentum concept (Lou & Polk 2021) but applied at the portfolio level.
**Risk it doesn't work:** Tech ETFs are ALWAYS highly correlated (structurally, they overlap). The threshold may need to be set very high (> 0.95) to avoid always triggering.

---

## N16: VOLATILITY OF VOLATILITY (VVIX) AS REGIME TRANSITION SIGNAL
**Idea:** VVIX (volatility of VIX) spikes BEFORE VIX spikes. When VVIX rises above 120 while VIX is still below 20, this signals an impending vol regime shift. Pre-emptively rotate toward defensive (GLD, SHY) before VIX catches up.
**Data:** VVIX daily (free from CBOE).
**Modification:** Early warning signal — VVIX leads VIX which leads equity drawdowns.
**Why it should work:** VVIX captures uncertainty about FUTURE volatility. It's a second derivative of market stress. The temporal sequence is: VVIX spikes → VIX options market gets stressed → VIX spikes → equities fall. Gives 1-3 weeks of lead time vs using VIX directly.
**Risk it doesn't work:** VVIX is noisy and spikes frequently without VIX following. Short history (2006). May produce too many false positives.

---

## N17: COPULA-BASED TAIL DEPENDENCE MONITORING
**Idea:** Estimate the tail dependence coefficient between each ETF pair using a Clayton copula on 252-day rolling windows. When lower-tail dependence increases (crash-together probability rises), reduce portfolio concentration and increase diversification.
**Data:** Daily returns (already available).
**Modification:** Risk filter — tail dependence gates concentration level.
**Why it should work:** Standard correlation measures average co-movement, not crash co-movement. Tail dependence specifically measures the probability that assets crash together. This is the risk that matters for a concentrated portfolio. Guidolin & Timmermann (2007) show correlation structure changes sign between regimes — tail dependence captures this.
**Risk it doesn't work:** Clayton copula estimation is noisy with 252 days of data. Model misspecification risk. The signal may react too slowly to sudden correlation spikes.

---

## N18: ECONOMIC SURPRISE INDEX AS MOMENTUM QUALITY FILTER
**Idea:** Track the Citi Economic Surprise Index (CESI). When surprises are positive (data beating expectations), momentum signals are more trustworthy — increase conviction. When surprises are negative (data disappointing), momentum may be chasing a dying trend — reduce conviction.
**Data:** Citi Economic Surprise Index (Bloomberg, or approximate with FRED data).
**Modification:** Signal modifier — economic surprise conditions momentum conviction.
**Why it should work:** Positive economic surprises validate the fundamental basis for equity momentum. Negative surprises suggest momentum is being driven by speculative flows rather than fundamentals. The 2022 negative surprise environment preceded the growth→value rotation.
**Risk it doesn't work:** CESI is mean-reverting by construction (expectations adjust). May be a contrarian signal rather than a momentum confirmation.

---

## N19: RELATIVE STRENGTH INDEX (RSI) DIVERGENCE AS REVERSAL WARNING
**Idea:** When an ETF is making new 63-day highs but its 14-day RSI is making lower highs (bearish RSI divergence), this is a warning that momentum is fading. Reduce allocation to that ETF by 30% in favor of the #2 ETF.
**Data:** Daily prices (already available, RSI is trivially computable).
**Modification:** Signal modifier — RSI divergence reduces conviction in the current leader.
**Why it should work:** RSI divergence is one of the oldest technical signals, but it's rarely applied systematically to ETF rotation. It captures deceleration of momentum before the absolute level turns negative. Would have flagged the SOXX slowdown in late 2021 before the 2022 breakdown.
**Risk it doesn't work:** RSI divergences produce many false signals, especially in strong trends. An ETF can show RSI divergence for months while continuing to rise.

---

## N20: REGIME-CONDITIONAL TRANSACTION COST BUDGET
**Idea:** Set a monthly "transaction cost budget" that varies with regime. Low-VIX: allow up to 20 bps in monthly costs (2 rotations). High-VIX: allow only 5 bps (stay put unless overwhelming signal). This forces the strategy to be conservative with rotations precisely when they're most likely to whipsaw.
**Data:** VIX and transaction cost tracking.
**Modification:** Portfolio construction — cost budget constrains trading.
**Why it should work:** The main cost of whipsaw is transaction costs + opportunity cost from mis-timing. By budgeting costs tighter in high-vol regimes, the strategy naturally reduces turnover during the periods where turnover is most harmful. Related to Model Predictive Control (Nystrup 2021) — optimizing OVER transaction costs.
**Risk it doesn't work:** The budget may prevent a genuinely necessary rotation during a crisis (e.g., must exit tech for SHY). Need an emergency override.

---

## N21: MAHALANOBIS TURBULENCE AS DAILY CIRCUIT BREAKER
**Idea:** Compute daily Mahalanobis turbulence score across the 8-ETF universe. When turbulence exceeds the 95th percentile of its trailing 252-day distribution, trigger an IMMEDIATE rotation to SHY regardless of monthly schedule.
**Data:** Daily returns for all 8 ETFs (already available).
**Modification:** Risk filter — real-time circuit breaker.
**Why it should work:** Kritzman & Li (2010) show Mahalanobis turbulence captures multi-asset correlation breakdowns that precede large drawdowns. Unlike VIX (which is SPY-specific), turbulence measures disturbance in the SPECIFIC universe we trade. Would have triggered on Feb 20, 2020, before the main crash.
**Risk it doesn't work:** 95th percentile triggers are uncommon but volatile — may trigger during a one-day flash crash that immediately reverses. Re-entry logic is unclear (when does the circuit breaker release?).

---

## N22: TRANSFER ENTROPY NETWORK FOR PREDICTIVE ROTATION
**Idea:** Compute transfer entropy (information flow) between ETF pairs on 60-day rolling windows. Identify which ETFs are "information transmitters" (causing others to move) vs "receivers" (reacting later). Allocate to current transmitters — they're leading the market.
**Data:** Daily returns (already available).
**Modification:** Signal generation — information-theoretic ranking.
**Why it should work:** Transfer entropy measures directed information flow, not just correlation. When XLE becomes a strong transmitter (information flows FROM XLE TO other sectors), it means energy dynamics are driving the market. This would have caught the 2022 energy leadership earlier than price momentum.
**Risk it doesn't work:** Transfer entropy estimation is noisy with financial data (fat tails, non-stationarity). 60-day windows may be too short for stable estimation. Never validated for ETF rotation.

---

## N23: LEVERAGED ETF REBALANCING FLOW PREDICTION
**Idea:** Track the size of leveraged ETF assets (TQQQ, SOXL, UPRO) relative to their underlying. Large leveraged ETF AUM creates predictable end-of-day rebalancing flows. When leveraged ETFs have large AUM AND the market moves significantly, the forced rebalancing creates next-day momentum (after up days) or reversal pressure (after extreme moves).
**Data:** Leveraged ETF shares outstanding (free via Yahoo Finance).
**Modification:** Timing signal — predict rebalancing-induced short-term momentum.
**Why it should work:** Barbon et al. (2021) documented this effect. TQQQ alone has ~$25B in AUM — a 3% QQQ move forces ~$1.5B in same-direction buying at close. This creates short-term momentum that the strategy could exploit by timing rebalance dates.
**Risk it doesn't work:** Market participants are aware of this flow and may front-run it, reducing the signal. Effect has decreased since publication. Only useful for very short-term timing, not monthly rotation.

---

## N24: GEOPOLITICAL RISK ASYMMETRY SIGNAL
**Idea:** Instead of the level of the GPR index, track the ASYMMETRY between GPR "Threats" (forward-looking) and GPR "Acts" (realized events). When Threats >> Acts (market is worried but nothing has happened), this is usually peak fear — contrarian overweight growth. When Acts >> Threats (events happening but market complacent), this is dangerous — overweight defensive.
**Data:** Caldara-Iacoviello GPR components (free, matteoiacoviello.com).
**Modification:** Signal modifier — geopolitical asymmetry conditions risk appetite.
**Why it should work:** Markets overreact to threats and underreact to acts. The threat/act ratio captures this asymmetry. Peak Ukraine fear (Feb 2022) was Threats >> Acts — energy was already pricing the risk. By the time Acts caught up, the trade was crowded.
**Risk it doesn't work:** GPR components are noisy and backward-looking (text-based). The threat/act distinction may not be robust. Very few extreme events in sample.

---

## N25: BAYESIAN SURPRISE AS REGIME CHANGE DETECTOR
**Idea:** For each ETF, maintain a Bayesian belief about its "normal" return distribution (mu, sigma). Compute the KL-divergence between the current 21-day return distribution and the prior belief. When KL-divergence exceeds a threshold, flag a regime change for that specific ETF.
**Data:** Daily returns (already available).
**Modification:** Regime detection — per-asset Bayesian surprise.
**Why it should work:** KL-divergence measures how "surprised" the model is by recent data. A sudden shift in XLE's return distribution (2022 energy spike) would register as high surprise before the 63-day return fully reflects it. This is mathematically principled and doesn't require supervised labels.
**Risk it doesn't work:** KL-divergence with small samples (21 days) is noisy. Choosing the prior distribution and update rate introduces parameters that can overfit. May trigger on high-vol periods that aren't genuine regime changes.

---

## N26: OPTION SKEW DIFFERENTIAL AS SECTOR ROTATION SIGNAL
**Idea:** Compare 25-delta put skew (OTM put IV minus ATM IV) across sector ETFs. When one sector's skew is elevated relative to others, the market is hedging against that sector's downside. The sector with the LOWEST relative skew is the market's most complacent position — overweight it (momentum continuation).
**Data:** Option implied volatility surface (Yahoo Finance options, CBOE OptionMetrics).
**Modification:** Signal modifier — relative option skew adjusts ranking.
**Why it should work:** Option skew reflects institutional hedging demand. Low skew = low hedge demand = market is long and confident = momentum likely to continue. High skew = heavy hedging = market is positioned defensively = momentum may be exhausted.
**Risk it doesn't work:** Option data for sector ETFs may be illiquid, making skew estimates unreliable. The relationship between skew and future returns may not be monotonic.

---

## N27: EARNINGS CALL TONE DIFFERENTIAL ACROSS SECTORS
**Idea:** Use NLP sentiment analysis on earnings call transcripts for the top 5 holdings of each ETF. Compute the average sentiment z-score per sector. Sectors with improving sentiment (positive z-score acceleration) get a momentum boost; declining sentiment gets a penalty.
**Data:** Earnings call transcripts (Seeking Alpha free tier, or SEC EDGAR 8-K filings).
**Modification:** Signal modifier — text-based fundamental sentiment.
**Why it should work:** Management tone on earnings calls reflects private information about future prospects. Cross-sector tone differential captures which sectors' managements are most optimistic. This is "soft data" that precedes "hard data" (actual earnings) by one quarter.
**Risk it doesn't work:** Requires NLP pipeline, which adds complexity. Management tone can be performative. Quarterly frequency is slow for monthly rotation. Free transcript sources may be incomplete.

---

## N28: ABSORPTION RATIO DELTA AS SYSTEMIC FRAGILITY SIGNAL
**Idea:** Compute the Absorption Ratio (fraction of total variance explained by top principal components) from daily returns of 50+ assets. Track the standardized 2-week change in AR. When delta-AR spikes above 1 standard deviation, the system is becoming fragile — reduce equity exposure.
**Data:** Daily returns for 50+ assets (expand to include international equities, commodities, bonds, currencies).
**Modification:** Risk filter — systemic fragility overlay.
**Why it should work:** Kritzman et al. (2011) show delta-AR has strong predictive power for market stress. When top eigenvalues suddenly explain more variance, it means assets are moving in lockstep (correlation convergence), which precedes crashes. This is a broader systemic measure than any single-asset indicator.
**Risk it doesn't work:** Requires a broader asset universe than the 8 ETFs for stable PCA estimation. Lag between AR spike and actual crash is variable (days to months).

---

## N29: TOPOLOGICAL DATA ANALYSIS (TDA) CRASH EARLY WARNING
**Idea:** Apply persistent homology to the 8-ETF multivariate return time series. Compute the Lp-norm of the persistence landscape. When the norm is rising on a 252-day window, the system's topological complexity is increasing — a crash is approaching.
**Data:** Daily returns (already available).
**Modification:** Risk filter — topology-based early warning with 6-12 month lead time.
**Why it should work:** Gidea & Katz (2018) show TDA provided a 250-day lead warning before the 2008 crash and identified the pre-2000 bubble topology. Topology captures structural features of the return space that correlation and volatility cannot. It's coordinate-invariant (doesn't depend on which ETFs you measure).
**Risk it doesn't work:** TDA is computationally expensive and mathematically complex. Only validated on 2-3 historical episodes. The 250-day lead is useful for strategic overlay but useless for monthly timing. May produce extended false positives.

---

## N30: MULTI-AGENT BANDIT WITH THOMPSON SAMPLING
**Idea:** Model ETF selection as a non-stationary multi-armed bandit problem. Each ETF is an "arm." Use discounted Thompson Sampling (CADTS) where the discount factor varies with VIX regime. Low VIX: high discount (trust recent returns). High VIX: low discount (distrust recent returns, explore more).
**Data:** Daily returns (already available).
**Modification:** Full signal generation — replace momentum ranking with principled exploration/exploitation.
**Why it should work:** The bandit framework naturally handles the exploration/exploitation tradeoff — when to keep riding a winner vs when to look for the next leader. Thompson Sampling provides automatic uncertainty quantification. The regime-conditional discount handles non-stationarity. Unlike momentum (pure exploitation), the bandit will occasionally "explore" ETFs that aren't currently leading, catching early breakouts.
**Risk it doesn't work:** Bandit theory assumes stationary or slowly-changing rewards, which financial returns violate. Discount factor selection is itself a parameter. The exploration mechanism may introduce random rotations that look like whipsaw.

---

## SUMMARY TABLE

| # | Idea | Signal Type | Data Effort | Expected Impact | Novelty |
|---|------|-------------|-------------|-----------------|---------|
| N1 | IV/RV ratio | Momentum quality | Medium | Moderate | Medium |
| N2 | Semiconductor B/B | Sector leading | Medium | Moderate-High | High |
| N3 | Oil term structure | Energy timing | Low | High | Medium |
| N4 | Multi-asset vol surface | Regime | Low | Moderate | High |
| N5 | Dark pool ratio | Institutional flow | Medium | Moderate | High |
| N6 | Patent filing velocity | Innovation cycle | High | Low | Very High |
| N7 | Electricity demand | Real activity | Low | Low-Moderate | High |
| N8 | Fed Funds futures path | Rate regime | Low | Moderate-High | Medium |
| N9 | Earnings revision breadth | Fundamental | Medium-High | High | Medium |
| N10 | Insider transactions | Insider sentiment | Low | Moderate | Medium |
| N11 | Momentum diffusion map | Lead-lag | Low | Moderate | High |
| N12 | Mean-reversion overshoot | Position sizing | None | Moderate | Medium |
| N13 | Calendar seasonality | Timing | None | Low | Low |
| N14 | Supply chain stress | Macro | Low | Moderate | High |
| N15 | Realized correlation gate | Risk | None | High | Medium |
| N16 | VVIX early warning | Regime | Low | Moderate-High | High |
| N17 | Copula tail dependence | Risk | None | Moderate | High |
| N18 | Economic surprise index | Signal quality | Low | Moderate | Medium |
| N19 | RSI divergence | Reversal warning | None | Low-Moderate | Low |
| N20 | Regime cost budget | Construction | None | Moderate | High |
| N21 | Mahalanobis circuit breaker | Risk | None | High | Medium |
| N22 | Transfer entropy network | Lead-lag | None | Moderate | Very High |
| N23 | Leveraged ETF flow | Short-term timing | Low | Low | Medium |
| N24 | GPR threat/act asymmetry | Geopolitical | Low | Low-Moderate | High |
| N25 | Bayesian surprise per ETF | Regime | None | Moderate-High | High |
| N26 | Option skew differential | Positioning | Medium | Moderate | High |
| N27 | Earnings call tone NLP | Fundamental | High | Moderate | High |
| N28 | Absorption ratio delta | Systemic risk | Low | High | Medium |
| N29 | TDA persistence landscape | Crash warning | Low | Moderate | Very High |
| N30 | Thompson sampling bandit | Full strategy | None | Moderate-High | Very High |

### Top 5 Most Promising Novel Ideas (by expected impact / effort ratio):
1. **N3** — Oil term structure for XLE timing (free data, high impact, proven in commodities)
2. **N15** — Realized correlation gate (no new data, forces genuine diversification)
3. **N21** — Mahalanobis circuit breaker (no new data, proven in literature, real-time)
4. **N25** — Bayesian surprise per ETF (no new data, principled, fast detection)
5. **N16** — VVIX early warning (free data, true leading indicator)
