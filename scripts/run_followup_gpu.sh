#!/usr/bin/env bash
# Start Q11 then Q14 on the same rented GPU after Q10 validates and publishes.
# SSH/browser/local PC can disconnect; the paid cloud instance must stay on.
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"
FOLLOWUP_PYTHON="${FOLLOWUP_PYTHON:-/root/autodl-tmp/q9-venv/bin/python}"
if [[ ! -x "$FOLLOWUP_PYTHON" && -x "$PROJECT_ROOT/.venv-cloud/bin/python" ]]; then
  FOLLOWUP_PYTHON="$PROJECT_ROOT/.venv-cloud/bin/python"
fi
BNCI_DATA_DIR="${BNCI_DATA_DIR:-/root/autodl-tmp/data/raw}"
PHYSIONET_DATA_DIR="${PHYSIONET_DATA_DIR:-/root/autodl-tmp/physionet}"
export MOABB_DOWNLOAD_PROVIDER=upstream
QUEUE_DIR="$PROJECT_ROOT/results/Q14-QUEUE"
MODE="${1:-start}"

case "$MODE" in
  start|foreground|status|publish-only) ;;
  *) echo "Usage: bash scripts/run_followup_gpu.sh [start|foreground|status|publish-only]" >&2; exit 2 ;;
esac

if [[ "$MODE" == status ]]; then
  if [[ -f "$QUEUE_DIR/batch_status.json" ]]; then
    if [[ -x "$FOLLOWUP_PYTHON" ]]; then
      "$FOLLOWUP_PYTHON" -m json.tool "$QUEUE_DIR/batch_status.json"
    else
      sed -n '1,120p' "$QUEUE_DIR/batch_status.json"
    fi
  else
    echo "No Q11/Q14 follow-up queue has started yet."
  fi
  for receipt in results/Q11-BATCH/publish_status.json \
                 results/Q14-BATCH/publish_status.json \
                 results/Q14-QUEUE/publish_status.json; do
    if [[ -f "$receipt" ]]; then
      echo "Publication receipt: $receipt"
      sed -n '1,70p' "$receipt"
    fi
  done
  if [[ -f "$QUEUE_DIR/supervisor.pid" ]]; then
    PID="$(sed -n '1p' "$QUEUE_DIR/supervisor.pid")"
    if [[ "$PID" =~ ^[0-9]+$ ]] && kill -0 "$PID" 2>/dev/null && \
       ps -p "$PID" -o args= | grep -Fq 'scripts/followup_queue.py'; then
      echo "Detached follow-up supervisor is running (PID $PID)."
    fi
  fi
  exit 0
fi

if [[ ! -x "$FOLLOWUP_PYTHON" ]]; then
  echo "Cloud Python environment not found: $FOLLOWUP_PYTHON" >&2; exit 2
fi
if [[ ! -d "$BNCI_DATA_DIR" ]]; then
  echo "BNCI data cache not found: $BNCI_DATA_DIR" >&2; exit 2
fi
if [[ ! -f scripts/followup_queue.py || ! -f scripts/q11_batch.py || \
      ! -f scripts/q14_batch.py || ! -f scripts/publish_research_run.py ]]; then
  echo "Required frozen follow-up scripts missing; update the repository." >&2; exit 2
fi
if [[ "$(git branch --show-current)" != main ]]; then
  echo "Follow-up requires main branch." >&2; exit 2
fi
case "$(git remote get-url origin)" in
  'https://github.com/jackzhu119/cross-subject-mi-eeg.git'|\
  'git@github.com:jackzhu119/cross-subject-mi-eeg.git'|\
  'ssh://git@github.com/jackzhu119/cross-subject-mi-eeg.git') ;;
  *) echo "origin is not the allowlisted research repository." >&2; exit 2 ;;
esac

GIT_SAFE_ENV=(GIT_TERMINAL_PROMPT=0 GIT_ASKPASS=/bin/false SSH_ASKPASS=/bin/false \
              GIT_SSH_COMMAND='ssh -o BatchMode=yes -o StrictHostKeyChecking=yes')
if [[ "$MODE" == publish-only ]]; then
  for pair in 'Q11-BATCH Q11-E001' 'Q14-BATCH Q14-E001' 'Q14-QUEUE Q14-E002'; do
    read -r batch experiment <<<"$pair"
    if [[ -d "results/$batch" ]]; then
      "$FOLLOWUP_PYTHON" scripts/publish_research_run.py \
        --batch-dir "$PROJECT_ROOT/results/$batch" \
        --experiment-dir "$PROJECT_ROOT/results/$experiment"
    fi
  done
  exit 0
fi

# The source-only and external freeze scripts themselves independently verify
# their own code/config hashes; this preflight prevents an uncommitted protocol
# from being carried into a long detached GPU run.
FROZEN_FILES=(research_runs/Q11-E001/MATRIX.json \
              research_runs/Q14-E001/CONFIG.json \
              research_runs/Q14-E001/PROTOCOL.md \
              scripts/q11_neural.py scripts/q11_batch.py scripts/validate_q11_e001.py \
              scripts/q14_source.py scripts/q14_external.py scripts/q14_validate.py \
              scripts/q14_batch.py tests/test_q14_external_protocol.py)
if ! git ls-files --error-unmatch "${FROZEN_FILES[@]}" >/dev/null 2>&1; then
  echo "A Q11/Q14 protocol file is not committed; refusing to start." >&2; exit 2
fi
if [[ -n "$(git status --porcelain -- "${FROZEN_FILES[@]}")" ]]; then
  echo "A frozen Q11/Q14 protocol file is dirty; refusing to start." >&2; exit 2
fi

"$FOLLOWUP_PYTHON" check_gpu.py
"$FOLLOWUP_PYTHON" scripts/followup_queue.py --bnci-data-dir "$BNCI_DATA_DIR" \
  --physionet-data-dir "$PHYSIONET_DATA_DIR" --plan-only >/dev/null
if ! env "${GIT_SAFE_ENV[@]}" git push --dry-run origin HEAD:main >/dev/null 2>&1; then
  echo "Noninteractive GitHub push preflight failed; follow-up not started." >&2; exit 2
fi

ARGS=(scripts/followup_queue.py --bnci-data-dir "$BNCI_DATA_DIR" \
      --physionet-data-dir "$PHYSIONET_DATA_DIR")
if [[ "$MODE" == foreground ]]; then
  exec "$FOLLOWUP_PYTHON" "${ARGS[@]}"
fi

mkdir -p "$QUEUE_DIR"
PID_FILE="$QUEUE_DIR/supervisor.pid"
if [[ -f "$PID_FILE" ]]; then
  OLD_PID="$(sed -n '1p' "$PID_FILE")"
  if [[ "$OLD_PID" =~ ^[0-9]+$ ]] && kill -0 "$OLD_PID" 2>/dev/null && \
     ps -p "$OLD_PID" -o args= | grep -Fq 'scripts/followup_queue.py'; then
    echo "Follow-up is already running (PID $OLD_PID); no duplicate started."
    exit 0
  fi
fi
nohup "$FOLLOWUP_PYTHON" "${ARGS[@]}" </dev/null >>"$QUEUE_DIR/supervisor.log" 2>&1 &
PID=$!
printf '%s\n' "$PID" >"$PID_FILE"
sleep 3
if kill -0 "$PID" 2>/dev/null; then
  echo "Detached follow-up supervisor running (PID $PID)."
  echo "It will wait for Q10 validation and both Git pushes before Q11 then Q14."
  echo "Status: bash scripts/run_followup_gpu.sh status"
  echo "Cloud data/results persist under $PROJECT_ROOT/results/ and $PHYSIONET_DATA_DIR."
else
  echo "Follow-up exited during startup; inspect $QUEUE_DIR/supervisor.log." >&2
  exit 1
fi
