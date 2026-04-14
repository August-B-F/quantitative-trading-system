#!/bin/bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$PROJECT_DIR/logs"

for f in health_check.log rebalance.log retrain.log alerts.log; do
  if [ -f "$f" ]; then
    tail -n 10000 "$f" > "${f}.tmp" && mv "${f}.tmp" "$f"
  fi
done
