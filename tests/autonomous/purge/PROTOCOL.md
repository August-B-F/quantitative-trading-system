# OVERFITTING PURGE PROTOCOL

Scheduled to run after 3-hour pause. User instruction (verbatim) follows.
**The "full stack" target is the CURRENT robust champion P59** (30.73/1.88/-12.66) —
the protocol references P55 but since the session has moved on, treat P59 as
the full stack. P59 is documented in `tests/autonomous/champions/p59_champion.py`
and `tests/autonomous/BEST.md`.

The user's preference is clear: **prefer a slightly worse, robust strategy
over a slightly better, overfit one**. Be aggressive in stripping.

---

OVERFITTING PURGE PROTOCOL

Read /tests/autonomous/BEST.md and the full P59 champion recipe.
Read /tests/autonomous/champions/ for all champion scripts.

The champion has many stacked modifications on top of the canonical baseline.
Your job: strip it down to only what's real. Be aggressive. It's better
to ship a slightly worse strategy that's robust than a slightly better
one that's overfit.

## SETUP — list every individual modification in the stack as a numbered layer

Example (real list will follow exact P59):
  L1: drop VGT/XLK from universe
  L2: 62/38 split (was 50/50 baseline)
  L3: classifier confidence gate 0.40
  L4: rank aggregation (42:1, 63:3, 126:1) replacing pure 63d
  L5: regime-conditional transition universe (TLT, AGG, XLV, XLF)
  L6: classifier extra features (credit, yc, copper/gold)
  L7: FOMC window pre=0 post=1 defer=4 (replacing canonical post=2 defer=3)
  L8: self-DD adaptive sizing (3m/-2% trigger → top1=0.40)
  L9: asymmetric Kelly boost (9m/+30% OR SPY63d/+12% → top1=0.82)
  L10: warm boost (6m/+25% OR SPY21d/+10% → top1=0.70)
  L11: tier-proba universe selection (proba >= 0.50 for trans-universe)

Save this layer list to /tests/autonomous/purge/LAYERS.md.

## TEST 1 — LEAVE-ONE-OUT LAYER ABLATION

Remove each layer ONE AT A TIME from the full stack.
Run full walk-forward backtest for each removal.

| Removed | CAGR | Sharpe | MaxDD | Δ CAGR | Δ Sharpe | Verdict |
|---------|------|--------|-------|--------|----------|---------|
| None    | 30.73| 1.88   | -12.66| --     | --       | full    |
| L1      | ...  | ...    | ...   | ...    | ...      | ...     |

Rules:
- If removing a layer IMPROVES or barely changes performance (Sharpe drop
  < 0.02): mark REMOVE.
- If removing a layer drops Sharpe by > 0.05: load-bearing → KEEP.
- In between: UNCERTAIN.

Save to /tests/autonomous/purge/TEST1_ablation.md.

## TEST 2 — FORWARD WALK HOLDOUT

Split data:
- Period A: 2010-2017 (8 years)
- Period B: 2018-2025 (8 years)

For each layer marked KEEP or UNCERTAIN:
- Test on Period A only. Does the layer help (Δ Sharpe vs no-layer)?
- Test on Period B only. Does the layer help?
- A layer must help in BOTH periods independently to survive.
  If it only helps in one period, it's fitting to that era. REMOVE.

| Layer | Period A Δ Sharpe | Period B Δ Sharpe | Both positive? | Verdict |
|-------|-------------------|-------------------|----------------|---------|
| L1    | ...               | ...               | ...            | ...     |

Save to /tests/autonomous/purge/TEST2_holdout.md.

## TEST 3 — RANDOM TIMING TEST

For each layer that involves a TRIGGER (self-DD, Kelly boost, stagflation
defend, uncertain-top, confidence gate):

Replace the trigger's actual firing dates with RANDOM dates that fire at
the same frequency. Run 500 iterations.

Example: self-DD fires 9 of 190 months. Pick 9 random months, apply the
same sizing change, measure Sharpe. Repeat 500 times.

If the actual trigger's Sharpe improvement is BELOW the 75th percentile of
random triggers: timing doesn't matter → either simplify to always-on or
declare the change is noise. REMOVE.

If the actual trigger is ABOVE the 95th percentile: timing genuinely
matters → KEEP.

| Layer | Actual ΔSh | Random p50 | p75 | p95 | Pct | Verdict |
|-------|------------|------------|-----|-----|-----|---------|

Save to /tests/autonomous/purge/TEST3_random_timing.md.

## TEST 4 — PARAMETER NEIGHBORHOOD TEST

For each layer with a tuned parameter (gate=0.40, split=62/38, rank
weights 1:3:1, DD threshold -2%, boost +30%, etc):

Test 5 nearby parameter values (±20%, ±40%). Smooth = all 5 improve
over no-layer baseline. Not smooth (only 1-2 of 5 help) = overfit to
that exact value, REMOVE or use neighborhood center.

| Layer | Param  | -40% | -20% | Base | +20% | +40% | Smooth? |
|-------|--------|------|------|------|------|------|---------|
| L3    | gate   | 0.24 | 0.32 | 0.40 | 0.48 | 0.56 | ...     |

Save to /tests/autonomous/purge/TEST4_parameter_neighborhood.md.

## TEST 5 — REBUILD FROM SCRATCH (nuclear test)

Start from canonical baseline (23.61/1.50/-12.94).
Add layers back ONE AT A TIME, but ONLY layers that passed Tests 1-4.
Add in order of Test 1 Sharpe impact (biggest first).

After adding each layer:
- Run full walk-forward backtest.
- Check: does this layer STILL help on top of the previous layers?
- If it doesn't help on top of the stack: drop it.

This produces the **MINIMAL ROBUST STACK**: the smallest set of
modifications that are individually justified, era-independent,
timing-verified, parameter-stable, and stack-verified.

Save to /tests/autonomous/purge/TEST5_rebuild.md and
/tests/autonomous/purge/ROBUST_STACK.md.

## TEST 6 — FINAL BOOTSTRAP COMPARISON

Three variants side by side, 10,000 bootstrap iterations:
- Canonical baseline (23.61/1.50/-12.94)
- ROBUST STACK (from Test 5)
- Full P59 (30.73/1.88/-12.66)

For each pair: t-stat, P(edge>0), 95% CI on annualized edge.

If ROBUST STACK has similar bootstrap stats to P59 → P59's extras
were complexity without real edge → ship ROBUST STACK.

If P59 is significantly better → keep P59 with caveats.

Save to /tests/autonomous/purge/TEST6_bootstrap.md.

## DELIVERABLES (all in /tests/autonomous/purge/)

- LAYERS.md — layer inventory
- TEST1_ablation.md
- TEST2_holdout.md
- TEST3_random_timing.md
- TEST4_parameter_neighborhood.md
- TEST5_rebuild.md
- TEST6_bootstrap.md
- ROBUST_STACK.md — THE FINAL ANSWER (what survived)
- VERDICT.md — one page: what to ship and why

## RESUMPTION INSTRUCTIONS

This file was saved 2026-04-13 ~17:10 local. The user said "pause and
start again in 3h". The first ScheduleWakeup will fire ~1h from now;
each successive wakeup will check time elapsed and either sleep more or
begin executing this protocol.

Bottom-of-page reminder: P59 is the robust champion (30.73/1.88/-12.66,
OOS-validated). P57 (30.48/1.90) was full-sample-best but flagged for
overfitting. The protocol's reference to P55 is from before the session
moved past it; treat P59 as "full stack" target.
