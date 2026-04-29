#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="${SCRIPT_DIR}"
TOKEN_FILE="${PROJECT_DIR}/../.github_token"
LOG_DIR="${PROJECT_DIR}/logs"
LOG_FILE="${LOG_DIR}/daily_story_workflow.log"

mkdir -p "${LOG_DIR}"

exec >>"${LOG_FILE}" 2>&1

echo "============================================================"
echo "[$(date -u '+%Y-%m-%d %H:%M:%S UTC')] Workflow started"

cd "${PROJECT_DIR}"

if [[ -f ".venv/bin/activate" ]]; then
  source ".venv/bin/activate"
fi

if [[ ! -f "${TOKEN_FILE}" ]]; then
  echo "[ERROR] Missing token file: ${TOKEN_FILE}"
  echo "[ERROR] Run push_to_github_token.py manually once to save token before using cron."
  exit 1
fi

if ! command -v xvfb-run >/dev/null 2>&1; then
  echo "[ERROR] xvfb-run not found. Install it with: sudo apt install -y xvfb"
  exit 1
fi

echo "[STEP] Running auto_story.py"
xvfb-run -a python3 auto_story.py

echo "[STEP] Running scan.py"
python3 scan.py

echo "[STEP] Running push_to_github_token.py"
python3 push_to_github_token.py

echo "[$(date -u '+%Y-%m-%d %H:%M:%S UTC')] Workflow completed"
