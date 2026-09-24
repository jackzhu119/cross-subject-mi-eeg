#!/usr/bin/env bash
# One-command, detached Q10 research queue for the paid Linux GPU instance.
# Closing SSH, the browser, ChatGPT, or the local computer does not stop this
# process. The rented *cloud instance itself* must remain powered and funded.
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

Q10_PYTHON="${Q10_PYTHON:-/root/autodl-tmp/q9-venv/bin/python}"
if [[ ! -x "$Q10_PYTHON" && -x "$PROJECT_ROOT/.venv-cloud/bin/python" ]]; then
  Q10_PYTHON="$PROJECT_ROOT/.venv-cloud/bin/python"
fi
Q10_DATA_DIR="${Q10_DATA_DIR:-/root/autodl-tmp/data/raw}"
QUEUE_DIR="$PROJECT_ROOT/results/Q10-QUEUE"
MODE="${1:-start}"

case "$MODE" in
  start|foreground|status|publish-only) ;;
  *) echo "Usage: bash run_next_gpu.sh [start|foreground|status|publish-only]" >&2; exit 2 ;;
esac

if [[ "$MODE" == status ]]; then
  if [[ -f "$QUEUE_DIR/batch_status.json" ]]; then
    if [[ -x "$Q10_PYTHON" ]]; then
      "$Q10_PYTHON" -m json.tool "$QUEUE_DIR/batch_status.json"
    else
      sed -n '1,120p' "$QUEUE_DIR/batch_status.json"
    fi
  else
    echo "No Q10 cloud queue has started yet."
  fi
  for receipt in "$PROJECT_ROOT/results/Q10-BATCH/publish_status.json" \
                 "$QUEUE_DIR/publish_status.json"; do
    if [[ -f "$receipt" ]]; then
      echo "Publication receipt: $receipt"
      sed -n '1,80p' "$receipt"
    fi
  done
  exit 0
fi

if [[ ! -x "$Q10_PYTHON" ]]; then
  echo "Cloud Python environment not found: $Q10_PYTHON" >&2
  exit 2
fi
if [[ ! -f scripts/publish_research_run.py ]]; then
  echo "Research result publisher is missing; update the repository first." >&2
  exit 2
fi
mkdir -p "$QUEUE_DIR"

GIT_SAFE_ENV=(GIT_TERMINAL_PROMPT=0 GIT_ASKPASS=/bin/false SSH_ASKPASS=/bin/false \
              GIT_SSH_COMMAND='ssh -o BatchMode=yes -o StrictHostKeyChecking=yes')
ORIGIN="$(git remote get-url origin)"
case "$ORIGIN" in
  'https://github.com/jackzhu119/cross-subject-mi-eeg.git'|\
  'git@github.com:jackzhu119/cross-subject-mi-eeg.git'|\
  'ssh://git@github.com/jackzhu119/cross-subject-mi-eeg.git') ;;
  *) echo "origin is not the allowlisted public research repository." >&2; exit 2 ;;
esac
if [[ "$(git branch --show-current)" != main ]]; then
  echo "Cloud queue requires the frozen main branch." >&2
  exit 2
fi

if [[ "$MODE" == publish-only ]]; then
  for pair in 'Q10-BATCH Q10-E001' 'Q10-QUEUE Q10-A001'; do
    read -r batch experiment <<<"$pair"
    if [[ -d "$PROJECT_ROOT/results/$batch" ]]; then
      "$Q10_PYTHON" scripts/publish_research_run.py \
        --batch-dir "$PROJECT_ROOT/results/$batch" \
        --experiment-dir "$PROJECT_ROOT/results/$experiment"
    fi
  done
  exit 0
fi

if [[ ! -d "$Q10_DATA_DIR" ]]; then
  echo "EEG data cache not found: $Q10_DATA_DIR" >&2
  exit 2
fi
if [[ ! -f scripts/q10_geometry.py || ! -f scripts/q10_e001_batch.py || \
      ! -f scripts/q10_cloud_queue.py ]]; then
  echo "Required Q10 runner scripts are missing; update the repository first." >&2
  exit 2
fi

# A fully validated and published queue is immutable. A repeated 'start' is a
# status check, not a second scientific run or a timestamp-only Git commit.
if "$Q10_PYTHON" -c '
import json, pathlib, sys
def status(path):
    try:
        return json.loads(pathlib.Path(path).read_text()).get("status")
    except (OSError, ValueError):
        return None
values = [status(p) for p in sys.argv[1:]]
sys.exit(0 if values == ["complete_validated", "passed_scientific_checks",
                          "passed_scientific_artifact_validation", "pushed", "pushed"]
         or values[:3] == ["complete_validated", "passed_scientific_checks",
                            "passed_scientific_artifact_validation"]
         and all(str(v).startswith("pushed") for v in values[3:]) else 1)
' "$QUEUE_DIR/batch_status.json" \
  "$PROJECT_ROOT/results/Q10-E001/validation_report.json" \
  "$PROJECT_ROOT/results/Q10-A001/validation_report.json" \
  "$PROJECT_ROOT/results/Q10-BATCH/publish_status.json" \
  "$QUEUE_DIR/publish_status.json"; then
  echo "Q10 queue is already validated and published; no duplicate run started."
  exit 0
fi

# Validate a real CUDA allocation plus the import stack *before* detaching.
# The Q10-E001 batch repeats this check before any training.
"$Q10_PYTHON" check_gpu.py
"$Q10_PYTHON" -c 'import torch, torchaudio, braindecode, mne, moabb; assert torch.cuda.is_available()'
"$Q10_PYTHON" scripts/q10_cloud_queue.py --data-dir "$Q10_DATA_DIR" --plan-only >/dev/null

# The server must have a noninteractive writable GitHub deploy key; a failed
# preflight is surfaced before spending GPU hours, never hidden in a log.
if [[ "${Q10_REQUIRE_GIT_PUSH:-1}" == 1 ]]; then
  if ! env "${GIT_SAFE_ENV[@]}" git push --dry-run origin HEAD:main >/dev/null 2>&1; then
    echo "Noninteractive GitHub push preflight failed; training not started." >&2
    exit 2
  fi
fi

ARGS=(scripts/q10_cloud_queue.py --data-dir "$Q10_DATA_DIR")
if [[ "$MODE" == foreground ]]; then
  exec "$Q10_PYTHON" "${ARGS[@]}"
fi

PID_FILE="$QUEUE_DIR/supervisor.pid"
if [[ -f "$PID_FILE" ]]; then
  OLD_PID="$(sed -n '1p' "$PID_FILE")"
  if [[ "$OLD_PID" =~ ^[0-9]+$ ]] && kill -0 "$OLD_PID" 2>/dev/null; then
    if ps -p "$OLD_PID" -o args= | grep -Fq 'scripts/q10_cloud_queue.py'; then
      echo "Q10 queue is already running (PID $OLD_PID); no duplicate started."
      exit 0
    fi
  fi
fi

LOG="$QUEUE_DIR/supervisor.log"
nohup "$Q10_PYTHON" "${ARGS[@]}" </dev/null >>"$LOG" 2>&1 &
PID=$!
printf '%s\n' "$PID" >"$PID_FILE"
sleep 3
if kill -0 "$PID" 2>/dev/null; then
  echo "Q10 detached queue running (PID $PID)."
  echo "Follow: bash run_next_gpu.sh status"
  echo "Logs: $LOG; scientific results: $PROJECT_ROOT/results/"
  echo "Local shutdown is safe; do not stop or release the cloud instance until completion."
else
  echo "Q10 queue exited during startup; inspect $LOG." >&2
  exit 1
fi
