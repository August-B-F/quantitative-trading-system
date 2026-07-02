# STUDY 5 — Vol Targeting + Defensive Menu overlays on the untuned 63d top-3 rotation

Date: 2026-07-02. Author: study5 droplet (Claude research subagent).
Engine: `src/backtest/ledger.py::run_ledger_backtest` (daily_ledger_v1). Cash sleeve: SHV (ledger default; real tradable ETF, incurs costs; pre-2007-01-11 SHV rows are absent -> zero-return cash, per engine semantics).
Costs: every number reported at BOTH 10 bps/side and 20 bps/side.
Named naive baseline (Constitution rule 4): SPY/SMA200 (results/BASELINES.md net Sharpe 0.83 full window). This study measures OVERLAYS vs the fixed base rule; the base itself is also compared against spy_sma200 for context.

## Windows (fixed ex-ante)

- DEV (design/selection): decisions 2005-01-01 .. 2017-12-31, NAV window ends 2017-12-31. First decision is the first month-end at which ALL signal inputs have full history (SPY >= 200 bars; every risk asset and every defensive-menu asset >= 127 bars) — expected ~2005-10-31. All configs share the identical decision calendar so comparisons are like-for-like.
- VALIDATION (one look): 2018-01-01 .. latest available (2026-06-30/07-01). Exactly ONE validation execution, run on the single pre-declared final pick. The same execution also runs the BASE rule on the validation window as the comparator — the base is fully fixed ex-ante in this file (nothing about it is selected on dev), so this comparator does not constitute a second look. If no overlay passes the dev decision rule, the study is a null result and NO validation look is taken.

## Base rule (fixed ex-ante, no tuning, defined so this study stands independent of Study 4)

Universe (ex-ante, the live strategies' universe): risk assets R = [SOXX, QQQ, XLK, VGT, IGV, XLE, GLD]; park asset = SHY.
Monthly decision at each month-end (last trading day of the month on SPY's calendar), traded next open by the ledger engine. All signals use adj_close data strictly <= decision date.

1. GATE: risk-on iff SPY adj_close (last value) > mean of SPY's last 200 adj_close values (SMA200). Else risk-off.
2. RISK-ON: rank R by 63-trading-day total return r63 = P[-1]/P[-64] - 1; take top 3; weight each by inverse 63d realized vol (std of last 63 daily pct returns, ddof=1, annualized sqrt(252)), normalized to sum to 1.0.
3. RISK-OFF (base): 100% SHY.

## Hypotheses and configs (budget: 8 distinct configs total, <= the 10 allowed; no extras beyond these 8)

### A. Portfolio vol targeting (Moreira-Muir 2017; Barroso & Santa-Clara 2015)
Expectation stated before running: the base is a concentrated tech/semis book (~20-25% realized vol). Scaling exposure by s = min(1, target / realized_63d) should cut 2008-type crash participation and lift Sharpe at the cost of CAGR; the 10% target will likely give the biggest Sharpe lift but the biggest CAGR sacrifice; extra monthly re-scaling turnover may erode the edge at 20 bps.

Mechanics: at each decision, after computing target weights w (risk-on OR risk-off — the overlay applies to the whole book), compute realized vol = annualized std (ddof=1) of the implied portfolio daily returns over the trailing 63 days holding w constant (per-asset daily pct returns, missing day = 0; same construction as `src/strategy/sleeves.py::_vol_target_scale`). Scale ALL scheduled weights by s = min(1, target/realized); the remainder (1-s) is left unscheduled and falls to the SHV cash sleeve. No leverage.

- A1: target 10% ann
- A2: target 12% ann
- A3: target 15% ann

### B. Defensive menu when the gate is risk-off
Expectation stated before running: dev risk-off spans 2008-09/2010/2011/2015-16 — a bond-and-gold-friendly era, so IEF/GLD parks should beat SHY on dev; the honest test is 2022 in validation, where bonds failed as the hedge. The trend-filtered menu (B1) is the one with a mechanism to adapt; the static 50/50 (B2) is the fragile one.

- B1 (trend menu): park 100% in argmax of 126-trading-day total return over {SHY, IEF, GLD} (SHY is in the menu, so "else SHY" is automatic when neither IEF nor GLD out-trends it).
- B2 (static): park 50% IEF / 50% GLD.
- B3 (SHV): park 100% SHV.

### C. Combined
- C1: best passing A + best passing B stacked (defensive park replaced per best B; vol-target scale applied to the whole book per best A, including defensive parks). Exactly 1 config, run only after A and B results are read.

## Decision rule (pre-registered; not to be edited after results)

- An overlay config PASSES iff, on DEV: Sharpe(config) >= Sharpe(base) + 0.05 at BOTH 10 bps and 20 bps, AND |MaxDD(config)| <= |MaxDD(base)| + 1.0 percentage point at 10 bps.
- Best A = passing A config with highest dev Sharpe at 10 bps (tie -> higher at 20 bps). Same for Best B.
- If both an A and a B pass: run C1 on dev. Final pick = C1 if C1 itself passes the same rule; otherwise final pick = whichever of best-A / best-B has the higher dev Sharpe at 10 bps.
- If only one branch passes: final pick = that branch's best config (C1 is not run; it would equal it).
- KILL: if no A and no B passes, the idea is dead — report null, take no validation look.
- Validation is reported verbatim (10 & 20 bps, year-by-year for the final pick). Validation does not change the pick; it is the honesty check for the relaunch candidate.

## Measurements reported
cagr / vol / sharpe / max_dd / ann_turnover / ann_cost_drag from ledger stats, per config, per cost level, dev window; year-by-year calendar returns for the final pick (dev + validation) and base. Every config evaluated gets a row in trials.csv (engine=daily_ledger_v1).
