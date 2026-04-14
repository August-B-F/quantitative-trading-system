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

set +e
python scripts/run_health_check.py --probe-sources >> logs/health_check.log 2>&1
EXIT_CODE=$?
set -e

if [ $EXIT_CODE -ne 0 ]; then
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] Health check exit=$EXIT_CODE" >> logs/alerts.log
  python -c "from src.risk.notify import send_alert; send_alert('Health check ALERT', 'ALERT')" \
    >> logs/alerts.log 2>&1 || true
fi

exit $EXIT_CODE
