# AI Integration Design

**Date:** 2026-04-11
**Prerequisites:** Read [MECHANISM_ANALYSIS.md](MECHANISM_ANALYSIS.md), [AI_IMPROVEMENT_PLAN.md](AI_IMPROVEMENT_PLAN.md), and [STRATEGY_HYPOTHESES.md](STRATEGY_HYPOTHESES.md) first.

---

## Foundational Principle

The systematic strategy is the product. The AI is an optional overlay.

The systematic strategy (63-day momentum rotation, 23.0% CAGR, 0.96 Sharpe, 2018-2025) works because of behavioral underreaction and institutional flow persistence (MECHANISM_ANALYSIS.md Q1). These are structural mechanisms that do not require AI to exploit. The AI layer exists to solve a narrower problem: can we reduce the strategy's worst drawdowns (-28.4% max) or improve rotation timing at regime transitions — without degrading the base signal?

If the answer is no, the system ships without AI. Every integration mode below is designed so that removing it entirely returns the system to pure systematic operation with zero code changes to the core strategy.

---

## Architecture: AI as a Sidecar

```
                                    ┌─────────────────────┐
                                    │   AI Sidecar         │
                                    │                     │
  ┌──────────────┐    signal_date   │  ┌───────────────┐  │
  │  Data Feed   │───────────────── │  │ Feature Eng.  │  │
  │  (prices,    │                  │  └───────┬───────┘  │
  │   macro)     │                  │          │          │
  └──────┬───────┘                  │  ┌───────▼───────┐  │
         │                          │  │   Model       │  │
         │                          │  │  (XGB/Ridge)  │  │
         │                          │  └───────┬───────┘  │
         │                          │          │          │
         │                          │  ┌───────▼───────┐  │
         │                          │  │ Calibration   │  │
         │                          │  │ (Platt/Temp)  │  │
         │                          │  └───────┬───────┘  │
         │                          │          │          │
         │                          │     prediction      │
         │                          └──────────┼──────────┘
         │                                     │
  ┌──────▼───────┐                             │
  │  Systematic  │◄────────────────────────────┘
  │  Strategy    │   AI prediction consumed
  │  (momentum   │   ONLY through integration
  │   rotation)  │   mode interface
  └──────┬───────┘
         │
  ┌──────▼───────┐
  │  Execution   │
  │  (position,  │
  │   rebalance) │
  └──────────────┘
```

**Key constraint:** The AI sidecar communicates with the systematic strategy through exactly one interface — a prediction object:

```python
@dataclass
class AIPrediction:
    date: str                          # signal date
    mode: str                          # which integration mode produced this
    action: str                        # "hold" | "reduce" | "veto" | "defer"
    confidence: float                  # calibrated probability [0, 1]
    position_scale: float              # multiplier on systematic position [0, 1]
    shy_allocation: float              # fraction to SHY [0, 1], complement of position_scale
    metadata: dict                     # model type, features, raw scores, etc.
    disable_reason: str | None         # if auto-disable triggered, why
```

The systematic strategy reads this object. If it's absent (AI down, disabled, or not deployed), the strategy runs at `position_scale=1.0, shy_allocation=0.0` — pure systematic.

---

## Mode A: Confidence Gate

### Mechanism

The systematic strategy picks the top ETF by momentum score. The AI provides a calibrated confidence score for whether that pick will outperform SHY next month (binary: beat SHY or not). The confidence score sizes the position.

### Signal Flow

```
Systematic picks ETF_top (e.g., SOXX)
    │
    ▼
AI model predicts: P(ETF_top beats SHY next month) = 0.73
    │
    ▼
Compare to threshold T (set from validation ECE)
    │
    ├── P > T (high confidence):  100% ETF_top
    │
    └── P ≤ T (low confidence):   60% ETF_top + 40% SHY
```

### Threshold Selection

The threshold T is not a free parameter to optimize. It is derived from calibration:

1. **During walk-forward validation:** compute ECE (Expected Calibration Error) on each validation fold.
2. **If ECE < 0.10** (well-calibrated): set T = 0.60. Confidence scores are trustworthy — use them to modulate position size continuously: `position_scale = min(1.0, confidence / T)`.
3. **If 0.10 ≤ ECE < 0.15** (marginal calibration): set T = median confidence across training predictions. This creates a binary gate — above/below median — that doesn't rely on the absolute probability being meaningful.
4. **If ECE ≥ 0.15** (poor calibration): disable Mode A entirely. Confidence scores are unreliable.

**Why not optimize T on the test set?** Because with 60-80 effective monthly samples, any threshold optimized on test data is overfit. The validation-derived threshold is the only defensible approach.

### Model Specification

- **Architecture:** XGBoost (depth=3, 100 trees, min_child_weight=5, subsample=0.8) or Ridge Regression
- **Target:** Binary — does the systematic strategy's top pick beat SHY next month? (Yes/No)
- **Features:** 7-10 from the domain knowledge set (AI_IMPROVEMENT_PLAN.md Part D):
  - 63-day momentum of top ETF (relative to SHY)
  - 21-day momentum of top ETF
  - VIX level
  - VIX 21-day change
  - 20-day realized volatility of top ETF
  - Cross-sectional momentum dispersion
  - Top ETF momentum z-score (how far above the pack)
- **Training window:** 60 months rolling
- **Calibration:** Platt scaling on validation fold (6 months held out)
- **Samples per fold:** ~60 monthly observations (one per month — does the top pick beat SHY?)

### AIPrediction Output

```python
# High confidence example
AIPrediction(
    date="2024-07-01",
    mode="confidence_gate",
    action="hold",
    confidence=0.78,
    position_scale=1.0,
    shy_allocation=0.0,
    metadata={"model": "xgboost", "ece": 0.08, "threshold": 0.60},
    disable_reason=None
)

# Low confidence example
AIPrediction(
    date="2024-08-01",
    mode="confidence_gate",
    action="reduce",
    confidence=0.52,
    position_scale=0.60,
    shy_allocation=0.40,
    metadata={"model": "xgboost", "ece": 0.08, "threshold": 0.60},
    disable_reason=None
)
```

### Automatic Disable Trigger

**Metric:** Gate accuracy — when the gate says "high confidence," does the top pick actually beat SHY?

**Measurement:** Rolling 6-month window. Track every high-confidence prediction and whether the top pick beat SHY that month.

**Trigger:** If gate accuracy < 60% over any rolling 6-month window (i.e., the gate is wrong >40% of the time), disable Mode A.

**Why 60% and not 50%?** A random coin flip is 50%. The gate must beat random by a meaningful margin to justify its existence. At 60% accuracy over 6 months, that's ~4 correct out of 6 — barely above noise but enough to add value. Below 60%, the gate is not demonstrably better than ignoring AI entirely.

**Recovery:** After disable, wait 3 months. Retrain on the latest 60-month window. Re-evaluate ECE. If ECE < 0.15 and backtest gate accuracy > 65% on the new validation fold, re-enable.

### Failure Mode Analysis

| Failure | Detection | Impact | Response |
|---------|-----------|--------|----------|
| AI systematically overconfident | ECE > 0.15 on rolling validation | Amplifies bad picks (full position on wrong ETF) | Disable; revert to pure systematic |
| AI systematically underconfident | Gate always fires "low confidence" | Permanent 40% SHY drag → ~8% CAGR loss | If >80% of months are "low confidence" for 6 months, disable |
| Calibration drift (model was good, now isn't) | ECE computed monthly on last 12 predictions | Gradual degradation of position sizing | Retrain with latest data; if ECE still high, disable |

---

## Mode B: Veto Only

### Mechanism

The systematic strategy picks the top ETF. The AI can veto (send to SHY) but never redirect to a different ETF. Veto fires when the AI predicts the selected ETF will be among the worst performers.

This is the most conservative integration mode. It can only prevent losses, not generate alpha. The asymmetry is intentional — the cost of a missed veto (strategy takes a loss it would have taken anyway) is zero relative to the base strategy. The cost of a false veto (strategy misses a winning month) is bounded by one month of returns.

### Signal Flow

```
Systematic picks ETF_top (e.g., XLE)
    │
    ▼
AI model predicts: rank of ETF_top among 8 ETFs next month
    │
    ▼
Predicted rank in bottom 3 (rank 6, 7, or 8)?
    │
    ├── No:   100% ETF_top (no veto)
    │
    └── Yes:  100% SHY (veto fires)
```

### Model Specification

- **Architecture:** XGBoost (depth=3) or Random Forest (depth=4)
- **Target:** T2 regression — predict next-month return for each ETF. Rank predictions. Check if the systematic strategy's top pick ranks in bottom 3.
- **Features:** Same 7-10 domain features as Mode A, applied cross-sectionally (compute features for all 8 ETFs, predict returns for all 8, rank)
- **Training window:** 60 months rolling
- **Samples per fold:** 60 months x 8 ETFs = 480 cross-sectional observations (more data than Mode A's binary target)

**Why predict returns and rank, rather than directly predicting "will this ETF be bottom 3"?** Because the cross-sectional return prediction gives 480 training samples (8 ETFs x 60 months) instead of 60 binary labels. The rank is derived, not directly predicted — this is the T2 target from AI_IMPROVEMENT_PLAN.md.

### Veto Threshold

The veto fires when the systematic's top pick is predicted in the bottom 3 of 8. This is deliberately coarse:

- Bottom 3 of 8 = bottom 37.5%. A random model would veto 37.5% of the time.
- The veto should fire meaningfully less than 37.5% of the time (otherwise it's no better than random). Target: veto fires 10-20% of months.
- If the model vetoes >30% of months, it's too aggressive — recalibrate or disable.

### AIPrediction Output

```python
# No veto
AIPrediction(
    date="2024-07-01",
    mode="veto_only",
    action="hold",
    confidence=0.85,          # confidence that ETF_top is NOT bottom-3
    position_scale=1.0,
    shy_allocation=0.0,
    metadata={"predicted_rank": 2, "predicted_return": 0.04},
    disable_reason=None
)

# Veto fires
AIPrediction(
    date="2024-08-01",
    mode="veto_only",
    action="veto",
    confidence=0.71,          # confidence that ETF_top IS bottom-3
    position_scale=0.0,
    shy_allocation=1.0,
    metadata={"predicted_rank": 7, "predicted_return": -0.03},
    disable_reason=None
)
```

### Automatic Disable Trigger

**Metric:** Veto accuracy — when the veto fires, was the vetoed ETF actually in the bottom 3?

**Measurement:** Track every veto over a rolling 12-month window (expect 2-5 vetoes per year).

**Trigger:** If veto accuracy < 55% over any rolling 12-month window, disable.

**Why 12 months and not 6?** Vetoes are infrequent (target: 10-20% of months = 1-2 per quarter). A 6-month window might contain only 1-2 vetoes — too few to assess accuracy. 12 months should contain 3-6 vetoes, enough for a rough signal.

**Critical edge case — the XLE problem:** The 2022 XLE run was the strategy's single most valuable trade (+36% excess vs SPY). If the AI vetoes XLE entry in January 2022, the strategy loses its best trade. The veto model must be evaluated specifically on whether it would have vetoed the 2021-2022 XLE rotation. If it would have: the veto model is broken for regime transitions, and Mode B should not be deployed for ETFs entering a new trend.

**Mitigation:** Add a "first-month exemption" — the veto cannot fire on the first month after a new ETF becomes the top-ranked pick. The veto only applies when the strategy is continuing to hold an ETF that was already #1 last month. Rationale: the veto is designed to catch deteriorating positions, not to prevent new entries. New entries are the systematic strategy's primary alpha source.

### Failure Mode Analysis

| Failure | Detection | Impact | Response |
|---------|-----------|--------|----------|
| Veto fires on best trade (XLE 2022) | Retrospective analysis of vetoed months | Entire edge destroyed for that year | First-month exemption; disable if veto accuracy < 55% |
| Veto never fires (model too cautious) | Veto rate < 5% over 12 months | No impact (equivalent to pure systematic) | Acceptable — Mode B degrades gracefully to pure systematic |
| Veto fires too often (>30% of months) | Veto frequency tracking | Permanent SHY drag; strategy becomes a cash strategy | Retrain with stricter threshold or disable |

---

## Mode C: Drawdown Shield

### Mechanism

This mode is independent of the rotation signal. It does not care which ETF the strategy holds. It predicts whether the portfolio will experience a drawdown (>5% loss) next month and scales position size accordingly.

This is the AI's highest-probability value-add (AI_IMPROVEMENT_PLAN.md Part C). Drawdowns have observable precursors (VIX spikes, credit spread widening, momentum crashes) that are fundamentally different from predicting which ETF wins. The problem is binary classification with known features — the most tractable ML problem for small samples.

### Signal Flow

```
Systematic picks ETF_top and allocates 100%
    │
    ▼
AI predicts: P(portfolio loses >5% next month) = p
    │
    ├── p < 0.60:  No action. 100% ETF_top.
    │
    ├── 0.60 ≤ p < 0.80:  Reduce to 50% ETF_top + 50% SHY
    │
    └── p ≥ 0.80:  100% SHY (full defensive)
```

### Model Specification

- **Architecture:** XGBoost (depth=3, 100 trees) — primary. Logistic Regression — secondary/validation.
- **Target:** T4 — binary drawdown prediction. Label = 1 if the held ETF loses >5% in the next 21 trading days, else 0.
- **Features:** 7-10 features specifically chosen for drawdown prediction (different from Mode A/B):
  - VIX level (strongest single drawdown predictor)
  - VIX 21-day change (rising VIX = deteriorating conditions)
  - 20-day realized volatility of held ETF
  - 63-day momentum of held ETF (negative momentum + high vol = drawdown setup)
  - Credit spread z-score (HY-IG spread vs 252-day mean) — if available from FRED
  - Cross-sectional momentum dispersion (low dispersion = crowded trades, crash risk)
  - Yield curve slope (10Y-2Y, if available)
  - Held ETF's rolling max drawdown over last 63 days (drawdown clustering)
- **Training window:** 60 months rolling
- **Samples per fold:** 60 months x 8 ETFs = 480 samples (apply drawdown label to every ETF in every month, not just the held one — cross-sectional expansion)
- **Class imbalance:** Drawdowns (>5% monthly loss) occur ~10-15% of months. Handle with:
  - Class weights: 5:1 for drawdown vs no-drawdown
  - Evaluation metric: precision at 80% recall (catch 80% of drawdowns)
  - Decision threshold tuned on validation fold to hit 80% recall

### Calibration (Critical for This Mode)

The 60% and 80% probability thresholds in the signal flow are meaningless if the model's probabilities aren't calibrated. Calibration procedure:

1. Train XGBoost on training fold (54 months)
2. Apply Platt scaling (logistic calibration) on validation fold (6 months)
3. On test fold, check: when the model says "70% chance of drawdown," does a drawdown actually occur ~70% of the time?
4. Compute ECE on test fold
5. **If ECE > 0.15:** replace continuous probabilities with a binary signal. Set a single threshold that maximizes F1 on the validation fold. Action becomes binary: drawdown predicted → 50/50 split; no drawdown → full position.

### AIPrediction Output

```python
# No drawdown predicted
AIPrediction(
    date="2024-07-01",
    mode="drawdown_shield",
    action="hold",
    confidence=0.15,           # P(drawdown) = 0.15 → low risk
    position_scale=1.0,
    shy_allocation=0.0,
    metadata={"model": "xgboost", "precision_at_80_recall": 0.65},
    disable_reason=None
)

# High drawdown probability
AIPrediction(
    date="2024-08-01",
    mode="drawdown_shield",
    action="reduce",
    confidence=0.72,           # P(drawdown) = 0.72
    position_scale=0.50,
    shy_allocation=0.50,
    metadata={"model": "xgboost", "vix": 28.5, "vol_20d": 0.032},
    disable_reason=None
)

# Very high drawdown probability
AIPrediction(
    date="2020-03-01",
    mode="drawdown_shield",
    action="veto",
    confidence=0.88,           # P(drawdown) = 0.88
    position_scale=0.0,
    shy_allocation=1.0,
    metadata={"model": "xgboost", "vix": 42.0, "vol_20d": 0.058},
    disable_reason=None
)
```

### Automatic Disable Trigger

**Primary metric:** Precision at 80% recall, evaluated on a rolling 24-month window.

**Trigger:** If precision drops below 0.40 on a rolling 24-month window, disable.

**Why 0.40?** At 80% recall with 0.40 precision, 60% of drawdown alerts are false positives. Each false positive costs ~2-4% in missed equity returns (one month of unnecessary SHY allocation). With drawdowns occurring ~10-15% of months, 80% recall catches ~2 drawdowns per year. If 3 out of 5 alerts are false (0.40 precision), the cost is 3 x 3% = ~9% annually in false alarm drag vs 2 avoided drawdowns of ~7% each = ~14% saved. The math is still positive at 0.40, but barely — below 0.40, false alarm costs exceed drawdown avoidance benefits.

**Secondary metric:** False positive rate. If the model triggers "drawdown predicted" more than 25% of months over any 12-month rolling window, it's too sensitive. Disable and retrain.

**Why 24-month window?** Drawdowns are rare (~2-3 per year at >5% threshold). A 12-month window might contain zero actual drawdowns, making precision undefined. 24 months should contain 3-6 drawdown events — enough to assess whether the model catches them without excessive false alarms.

### Failure Mode Analysis

| Failure | Detection | Impact | Response |
|---------|-----------|--------|----------|
| False positives in strong rallies | False positive rate > 25% of months | 6-10% annual drag from unnecessary SHY | Retrain with higher threshold; disable if persists |
| Missed drawdown (false negative) | Actual drawdown >5% without prior alert | Same loss as pure systematic (no worse) | Acceptable — Mode C only helps, never hurts baseline |
| Model always predicts "no drawdown" | Alert rate < 2% over 12 months | No impact (equivalent to pure systematic) | Acceptable but investigate — model may have collapsed |
| Calibration drift | ECE computed quarterly | Probabilities become meaningless → wrong position sizes | Retrain; if ECE stays high, switch to binary signal |

---

## Mode D: Regime-Triggered

### Mechanism

The AI is consulted only when the regime detection model (HMM or Jump-Diffusion) identifies a regime transition. In stable regimes, the pure systematic strategy runs untouched.

Rationale from MECHANISM_ANALYSIS.md Q2: the systematic strategy is most vulnerable during regime transitions because the 63-day lookback window contains mixed-regime data. The 2019 V-recovery was exactly this — the lookback contained Q4 2018 crash returns during a recovery regime. An AI model that helps select the right ETF for the new regime could recover the 10-15% gap identified in Q2.

### Signal Flow

```
HMM / Jump Model monitors daily returns
    │
    ├── No regime change detected: pure systematic runs (AI not consulted)
    │
    └── Regime change detected:
            │
            ▼
        AI model predicts: which ETF best fits the NEW regime?
            │
            ├── AI agrees with systematic's pick: hold, position_scale = 1.0
            │
            ├── AI disagrees but low confidence: hold systematic pick,
            │   but reduce to 70% position + 30% SHY (hedged)
            │
            └── AI disagrees with high confidence: this is NOT a redirect.
                Reduce to 50% systematic pick + 50% SHY.
                (AI can reduce but never redirect — same principle as Mode B)
```

**Critical constraint:** Even in regime-triggered mode, the AI cannot redirect the strategy to a different ETF than the systematic signal chose. It can only scale down the position. Allowing AI to override the systematic pick at regime transitions is the single highest-risk integration possible — one wrong override at a major transition (like vetoing XLE in Jan 2022) destroys years of alpha.

### Regime Detection

The regime model is separate from the AI integration layer. It is a statistical model that classifies the current market regime:

- **Model:** 3-state Hidden Markov Model (HMM) trained on SPY daily returns
  - State 1: Low volatility / trending (bull)
  - State 2: High volatility / mean-reverting (bear/crisis)
  - State 3: Transitional (regime shift in progress)
- **Transition detection:** When the HMM's most likely state changes from state i to state j with posterior probability > 0.80
- **Training:** Re-estimate HMM parameters every 6 months on a rolling 5-year window
- **Regime transitions per year (historical estimate):** 2-4 genuine transitions

### AI Model at Transition Points

- **Architecture:** Ridge Regression (simplest viable model)
- **Target:** T2 — predict next-month return for each ETF, conditional on the detected regime
- **Features:** Same 7-10 domain features, plus:
  - Regime indicator (which regime the HMM just transitioned to)
  - Days since regime transition (early transitions are noisier)
  - Prior regime duration (longer prior regimes → stronger signals in new regime)
- **Training:** Only on historical regime transition months — this dramatically reduces the training set. With 2-4 transitions per year over 5 years, the AI model trains on ~10-20 transition events. This is very small.

### The Small Sample Problem

Mode D has the most severe sample problem of all modes. With ~10-20 regime transitions in the training window, the AI model has very few examples to learn from. This makes it the hardest mode to validate and the most likely to overfit.

**Mitigation:** Use the simplest possible model (Ridge Regression with 3-5 features). Do not use XGBoost or any nonlinear model — there aren't enough transition events. The model's job is to learn a linear relationship between features at transition points and subsequent returns. If even Ridge Regression can't learn this from 10-20 samples, the signal doesn't exist at regime transitions, and Mode D should not be deployed.

### AIPrediction Output

```python
# No regime change — AI not consulted
AIPrediction(
    date="2024-07-01",
    mode="regime_triggered",
    action="hold",
    confidence=1.0,            # pure systematic, no AI involvement
    position_scale=1.0,
    shy_allocation=0.0,
    metadata={"regime": "bull", "regime_change": False},
    disable_reason=None
)

# Regime change detected, AI agrees with systematic
AIPrediction(
    date="2024-08-01",
    mode="regime_triggered",
    action="hold",
    confidence=0.82,
    position_scale=1.0,
    shy_allocation=0.0,
    metadata={"regime": "transition", "regime_change": True,
              "ai_top_pick": "SOXX", "systematic_pick": "SOXX"},
    disable_reason=None
)

# Regime change detected, AI disagrees
AIPrediction(
    date="2019-01-01",
    mode="regime_triggered",
    action="reduce",
    confidence=0.65,
    position_scale=0.50,
    shy_allocation=0.50,
    metadata={"regime": "transition_bear_to_bull", "regime_change": True,
              "ai_top_pick": "QQQ", "systematic_pick": "GLD"},
    disable_reason=None
)
```

### Automatic Disable Triggers

**Trigger 1 — Regime model too sensitive:** If the HMM detects >6 regime transitions in any 12-month rolling window, the regime model is noisy and Mode D is being consulted too often. Disable until the regime model is recalibrated.

**Trigger 2 — AI adds no value at transitions:** Track AI performance specifically at regime transitions. Over a rolling 3-year window (expecting 6-12 transitions), compare: (a) systematic return in the month after transition, vs (b) AI-adjusted return in the month after transition. If AI-adjusted return is worse on average, disable.

**Trigger 3 — Regime model collapses:** If the HMM assigns >0.90 probability to a single state for >18 consecutive months, the model has effectively collapsed to one regime and is not detecting transitions. Retrain with a wider window or different number of states.

### Failure Mode Analysis

| Failure | Detection | Impact | Response |
|---------|-----------|--------|----------|
| Regime model too sensitive (>6 transitions/year) | Transition count monitoring | AI consulted too often → effective always-on Mode A | Disable; recalibrate HMM |
| AI wrong at transitions | Track AI vs systematic at transition points | Worse than pure systematic at the critical moments | Disable AI at transitions; keep regime model for informational logging |
| Regime model never fires | 0 transitions in 12 months | No impact (pure systematic runs) | Acceptable but investigate |
| Wrong regime classification | HMM calls bull → actually bear | AI gives wrong advice based on wrong regime | Mode D's reduce-only constraint limits damage to 50% position reduction |

---

## Mode E: Rebalance Timing

### Mechanism

The systematic signal is computed daily but only acted on when the AI says the current leader is likely to change. If the AI predicts the current leader will remain the leader next month, the strategy holds — avoiding unnecessary turnover. If the AI predicts a leadership change, the strategy rebalances immediately.

This mode addresses a real problem: the systematic strategy rebalances monthly on a fixed schedule, but regime transitions don't follow a calendar. Weekly checking with a hysteresis threshold (S17 from STRATEGY_HYPOTHESES.md) is a rules-based version of this idea. Mode E uses AI to make the timing decision.

### Signal Flow

```
Every Friday close:
    │
    ▼
Compute systematic rankings (daily — all 8 ETFs scored)
    │
    ▼
Current holding = ETF_current (e.g., SOXX)
New top-ranked  = ETF_new (e.g., XLE)
    │
    ├── ETF_current == ETF_new: hold (no action needed regardless of AI)
    │
    └── ETF_current ≠ ETF_new:
            │
            ▼
        AI predicts: P(ETF_current will still be #1 ranked in 21 trading days)
            │
            ├── P > 0.60: HOLD ETF_current (suppress rotation)
            │                AI says "the current leader will reassert"
            │
            └── P ≤ 0.60: REBALANCE to ETF_new now
                             AI says "leadership is genuinely changing"
```

### Model Specification

- **Architecture:** Logistic Regression or XGBoost (depth=2, 50 trees)
- **Target:** Binary — will the current top-ranked ETF still be top-ranked in 21 trading days?
- **Features:**
  - Score gap: `score(ETF_current) - score(ETF_new)` (larger gap → more likely current stays #1)
  - Current ETF's momentum acceleration (S04 from STRATEGY_HYPOTHESES.md — is the trend strengthening?)
  - Days current ETF has been #1 (longer reign → more persistence, per flow persistence mechanism)
  - VIX level (high VIX → faster leadership changes)
  - Cross-sectional dispersion (high dispersion → clearer leader → more persistence)
- **Training window:** 60 months. Label computed from historical daily rankings.
- **Samples:** Many more than other modes — every day where the top-ranked ETF changes provides a training sample. Roughly 3-5 leadership changes per month = ~180-300 samples per 60-month window. This is the most data-rich mode.

### AIPrediction Output

```python
# Hold — current leader will persist
AIPrediction(
    date="2024-07-05",        # Friday close
    mode="rebalance_timing",
    action="defer",
    confidence=0.75,          # 75% chance current leader stays #1
    position_scale=1.0,       # stay in current holding
    shy_allocation=0.0,
    metadata={"current": "SOXX", "challenger": "QQQ", "score_gap": 0.032},
    disable_reason=None
)

# Rebalance — leadership is changing
AIPrediction(
    date="2024-10-04",
    mode="rebalance_timing",
    action="hold",            # "hold" means proceed with systematic signal
    confidence=0.42,          # only 42% chance current stays #1
    position_scale=1.0,
    shy_allocation=0.0,
    metadata={"current": "QQQ", "challenger": "XLE", "score_gap": -0.085},
    disable_reason=None
)
```

### Interaction with Monthly Rebalance

Mode E supplements but does not replace the monthly rebalance. On the scheduled monthly rebalance date, the strategy always rebalances to the current top-ranked ETF, regardless of AI prediction. Mode E only affects intra-month decisions:

- **Monthly rebalance day:** Always rebalance (AI irrelevant)
- **Non-rebalance Fridays:** AI decides whether to act on intra-week leadership changes
- **Maximum hold override:** If the AI has suppressed rebalancing for 2 consecutive months (8 weeks), force a rebalance on the next monthly date regardless. This prevents the AI from permanently locking the strategy into a deteriorating position.

### Automatic Disable Trigger

**Metric:** Compare Mode E's entry/exit timing vs pure systematic (monthly rebalance) on a rolling 12-month window.

**Measurement:** For each rotation event, compute the return difference between Mode E's entry date and pure systematic's entry date. If Mode E defers rebalancing by 2 weeks and the ETF it held gained 3% more than the one it should have switched to, Mode E earned +3%. If the ETF it held lost 4% relative, Mode E cost -4%.

**Trigger:** If Mode E's cumulative timing edge is negative over any rolling 12-month window, disable.

**Why this metric?** Mode E's entire value proposition is better timing. If its timing is worse than fixed monthly rebalancing over a full year, it's subtracting value.

### Failure Mode Analysis

| Failure | Detection | Impact | Response |
|---------|-----------|--------|----------|
| AI delays necessary rotation (2022 XLE entry delayed) | Compare entry timing vs pure systematic | Misses first 2-4 weeks of new trend → 3-8% cost | Negative timing edge triggers disable |
| AI triggers unnecessary rotations | Turnover rate > 2x pure systematic | Transaction costs + tax drag | If turnover > 2x for 6 months, disable |
| AI always says "hold" | Defer rate > 90% for 6 months | Equivalent to "never rebalance intra-month" | Acceptable but effectively not useful — log and review |
| AI always says "rebalance" | Defer rate < 10% for 6 months | Equivalent to weekly rebalancing → more turnover | Disable; use fixed monthly schedule |

---

## Mode Selection: Which Mode to Deploy

The five modes are not mutually exclusive in all combinations. Some can stack; others conflict.

### Compatibility Matrix

| | A (Confidence) | B (Veto) | C (Drawdown) | D (Regime) | E (Timing) |
|---|---|---|---|---|---|
| **A** | — | Conflict | Compatible | Compatible | Compatible |
| **B** | Conflict | — | Compatible | Conflict | Compatible |
| **C** | Compatible | Compatible | — | Compatible | Compatible |
| **D** | Compatible | Conflict | Compatible | — | Compatible |
| **E** | Compatible | Compatible | Compatible | Compatible | — |

**A + B conflict:** Both modify the position based on the systematic pick's quality. A sizes the position; B vetoes it entirely. Running both means the AI is sizing AND vetoing — they can issue contradictory signals (A says "high confidence, full position" while B says "veto, 100% SHY").

**B + D conflict:** Both can override the systematic pick at the same time. D fires at regime transitions and might reduce the position; B might simultaneously veto it. The interaction is undefined.

### Recommended Deployment Order

**Phase 1 — Deploy standalone, test each in isolation:**

| Priority | Mode | Rationale |
|----------|------|-----------|
| 1st | **Mode C** (Drawdown Shield) | Highest probability of adding value. Independent of rotation signal. Binary classification with known predictors. Easiest to validate. If it works, deploy it and stop — it may be all the AI the strategy needs. |
| 2nd | **Mode B** (Veto Only) | Second safest. Can only prevent losses. Validates whether the AI can rank ETFs at all. If Mode B's veto accuracy > 55%, it demonstrates the AI has some cross-sectional prediction ability. |
| 3rd | **Mode E** (Rebalance Timing) | Most data-rich mode (daily samples). Tests a different capability: can the AI predict leadership persistence? If S17 (weekly check + threshold) from STRATEGY_HYPOTHESES.md works well as a rules-based version, Mode E may not be needed. |
| 4th | **Mode A** (Confidence Gate) | Requires good calibration (ECE < 0.15). Only deploy after Mode C validates that the AI's probability estimates are trustworthy. |
| 5th | **Mode D** (Regime-Triggered) | Hardest to validate (fewest samples). Only deploy after the HMM regime model is proven useful independently of AI. |

**Phase 2 — Stack compatible modes:**

If Phase 1 validates multiple modes, the natural stacking is:

```
Mode C (Drawdown Shield)        ← always-on risk layer
  + Mode E (Rebalance Timing)   ← entry/exit timing improvement
  + Mode A (Confidence Gate)    ← position sizing overlay
```

Mode C runs independently. Mode E adjusts when to rebalance. Mode A sizes the position once the entry is decided. Each layer is orthogonal.

**Do NOT stack more than 2 modes initially.** Each additional mode increases the probability of conflicting signals and makes it harder to attribute performance to any single component.

---

## Fallback Hierarchy

When the AI layer fails — model corruption, data feed down, confidence consistently miscalibrated, or any automatic disable trigger fires — the system follows this hierarchy:

```
Level 0: Normal operation
    AI sidecar produces AIPrediction each signal date.
    Systematic strategy consumes it via the integration mode interface.
        │
        ▼ (failure detected)
        
Level 1: Disable specific mode
    The failing mode's AIPrediction is replaced with:
    AIPrediction(action="hold", position_scale=1.0, shy_allocation=0.0,
                 disable_reason="[specific trigger that fired]")
    Other modes (if stacked) continue operating.
        │
        ▼ (multiple modes failing OR data feed down)

Level 2: Disable AI layer entirely
    ALL modes return default AIPrediction (position_scale=1.0).
    Pure systematic strategy runs.
    Log the failure with timestamp, trigger, and last 12 predictions.
        │
        ▼ (systematic strategy itself has issues — data feed, execution)

Level 3: Emergency SHY
    If the systematic strategy cannot compute a signal (data feed down,
    corrupted prices, missing tickers), allocate 100% SHY.
    Alert operator immediately.
    Do NOT attempt to run any model on stale or corrupted data.
```

### Rules

1. **Failover is always toward simpler, not smarter.** Level 1 → Level 2 → Level 3 moves from AI-augmented to pure systematic to cash. Never attempt to "fix" a model mid-month.
2. **Failover is automatic.** No human intervention required for Level 1 or Level 2. Level 3 (emergency SHY) should alert the operator but execute immediately.
3. **Recovery requires validation.** After a disable, the mode is not re-enabled until it passes validation on fresh data (see recovery procedures in each mode section above).
4. **Logging is mandatory.** Every failover event saves to `/results/ai_monitor/failover_log.jsonl`:

```json
{
  "timestamp": "2024-08-01T00:00:00Z",
  "mode": "confidence_gate",
  "trigger": "gate_accuracy_below_60_pct",
  "level": 1,
  "last_12_predictions": [...],
  "action_taken": "mode_A_disabled",
  "systematic_continues": true
}
```

---

## Monitoring Dashboard

Every month, the system computes and logs to `/results/ai_monitor/monthly_report.jsonl`:

### Per-Mode Metrics

| Metric | Mode A | Mode B | Mode C | Mode D | Mode E |
|--------|--------|--------|--------|--------|--------|
| Active/Disabled | yes/no | yes/no | yes/no | yes/no | yes/no |
| Predictions made this month | count | count | count | count | count |
| Action taken this month | hold/reduce | hold/veto | hold/reduce/full_shy | hold/reduce | hold/defer |
| Rolling accuracy (mode-specific window) | gate accuracy (6m) | veto accuracy (12m) | precision@80recall (24m) | transition accuracy (3yr) | timing edge (12m) |
| Disable trigger distance | % from threshold | % from threshold | % from threshold | transitions/year | cumulative edge |

### System-Level Metrics

| Metric | Computation | Threshold |
|--------|-------------|-----------|
| AI contribution to returns | (AI-augmented CAGR - pure systematic CAGR) on rolling 12m | Must be > -2% (AI should not drag returns by more than 2%) |
| AI contribution to drawdowns | (AI-augmented max DD - pure systematic max DD) on rolling 12m | Must be < 0 (AI should reduce drawdowns) |
| Data feed health | % of required features successfully computed | Must be 100% on signal date |
| Model staleness | Days since last retrain | Must be < 180 days |

### Monthly Report Format

```json
{
  "report_date": "2024-08-01",
  "active_modes": ["drawdown_shield"],
  "disabled_modes": ["confidence_gate"],
  "ai_augmented_cagr_12m": 0.21,
  "systematic_only_cagr_12m": 0.22,
  "ai_contribution_12m": -0.01,
  "ai_augmented_max_dd_12m": -0.12,
  "systematic_only_max_dd_12m": -0.18,
  "drawdown_reduction": 0.06,
  "verdict": "AI reduces drawdown by 6% with 1% CAGR cost. Net positive on risk-adjusted basis."
}
```

---

## Ground Truth Logging (All Modes)

Every AI prediction, regardless of mode, saves a ground truth record to `/results/ai_monitor/predictions.jsonl`. This is non-negotiable — it is the only way to evaluate whether the AI adds value after the fact.

```json
{
  "date": "2024-07-01",
  "mode": "drawdown_shield",
  "prediction": {
    "action": "reduce",
    "confidence": 0.72,
    "position_scale": 0.50
  },
  "systematic_signal": {
    "top_etf": "SOXX",
    "score": 0.15,
    "rank_2": "QQQ"
  },
  "actual_outcome": {
    "top_etf_return": -0.08,
    "shy_return": 0.003,
    "was_drawdown": true,
    "actual_drawdown": -0.082
  },
  "counterfactual": {
    "pure_systematic_return": -0.08,
    "ai_augmented_return": -0.038,
    "ai_value_added": 0.042
  },
  "features": {
    "vix_level": 28.5,
    "vol_20d": 0.032,
    "momentum_63d": 0.05,
    "credit_z": 1.8
  },
  "model_metadata": {
    "model_type": "xgboost",
    "training_window": "2019-07 to 2024-06",
    "feature_count": 8,
    "ece": 0.09
  }
}
```

**The counterfactual is critical.** Every prediction logs what would have happened without AI (pure systematic return) and what actually happened with AI. This is the only honest way to measure AI value — not by looking at the AI-augmented returns in isolation, but by comparing to the no-AI baseline month by month.

---

## Connection to Systematic Strategy Improvements

The AI integration modes interact with the systematic strategy hypotheses from STRATEGY_HYPOTHESES.md. Some hypotheses are rules-based alternatives to AI modes:

| AI Mode | Rules-Based Alternative | Recommendation |
|---------|------------------------|----------------|
| Mode A (Confidence Gate) | S12 (Kelly Criterion Sizing) | Test S12 first. If Kelly sizing with momentum z-score achieves the same effect as AI confidence, the AI is unnecessary for position sizing. |
| Mode B (Veto Only) | S08 (Canary Universe) | Test S08 first. If EEM+AGG canary gate catches the same drawdowns the AI would veto, Mode B adds no value over a simpler rule. |
| Mode C (Drawdown Shield) | S14 (Volatility Targeting) + S13 (Trailing Stop) | Test S14 first. If volatility targeting reduces max drawdown to <20%, Mode C's incremental value shrinks. Mode C is worth deploying only if rules-based risk management leaves residual drawdowns >15%. |
| Mode D (Regime-Triggered) | S16 (VIX Regime Lookback) | Test S16 first. If VIX-adaptive lookback handles regime transitions, Mode D's complex HMM+AI approach is unnecessary. |
| Mode E (Rebalance Timing) | S17 (Weekly Check + Threshold) | Test S17 first. If a 3% hysteresis threshold achieves good timing without AI, Mode E is unnecessary. |

**Priority rule:** Always test the rules-based alternative first. If the rules-based version captures >80% of the AI mode's benefit, do not deploy the AI mode. AI should only be deployed for problems where rules-based approaches leave significant residual value on the table.

---

## Phase 8 Testing Protocol

### Pre-Requisites (Before Testing Any Mode)

1. Pure systematic backtest is validated and reproducible (known CAGR, Sharpe, max DD)
2. Walk-forward framework is implemented (60-month train, 6-month val, 3-month test, rolling)
3. Feature pipeline produces all required features without lookahead
4. Ground truth logging is implemented and tested
5. Rules-based alternatives (S12-S17) have been tested and their results are documented

### Test Sequence

**Step 1: Validate drawdown prediction signal exists (E04 + E05 from AI_IMPROVEMENT_PLAN.md)**

Before testing any integration mode, confirm that the AI can predict drawdowns at all. Run experiments E04 (XGBoost drawdown) and E05 (Logistic Regression drawdown). If both fail to beat random baseline (AUROC < 0.55), stop. No integration mode will work because the underlying signal doesn't exist.

**Step 2: Test Mode C standalone**

If E04/E05 show signal (AUROC > 0.60):
1. Implement Mode C with the best-performing model from E04/E05
2. Run walk-forward backtest: pure systematic vs systematic + Mode C
3. Measure: max drawdown reduction, CAGR impact, precision at 80% recall
4. **Pass criterion:** Max drawdown reduced by >5 percentage points AND CAGR drag < 3%

**Step 3: Test Mode B standalone**

If E01-E03 show cross-sectional prediction signal (Spearman > 0.05):
1. Implement Mode B with the best return-prediction model
2. Run walk-forward backtest with veto logic
3. Measure: veto accuracy, veto frequency, CAGR impact
4. **Pass criterion:** Veto accuracy > 55% AND veto frequency 10-25% of months

**Step 4: Test Mode E standalone**

1. Implement Mode E with Logistic Regression on daily leadership persistence
2. Run walk-forward backtest: fixed monthly rebalance vs AI-timed rebalance
3. Measure: timing edge, turnover change, CAGR impact
4. Compare to S17 (rules-based weekly check). If Mode E's edge over S17 is < 1% CAGR, use S17 instead.
5. **Pass criterion:** Timing edge > 0 over OOS period AND improvement over S17

**Step 5: Test Mode A standalone**

Only if Mode C or Mode B demonstrate calibrated probabilities (ECE < 0.15):
1. Implement Mode A with the same model used for the calibrated mode
2. Run walk-forward backtest: full position vs confidence-gated position
3. Measure: gate accuracy, CAGR impact, Sharpe impact
4. **Pass criterion:** Gate accuracy > 60% AND Sharpe improvement > 0.05

**Step 6: Test Mode D standalone**

Only if HMM regime model is validated separately (2-4 transitions per year, transitions align with known market regime shifts):
1. Implement Mode D with Ridge Regression at transition points
2. Run walk-forward backtest over transition events only
3. Measure: AI accuracy at transition months vs systematic baseline
4. **Pass criterion:** AI-adjusted return > systematic return in >60% of transition months

**Step 7: Stack compatible modes**

If 2+ modes pass individually:
1. Stack Mode C + best-performing other mode
2. Run walk-forward backtest of stacked configuration
3. Measure: combined CAGR, max DD, Sharpe vs pure systematic
4. **Pass criterion:** Sharpe improvement > 0.10 over pure systematic

### Decision Framework

After all steps, classify the result:

| Outcome | Decision |
|---------|----------|
| No mode passes Step 2-6 individually | Ship without AI. The systematic strategy is sufficient. Document findings. |
| Only Mode C passes | Deploy Mode C as drawdown shield. All other AI disabled. |
| Mode C + one other mode pass | Deploy Mode C + the other mode stacked. Monitor for 6 months. |
| Multiple modes pass | Deploy Mode C + best complementary mode. Do NOT deploy more than 2 modes simultaneously in the first year. |

### The Honest Prediction

Based on the diagnosis in AI_IMPROVEMENT_PLAN.md:

- **Mode C (Drawdown Shield):** 60% chance of passing. Drawdowns have learnable precursors. This is the AI's most likely contribution.
- **Mode B (Veto Only):** 30% chance of passing. Requires cross-sectional return prediction, which is harder with 60 monthly samples.
- **Mode E (Rebalance Timing):** 40% chance of passing, but likely no better than S17 (rules-based weekly check + threshold). The rules-based version should be tested first.
- **Mode A (Confidence Gate):** 25% chance of passing. Requires calibrated probabilities, which are hard to achieve with small samples.
- **Mode D (Regime-Triggered):** 15% chance of passing. Too few regime transitions to train on. The concept is sound but the data is insufficient.

**Most likely outcome:** The system ships with Mode C (drawdown shield) as the only AI component, or with no AI at all. The systematic strategy's 23% CAGR and 0.96 Sharpe is already strong. The AI's realistic role is reducing the -28.4% max drawdown to -15 to -20%, not improving CAGR.

---

## Implementation Checklist

### Infrastructure (Build Before Any Mode)

- [ ] `AIPrediction` dataclass and serialization
- [ ] Integration mode interface in the systematic strategy (read AIPrediction, apply position scaling)
- [ ] Fallback logic (missing prediction → pure systematic)
- [ ] Ground truth logging pipeline (`predictions.jsonl`)
- [ ] Monthly monitoring report generation
- [ ] Automatic disable trigger framework (rolling window metrics + threshold checks)
- [ ] Failover logging (`failover_log.jsonl`)

### Per-Mode Implementation

- [ ] **Mode C:** Feature pipeline (VIX, vol, credit spread, momentum features) → XGBoost/LogReg drawdown model → Platt scaling → threshold logic → AIPrediction
- [ ] **Mode B:** Cross-sectional feature pipeline → return prediction model → rank derivation → veto logic (with first-month exemption) → AIPrediction
- [ ] **Mode E:** Daily ranking computation → leadership persistence model → hold/rebalance logic → AIPrediction
- [ ] **Mode A:** Confidence model → calibration (temperature/Platt) → ECE check → threshold selection → AIPrediction
- [ ] **Mode D:** HMM regime model → transition detection → transition-conditional Ridge Regression → AIPrediction

### Validation (After Implementation)

- [ ] Each mode tested in isolation with walk-forward backtest
- [ ] Each mode compared to its rules-based alternative (S12-S17)
- [ ] Each mode's automatic disable trigger tested on historical failure scenarios
- [ ] Stacked configurations tested if individual modes pass
- [ ] Final decision documented in `/results/EXPERIMENT_RANKING.md`
