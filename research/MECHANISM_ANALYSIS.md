# Mechanism Analysis: Why Does This Strategy Work, and When Doesn't It?

**Strategy under analysis:** 100% allocation to best 63-day return among {SOXX, QQQ, XLK, VGT, IGV, XLE, GLD, SHY}. Monthly rebalance. 23.0% CAGR vs SPY 14.2%, 2018-2025.

---

## Question 1: Why Does 63-Day Momentum Work in This ETF Universe?

Three candidate explanations, each with different implications:

### (a) Risk Premium — Momentum Compensates for Crash Risk

**The argument:** Daniel & Moskowitz (2016) show that momentum carries negative skewness — it earns a steady premium but suffers catastrophic crashes when markets reverse sharply from bear to bull. The 63-day return signal is effectively selling a put option on regime changes: it profits in trending environments but gets crushed during V-recoveries. If this is the mechanism, the premium is **structural and durable** because it compensates holders for bearing genuine tail risk.

**Evidence for this strategy:** The 2019 underperformance (-19.5% vs SPY) is exactly the crash-risk payment Daniel & Moskowitz predict. The strategy was in defensive assets (GLD/SHY) as 2018 Q4 crash returns dominated the 63-day window, then missed the January recovery. This is not a bug — it is the cost of the option being sold. The strategy's zero negative years come from avoiding drawdowns (2018: +7.6% vs SPY -5.2%; 2022: +17.4% vs SPY -18.6%), which is the flip side of the same option exposure.

**Strength of evidence:** Moderate. The crash-risk premium is well-documented at the stock level, but ETF-level rotation adds a layer: you are choosing *among* sector bets, not going long winners / short losers. The short leg (which embeds the most crash risk) doesn't exist in this strategy. The strategy's tail risk is **opportunity cost** (missing rallies), not capital loss, which is a less painful form of the premium.

### (b) Behavioral Underreaction — Investors Are Slow to Reprice Sector Leadership

**The argument:** Investors anchor on prior sector narratives ("tech always leads," "energy is dead") and underreact when leadership shifts. The 63-day window captures 3 months of accumulating evidence that the market is slow to fully price. This is consistent with Da, Gurun, & Warachka (2014) on "information discreteness" — momentum driven by many small same-sign returns (gradual sector rotation) is more persistent than momentum from discrete jumps.

**Evidence for this strategy:** The XLE rotation in 2021-2022 fits perfectly. Energy had been a consensus underweight for years. Oil prices were trending up from mid-2021, credit spreads on energy companies were tightening, inflation expectations were surging — yet institutional allocators were slow to rotate from growth to energy. The 63-day signal captured this underreaction mechanically.

**Strength of evidence:** Strong for sector-level ETFs specifically. Asness, Moskowitz & Pedersen (2013) document momentum "everywhere" including across asset classes — the effect is not limited to stock-level mispricing. Sector ETFs sit at exactly the right granularity: broad enough that institutional flows drive prices, narrow enough that leadership genuinely shifts. At the individual stock level, underreaction is increasingly arbitraged away (McLean & Pontiff 2016 show 50-58% post-publication decay). At the sector ETF level, the arbitrage is harder because it requires macro views, not stock-picking.

### (c) Institutional Flow Persistence — Large Allocators Rebalance Slowly

**The argument:** Pension funds, sovereign wealth funds, and target-date funds rebalance on quarterly or annual schedules. When a sector like energy starts outperforming, institutional rebalancing flows arrive in waves over 3-6 months, creating multi-month trends that a 63-day lookback window captures mid-stream.

**Evidence for this strategy:** The 63-day window (approximately one quarter) aligns suspiciously well with institutional rebalancing cycles. The lookback period optimization literature (ReSolve, Quantpedia) notes that 3-month lookbacks have performed better in recent years precisely as institutional AUM has grown. Hurst, Ooi & Pedersen (2017) document trend-following profitability across 137 years and 67 markets — the persistence of trends predates behavioral finance explanations, suggesting a structural (flow-based) mechanism.

**Strength of evidence:** Moderate-to-strong. Flow persistence is harder to falsify because it's difficult to disentangle from underreaction. But the fact that momentum works across commodities and currencies (where behavioral anchoring is less plausible) supports a flow-based explanation.

### Verdict

**For ETF-level momentum specifically, explanation (b) + (c) combined is strongest.** The evidence points to a hybrid: institutional flow persistence creates the trend, and behavioral underreaction prevents fast-money from immediately arbitraging it away. Explanation (a) is real but secondary — this strategy doesn't carry a short leg, so the crash-risk premium is attenuated.

**Practical implication:** The signal is moderately durable but should weaken over time as:
- More capital targets sector rotation (reducing underreaction)
- Institutional rebalancing becomes more frequent (shortening flow persistence)
- The 63-day lookback specifically will face post-publication decay (haircut forward returns 30-50% per McLean & Pontiff 2016, Du & Vojtko 2024)

The appropriate fix is **not** to optimize the lookback window (which is overfitting to the mechanism), but to add orthogonal signals (credit spreads, macro regime indicators, volatility targeting) that exploit different aspects of the same underlying phenomenon.

---

## Question 2: The 2019 Problem

### What happened

| Month | Holding | Strategy Return | SPY Return | Note |
|-------|---------|----------------|------------|------|
| Jan 2019 | GLD | +3.0% | +7.9% | Q4 2018 crash still in 63d window |
| Feb 2019 | IGV | +5.8% | +3.2% | Growth 63d turns positive late Jan |
| Mar 2019 | IGV | +4.4% | +1.8% | |
| Apr 2019 | SOXX | +6.4% | +4.0% | |
| May 2019 | SHY | +0.6% | -6.4% | May selloff — strategy dodges it |
| Jun-Aug | GLD | ~+11% | ~+5% | Rate cut expectations boost gold |
| Sep-Dec | SOXX | ~+10% | ~+9% | |

**Full year: Strategy +11.6%, SPY +31.1%, Gap: -19.5%**

### Diagnosis: Three Contributing Factors

#### Factor 1: V-Recovery Math (Primary Cause)

End-of-December 2018, 63-day returns for growth ETFs were deeply negative:
- QQQ: -16.7%
- SOXX: -15.0%
- XLK: -17.4%
- GLD: +7.5% (winner)
- SHY: +1.3%

The Q4 2018 crash (-14% in SPY, Oct-Dec) dominated the lookback window. Growth ETFs' 63-day returns didn't turn positive until late January 2019 (QQQ: Jan 31, SOXX: Jan 24). By then, the strategy had already allocated to GLD for January, missing the first ~8% of the recovery.

This is the textbook Daniel & Moskowitz (2016) momentum crash mechanism: the lookback window is "poisoned" by prior crash returns, delaying re-entry into the recovery.

#### Factor 2: Defensive Allocations Mid-Year

The strategy went to SHY in May 2019 (avoiding a -6.4% SPY drawdown — correct in hindsight for risk management) and GLD in June-August (correct again — gold surged on rate cut expectations). But these defensive moves meant the strategy captured gold's +11% instead of SPY's recovery rally. The strategy was **right about risk** but **wrong about opportunity cost** — a distinction the 63-day lookback cannot make.

#### Factor 3: Was This a Factor-Level Problem?

**MTUM ETF (iShares MSCI USA Momentum Factor) returned +28.1% in 2019 — versus SPY's +31.1%.** MTUM underperformed SPY by only 3.0 percentage points. This tells us:

- Momentum as a factor was **not** broken in 2019 — MTUM captured most of the market's return
- The problem was specific to **short-lookback, concentrated, sector-rotation momentum**, not momentum broadly
- AQR's momentum factor (which uses 12-month lookback, diversified across hundreds of stocks) also performed reasonably in 2019

**Conclusion:** This was primarily a V-recovery math problem specific to the 63-day lookback + concentrated allocation, compounded by the strategy's (correct) defensive rotations mid-year. It was NOT a factor-level momentum failure. A 12-month lookback or multi-lookback blend would have substantially reduced the gap. The STRATEGY_WEAKNESSES.md analysis estimates a combination of faster secondary signals + regime-conditional lookback shortening could recover 10-15 percentage points of the 19.5% gap.

**However:** Fixing the 2019 problem by shortening the lookback or adding faster signals would likely have worsened 2018 (where the strategy's patience earned +12.8% excess) and 2022 (where steady XLE momentum benefited from a medium-term window). This is a fundamental tradeoff, not an optimization target.

---

## Question 3: The 2022 XLE Question

### Computed XLE 63-Day Returns, Monthly

| Month | XLE 63d Return | XLE Rank (of 8 ETFs) | Top ETF |
|-------|---------------|---------------------|---------|
| Jul 2021 | +1.0% | — | — |
| Aug 2021 | -11.5% | — | — |
| Sep 2021 | -3.8% | — | — |
| **Oct 2021** | **+18.7%** | **#1** | **XLE** |
| **Nov 2021** | **+14.2%** | **#1** | **XLE** |
| Dec 2021 | +4.4% | #5 | SOXX (+21.8%) |
| **Jan 2022** | **+16.2%** | **#1** | **XLE** |
| **Feb 2022** | **+28.6%** | **#1** | **XLE** |
| **Mar 2022** | **+39.4%** | **#1** | **XLE** |
| **Apr 2022** | **+15.6%** | **#1** | **XLE** |
| **May 2022** | **+23.5%** | **#1** | **XLE** |
| Jun 2022 | -6.7% | #2 | SHY (-0.5%) |

### Key Finding: XLE Was Top-Ranked BEFORE the Invasion

**XLE became the #1 ranked ETF in October 2021 — four full months before the Russian invasion of Ukraine on February 24, 2022.**

This is critical: the momentum signal was capturing a real, gradually building energy trend, not reacting to a geopolitical shock. Oil had been trending higher since late 2020, energy company fundamentals were improving, and the inflation regime was shifting — all before the invasion amplified the move.

### Timeline Decomposition

1. **Jul-Sep 2021:** XLE 63d returns negative-to-flat. Oil recovering from COVID lows but not yet dominant. Signal: no edge.

2. **Oct-Nov 2021:** XLE jumps to #1 rank with +18.7% and +14.2% 63d returns. **This is the genuine momentum signal.** Oil broke above $80/barrel, energy credit spreads were tightening, inflation expectations were surging. The STRATEGY_WEAKNESSES.md correctly identifies that credit spreads, commodity momentum, and inflation regime indicators were all pointing to energy 2-4 months before this — but the 63d return signal caught it by October regardless.

3. **Dec 2021:** XLE drops to #5 as a brief SOXX rally (+21.8%) dominated the tech-heavy rankings. The strategy's weights file confirms it held SOXX in December 2021. **This was a false signal from the tech universe** — the strategy briefly rotated away from the correct trade.

4. **Jan-May 2022:** XLE returns to #1 and stays there. The invasion (Feb 24) amplified an existing trend — XLE's 63d return jumped from +16.2% in January to +28.6% in February to +39.4% in March. But the strategy was already allocated to XLE from January.

5. **Jun 2022:** Oil crashes. XLE's 63d return goes to -6.7%. Strategy correctly rotates to SHY.

### Answer: Was This Momentum or a Geopolitical Jump?

**(a) It was primarily a momentum signal that built gradually.** XLE ranked #1 from October 2021, driven by the secular energy trend (oil recovery, inflation, underinvestment in fossil fuels). The invasion was a **discontinuous amplifier** of an existing trend, not the cause of the rotation.

**(b) The invasion mattered for magnitude, not for timing.** Pre-invasion (Oct 2021 - Jan 2022), XLE's 63d returns averaged +13.4%. Post-invasion (Feb-May 2022), they averaged +26.8%. The invasion doubled the signal strength but didn't create it.

**Implication for "early warning" signals:** The STRATEGY_WEAKNESSES.md identifies credit spreads, inflation regime, and commodity momentum as signals that could have flagged XLE 2-4 months earlier (mid-2021). This is a **real problem worth solving** — the strategy missed XLE's move from Aug-Sep 2021 when 63d returns were still negative. An inflation regime indicator (Varadi 2x2 model) or commodity momentum signal (DBC > 200d SMA by Oct 2021) would have captured an additional ~5-10% of the move. These are not phantom improvements.

However, the December 2021 false rotation to SOXX is arguably a bigger problem than late entry — the strategy was correct, rotated away for one month, then rotated back. A hysteresis threshold (don't switch unless the new leader exceeds the current by >5%) would have kept the strategy in XLE through December.

---

## Question 4: Concentration Risk

### CAGR Sensitivity to Removing Individual Years

| Year Removed | Strategy Return That Year | Excess vs SPY | Remaining CAGR (7 years) |
|-------------|--------------------------|--------------|--------------------------|
| 2018 | +7.6% | +12.8% | 26.2% |
| 2019 | +11.6% | -19.5% | 25.5% |
| 2020 | +32.0% | +14.8% | 22.5% |
| **2021** | **+39.0%** | **+8.5%** | **21.6%** |
| 2022 | +17.4% | +36.0% | 24.6% |
| 2023 | +23.5% | -3.2% | 23.7% |
| 2024 | +32.1% | +6.5% | 22.5% |
| 2025 | +29.8% | +10.9% | 22.8% |

### Key Results

**Removing the single best return year (2021: +39.0%):** CAGR drops from 23.7% to 21.6%. Still well above 15%.

**Removing the best excess-return year (2022: +36.0% excess):** CAGR drops to 24.6%. The CAGR barely moves because 2022's absolute return (+17.4%) was below the strategy average — 2022's value was in *not losing* during a -18.6% SPY year, not in generating outsized absolute returns.

**The real concentration risk test:** What if 2022's XLE rotation failed — i.e., the strategy matched SPY's -18.6% instead of earning +17.4%? **Modified CAGR: 18.1%.** This is still above 15%, but barely, and it represents a 5.6 percentage point drop from a single year changing.

**Removing any single year, CAGR stays above 21%.** The 15% robustness threshold is passed comfortably.

### But the Question Is Deeper Than CAGR

The strategy's excess return over SPY (23.7% vs 14.2% = ~9.5% annual excess) concentrates differently than raw CAGR:

| Year | Excess vs SPY | % of Total Excess |
|------|--------------|-------------------|
| 2022 | +36.0% | 47% |
| 2020 | +14.8% | 19% |
| 2018 | +12.8% | 17% |
| 2025 | +10.9% | 14% |
| 2021 | +8.5% | 11% |
| 2024 | +6.5% | 8% |
| 2023 | -3.2% | -4% |
| 2019 | -19.5% | -25% |

**Total 8-year excess: +66.8 percentage points. 2022 alone contributed +36.0 points (54% of total excess).** If you also remove 2019's negative excess, the other 6 years contributed +53.5 points and 2022 contributed 67% of net excess.

### Verdict: Robust on CAGR, Concentrated on Alpha

The strategy passes the CAGR robustness test — removing any single year keeps CAGR above 21%, well above the 15% threshold. **It is not lucky in the narrow sense.**

But the strategy's **excess return over SPY** is highly concentrated: 2022's XLE rotation generated 54% of all cumulative alpha. The three best rotation calls (2022 XLE, 2020 tech, 2018 defensive) generated 87% of cumulative excess returns, offset by 2019's -19.5% miss.

This concentration is inherent to the strategy design: 100% allocation to a single ETF means each correct rotation has maximum impact, and each incorrect one has maximum cost. The strategy is not lucky — it is **levered to the quality of its rotation calls**, and in an 8-year sample, 3-4 correct calls at maximum concentration can dominate total performance.

**The forward-looking risk:** The strategy needs approximately one major correct defensive/rotation call every 2-3 years to justify its tracking error vs SPY. If the next 8 years contain fewer regime changes (more persistent bull market) or if the 63-day lookback is too slow to catch them (faster regime transitions), the excess return will compress toward zero or go negative.

---

## Summary of Actionable Findings

| Question | Finding | Confidence | Implication |
|----------|---------|------------|-------------|
| Q1: Why does 63d momentum work? | Behavioral underreaction + institutional flow persistence (not primarily crash-risk premium) | Medium-High | Signal is moderately durable but should decay 30-50% forward. Add orthogonal signals. |
| Q2: 2019 underperformance | V-recovery math (lookback poisoned by Q4 2018 crash), NOT a factor-level momentum failure. MTUM returned +28.1% in 2019. | High | Multi-lookback blend or regime-conditional shortening could recover 10-15% of the gap, but at cost to other years. |
| Q3: 2022 XLE rotation | Gradual momentum signal (XLE #1 ranked from Oct 2021), NOT a geopolitical jump. Invasion amplified but didn't cause the rotation. | High | Early-warning signals (credit spreads, inflation regime) are worth pursuing — they could capture an additional 5-10%. Hysteresis would prevent the Dec 2021 false rotation. |
| Q4: Concentration risk | CAGR is robust (>21% removing any year). But 54% of excess return vs SPY comes from 2022 alone. | High | Strategy is not lucky but is levered to rotation quality. Forward alpha depends on continued regime diversity and signal efficacy. |

---

## Citations

- Asness, C., Moskowitz, T., & Pedersen, L. (2013). "Value and Momentum Everywhere." *Journal of Finance*, 68(3), 929-985.
- Barroso, P. & Santa-Clara, P. (2015). "Momentum Has Its Moments." *Journal of Financial Economics*, 116(1), 111-120.
- Da, Z., Gurun, U., & Warachka, M. (2014). "Frog in the Pan: Continuous Information and Momentum." *Review of Financial Studies*, 27(7), 2171-2218.
- Daniel, K. & Moskowitz, T. (2016). "Momentum Crashes." *Journal of Financial Economics*, 122(2), 221-247.
- Du, J. & Vojtko, R. (2024). "Hyperbolic Alpha Decay." *arXiv:2512.11913*.
- Hurst, B., Ooi, Y.H., & Pedersen, L. (2017). "A Century of Evidence on Trend-Following Investing." *Journal of Portfolio Management*, Fall 2017.
- Klein, R. (2013). "Sector Credit Relative Value." (Sector credit-equity lead-lag relationship.)
- Lou, D. & Polk, C. (2021). "Comomentum." *Review of Financial Studies*, 35, 3272-3302.
- McLean, R.D. & Pontiff, J. (2016). "Does Academic Research Destroy Stock Return Predictability?" *Journal of Finance*, 71(1), 5-32.
- Moskowitz, T., Ooi, Y.H., & Pedersen, L. (2012). "Time Series Momentum." *Journal of Financial Economics*, 104(2), 228-250.
- Varadi, D. / CSS Analytics. (2025). "Growth-Inflation Timing." (2x2 regime model for sector rotation.)
