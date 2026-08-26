#!/bin/bash
# Daily Market Wrap Up scheduled run - Monday to Friday 18:00 (Australia/Sydney).
# Rebuilds the digest, produces the snapshot + full PDF, then emails the snapshot.
set -euo pipefail

PROJ="/Users/brandonpotts/.verdent/verdent-projects/run-the-public-news"
LOG="$PROJ/scheduler.log"
export PATH="/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin"

cd "$PROJ"
{
  echo "===== RUN $(date '+%Y-%m-%d %H:%M:%S %Z') ====="
  python3 build.py
  python3 make_snapshot.py
  python3 make_pdf.py
  python3 "$PROJ/scripts/send_email.py"
  echo "===== DONE $(date '+%Y-%m-%d %H:%M:%S %Z') ====="
} >> "$LOG" 2>&1
