# Operational Schedule

## Monthly — Rebalance
- **When:** last trading day of each calendar month, 4:30 PM ET
  (after US market close at 4:00 PM ET; allow 30 min for data propagation).
- **Command:** `python scripts/run_rebalance.py`
- **FOMC deferral:** if the scheduled day falls inside the FOMC
  post-window, the script prints a deferral notice and exits. Re-run
  on the deferred date with `--force`.
- **After execution:** run `python scripts/run_rebalance.py --confirm`
  once trades are filled so `configs/holdings.json` reflects the new
  state.

## Daily — Health Check
- **When:** every trading day at 5:00 PM ET (1h after market close,
  allowing Yahoo + FRED propagation).
- **Command:** `python scripts/run_health_check.py`
- **Exit code:** 0 on OK / WARNING-only runs, 1 on any ALERT.
- **Log:** appends a timestamped report to `logs/health_check.log`.

### Cron entry
```
30 17 * * 1-5 cd /path/to/quantitative-trading-system && python scripts/run_health_check.py >> logs/health_check.log 2>&1
```

Standard `MAILTO=` cron behavior delivers the output on non-zero exit.
For alert-only delivery, wrap the command so tail only fires on exit 1:
```
MAILTO=oncall@example.com
30 17 * * 1-5 cd /path/to/quantitative-trading-system && python scripts/run_health_check.py > logs/health_check.log 2>&1 || tail -40 logs/health_check.log
```

### Slack (optional, not wired)
[src/risk/notify.py](../src/risk/notify.py) exposes `send_alert()` that
POSTs to `SLACK_WEBHOOK_URL` if set. Scaffold only — drop calls into the
health check when ready to route.

## Quarterly — Retrain
- **When:** first trading day of each new quarter.
- **Command:** `python scripts/run_retrain.py`

## Ad-hoc
- `--status` — current holdings + next scheduled rebalance
- `--force`  — override the schedule / FOMC gate (testing / deferral re-run)
- `--date YYYY-MM-DD` — pretend today is this date (testing)

**No cron is configured.** Operator runs the scripts manually per the
schedule above.
