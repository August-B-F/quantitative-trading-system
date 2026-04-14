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

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Quarterly retrain start" >> logs/retrain.log
python scripts/run_retrain.py >> logs/retrain.log 2>&1
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Quarterly retrain end" >> logs/retrain.log
