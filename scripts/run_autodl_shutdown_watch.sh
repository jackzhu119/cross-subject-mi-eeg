#!/usr/bin/env bash
# Explicitly arm this AutoDL instance to power off only after Q10 and the
# Q11/Q14 follow-up queue stop, their evidence is published (or a failure and
# bounded publication attempts are recorded). Does not affect a local PC.
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"
WATCH_PYTHON="${WATCH_PYTHON:-/root/autodl-tmp/q9-venv/bin/python}"
WATCH_DIR="$PROJECT_ROOT/results/Q14-QUEUE"
MODE="${1:-status}"

case "$MODE" in
  start|status|dry-run) ;;
  *) echo "Usage: bash scripts/run_autodl_shutdown_watch.sh [start|status|dry-run]" >&2; exit 2 ;;
esac

if [[ "$MODE" == status ]]; then
  if [[ -f "$WATCH_DIR/autoshutdown_status.json" ]]; then
    sed -n '1,100p' "$WATCH_DIR/autoshutdown_status.json"
  else
    echo "No AutoDL shutdown watcher status recorded."
  fi
  if [[ -f "$WATCH_DIR/autoshutdown_receipt.json" ]]; then
    echo "Shutdown receipt: $WATCH_DIR/autoshutdown_receipt.json"
    sed -n '1,100p' "$WATCH_DIR/autoshutdown_receipt.json"
  fi
  if [[ -f "$WATCH_DIR/autoshutdown.pid" ]]; then
    PID="$(sed -n '1p' "$WATCH_DIR/autoshutdown.pid")"
    if [[ "$PID" =~ ^[0-9]+$ ]] && kill -0 "$PID" 2>/dev/null && \
       ps -p "$PID" -o args= | grep -Fq 'scripts/autodl_queue_shutdown.py'; then
      echo "Detached shutdown watcher running (PID $PID)."
    fi
  fi
  exit 0
fi

case "$PROJECT_ROOT" in
  /root/autodl-tmp/*) ;;
  *) echo "Refusing to arm outside the AutoDL data volume." >&2; exit 2 ;;
esac
if [[ "$(id -u)" != 0 ]]; then
  echo "AutoDL shutdown requires root on this instance." >&2; exit 2
fi
if [[ ! -x /usr/bin/shutdown ]]; then
  echo "Official AutoDL /usr/bin/shutdown is not executable." >&2; exit 2
fi
if [[ ! -x "$WATCH_PYTHON" ]]; then
  echo "Cloud Python environment unavailable: $WATCH_PYTHON" >&2; exit 2
fi
if [[ "$(git branch --show-current)" != main ]]; then
  echo "Shutdown watcher requires frozen main branch." >&2; exit 2
fi
case "$(git remote get-url origin)" in
  'https://github.com/jackzhu119/cross-subject-mi-eeg.git'|\
  'git@github.com:jackzhu119/cross-subject-mi-eeg.git'|\
  'ssh://git@github.com/jackzhu119/cross-subject-mi-eeg.git') ;;
  *) echo "origin is not the allowlisted research repository." >&2; exit 2 ;;
esac
if [[ ! -f results/Q10-QUEUE/batch_status.json || \
      ! -f results/Q14-QUEUE/batch_status.json ]]; then
  echo "Both Q10 and follow-up queue status files must exist before arming." >&2
  exit 2
fi
if [[ ! -f scripts/autodl_queue_shutdown.py || \
      ! -f scripts/publish_research_run.py ]]; then
  echo "Shutdown watcher or publisher missing." >&2; exit 2
fi

mkdir -p "$WATCH_DIR"
PID_FILE="$WATCH_DIR/autoshutdown.pid"
if [[ -f "$PID_FILE" ]]; then
  OLD_PID="$(sed -n '1p' "$PID_FILE")"
  if [[ "$OLD_PID" =~ ^[0-9]+$ ]] && kill -0 "$OLD_PID" 2>/dev/null && \
     ps -p "$OLD_PID" -o args= | grep -Fq 'scripts/autodl_queue_shutdown.py'; then
    echo "Shutdown watcher is already running (PID $OLD_PID); no duplicate armed."
    exit 0
  fi
fi

if [[ "$MODE" == dry-run ]]; then
  exec "$WATCH_PYTHON" scripts/autodl_queue_shutdown.py \
    --poll-seconds 2 --settle-seconds 3 --publish-attempts 1
fi

# `start` is the explicit arming action. The Python watcher also requires its
# own --execute-shutdown flag, so a direct inspection invocation is harmless.
nohup "$WATCH_PYTHON" scripts/autodl_queue_shutdown.py --execute-shutdown \
  </dev/null >>"$WATCH_DIR/autoshutdown.log" 2>&1 &
PID=$!
printf '%s\n' "$PID" >"$PID_FILE"
sleep 3
if kill -0 "$PID" 2>/dev/null && \
   ps -p "$PID" -o args= | grep -Fq 'scripts/autodl_queue_shutdown.py'; then
  echo "AutoDL shutdown watcher armed and detached (PID $PID)."
  echo "It will not stop a running Q10/Q11/Q14 worker."
  echo "Status: bash scripts/run_autodl_shutdown_watch.sh status"
else
  echo "Watcher exited during startup; inspect $WATCH_DIR/autoshutdown.log." >&2
  exit 1
fi
