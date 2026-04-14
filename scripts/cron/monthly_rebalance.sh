#!/bin/bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$PROJECT_DIR"

mkdir -p logs

if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

# 1. Skip non-trading days (weekends / NYSE holidays).
MARKET_DAY=$(python -c "
from src.data.utils import get_trading_calendar
import datetime
today = datetime.date.today()
cal = get_trading_calendar(str(today), str(today))
print('yes' if len(cal) > 0 else 'no')
")
if [ "$MARKET_DAY" = "no" ]; then
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] Not a trading day, skipping" >> logs/rebalance.log
  exit 0
fi

# 2. Pick up any FOMC-deferred rebalance scheduled for today.
DEFERRED=$(python -c "
import json, os, datetime
log_path = 'logs/rebalance_log.json'
out = 'no'
if os.path.exists(log_path):
    try:
        with open(log_path) as f:
            log = json.load(f)
    except Exception:
        log = None
    if isinstance(log, list) and log:
        last = log[-1]
        defer = last.get('fomc_deferred_to')
        if defer:
            try:
                if datetime.date.fromisoformat(defer) == datetime.date.today():
                    out = 'yes'
            except ValueError:
                pass
print(out)
")

set +e
if [ "$DEFERRED" = "yes" ]; then
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] Running deferred FOMC rebalance" >> logs/rebalance.log
  python scripts/run_rebalance.py --force --execute >> logs/rebalance.log 2>&1
  EXIT_CODE=$?
else
  python scripts/run_rebalance.py --execute >> logs/rebalance.log 2>&1
  EXIT_CODE=$?
fi
set -e

if [ $EXIT_CODE -eq 2 ]; then
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] Data unavailable, will retry tomorrow" >> logs/alerts.log
  python -c "from src.risk.notify import send_alert; send_alert('Rebalance deferred: data unavailable', 'WARNING')" \
    >> logs/alerts.log 2>&1 || true
elif [ $EXIT_CODE -ne 0 ]; then
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] Rebalance FAILED exit=$EXIT_CODE" >> logs/alerts.log
  python -c "from src.risk.notify import send_alert; send_alert('Rebalance FAILED', 'ALERT')" \
    >> logs/alerts.log 2>&1 || true
fi

exit $EXIT_CODE
