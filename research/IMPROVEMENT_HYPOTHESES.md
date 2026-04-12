# Improvement Hypotheses

Each hypothesis specifies: idea, data needed, how it modifies the strategy, why it should work, and risk it doesn't.

---

## H1: ALTERNATIVE LOOKBACK PERIODS

### H1a: Multi-Lookback Blend
**Idea:** Replace single 63-day return with weighted average of 21, 42, 63, and 126-day returns. Weight: 30% on 21d, 25% on 42d, 25% on 63d, 20% on 126d.
**Data:** Same daily price data already available.
**Modification:** Signal generation — replace `ret_63d` with blended score for ranking.
**Why it should work:** ReSolve Asset Management and Keller (VAA) show multi-lookback blends are more robust than any single period. Short lookbacks catch recoveries faster; long lookbacks filter noise. The blend reduces sensitivity to any single lookback's failure mode.
**Risk it doesn't work:** The blend may be worse than 63-day in strongly trending markets. Added complexity for marginal improvement. The optimal blend weights are themselves a parameter that can be overfit.

### H1b: VAA Weighted Momentum (Keller Formula)
**Idea:** Score = `12 × 1M_return + 4 × 3M_return + 2 × 6M_return + 1 × 12M_return`. Rank ETFs by this score.
**Data:** Same daily price data.
**Modification:** Signal generation — replace 63-day return with VAA score.
**Why it should work:** Keller (2017) reports Sharpe 1.10 with this formula. 40% weight on most recent month means V-recoveries are caught 4-6 weeks faster than pure 63-day. Backtested over 45+ years.
**Risk it doesn't work:** Heavy weighting on 1-month return increases whipsaw risk. May underperform in slow, steady trends where the 63-day lookback is ideal.

### H1c: Dynamic Lookback Selection (Regime-Conditional)
**Idea:** Use VIX regime to select lookback. Low VIX (< 18): use 63-day. Medium VIX (18-25): use 42-day. High VIX (> 25): use 21-day. Falling VIX from elevated: use 21-day.
**Data:** VIX daily close (free from CBOE/Yahoo).
**Modification:** Signal generation — lookback period becomes a function of VIX.
**Why it should work:** RegimeFolio (2025) SHAP analysis shows momentum signal importance collapses in high-vol regimes. Shorter lookbacks adapt faster when the environment is changing rapidly. After a vol spike, the long lookback is contaminated with crisis returns.
**Risk it doesn't work:** VIX regime thresholds are arbitrary. Rapid VIX oscillation could cause lookback to change too frequently. Adds a parameter (threshold levels) that can be overfit.

---

## H2: MACRO SIGNALS THAT COULD PREEMPT ROTATIONS

### H2a: Yield Curve Slope as Regime Signal
**Idea:** Monitor 10Y-2Y Treasury spread. When slope is steepening (rising from inversion), tilt toward cyclicals (SOXX, XLE). When flattening/inverting, tilt toward defensive (GLD, SHY).
**Data:** FRED DGS10, DGS2 (free, daily).
**Modification:** Signal filter — regime overlay that adjusts which ETFs are eligible for selection.
**Why it should work:** Yield curve is the most reliable recession predictor in finance. Steepening = expansion ahead, favoring cyclicals. Inversions have preceded every recession since 1960.
**Risk it doesn't work:** The yield curve leads by 12-18 months — too early for a monthly system. False inversions (2019) can cause premature defensive positioning. The signal is so well-known that it may be priced in.

### H2b: Excess Bond Premium (Gilchrist-Zakrajsek)
**Idea:** Rising EBP = risk-off signal. When EBP is above its 12-month average and rising, penalize growth ETFs and favor SHY/GLD. When EBP is declining, favor growth.
**Data:** Fed publishes monthly (free since 1973 on Fed website).
**Modification:** Signal filter — EBP regime conditions eligibility of growth vs defensive ETFs.
**Why it should work:** EBP is the strongest recession predictor in academic literature, better than the yield curve. It captures credit market stress that precedes equity weakness by 2-4 months. Would have flagged 2020 and 2022 transitions early.
**Risk it doesn't work:** Monthly publication frequency means 1-month lag. May generate premature defensive signals during temporary credit stress that resolves (2011, 2016).

### H2c: Inflation Regime via Sector Ratio (Varadi 2x2)
**Idea:** Compute inflation indicator as ratio of inflation-positive sector returns (XLE, XLI, XLF, XLB) to inflation-negative (XLU, XLV, XLP), vs 200-day median. Rising inflation → favor XLE. Falling inflation → favor tech.
**Data:** Sector ETF prices (free, already available).
**Modification:** Regime overlay — determines which "bucket" of ETFs is favored.
**Why it should work:** This price-based inflation indicator has no publication lag (unlike CPI). Would have caught the 2021-2022 inflation regime shift months before the strategy rotated to XLE. Varadi backtests show substantial outperformance since 1990.
**Risk it doesn't work:** Sector ratios can give false inflation signals during sector-specific events (oil supply shocks that aren't driven by broad inflation).

### H2d: Canary Universe (EEM + AGG Momentum)
**Idea:** Monitor 63-day returns of EEM (emerging markets) and AGG (aggregate bonds). If either is negative, increase defensive allocation. If both negative, go 100% SHY.
**Data:** EEM, AGG daily prices (free).
**Modification:** Risk filter — canary signals can override the momentum ranking to force defensive positioning.
**Why it should work:** Keller DAA (2018) shows EM equities and aggregate bonds tend to weaken BEFORE US equities in risk-off events. They're the "canary in the coal mine." CAGR >10% with max DD <15% out-of-sample.
**Risk it doesn't work:** EM-specific events (China regulation, EM currency crisis) can trigger false canary signals unrelated to US sector rotation. AGG sensitivity to interest rates may conflict with equity signals.

---

## H3: SENTIMENT SIGNALS AT ETF/SECTOR LEVEL

### H3a: ETF Flow Contrarian Signal
**Idea:** Track net ETF creation/redemption normalized by AUM. Penalize ETFs with extreme recent inflows (crowding risk), favor ETFs with recent outflows (contrarian opportunity).
**Data:** ETF shares outstanding (daily from Yahoo Finance, free), AUM.
**Modification:** Signal modifier — adjust momentum score by flow z-score. Extreme inflows reduce score, extreme outflows increase score.
**Why it should work:** Brown, Davies, Ringgenberg (2021) show extreme ETF inflows predict lower future returns. Crowded momentum trades are more fragile. This acts as a contrarian overlay that reduces concentration in overcrowded winners.
**Risk it doesn't work:** ETF flows are noisy. Systematic inflows (401k contributions, index rebalancing) aren't informative. Signal-to-noise ratio at the ETF level may be too low.

### H3b: Put/Call Ratio as Sector Sentiment
**Idea:** Monitor equity put/call ratio. Extreme bearish sentiment (high P/C ratio) is a contrarian buy signal for growth ETFs. Extreme bullish sentiment (low P/C ratio) is a warning to reduce growth.
**Data:** CBOE equity put/call ratio (free, daily).
**Modification:** Signal modifier — sentiment extreme adjusts conviction in the momentum signal. Very bearish sentiment + positive momentum = high conviction. Very bullish sentiment + positive momentum = lower conviction.
**Why it should work:** Sentiment extremes have documented contrarian value. When everyone is bearish, the marginal seller is exhausted. When everyone is bullish, the marginal buyer is depleted.
**Risk it doesn't work:** P/C ratio has become noisier with the rise of options-based ETFs and zero-DTE options. Institutional hedging patterns may distort the signal.

### H3c: 52-Week High Nearness Ranking
**Idea:** Replace or blend with 63-day return a ranking by Price / 52-Week High. ETFs nearest their highs rank highest.
**Data:** Daily prices (already available).
**Modification:** Signal generation — blend 52-week high nearness (50%) with 63-day return (50%) for ranking.
**Why it should work:** George & Hwang (2004) show 52-week high nearness predicts future returns better than raw momentum AND has no long-run reversal (momentum's key weakness). It's a psychological anchor — investors are reluctant to buy above the prior high, creating underreaction.
**Risk it doesn't work:** At the ETF level (broad sectors), the anchoring effect may be weaker than at the individual stock level. The signal is mechanically correlated with momentum, so the blend may add little.

---

## H4: VOLATILITY-ADJUSTED MOMENTUM SCORING

### H4a: Sharpe-Like Momentum Ranking
**Idea:** Rank ETFs by `63-day return / 63-day realized volatility` instead of raw 63-day return.
**Data:** Daily prices (already available — just need realized vol calculation).
**Modification:** Signal generation — vol-adjusted ranking.
**Why it should work:** Van Zundert (2018) shows vol-adjusted momentum improves Sharpe from 0.34 to 1.14 (3.4x) for equities. The mechanism: high-vol losers have option-like convexity and tend to rebound, causing crashes. Vol-adjusting underweights them. For our system, it penalizes XLE during volatile energy spikes and rewards steady tech trends.
**Risk it doesn't work:** May systematically favor SHY (lowest vol) during choppy markets, creating a defensive bias. Could miss explosive momentum in high-vol winners.

### H4b: Constant Volatility Targeting
**Idea:** Target 12% annualized strategy volatility. `Position = min(1.0, 0.12 / trailing_63d_strategy_vol)`. When strategy vol is above target, scale down to fractional allocation with remainder in SHY.
**Data:** Strategy returns (derived from backtest).
**Modification:** Position sizing — varies allocation between 0% and 100% based on strategy vol.
**Why it should work:** Barroso & Santa-Clara (2015) show vol-targeting nearly doubles Sharpe ratio and virtually eliminates crashes. Harvey et al. (2018) confirm across 60+ assets. The mechanism: negative return-volatility correlation means high-vol periods are bad-return periods. Reducing exposure during high vol is inherently profitable for equity-like assets.
**Risk it doesn't work:** In the one scenario that matters most (strategy makes a correct call during a volatile period, e.g., XLE in 2022), vol targeting would REDUCE the winning position. May also create cash drag in moderately volatile but upward-trending markets.

### H4c: Yang-Zhang Volatility Estimator
**Idea:** Replace close-to-close realized vol with Yang-Zhang estimator (uses OHLC data). This captures intraday volatility more accurately and reduces turnover by 35%.
**Data:** OHLC prices (already available from Yahoo Finance).
**Modification:** Signal generation — more efficient vol estimation.
**Why it should work:** Baltas & Kosowski (2013) show OHLC-based estimators reduce noise in vol estimates, leading to fewer false vol signals and lower turnover. The 35% turnover reduction directly reduces transaction costs.
**Risk it doesn't work:** Marginal improvement over simpler close-to-close vol. Added complexity for potentially negligible edge.

---

## H5: ADDING NEW ETFs TO THE UNIVERSE

### H5a: TLT (20+ Year Treasury)
**Idea:** Add TLT as a long-duration defensive option alongside SHY.
**Data:** TLT daily prices (free).
**Modification:** Universe expansion — TLT becomes the 9th ETF.
**Why it should work:** In deflationary crashes (2008, 2020 initial phase), TLT surges 20-30% while SHY gains 2-3%. The strategy currently has no access to this powerful crisis alpha. TLT would dominate the momentum ranking during flight-to-quality events, providing much larger defensive returns than SHY.
**Risk it doesn't work:** TLT is extremely volatile (2022: -31%). In rising-rate environments, TLT would be the WORST asset in the universe and the momentum signal would correctly avoid it — but if it appears as the "leader" during a flight-to-quality event, the subsequent rate move could reverse gains quickly. Also, TLT's negative correlation with growth ETFs could cause whipsaw during Fed policy pivots.

### H5b: DBC/PDBC (Broad Commodities)
**Idea:** Add a broad commodity ETF to capture commodity cycles beyond just energy.
**Data:** DBC or PDBC daily prices (free).
**Modification:** Universe expansion.
**Why it should work:** Commodities are the only asset class with positive correlation to inflation AND negative correlation to equities during stagflation. Adds a diversification path the strategy currently lacks. BDI and commodity momentum have documented predictive power for macro cycles.
**Risk it doesn't work:** Commodities have structural negative roll yield (contango). Long-term expected returns are lower than equities. DBC has underperformed since 2008 due to this structural drag.

### H5c: XLU (Utilities) + XLV (Healthcare)
**Idea:** Add defensive equity sectors that outperform in late-cycle/recession without the interest rate sensitivity of TLT.
**Data:** XLU, XLV daily prices (free).
**Modification:** Universe expansion to 10 ETFs.
**Why it should work:** XLU and XLV outperform during growth slowdowns (deflation regime in Varadi 2x2). They provide equity-like returns with lower drawdowns. Adds more defensive paths beyond just GLD/SHY.
**Risk it doesn't work:** Increases universe complexity. XLU has become highly correlated with interest rates (bond proxy). XLV is subject to regulatory risk. More ETFs means more opportunities for whipsaw.

### H5d: TIP (TIPS / Inflation-Protected Bonds)
**Idea:** Add TIP as an inflation hedge that doesn't carry commodity volatility.
**Data:** TIP daily prices (free).
**Modification:** Universe expansion.
**Why it should work:** TIP captures inflation protection with bond-like volatility. In 2021-2022, TIP outperformed before XLE broke out, providing an earlier inflation rotation target. Bridges the gap between GLD (volatile) and SHY (no inflation protection).
**Risk it doesn't work:** TIP has duration risk — it fell significantly in 2022 as real rates surged, even though inflation was high. The "inflation protection" failed precisely when it was needed most.

---

## H6: BLENDED POSITIONS INSTEAD OF 100% CONCENTRATION

### H6a: Top-2 Equal Weight
**Idea:** Hold the top 2 ETFs by momentum score at 50% each instead of 100% in the single best.
**Data:** None additional.
**Modification:** Portfolio construction — select top 2, equal weight.
**Why it should work:** Reduces single-asset concentration risk. When the #1 and #2 are from different sectors (e.g., SOXX + XLE), provides genuine diversification. Reduces the damage from a single rotation error. Butler et al. (2012) show top-N selection consistently beats single-asset.
**Risk it doesn't work:** When the top 2 are from the same sector (SOXX + QQQ), no diversification benefit. Dilutes returns in strongly trending markets where the #1 asset is clearly dominant.

### H6b: Inverse-Volatility Weighted Top-3
**Idea:** Select top 3 ETFs by momentum, weight inversely proportional to their trailing 63-day volatility.
**Data:** Daily prices (already available for vol calculation).
**Modification:** Portfolio construction — top-3 selection with inv-vol weights.
**Why it should work:** Butler, Philbrick, Gordillo (2012) — Adaptive Asset Allocation — show inv-vol weighting equalizes risk contribution across selected assets. This means SHY at 30% vol-weight contributes equal risk as SOXX at 5% vol-weight. Produces smoother return streams.
**Risk it doesn't work:** Inv-vol weighting systematically overweights low-vol assets (SHY, GLD) and underweights the growth ETFs that drive returns. In strong tech trends, this is a drag. The strategy's 23% CAGR partly comes from full concentration in high-returning tech ETFs.

### H6c: Core-Satellite (70/30)
**Idea:** 70% in the momentum leader, 30% in SHY as permanent anchor. Only go 100% in a single asset when the momentum leader has both positive absolute momentum AND is above its 10-month SMA.
**Data:** 10-month SMA (already computable).
**Modification:** Portfolio construction — conditional allocation split.
**Why it should work:** The 30% SHY anchor limits max drawdown on any single rotation error. Faber (2006) shows the 10-month SMA filter has "equity-like returns with bond-like volatility." Combining with momentum ranking keeps the upside.
**Risk it doesn't work:** 30% cash drag reduces CAGR by ~3-5% in trending markets. May convert the strategy from high-return/high-vol to moderate-return/moderate-vol, which may not be what's desired.

---

## H7: WEEKLY REBALANCE TRIGGER CONDITIONS

### H7a: Conditional Weekly Check
**Idea:** Rebalance monthly as default. BUT check weekly for "emergency triggers": (a) Current holding drops >5% in a week, (b) VIX spikes above 30, (c) Current holding's 21-day momentum turns negative. If triggered, do an intra-month rebalance.
**Data:** Weekly prices, VIX (all already available).
**Modification:** Rebalance frequency — monthly with weekly emergency override.
**Why it should work:** The March 2020 crash happened within a single month. A weekly check would have moved to SHY/GLD 2-3 weeks earlier, avoiding ~10% of the drawdown. The emergency triggers are designed to catch only genuine regime breaks, not noise.
**Risk it doesn't work:** False triggers in volatile but ultimately bullish periods (Feb 2018 VIX spike, Aug 2024 Yen carry unwind). Each false trigger incurs transaction costs and may cause whipsaw. Need to calibrate thresholds carefully.

### H7b: Weekly Signal, Monthly Execution with Confirmation
**Idea:** Calculate momentum scores weekly but only execute a rotation if the signal has been consistent for 2+ consecutive weeks. This catches trends faster than monthly while filtering weekly noise.
**Data:** Weekly prices.
**Modification:** Signal timing — weekly signal with confirmation delay.
**Why it should work:** Combines the responsiveness of weekly signals with the noise-filtering of monthly execution. A genuine regime shift (2022 XLE breakout) would show consistent signal for 2+ weeks. A one-week spike (noise) would be filtered.
**Risk it doesn't work:** The 2-week confirmation delay may be too slow for sharp V-recoveries. Adds operational complexity. May not improve over just using a shorter lookback.

---

## H8: REGIME-CONDITIONAL PARAMETER SWITCHING

### H8a: VIX-Tercile Parameter Switching
**Idea:** Maintain three parameter sets:
- Low VIX (< 33rd percentile rolling 252-day): 63-day lookback, 100% concentration, monthly rebalance.
- Medium VIX (33rd-67th): 42-day lookback, top-2 allocation, monthly rebalance.
- High VIX (> 67th): 21-day lookback, top-3 allocation with inv-vol weighting, weekly checks.

**Data:** VIX daily (free).
**Modification:** Full parameter set switches with regime.
**Why it should work:** RegimeFolio (2025) shows feature importance shifts dramatically across VIX regimes. Momentum dominates in low-vol (SHAP 0.342), mean-reversion in medium (0.267), and volatility in high (0.456). Using one parameter set across all regimes is suboptimal. This is the most significant finding in the research: separate models per regime.
**Risk it doesn't work:** Three parameter sets = three times the parameters to overfit. Regime transitions are noisy — VIX oscillating around the tercile boundary causes rapid switching. Need hysteresis (require VIX to cross by a margin before switching).

### H8b: Growth-Inflation 2x2 Regime Mapping
**Idea:** Compute growth (SPY vs 200-day SMA) and inflation (sector ratio) regime. Map ETFs:
- Goldilocks (growth rising, inflation falling): SOXX, QQQ, XLK, VGT, IGV
- Reflation (growth rising, inflation rising): XLE, DBC
- Stagflation (growth falling, inflation rising): GLD, XLE
- Deflation (growth falling, inflation falling): SHY, TLT, GLD

Only allow ETFs matching the current regime to be selected.

**Data:** SPY 200-day SMA, sector ETF prices for inflation ratio (free).
**Modification:** Universe filter — regime determines eligible ETF subset, momentum ranks within subset.
**Why it should work:** Varadi (2025) backtests from 1990 show this 2x2 model substantially outperforms. It prevents the strategy from holding tech in a stagflationary environment or energy in a deflationary one. Would have caught the 2022 tech→energy rotation faster.
**Risk it doesn't work:** Binary regime classification is fragile at boundaries. Sector-regime relationships may not be stable (XLE performed well in goldilocks 2023-2024 due to AI energy demand, not inflation). Reduces the universe in each regime, which could miss cross-regime winners.

---

## H9: USING THE EXISTING HMM REGIME DETECTOR BETTER

### H9a: HMM-Gated Rotation Aggressiveness
**Idea:** The existing HMM detects Bull/Bear/Sideways/Crisis states. Use it to gate aggressiveness:
- Bull: allow full 100% concentration in momentum leader.
- Sideways: require top-2 allocation, reducing concentration.
- Bear: force allocation to defensive subset only (GLD, SHY, TLT).
- Crisis: force 100% SHY, no momentum — momentum fails in crisis.

**Data:** HMM already implemented in `ultimate_trader/features/regimes.py`.
**Modification:** Risk filter — HMM state restricts strategy behavior.
**Why it should work:** The HMM captures return/volatility regime shifts that pure momentum ignores. Forcing defensive positioning in Bear/Crisis prevents the strategy from holding growth ETFs through crashes. The strategy's existing protection (SHY having high 63-day return in crashes) is slow — the HMM would trigger faster.
**Risk it doesn't work:** The existing HMM switches too frequently (115 switches in 33 years per literature). False bear signals would force defensive positioning during corrections that recover. Need to either add hysteresis or replace HMM with Statistical Jump Model (14 switches in 33 years).

### H9b: Replace HMM with Statistical Jump Model
**Idea:** Swap the 4-state Gaussian HMM for a 2-state Statistical Jump Model (SJM) per asset. Lambda=100 penalty produces only ~14 regime switches over 33 years vs HMM's 115.
**Data:** Same daily returns already used by HMM.
**Modification:** Regime detection — SJM replaces HMM.
**Why it should work:** Shu & Mulvey (2024) show SJM beats HMM on every metric: Sharpe 0.78 vs 0.51, turnover 0.16% vs 1.35%. The jump penalty prevents the pathological over-switching that makes HMMs impractical for trading. Per-asset regimes are more actionable than a single market state.
**Risk it doesn't work:** SJM requires periodic refitting (every 6 months with 2000-day lookback). It missed Black Monday (too rapid) and was late exiting the dot-com bubble. The 2-state model may not capture nuanced regimes.

### H9c: HMM Regime Probability as Momentum Weight
**Idea:** Instead of binary regime classification, use the HMM's posterior probability of bull state as a multiplier on the momentum signal. If P(bull) = 0.8, momentum score is multiplied by 0.8. If P(bull) = 0.3, score is multiplied by 0.3.
**Data:** HMM probabilities (already computable from existing code).
**Modification:** Signal modifier — continuous regime weighting.
**Why it should work:** Avoids the hard-switching problem of binary regimes. Gradual transitions reduce whipsaw. A 0.5 probability naturally produces a blended allocation (50% momentum leader, 50% defensive), smoothly transitioning between states.
**Risk it doesn't work:** HMM probabilities are noisy and can oscillate rapidly. The smooth transition may actually be worse than a sharp binary switch if the HMM is oscillating.

---

## H10: ML TO PREDICT WHICH ETF WILL LEAD BEFORE MOMENTUM CATCHES IT

### H10a: XGBoost Next-Month ETF Classifier
**Idea:** Train XGBoost to predict which of the 8 ETFs will have the highest next-month return. Features: current momentum scores, VIX, yield curve, HY spread, sector credit spreads, inflation indicators, ETF flows.
**Data:** All signals from MASTER_SIGNAL_LIST, macro data from FRED (free).
**Modification:** Signal generation — ML prediction replaces or blends with momentum ranking.
**Why it should work:** Shu et al. (2024) show XGBoost on top of Jump Model labels adds genuine predictive power beyond regime persistence. The key: macro features (VIX, yield curve, stock-bond correlation) contain FORWARD-looking information that trailing momentum doesn't. Would have predicted XLE rotation via inflation/energy credit signals.
**Risk it doesn't work:** 8-class classification with monthly observations = ~96 samples/year. Severe overfitting risk. Walk-forward validation shows most ML strategies fail live (12% statistical power with 34 quarterly folds per arXiv:2512.12924). The curse of dimensionality with many features and few observations.

### H10b: Deep Ensemble Uncertainty-Gated Allocation
**Idea:** Train 5 independent models (deep ensemble). When ensemble disagreement is high (large variance in predictions), reduce allocation to 50% with remainder in SHY. When agreement is high, go 100% in the consensus pick.
**Data:** Same as H10a.
**Modification:** Position sizing — uncertainty-based scaling.
**Why it should work:** Lakshminarayanan et al. (2017) show deep ensembles produce well-calibrated uncertainty. High disagreement = model doesn't know = reduce exposure. This is the simplest and most robust uncertainty quantification available. Prevents the strategy from being 100% in a pick that the model is unsure about.
**Risk it doesn't work:** Deep ensemble variance may be poorly calibrated on financial data (non-stationary, fat-tailed). If all 5 models are wrong in the same direction (systematic bias), ensemble agreement is falsely high.

### H10c: Per-Regime Gradient Boosting (RegimeFolio Approach)
**Idea:** Detect VIX regime (low/medium/high). Train separate gradient boosting models per regime. Features standardized per-regime. Use SHAP for interpretability.
**Data:** Same as H10a plus VIX regime labels.
**Modification:** Full ML pipeline replacing momentum ranking.
**Why it should work:** RegimeFolio (2025) reports 137% total return vs 73.8% S&P (2020-2024), Sharpe 1.17. The key insight: momentum features dominate in low-vol but are IRRELEVANT in high-vol. Using one model across all regimes is like using one shoe size for everyone.
**Risk it doesn't work:** 2020-2024 backtest is too short (4 years). Separate models per regime = 3x the parameters to overfit. Regime misclassification cascades into wrong model selection.

### H10d: Temporal Fusion Transformer for Multi-Step Prediction
**Idea:** Use TFT with three input types: static (ETF asset class encoding), known future (calendar, scheduled macro releases), historical (returns, vol, macro). Predict next-month rank of each ETF.
**Data:** All signals plus calendar features.
**Modification:** Full signal generation replacement with ML.
**Why it should work:** Lim et al. (2021, Google) report 7-36% improvement over baselines. TFT's Variable Selection Networks automatically learn which features matter, reducing the need for manual signal engineering. Multi-horizon output enables looking 1-3 months ahead.
**Risk it doesn't work:** Transformers are "harder to train than originally expected" (Stockformer paper). Requires substantial data (probably insufficient with monthly rebalancing on 8 ETFs). LR sensitivity, gradient collapse. HAELT finding: transformer-only ≈ full hybrid, diminishing returns from complexity.
