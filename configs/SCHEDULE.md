# Operational Schedule

The system runs **unattended**. The strategy trades once a month, so a
long-running scheduler process is unnecessary — the OS scheduler is
battle-tested, survives reboots, and is managed by the OS.

Two parallel implementations:
- **Windows Task Scheduler** (production on `the-tower`, Sweden) —
  PowerShell wrappers in [scripts/scheduler/](../scripts/scheduler/),
  installed via `scripts\scheduler\install_tasks.ps1` (elevated).
- **Linux cron** (VPS fallback) — bash wrappers in
  [scripts/cron/](../scripts/cron/), installed via
  `bash scripts/cron/install_crontab.sh`.

Both implementations share the same timing spec and gate logic.

---

## Timezone math (the-tower, Sweden)

The host runs in **Europe/Stockholm** (CET / CEST). NYSE close maps to:

| US clock      | Stockholm clock (DST)  | Stockholm clock (standard) |
|---------------|------------------------|----------------------------|
| 16:00 ET close| 22:00 CEST             | 22:00 CET                  |
| 17:30 ET      | 23:30 CEST             | 23:30 CET                  |
| 22:15 ET      | 04:15 CEST (next day)  | 04:15 CET (next day)       |

Cron entries below are written in **server local time**. Set the box's
timezone to `Europe/Stockholm` (`timedatectl set-timezone Europe/Stockholm`)
so they line up with the table above.

---

## Monthly — Rebalance
- **When:** every trading day at 04:15 server-local (≈ 22:15 ET, 15 min
  after the close — gives Yahoo + FRED time to settle the close print).
  The wrapper runs daily; the Python script itself checks whether today
  is the last trading day of the month.
- **Wrapper:** [scripts/cron/monthly_rebalance.sh](../scripts/cron/monthly_rebalance.sh)
- **Command inside:** `python scripts/run_rebalance.py --execute`
- **FOMC deferral:** if `run_rebalance.py` defers due to a FOMC conflict,
  it records a `fomc_deferred_to` field in `logs/rebalance_log.json`. The
  wrapper checks that field on every run and re-fires with `--force --execute`
  on the deferred date — no manual intervention needed.
- **Trading day gate:** the wrapper exits early on weekends / NYSE holidays
  via `src.data.utils.get_trading_calendar`.
- **Exit codes the wrapper reacts to:**
  - `0` — success (or "not a rebalance day")
  - `2` — data unavailable, defer to next trading day (logs warning)
  - other non-zero — alert via `src.risk.notify.send_alert`

## Daily — Health Check
- **When:** every weekday at 23:30 server-local (≈ 17:30 ET, 1.5h after
  close).
- **Wrapper:** [scripts/cron/daily_health.sh](../scripts/cron/daily_health.sh)
- **Command inside:** `python scripts/run_health_check.py --probe-sources`
- **Exit code:** 0 on OK / WARNING-only, 1 on any ALERT (wrapper escalates
  via `send_alert`).
- **Log:** `logs/health_check.log`.

## Quarterly — Retrain
- **When:** 06:00 server-local on the 1st of Jan / Apr / Jul / Oct.
- **Wrapper:** [scripts/cron/quarterly_retrain.sh](../scripts/cron/quarterly_retrain.sh)
- **Command inside:** `python scripts/run_retrain.py`
- Not time-critical; wrapper just logs.

## Log rotation
- **When:** 05:00 server-local on the 1st of every month.
- **Wrapper:** [scripts/cron/rotate_logs.sh](../scripts/cron/rotate_logs.sh)
- Truncates `health_check.log`, `rebalance.log`, `retrain.log`, `alerts.log`
  to the last 10k lines.

---

## Crontab (installed by install_crontab.sh)

```cron
# >>> iStock scheduler >>>
30 23 * * 1-5 /path/to/quantitative-trading-system/scripts/cron/daily_health.sh
15 4  * * 2-6 /path/to/quantitative-trading-system/scripts/cron/monthly_rebalance.sh
0  6  1 1,4,7,10 * /path/to/quantitative-trading-system/scripts/cron/quarterly_retrain.sh
0  5  1 * * /path/to/quantitative-trading-system/scripts/cron/rotate_logs.sh
# <<< iStock scheduler <<<
```

`install_crontab.sh` is **idempotent** — re-running it strips the prior
iStock block (matched by the marker comments) and writes a fresh one,
preserving any unrelated entries already in the user crontab.

---

## Deployment on the-tower (Sweden, Windows)

Production target: Windows 10 Pro, RTX 4060 Ti, i5-13600K, Europe/Stockholm.

1. Clone the repo.
2. Create `.env` from `.env.example`, fill in all API keys + Alpaca paper
   credentials. Set `ALPACA_PAPER_MODE=true`.
3. `pip install -r requirements.txt`.
4. **Verify the canary:** `python scripts\run_backtest.py` — must pass.
5. **Verify accounts:** `python scripts\run_rebalance.py --status` — all
   9 accounts visible.
6. **Verify data sources:** `python scripts\run_health_check.py --probe-sources`
   — all sources OK or only WARNING-level.
7. Confirm the Windows timezone is `(UTC+01:00) Stockholm`
   (`Get-TimeZone` in PowerShell). Task Scheduler fires on local time.
8. **Wake timers + sleep settings** (required for unattended operation):
   - Control Panel → Power Options → Change plan settings →
     Change advanced power settings → Sleep → **Allow wake timers = Enable**.
   - Set "Put the computer to sleep" to **Never** on AC power, or at
     minimum ensure the registered tasks' `WakeToRun` flag is honored.
   - If accessed via Parsec + WireGuard, Parsec keeps the box awake while
     connected; the wake timer covers the unattended windows.
9. Install tasks from an **elevated** PowerShell:
   `powershell -ExecutionPolicy Bypass -File scripts\scheduler\install_tasks.ps1`
10. Verify:
    `Get-ScheduledTask | Where-Object TaskName -like 'iStock_*'` — should
    show `iStock_DailyHealth`, `iStock_MonthlyRebalance`,
    `iStock_QuarterlyRetrain`.
11. Confirm `WakeToRun` on all three:
    `Get-ScheduledTask -TaskName 'iStock_*' | ForEach-Object { "$($_.TaskName): $($_.Settings.WakeToRun)" }`
12. **Smoke test (manual run):**
    `powershell -ExecutionPolicy Bypass -File scripts\scheduler\daily_health.ps1`
    then `Get-Content logs\health_check.log -Tail 50`.
13. **Smoke test (rebalance, non-month-end):**
    `powershell -ExecutionPolicy Bypass -File scripts\scheduler\monthly_rebalance.ps1`
    then `Get-Content logs\rebalance.log -Tail 50` — should log "Not a
    trading day" on weekends or exit cleanly after the script's internal
    month-end check.
14. **Smoke test (Task Scheduler GUI):** `taskschd.msc` → find
    `iStock_DailyHealth` → right-click → Run → verify log updated.
15. **Uninstall:** `powershell -ExecutionPolicy Bypass -File scripts\scheduler\uninstall_tasks.ps1`
    (elevated).

### Windows task mapping

| Task | Trigger | Notes |
|---|---|---|
| `iStock_DailyHealth` | Weekly, Mon–Fri, 23:30 | ≈ 17:30 ET, 1.5h post-close |
| `iStock_MonthlyRebalance` | Weekly, Tue–Sat, 04:15 | ≈ 22:15 ET previous day; script gates on month-end + trading day + FOMC |
| `iStock_QuarterlyRetrain` | Daily, 06:00 | Script exits immediately unless it is the 1st of Jan/Apr/Jul/Oct (Task Scheduler has no native "1st of specific months" trigger) |

All tasks set `AllowStartIfOnBatteries`, `DontStopIfGoingOnBatteries`,
`StartWhenAvailable`, `WakeToRun`, and a 1-hour `ExecutionTimeLimit`.
`StartWhenAvailable` catches missed runs when the box was off/asleep.

## Deployment on Linux (VPS fallback)

1. Clone the repo.
2. Create `.env` from `.env.example`, fill in all API keys + Alpaca paper
   credentials. Set `ALPACA_PAPER_MODE=true`.
3. `pip install -r requirements.txt`.
4. **Verify the canary:** `python scripts/run_backtest.py` — must pass.
5. **Verify accounts:** `python scripts/run_rebalance.py --status` — all
   9 accounts visible.
6. **Verify data sources:** `python scripts/run_health_check.py --probe-sources`
   — all sources OK or only WARNING-level.
7. Set the host timezone: `sudo timedatectl set-timezone Europe/Stockholm`.
8. Install cron: `bash scripts/cron/install_crontab.sh`.
9. Verify: `crontab -l` — should show the iStock block (4 entries).
10. **Smoke test:** `bash scripts/cron/daily_health.sh && tail -50 logs/health_check.log`.
11. **Smoke test:** `bash scripts/cron/monthly_rebalance.sh && tail -50 logs/rebalance.log`
    — on a non-month-end day this should log "Not a rebalance day" and exit 0.
12. Wait for the next month-end: the first automated rebalance runs itself.

A $5/mo Hetzner or DigitalOcean droplet works. Advantage: always-on,
no dependency on a home machine being awake or reachable.

## Monitoring the scheduler
- Tail `logs/health_check.log` daily (or wire `SLACK_WEBHOOK_URL` so the
  wrapper's `send_alert` calls reach you).
- After each month-end: check `logs/rebalance.log` for `EXECUTED` lines on
  all 9 strategies.
- If a rebalance failed: re-run manually with `python scripts/run_rebalance.py --force --execute`.

## Emergency procedures
- **Liquidate everything:** `python scripts/run_rebalance.py --kill-all`
- **Disable the scheduler:** edit the crontab and remove the iStock block,
  or `crontab -r` to wipe all entries.
- **Manual rebalance:** `python scripts/run_rebalance.py --force --execute`
- **Status snapshot:** `python scripts/run_rebalance.py --status`

---

## Ad-hoc flags (for manual runs)
- `--status` — current holdings + next scheduled rebalance
- `--force` — override the schedule / FOMC gate (testing / deferral re-run)
- `--execute` — actually submit orders (otherwise dry run)
- `--date YYYY-MM-DD` — pretend today is this date (testing)
