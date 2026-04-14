#!/bin/bash
# Install iStock cron jobs on the target machine. Run once.
# Preserves any existing user crontab entries.
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
MARK_BEGIN="# >>> iStock scheduler >>>"
MARK_END="# <<< iStock scheduler <<<"

CRON_BLOCK=$(cat <<EOF
${MARK_BEGIN}
# Timezone: server local time (set to Europe/Stockholm on the-tower).
# NYSE close 22:00 CET (DST) / 23:00 CET (standard).

# Daily health check — 23:30 CET ≈ 17:30 ET, Mon–Fri
30 23 * * 1-5 ${PROJECT_DIR}/scripts/cron/daily_health.sh

# Monthly rebalance attempt — 04:15 CET (next day) ≈ 22:15 ET, Tue–Sat.
# Cron fires every weekday after market close; the script itself checks
# whether today is the last trading day of the month (or a FOMC-deferred date).
15 4 * * 2-6 ${PROJECT_DIR}/scripts/cron/monthly_rebalance.sh

# Quarterly retrain — 06:00 CET on the 1st of Jan/Apr/Jul/Oct
0 6 1 1,4,7,10 * ${PROJECT_DIR}/scripts/cron/quarterly_retrain.sh

# Log rotation — 05:00 CET on the 1st of every month
0 5 1 * * ${PROJECT_DIR}/scripts/cron/rotate_logs.sh
${MARK_END}
EOF
)

# Strip any prior iStock block, then append the fresh one.
EXISTING=$(crontab -l 2>/dev/null || true)
FILTERED=$(echo "$EXISTING" | awk -v b="$MARK_BEGIN" -v e="$MARK_END" '
  $0 == b {skip=1; next}
  $0 == e {skip=0; next}
  !skip {print}
')

{
  if [ -n "$FILTERED" ]; then
    echo "$FILTERED"
  fi
  echo "$CRON_BLOCK"
} | crontab -

echo "Crontab installed. Verify with: crontab -l"
