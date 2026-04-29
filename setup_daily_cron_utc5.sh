#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUN_SCRIPT="${SCRIPT_DIR}/daily_story_workflow.sh"
CRON_TAG="# gms-daily-story-workflow"

if [[ ! -f "${RUN_SCRIPT}" ]]; then
  echo "[ERROR] Runner script not found: ${RUN_SCRIPT}"
  exit 1
fi

chmod +x "${RUN_SCRIPT}"

if ! command -v crontab >/dev/null 2>&1; then
  echo "[ERROR] crontab not found. Install cron first: sudo apt install -y cron"
  exit 1
fi

if ! command -v xvfb-run >/dev/null 2>&1; then
  echo "[ERROR] xvfb-run not found. Install with: sudo apt install -y xvfb"
  exit 1
fi

CURRENT_CRON="$(crontab -l 2>/dev/null || true)"
CLEANED_CRON="$(printf "%s\n" "${CURRENT_CRON}" | grep -v "${CRON_TAG}" | grep -v "daily_story_workflow.sh" || true)"

NEW_ENTRY="CRON_TZ=UTC\n0 5 * * * /bin/bash ${RUN_SCRIPT} ${CRON_TAG}"

printf "%b\n" "${CLEANED_CRON}" > /tmp/gms_cron_tmp.txt
printf "%b\n" "${NEW_ENTRY}" >> /tmp/gms_cron_tmp.txt
crontab /tmp/gms_cron_tmp.txt
rm -f /tmp/gms_cron_tmp.txt

echo "[OK] Cron installed: every day at 05:00 UTC"
echo "[INFO] Entry: 0 5 * * * /bin/bash ${RUN_SCRIPT}"
echo "[INFO] Check with: crontab -l"
echo "[INFO] Logs: ${SCRIPT_DIR}/logs/daily_story_workflow.log"
