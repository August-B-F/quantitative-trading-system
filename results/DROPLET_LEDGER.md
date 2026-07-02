# DROPLET LEDGER — every measured basis point for the relaunch

Generated 2026-07-02 from seven pre-registered studies under
`research/droplets/` (all through the daily-ledger engine, hypotheses
committed before any run, trials merged into `results/TRIAL_LEDGER.csv`).
Every number below is net of costs at the stated bps/side.

## ADOPTED — implemented in this tree

| # | Droplet | Impact (bps/yr) | Confidence | Where |
|---|---------|-----------------|------------|-------|
| 1 | **blend_126_252 ranking** replaces pinned 63d momentum | **~+250 dev** (Sharpe +0.074/+0.103 @10/20bps; validation look 0.822 vs 0.64 bar) | measured, validated | [src/strategy/rotation.py](../src/strategy/rotation.py), [candidate_blend_rotation.yaml](../configs/strategies/candidate_blend_rotation.yaml) |
| 2 | **4-tranche staggered rebalance** (+0/+5/+10/+15 td) | 0 EV, removes ~2/3 of ±150-260 bps/yr date-luck dispersion; avoids 209 bps/yr median-vs-p5 regret; cost ≈ -2 bps/yr (free) | measured | rotation.py `build_tranched_schedules`, candidate config |
| 3 | **Executor cash-drag pack**: plan headroom 0.99→0.998, buy headroom 0.995→0.999, residual sweep into largest buy leg, new-position noise-gate exemption | **+11 avg, up to +30** on books with sub-1% legs | measured (1.10% mean idle, median exactly 1.000%) | [executor.py](../src/execution/executor.py) `PLAN_EQUITY_HEADROOM`/`BUY_CASH_HEADROOM`/sweep |
| 4 | **Keep next-open fills** (confirmed vs next-close) | +64 to +136 vs the alternative | measured (t≈1.8-1.9) | no change needed — ledger + executor already correct |
| 5 | **Execution promptness protection** (locks, watchdog, freshness gates already built) | ~+72 to +145 per avoided slipped day | measured | already shipped in the hardening pass |
| 6 | **Keep SHY as the gate park** (vs SHV/BIL/menu) | +20 full-window vs SHV (costs ~2-3pp deeper gate-period DD, e.g. 2022) | measured | no change — already the spec |

## REJECTED — measured, would have LOST money (kept per constitution rule 7)

| Droplet | Measured damage | Study |
|---------|-----------------|-------|
| Vol-targeting overlay on a gated rotation | -159 to -461 bps/yr CAGR, Sharpe -0.05..-0.09 (gate/vol-target redundancy) | study5 |
| Vol-adjusted momentum ranks in this universe | **-580 bps/yr** dev (pushes ranks into SHY/GLD) | study4 |
| Rank hysteresis / no-trade bands | dev win reversed on validation: -129 bps/yr; two-sleeve bands lose even on dev | study3 |
| Defensive menu park (trend-picked SHY/IEF/GLD, 50/50 IEF/GLD, SHV) | fails +0.05 Sharpe bar; trend-menu strictly worse (-0.14 Sharpe) | study5 |
| Two-sleeve respec (all 10 configs: trend ensembles, Faber SMA, equal-weight, vol-target/frac variants) | best 0.846 dev vs 0.901 bar — **death certificate**; direction closed | study7 |
| Twin substitution SMH↔SOXX | TE 6.6% > 6% cap for ~1 bp/yr saved | study1 |
| Close-pegged marketable limit orders | ~-130 bps/yr chase cost vs ~5 bps/yr saved (39-44% open-miss rate) | study1 |
| NOISE_FRACTION 0.01→0.005 | fails pre-declared drift threshold (0.471% < 0.5%); ~1 bp/yr cost | study6 |
| MOC-next-day fills | -64 to -136 bps/yr vs next-open | study1 |

## LEADS — recorded for future pre-registered specs (not actioned)

| Lead | Potential | Constraint discovered |
|------|-----------|----------------------|
| Pre-close signal + `cls` (market-on-close) auction orders on decision day | ~+46-50 bps/yr (overnight-gap capture; top-1 leg t=0.98 — weak) | Alpaca `cls` cutoff 15:50 ET; **whole-share qty only** (notional/fractional = `day` TIF only); needs 15:40-price-vs-close signal-flip shadow study first |
| `opg` (market-on-open) auction orders for backtest-exact open fills | fidelity + a few bps of post-open drift | same whole-share constraint; sells+buys in one auction needs buying power upfront (cash-account conflict) — test on one paper account |
| Drop VGT from the universe (XLK twin) | ~+5-10 bps/yr turnover savings, dev Sharpe unchanged | missed pre-declared bar by a hair; belongs in a future ex-ante universe spec |
| 50/50 IEF/GLD gate park as a lower-DD variant | +143 bps CAGR dev but uncompensated risk; -2pp MaxDD | must pass a 2022-style rates-up stress in its own spec |
| Cross-strategy trade netting at the executor (9 accounts often trade the same tickers opposite ways on the same day) | unmeasured | needs a shared-execution design; per-account isolation currently intentional |

## EXPECTATIONS CALIBRATION (study 2 — read before judging live results)

Month-end (offset 0) was the **luckiest of all 10 rebalance days** on this
sample for both untuned reference rules — the very shape the old stress
report sold as "month-end is load-bearing." Consequences:

- Haircut ANY single-date month-end backtest by **~200-260 bps/yr CAGR /
  ~0.15-0.18 Sharpe** when setting forward expectations.
- The blend candidate's honest forward numbers are the 4-tranche book's
  (2018+: Sharpe 0.788 / CAGR 13.7% / MaxDD -24.3% @10bps), NOT the
  single-date 0.822 — and EVALUATION.md sets the race expectation at
  net Sharpe 0.6-0.8 accordingly.
- Never compare two candidates backtested on different rebalance days.

---

# FRONTIER ROUND (2026-07-02, second batch — owner-authorized budget expansion)

Nine workstreams: universe legitimacy, real intraday data, calendar
effects, weekly breadth, arm portfolios, race power, Swedish tax
structure, CLS auction mode, live tranche wiring. Studies under
`research/droplets/study8..15`; full agent evidence in each folder.

## Adopted / implemented

| Finding | Impact | Where |
|---|---|---|
| **Deterministic rank tie-break** (study8 exposed ±0.085 dev Sharpe of pure tie-order ambiguity; the quoted dev 1.005 was tie-break luck, production unstable-sort scored 0.920). Fixed: ties → higher 252d return → ticker; ONE principled rule tried, not scanned. Re-quoted production numbers: dev 0.993/0.943 @10/20bps (adoption bar vs pin_63 0.931/0.855 HOLDS), validation-window 0.803, full 0.898, 4-tranche book 0.830/-24.4% | spec-completion; all candidate claims now describe the code that trades | [rotation.py](../src/strategy/rotation.py), candidate yaml |
| **Live tranche wiring**: candidate now tradeable behind `engine: rotation` in accounts.yaml — tranche state at logs/tranche_state.json, same freshness gates/locks/exit codes, provably dormant until wired (33 tests) | closes the config-exists-but-can't-trade gap | [run_rebalance.py](../scripts/run_rebalance.py) |
| **Automated race report** + power-corrected verdict language (11 tests) | ops | [run_race_report.py](../scripts/run_race_report.py) |
| **Dormant CLS/OPG auction executor** + whole-share client methods (11 tests; NOT enabled — flip-study bar failed) | ready if a live shadow study ever passes | [auction_executor.py](../src/execution/auction_executor.py) |
| **Corrected month-12 race rule** (study13: the 0.20-Sharpe rule has 34% FPR / 50-57% FNR; 80% power unreachable at 240 months) — promotion now judges fidelity/drawdown/process; paired-difference CI is the only quoted statistic | prevents a coin-flip promotion decision | EVALUATION.md §4 |
| **Ex-ante universe rule** (study8 deliverable) adopted for ALL future specs: one largest-AUM fund per fixed written category list, ≥15y history, no thematic funds unless the hypothesis is the theme, membership only by re-running the written rule | ends hindsight-universe selection | below + EVALUATION.md |

## Reframed (the biggest finding of the round)

**blend_126_252 is NOT universe-robust** (study8, 40 ledger backtests):
applied verbatim to ex-ante universes it adds ~0 Sharpe over its own
SMA200 gate (U2 sectors: FAIL by -0.12..-0.21; U3 cross-asset: ±0.00).
The incumbent universe's excess (+0.11-0.16 Sharpe over gate) is **tech-block
composition** — the risk-on book is ~78% one theme, and dropping SOXX alone
changes nothing (the block, not the semis leg, carries it). The candidate
stays in the race because it clears its bars *as a gated tech book*, but
every document now names it that, and the dominant risk is a multi-year
tech bust, not signal decay. Rule-built universes deliver gate-level
Sharpe ~0.6-0.75 — that is the honest expectation for any future
universe-legitimate strategy.

## Measured and confirmed (execution reality, study9 — 10.5y of SIP minute data)

- Market-at-open slippage vs the backtest's auction-open assumption:
  **±0.6 bps mean** on all six symbols — the executor's immediate-at-open
  market orders are effectively free; folklore refuted, no change.
- Afternoon spreads are 2-4x tighter than the open on SOXX/XLE — but the
  saving (~1-2 bps/side) never justifies delay (drift costs more).
- Alpaca keys serve **full SIP consolidated data from 2016** (not just IEX)
  — future execution studies should use `feed=sip, adjustment=split`.
- 15:45-signal staleness flips the top-3 on only **6.8%** of decision days
  (real minute data) vs the 27.5% full-day proxy — the CLS lead's flip
  risk was overstated by the daily-data bracket, but the pre-registered
  bar binds: CLS stays dormant pending a live shadow study.

## Killed this round (all pre-registered, all logged)

| Idea | Where it died |
|---|---|
| Weekly cross-sectional breadth (39 ETFs, 10 configs) | the SIGNAL: dev 0.594 vs 0.90 bar; 0.692 even at ZERO cost — execution can't revive it; every axis rewarded trading less |
| Turn-of-month SPY | half1 net Sharpe 0.27 < 0.4 bar (gross edge real, t=2.2, too small) |
| Overnight QQQ | costs: gross Sharpe 0.94 (t=4.4!) → net 0.14 at 2 bps/side; passes at 1 bp/side — recorded as an execution-measurement lead only |
| Pre-FOMC drift | post-2015 decay: half2 0.36 < 0.4 (classic arbitraged-away signature) |
| Portfolio-of-arms books | dilution, not diversification: best book 0.902 vs blend 0.969 (arms correlate 0.65-0.85); books do cut MaxDD 1.8-2.7pp — recorded for a drawdown-constrained future |
| CLS auction execution (enable) | pre-registered flip bar failed on the daily proxy (72.5% vs 90%); implementation shipped dormant |

## The wrapper lever (study14 — likely the largest single real-money number)

For real Swedish money at 12% CAGR: **ISK beats the Alpaca depå by +134
to +240 bps/yr** (10-year horizon, 100k-3M SEK), the first ~300k SEK is
schablon-tax-free (2026 allowance), and the depå structurally punishes
this exact strategy (8x turnover destroys deferral: -50..-180 bps/yr vs
buy-and-hold before any alpha). Critical implementation detail: **broker
FX handling swings ~190 bps/yr** (Avanza auto-FX 0.25%/trade vs Nordnet
valutakonto 0.075%) and flips the sign in the low-CAGR corner. PRIIPs
still blocks US ETFs; the UCITS mapping is TER-neutral with two real gaps
(no IGV twin; SMH-UCITS crosses indices). Manual execution at ~48 short
sessions/yr is viable — the pipeline emits tickets, the human clicks.
Full analysis + migration plan: `docs/REAL_MONEY_SWEDEN.md`.

## Net effect on the relaunch

Adopted engineering droplets: **~+11-30 bps/yr hard cash** + large variance
reduction (tranching) + confirmed-optimal execution conventions. Adopted
signal change: blend_126_252, the only candidate that survived
pre-registration, a +0.05-Sharpe dev bar, 12/12 leave-one-year-out checks,
a lookback-cliff robustness test, and a clean one-shot validation.
Five ideas that would have silently cost 130-580 bps/yr are now
documented rejections instead of live positions.
