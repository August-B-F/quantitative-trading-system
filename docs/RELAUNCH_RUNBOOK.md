# RELAUNCH RUNBOOK — Operator Steps

For restarting paper trading after the H1 void
(`docs/POSTMORTEM_2026H1.md`). Race rules: `EVALUATION.md`. Research
rules: `CONSTITUTION.md`.

**This repo's automation deliberately does NOT reset accounts or pick
the lineup.** Those are operator decisions (§6). Do not script them.

## 1. Reset the paper accounts

For each of the 9 Alpaca paper accounts in `configs/accounts.yaml`,
either:

- **Reset** the paper account from the Alpaca dashboard (Paper Account →
  Reset), which restores $100k and clears positions/history, or
- **Archive + open fresh**: export the account's order/position history
  for the archive, close the account, create a new paper account, and
  update the key/secret env vars named in `configs/accounts.yaml`
  (`alpaca_key_env` / `alpaca_secret_env`) in `.env`.

Verify: `py -3 scripts/run_rebalance.py --status` shows every in-use
slot at $100,000 with no positions.

## 2. Choose the lineup

Per `EVALUATION.md` §1: the two permanent controls (GEM dual momentum,
SPY/SMA200), plus at most 3 candidates that pass the entry gates.
Record the lineup and the gate evidence (DSR output, bootstrap
CI) in a dated file under `results/` before go-live. Unused accounts
stay empty.

**As of 2026-07-02 the qualified lineup is** (EVALUATION.md §1
"Current lineup"): GEM control, SPY/SMA200 control, and
`candidate_blend_rotation` (configs/strategies/candidate_blend_rotation.yaml
— blend_126_252 ranking with deterministic tie-break, 4-tranche staggered
rebalance, implemented in `src/strategy/rotation.py` and wired into
run_rebalance behind the `engine: rotation` accounts.yaml flag — the
yaml's comment block has the exact entry shape). Two-sleeve was retired
by Study 7's death certificate. The full bps-by-bps evidence behind every
adopted and rejected change is in `results/DROPLET_LEDGER.md` — read it
before adjusting anything about how the system buys.

**Monthly during the race:** run `py -3 scripts/run_race_report.py`
(first week of each month) — it renders results/RACE_REPORT.md with the
EVALUATION §3 checks and the power-corrected verdict language.

**Real-money planning:** the wrapper decision (ISK vs depå, UCITS
mapping, broker FX, migration steps) is analyzed with 2026 rules in
`docs/REAL_MONEY_SWEDEN.md` — worth +134..+240 bps/yr at 12% CAGR and
therefore read-before-funding material.

## 3. Pre-flight checklist (all must pass, in order)

1. **Data fresh:** run the nightly download
   (`scripts/scheduler/daily_download.ps1` payload) manually; confirm
   `data/features/master_panel.parquet` max date is the last trading
   day.
2. **Health check:** `py -3 scripts/run_health_check.py` → expect
   **exit 0** and `ALERTS: 0`, and confirm it now covers the
   panel/feature layer, not just `data/clean/prices` (post-mortem §2.4).
3. **Dry-run rebalance:** `py -3 scripts/run_rebalance.py --force`
   (no `--execute`) → expect:
   - `as_of` equals the last trading day (**fresh** — if it prints
     2026-04-10 or anything stale, STOP; the freshness gate should have
     refused);
   - sane signals (no 100% SHY while SPY is above its SMA200; no NaN
     weights; top holdings consistent with current 63d momentum).
4. **Alert channel:** send a test message through
   `src/risk/notify.py::send_alert` (set `SLACK_WEBHOOK_URL` if using
   Slack) and confirm it arrives.
5. **Classifier freshness:** retrain if the last fit is > 90 days old
   (`scripts/scheduler/quarterly_retrain.ps1` payload); stale-classifier
   accuracy decays per `results/FINAL_STRATEGY_VALIDATED.md` §3.

## 4. Re-enable the scheduled tasks

```powershell
# elevated PowerShell, repo root
scripts/scheduler/install_tasks.ps1
Get-ScheduledTask | Where-Object TaskName -like 'iStock_*'
```

Tasks: `iStock_DailyDownload` (Mon–Fri 22:00), `iStock_DailyHealth`
(Mon–Fri 23:30), `iStock_MonthlyRebalance` (Tue–Sat 04:15 Stockholm,
month-end gate internal), `iStock_QuarterlyRetrain` (daily 06:00,
quarter-boundary gate internal).

**Known scheduler gap:** a month-end falling on a Monday is silently
skipped by the Tue–Sat trigger (next: **2026-08-31**). Until the trigger
is fixed, calendar those dates and run
`py -3 scripts/run_rebalance.py --execute` manually.

## 5. Exit codes

`scripts/run_rebalance.py` (consumed by
`scripts/scheduler/monthly_rebalance.ps1`):

| Code | Meaning | Scheduler wrapper action |
|---|---|---|
| 0 | Success (or "not a rebalance day") | log only |
| 1 | Run failed (bad arguments, aborted, strategy-level failure) | **FAILED** alert to `logs/alerts.log` |
| 2 | Data unavailable / paper-mode assertion — **defer**, do not trade | "data unavailable, defer" alert |
| 3 | **Stale signal — freshness gate refused to trade** (CONSTITUTION rule 10) | FAILED alert; investigate panel rebuild before retrying |

Any non-zero exit means no orders (or partial orders logged in
`logs/rebalance_log.json`) — never assume fills without checking
`--status`.

## 6. Operator decisions (never automated)

The operator — not the code — decides:

1. Whether each account is **reset vs archived-and-reopened** (§1).
2. **The lineup**: which candidates enter, per the EVALUATION gates.
3. Go-live date (first month-end after all pre-flight checks pass).
4. Tripwire actions when fired (**-20% de-risk 50%, -25% halt** —
   EVALUATION §3): the alert fires automatically, the position change
   is an operator order.
5. Month-12 promotion/kill calls (EVALUATION §4).
6. Any real-capital decision (CONSTITUTION rule 6 gates it; a human
   signs it).
