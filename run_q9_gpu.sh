#!/usr/bin/env bash
# Start the vetted Q9 subset in a detached process that survives SSH logout.
# This does not reboot/restart a rented cloud instance or provision GitHub auth.
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

Q9_PYTHON="${Q9_PYTHON:-$PROJECT_ROOT/.venv-cloud/bin/python}"
Q9_DATA_DIR="${Q9_DATA_DIR:-$PROJECT_ROOT/data/raw}"
Q9_OUTPUT_ROOT="${Q9_OUTPUT_ROOT:-$PROJECT_ROOT/results}"
# Only implemented E001/E002/E004/E005 neural variants and paired Q9-A001
# PSD controls. E003 CSP/PCA neural variants remain explicitly unrun.
Q9_CONDITIONS="${Q9_CONDITIONS:-MID_8_30,MU_8_13,BETA_13_30,MU_BETA_SHARED,PSD44_LDA,PSD44_LINEAR_SVM,MID_8_30_Q8_EPOCHS,MU_BETA_SHARED_Q8_EPOCHS,MU_BETA_SHARED_SOURCE_CLEAN,MU_BETA_SHARED_SOURCE_NORM}"

if [[ ! -x "$Q9_PYTHON" ]]; then
  echo "Q9 Python environment is missing: $Q9_PYTHON" >&2
  exit 2
fi
if [[ ! -d "$Q9_DATA_DIR" ]]; then
  echo "Q9 data directory is missing: $Q9_DATA_DIR" >&2
  exit 2
fi

mkdir -p "$Q9_OUTPUT_ROOT/Q9-BATCH"
case "${1:-start}" in
  status)
    if [[ -f "$Q9_OUTPUT_ROOT/Q9-BATCH/batch_status.json" ]]; then
      "$Q9_PYTHON" -m json.tool "$Q9_OUTPUT_ROOT/Q9-BATCH/batch_status.json"
    else
      echo "No Q9 batch status yet."
    fi
    exit 0
    ;;
  start|foreground) ;;
  *) echo "Usage: bash run_q9_gpu.sh [start|foreground|status]" >&2; exit 2 ;;
esac

# This is a real CUDA allocation test on the cloud host. Failure stops before
# any target inference; it never falls back to CPU silently.
"$Q9_PYTHON" check_gpu.py

ARGS=(
  scripts/q9_batch.py
  --matrix research_runs/Q9-E001/Q9_BATCH_MATRIX.json
  --data-dir "$Q9_DATA_DIR"
  --output-root "$Q9_OUTPUT_ROOT"
  --conditions "$Q9_CONDITIONS"
  --device cuda
  --publish
)
if [[ -n "${Q9_TEMPLATE_FILE:-}" ]]; then
  ARGS+=(--template-file "$Q9_TEMPLATE_FILE")
fi

# Planning is read-only; malformed names/templates stop before renting hours
# are consumed by the detached worker.
"$Q9_PYTHON" "${ARGS[@]}" --plan-only >/dev/null

# A batch that must publish itself should not begin costly training with an
# unusable Git remote. Keep credentials in the host's SSH agent/deploy-key
# configuration, never in this script, command line, or repository.
if [[ "${Q9_REQUIRE_GIT_PUSH:-1}" == 1 ]]; then
  REMOTE="$(git remote get-url origin)"
  case "$REMOTE" in
    "git@github.com:jackzhu119/cross-subject-mi-eeg.git"|\
    "ssh://git@github.com/jackzhu119/cross-subject-mi-eeg.git"|\
    "https://github.com/jackzhu119/cross-subject-mi-eeg.git") ;;
    *) echo "Q9 origin is not the allowlisted public research repository." >&2; exit 2 ;;
  esac
  if ! GIT_TERMINAL_PROMPT=0 GIT_ASKPASS=/bin/false SSH_ASKPASS=/bin/false \
       GIT_SSH_COMMAND='ssh -o BatchMode=yes -o StrictHostKeyChecking=yes' \
       git push --dry-run origin HEAD:main >/dev/null 2>&1; then
    echo "Noninteractive GitHub push preflight failed; Q9 training not started." >&2
    exit 2
  fi
fi

if [[ "${1:-start}" == foreground ]]; then
  exec "$Q9_PYTHON" "${ARGS[@]}"
fi

LOG="$Q9_OUTPUT_ROOT/Q9-BATCH/supervisor.log"
nohup "$Q9_PYTHON" "${ARGS[@]}" </dev/null >>"$LOG" 2>&1 &
PID=$!
printf '%s\n' "$PID" >"$Q9_OUTPUT_ROOT/Q9-BATCH/supervisor.pid"
sleep 2
if kill -0 "$PID" 2>/dev/null; then
  echo "Q9 detached supervisor started (PID $PID)."
  echo "Inspect $Q9_OUTPUT_ROOT/Q9-BATCH/batch_status.json and supervisor.log."
else
  echo "Q9 supervisor exited during startup; inspect $LOG." >&2
  exit 1
fi
