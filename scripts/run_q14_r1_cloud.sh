#!/usr/bin/env bash
# Resume the interrupted Q14 external cohort on this AutoDL instance only.
# The independent migration runner preserves all original Q14-E002 artifacts.
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"
MODE="${1:-start}"
PYTHON_BIN="${Q14_R1_PYTHON:-/root/autodl-tmp/q9-venv/bin/python}"
PHYSIONET_DATA_DIR="${PHYSIONET_DATA_DIR:-/root/autodl-tmp/physionet}"
BATCH_DIR="$PROJECT_ROOT/results/Q14-R1BATCH"
PID_FILE="$BATCH_DIR/supervisor.pid"

case "$MODE" in
  start|foreground|status) ;;
  *) echo "Usage: bash scripts/run_q14_r1_cloud.sh [start|foreground|status]" >&2; exit 2 ;;
esac

if [[ "$MODE" == status ]]; then
  if [[ -f "$BATCH_DIR/batch_status.json" ]]; then
    sed -n '1,120p' "$BATCH_DIR/batch_status.json"
  else
    echo "Q14-E002R1 has not started."
  fi
  if [[ -f "$BATCH_DIR/completion_receipt.json" ]]; then
    sed -n '1,120p' "$BATCH_DIR/completion_receipt.json"
  fi
  if [[ -f "$PID_FILE" ]]; then
    PID="$(sed -n '1p' "$PID_FILE")"
    if [[ "$PID" =~ ^[0-9]+$ ]] && kill -0 "$PID" 2>/dev/null && \
       ps -p "$PID" -o args= | grep -Fq 'scripts/q14_r1_supervisor.py'; then
      echo "Detached Q14-E002R1 supervisor is running (PID $PID)."
    fi
  fi
  exit 0
fi

case "$PROJECT_ROOT" in
  /root/autodl-tmp/*) ;;
  *) echo "Refusing outside the AutoDL data volume." >&2; exit 2 ;;
esac
if [[ "$(git branch --show-current)" != main ]]; then
  echo "This publisher requires the cloud's main branch." >&2; exit 2
fi
case "$(git remote get-url origin)" in
  'https://github.com/jackzhu119/cross-subject-mi-eeg.git'|\
  'git@github.com:jackzhu119/cross-subject-mi-eeg.git'|\
  'ssh://git@github.com/jackzhu119/cross-subject-mi-eeg.git') ;;
  *) echo "Unexpected Git remote; refusing." >&2; exit 2 ;;
esac
if [[ ! -x "$PYTHON_BIN" || ! -d "$PHYSIONET_DATA_DIR" ]]; then
  echo "Frozen Python environment or PhysioNet cache missing." >&2; exit 2
fi
REQUIRED=(scripts/q14_r1_migration.py scripts/q14_r1_validate.py
          scripts/q14_r1_supervisor.py research_runs/Q14-E002R1/PROTOCOL.md)
if ! git ls-files --error-unmatch "${REQUIRED[@]}" >/dev/null 2>&1; then
  echo "Migration code/protocol must be committed before running." >&2; exit 2
fi
if [[ -n "$(git status --porcelain -- "${REQUIRED[@]}")" ]]; then
  echo "Migration code/protocol is dirty; refusing to mix versions." >&2; exit 2
fi
for script in followup_queue.py autodl_queue_shutdown.py q14_batch.py q14_external.py; do
  if pgrep -f "scripts/$script" >/dev/null; then
    echo "Another Q14/Q10 worker or old shutdown watcher is active: $script" >&2
    exit 2
  fi
done
"$PYTHON_BIN" check_gpu.py
if ! env GIT_TERMINAL_PROMPT=0 GIT_ASKPASS=/bin/false SSH_ASKPASS=/bin/false \
  GIT_SSH_COMMAND='ssh -o BatchMode=yes -o StrictHostKeyChecking=yes' \
  git push --dry-run origin HEAD:main >/dev/null 2>&1; then
  echo "Noninteractive GitHub push preflight failed; not starting." >&2; exit 2
fi

mkdir -p "$BATCH_DIR"
ARGS=(scripts/q14_r1_supervisor.py --data-dir "$PHYSIONET_DATA_DIR" \
      --python "$PYTHON_BIN" --execute-shutdown)
if [[ "$MODE" == foreground ]]; then
  exec "$PYTHON_BIN" "${ARGS[@]}"
fi
if [[ -f "$PID_FILE" ]]; then
  PID="$(sed -n '1p' "$PID_FILE")"
  if [[ "$PID" =~ ^[0-9]+$ ]] && kill -0 "$PID" 2>/dev/null && \
     ps -p "$PID" -o args= | grep -Fq 'scripts/q14_r1_supervisor.py'; then
    echo "Q14-E002R1 is already running (PID $PID)."
    exit 0
  fi
fi
nohup "$PYTHON_BIN" "${ARGS[@]}" </dev/null >>"$BATCH_DIR/supervisor.log" 2>&1 &
PID=$!
printf '%s\n' "$PID" >"$PID_FILE"
sleep 3
if kill -0 "$PID" 2>/dev/null && \
   ps -p "$PID" -o args= | grep -Fq 'scripts/q14_r1_supervisor.py'; then
  echo "Detached Q14-E002R1 supervisor is running (PID $PID)."
  echo "It will continue the independent cohort, validate, publish, then request cloud shutdown."
  echo "Status: bash scripts/run_q14_r1_cloud.sh status"
else
  echo "Supervisor exited during startup; inspect $BATCH_DIR/supervisor.log." >&2
  exit 1
fi
