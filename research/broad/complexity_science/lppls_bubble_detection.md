# LPPLS Bubble Detection

**Citation:** Shu, M. and Song, R. (2024). "Detection of Financial Bubbles Using a Log-Periodic Power Law Singularity (LPPLS) Model." SSRN 4734944. Also: Zhang, Q., Sornette, D. et al. "LPPLS Bubble Indicators over Two Centuries of the S&P 500 Index." SSRN 2727755.

**Core mechanism:** LPPLS fits price trajectories to: p(t) = A + B(tc-t)^m + C(tc-t)^m * cos(w*ln(tc-t) + phi), where tc is critical crash time. Faster-than-exponential growth with log-periodic oscillations indicates a bubble driven by herding and self-reinforcing imitation.

**Signal:** Calibrate LPPLS over multiple overlapping windows (100-750 days). Confidence indicator = fraction of fits passing filter criteria (0.1<m<0.9, 6<w<13, tc in reasonable window). Cluster of high confidence (>0.5) across scales signals bubble nearing critical time.

**Data needed:** Daily price series for asset/index being monitored.

**Performance:** 34.13% annualized in backtest 2018-2024. Successfully diagnosed bubbles across 200+ years of S&P 500 history. Outperforms exponential fitting and sup-ADF tests.

**Weaknesses:** Nonlinear fitting is expensive with multiple local optima. Primarily for crash timing, less useful for risk-on entry. False positives exist. Monthly rebalancing may miss sharp timing. Some subjective filter parameters.

**Assessment:** Most battle-tested bubble detection model. Physics mechanism (discrete scale invariance) is grounded. Sornette's group has run it real-time since ~2009. **Real mechanism, partially degraded at monthly frequency.**

**Application to 8-ETF rotation:** Multi-scale LPPLS confidence indicator on SPY as "bubble proximity" overlay. When positive bubble confidence elevated across scales, shift toward bonds/alternatives. More targeted than generic volatility signals.
