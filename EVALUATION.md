# EVALUATION — Relaunch Race Protocol

Governs the paper-trading race that replaces the voided 2026 H1 record
(`docs/POSTMORTEM_2026H1.md`). Operator steps live in
`docs/RELAUNCH_RUNBOOK.md`. Rules of research conduct live in
`CONSTITUTION.md`.

## 1. Arms — max 5

| Arm | Role | Selection rule |
|---|---|---|
| GEM dual momentum (Antonacci 12-1m) | **permanent control** | always runs |
| SPY/SMA200 trend (SPY above 200d SMA else SHY) | **permanent control** | always runs |
| Candidate 1..3 (at most 3) | challengers | must pass BOTH gates below before entry |

**Entry gates for candidates** (evaluated on daily-ledger-engine numbers,
net of 20 bps, before the race starts):

- **DSR gate:** Deflated Sharpe ≥ 0.95 against the cumulative
  `results/TRIAL_LEDGER.csv` trial count
  (`scripts/research/deflated_sharpe.py --ledger results/TRIAL_LEDGER.csv`).
- **SPA gate:** beats its named naive baseline (CONSTITUTION rule 4)
  with statistical significance (paired bootstrap, 95% CI on the edge
  strictly above zero).

If fewer than 3 candidates pass, run fewer. An empty candidate list is
an acceptable outcome: the controls run alone and the research layer
goes back to work.

### Current lineup (set 2026-07-02 after the droplet studies)

| Arm | Status | Basis |
|---|---|---|
| GEM dual momentum | control | permanent |
| SPY/SMA200 trend | control | permanent |
| **candidate_blend_rotation** (blend_126_252, 4-tranche, deterministic tie-break) | candidate | survived Study 4 pre-registration + one-shot validation (production numbers: dev 0.993 vs incumbent 0.931; validation-window 0.803; full 0.898 vs 0.83 bar); SPA vs SPY/SMA200 p=0.008, vs GEM p=0.059 (study 13) |
| two_sleeve | **retired before entry** | Study 7 death certificate — stays in `results/BASELINES.md` as a baseline only |

**What the candidate IS (study 8, binding language for all race
documents):** a *gated tech-concentration book* — its risk-on holdings
average ~78% in the correlated 5-fund tech block, and the chassis applied
verbatim to ex-ante universes adds ~0 Sharpe over its own SMA200 gate.
The gate supplies the drawdown control; the universe supplies the return.
Do not describe it as a momentum edge. Its dominant risk is a multi-year
tech-theme bust, which no backtest window since 2005 contains at full
severity.

**Funding structure (study 12):** race the arms in separate paper
accounts for evaluation fidelity, but at real-funding time capital goes
to the promoted arm ALONE — every fixed-weight book of these arms was
measured as Sharpe dilution (arms correlate 0.65–0.85; ~1.3 independent
bets). If a genuinely low-correlation arm ever exists, fund a combined
book through ONE netted account, never parallel accounts.

DSR caveat, recorded honestly: at the cumulative ledger count (~741
trials) no strategy in this repo clears DSR ≥ 0.95, including the blend
candidate — the entry is justified by its *pre-registered out-of-sample
validation pass*, which the DSR formula does not credit. The race itself
is the arbiter; the gate stands for future candidates without a clean
validation look.

**Expectations calibration (Study 2, `results/DROPLET_LEDGER.md`):**
single-date month-end backtests on this sample carry ~+0.15–0.18 Sharpe
(~200–260 bps/yr CAGR) of rebalance-date luck. The blend candidate's
honest forward expectation is the 4-tranche book: **net Sharpe ≈ 0.6–0.8,
MaxDD budget -30%** — judge the race against that, not against 1.0.

## 2. Window and change policy

- **12 months**, monthly rebalance at natural cadence (month-end for
  monthly arms; SMA-cross for the trend control). No early promotion.
- **No parameter changes** during the window. The only permitted code
  change to a running arm is a **spec-conformance bug fix** (the live
  implementation deviates from the committed hypothesis file). Every
  such fix is logged in the rebalance log with before/after positions.
- Accounts start reset at $100k (runbook §1). One strategy per account.

## 3. Monthly checks (first week of each month)

| Check | Method | Threshold / action |
|---|---|---|
| **Implementation fidelity** | Re-run the daily-ledger engine on the same signals the live system claims it traded; compare simulated vs realized account return | **Alert if divergence > 50 bps/month**; investigate before next rebalance |
| **Signal freshness (retro)** | `as_of` of each executed rebalance vs rebalance date | any gap > 3 trading days ⇒ incident, arm's month flagged |
| **Realized vol vs target** | trailing realized vol vs spec target | > 1.5x target ⇒ investigate sizing |
| **Drawdown tripwires** | account equity vs its high-water mark | **-20%: de-risk the arm 50%** (halve exposure) · **-25%: halt the arm** (to SHY/cash, stays in race as a halted record) |
| **Execution errors** | submit errors, unfilled orders, retries, lock violations from `logs/rebalance_log.json` | **target 0**; any error ⇒ fix before next rebalance |
| **spy_return recorded** | `logs/monthly_comparison.csv` benchmark column non-empty | empty ⇒ ops bug, fix |

## 4. Promotion / kill decision table (at month 12)

**Power correction (study 13, block-bootstrap on the actual arm returns):**
a 12-month Sharpe race CANNOT resolve a 0.20 edge — the literal rule has a
~34-35% false-positive rate and ~50-57% false-negative rate, and 80% power
is unreachable even at 240 months. The 12-month window therefore judges
**implementability, not alpha**; the candidate's statistical case was made
on 19.4 years of history (SPA p=0.008 vs SPY/SMA200) and is not
re-litigated by 12 noisy months.

Primary criteria (ALL must hold to promote):

| Criterion | Bar |
|---|---|
| Implementation fidelity | live vs ledger-sim divergence ≤ 50 bps/month, every month |
| Drawdown discipline | tripwires never breached without the prescribed de-risk/halt response |
| Process compliance | 0 unresolved execution errors, 0 freshness incidents, 0 unlogged parameter changes |
| Risk behavior | realized vol and holdings concentration within spec expectations |

Sharpe is a **tiebreak only**, and the only significance number ever
quoted is the *paired daily-difference* statistic with its bootstrap CI
(the highest-power instrument available; still underpowered — say so).

| Outcome after 12 months | Decision |
|---|---|
| All four criteria pass | **Promote**: eligible for real capital sizing (see `docs/REAL_MONEY_SWEDEN.md` for the wrapper decision) |
| Fidelity or process failures | **Fix and extend** 6 months; failures are ops findings, not strategy findings |
| Candidate breaches -25% halt | **Kill** the arm; log per CONSTITUTION rule 7 |
| Candidate's paired-difference CI vs BOTH controls sits materially negative | **Kill** — the one Sharpe-based kill branch, requiring the CI, not the point estimate |
| Candidate tripped -25% halt | **Kill**, regardless of recovery |
| Fidelity check failed > 2 months (divergence > 50 bps unexplained) | **Void that arm's record**, fix plumbing, restart the arm |
| Both controls beat every candidate | Fund nothing; the research process itself goes under review |

## 5. Reporting

- Monthly one-pager appended to `logs/` (equities, checks table,
  incidents). Numbers quoted with DSR per CONSTITUTION rule 3.
- No mid-race leaderboard commentary in specs or configs — criteria are
  frozen (CONSTITUTION rule 8).
