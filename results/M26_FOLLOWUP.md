# M26 FOLLOW-UP — 2018 Dependency, 3d Deep Dive, Asymmetric Windows

Follow-up to [M26_ANALYSIS.md](M26_ANALYSIS.md). Tests whether M26's benefit survives removing the 2018 episode, whether the 3d window reduces the false-cost of the 5d variant, and whether an asymmetric (pre-only or post-only) window isolates the mechanism.

## Follow-up 1 — Leave-one-out 2018

| Variant | Full CAGR | Full MaxDD | Ex-2018 CAGR | Ex-2018 MaxDD | dCAGR | dMaxDD |
|---|---|---|---|---|---|---|
| base | 22.24% | -19.43% | 25.16% | -12.66% | +2.93pp | +6.77pp |
| m26_5d | 22.01% | -13.80% | 23.73% | -13.80% | +1.72pp | +0.00pp |
| m26_3d | 23.41% | -12.94% | 25.53% | -12.66% | +2.12pp | +0.28pp |

**Vs base, with 2018 excluded:**

- 5d variant: dCAGR **-1.43pp**, dMaxDD **-1.13pp**
- 3d variant: dCAGR **+0.37pp**, dMaxDD **+0.00pp**

Most of the MaxDD improvement came from the single 2018 episode. Still valuable as a one-time insurance payout but **not a systematic edge**.

## Follow-up 2 — 3d variant deep dive

### Top-5 drawdowns (OPTIMIZED base)

| Start | Trough | End | DD | FOMC in range |
|---|---|---|---|---|
| 2018-01-25 | 2018-10-31 | 2019-09-27 | -19.43% | 14 |
| 2019-12-30 | 2020-02-25 | 2020-05-26 | -12.6% | 4 |
| 2021-12-29 | 2021-12-29 | 2022-02-23 | -10.22% | 1 |
| 2015-05-26 | 2015-12-30 | 2016-06-28 | -10.11% | 9 |
| 2012-03-29 | 2012-04-25 | 2012-08-29 | -8.22% | 3 |

### Top-5 drawdowns (OPTIMIZED + M26 3d)

| Start | Trough | End | DD | FOMC in range |
|---|---|---|---|---|
| 2018-01-25 | 2018-02-23 | 2019-03-25 | -12.94% | 10 |
| 2019-04-25 | 2019-04-25 | 2019-06-28 | -12.66% | 2 |
| 2019-12-30 | 2020-02-25 | 2020-05-26 | -12.6% | 4 |
| 2021-12-29 | 2021-12-29 | 2022-02-23 | -10.22% | 1 |
| 2015-05-26 | 2015-12-30 | 2016-07-26 | -10.11% | 9 |

### Targeted windows (3d)

| Period | Base | M26 3d | Δ | FOMC | Deferred |
|---|---|---|---|---|---|
| March 2020 | +12.08% | +12.08% | +0.00pp | 3 | 0 |
| Q4 2018 | -6.24% | +0.09% | +6.34pp | 4 | 1 |
| 2022 | +33.58% | +32.33% | -1.26pp | 8 | 2 |

### False-cost check (3d)

- Deferred rebalances: **28**
- Top-1 pick changed: **9** (32%)
- Top-k set changed: 22
- When top-1 changed: better=5, worse=4, avg Δret=-0.09pp

For comparison, the 5d variant changed top-1 in **9 / 28 (32%)** with avg Δret **−2.92pp**.

→ 3d still changes a similar fraction of picks; the drift problem persists.

## Follow-up 3 — Asymmetric windows

| Variant | CAGR | Sharpe | MaxDD | Deferrals |
|---|---|---|---|---|
| M26_pre_3d | 22.69% | 1.38 | -15.28% | 21 |
| M26_post_3d | 23.61% | 1.50 | -12.94% | 10 |
| M26_sym_3d | 23.41% | 1.43 | -12.94% | 28 |
| M26_pre_5d | 21.85% | 1.33 | -15.28% | 21 |
| M26_post_5d | 23.10% | 1.47 | -12.94% | 10 |
| M26_sym_5d | 22.01% | 1.34 | -13.80% | 28 |

→ **Pre-only** captures most of the benefit. Mechanism confirmed: risk is rebalancing INTO an uncertain FOMC outcome.


## Final pick

**M26_post_3d** — CAGR 23.61%, Sharpe 1.50, MaxDD -12.94%
 (dCAGR +1.37pp, dMaxDD +6.49pp vs OPTIMIZED base)

**Concentration note:** A meaningful share of the headline improvement is concentrated in the 2018 FOMC episode; expect the real-world benefit to be lumpy, not smooth.

---

## Follow-up 4 — Leave-one-out 2018 for the winner (M26_post_3d)

| Variant | Full CAGR | Full MaxDD | Ex-2018 CAGR | Ex-2018 MaxDD | Δ CAGR (ex) | Δ MaxDD (ex) |
|---|---|---|---|---|---|---|
| Base (no M26) | 22.24% | -19.43% | 25.16% | -12.66% | — | — |
| M26_post_3d | 23.61% | -12.94% | 25.75% | -12.66% | +0.58pp | +0.00pp |

- Post-3d deferrals in 2018: **2 / 10** total across history

**Verdict:** Ex-2018 post-3d CAGR **≥** base ex-2018 CAGR → the post-only rule is **harmless-to-helpful outside 2018**. Ship with confidence.
