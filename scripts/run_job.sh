#!/usr/bin/env bash
set -uo pipefail

ROOT="/opt/data/ff-model"
JOB="${1:-}"
if [[ "$JOB" != "daily" && "$JOB" != "waivers" ]]; then
  echo "usage: $0 <daily|waivers> [--dry-run]" >&2
  exit 64
fi
shift

LOG_DIR="${FF_JOB_LOG_DIR:-$ROOT/logs}"
REPORT_DIR="${FF_JOB_REPORT_DIR:-$ROOT/reports}"
LOCK_FILE="${FF_JOB_LOCK:-/tmp/ff-job.lock}"
DATE="$(TZ=America/Chicago date +%F)"
LOG="$LOG_DIR/${JOB}_${DATE}.log"
FAILURE="$REPORT_DIR/JOB_FAILED_${JOB}.md"
mkdir -p "$LOG_DIR" "$REPORT_DIR"
find "$LOG_DIR" -type f -name "${JOB}_*.log" -mtime +30 -delete

write_failure() {
  local status="$1"
  {
    echo "# Job failed: $JOB"
    echo
    echo "- Date: $DATE"
    echo "- Exit status: $status"
    echo "- Log: $LOG"
    echo
    echo '```text'
    tail -n 40 "$LOG" 2>/dev/null || true
    echo '```'
  } > "$FAILURE"
}

exec 9>"$LOCK_FILE"
if ! flock -n 9; then
  echo "$(date -Is) job refused: another ff-model job holds $LOCK_FILE" >> "$LOG"
  write_failure 75
  exit 75
fi

{
  echo "$(date -Is) starting $JOB $*"
  "$ROOT/scripts/ensure_env.sh"
} >> "$LOG" 2>&1
status=$?
if [[ $status -ne 0 ]]; then
  write_failure "$status"
  exit "$status"
fi

case "$JOB" in
  daily) script="$ROOT/scripts/daily_job.py" ;;
  waivers) script="$ROOT/scripts/waivers_job.py" ;;
esac

nice -n 10 /tmp/ff-venv/bin/python "$script" "$@" >> "$LOG" 2>&1
status=$?
if [[ $status -ne 0 ]]; then
  write_failure "$status"
  exit "$status"
fi

rm -f "$FAILURE"
echo "$(date -Is) completed $JOB" >> "$LOG"
