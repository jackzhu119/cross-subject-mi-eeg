#!/usr/bin/env bash
printf 'BATCH_START job=%s task=%s host=%s utc=%s\n' "${SLURM_JOB_ID:-unknown}" "${SLURM_ARRAY_TASK_ID:-unknown}" "$(hostname)" "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
set -uo pipefail
if [ "$#" -ne 4 ]; then
  printf 'Expected PROJECT PYTHON CODE_ROOT MAP_JSON\n' >&2
  exit 2
fi
PROJECT="$1"
PYTHON_BIN="$2"
CODE_ROOT="$3"
MAP_JSON="$4"
export PYTHONUNBUFFERED=1 PYTHONNOUSERSITE=1
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
export CUBLAS_WORKSPACE_CONFIG=:4096:8
# CUDA_VISIBLE_DEVICES is owned by Slurm and is intentionally left intact.
cd "$CODE_ROOT" || exit 2
TASK_ID="$("$PYTHON_BIN" -c 'import json,re,sys; m=json.load(open(sys.argv[1])); t=m["tasks"][int(sys.argv[2])]; assert re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}",t); print(t)' "$MAP_JSON" "${SLURM_ARRAY_TASK_ID:?Slurm array index is required}")" || exit "$?"
worker_pid=""
usr1_requested=0
cancel_code=0
forward_usr1() {
  usr1_requested=1
  printf 'BATCH_SIGNAL signal=USR1 task=%s utc=%s\n' "$TASK_ID" "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  if [ -n "$worker_pid" ]; then kill -USR1 "$worker_pid" 2>/dev/null || true; fi
}
forward_cancel() {
  cancel_code="$1"
  printf 'BATCH_SIGNAL signal=%s task=%s utc=%s\n' "$2" "$TASK_ID" "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  if [ -n "$worker_pid" ]; then kill -"$2" "$worker_pid" 2>/dev/null || true; fi
}
trap forward_usr1 USR1
trap 'forward_cancel 143 TERM' TERM
trap 'forward_cancel 130 INT' INT
"$PYTHON_BIN" -u -m hpcmi.worker --project "$PROJECT" --task-id "$TASK_ID" --device cuda &
worker_pid=$!
printf 'WORKER_START pid=%s task=%s utc=%s\n' "$worker_pid" "$TASK_ID" "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
if [ "$cancel_code" -ne 0 ]; then
  kill -TERM "$worker_pid" 2>/dev/null || true
elif [ "$usr1_requested" -eq 1 ]; then
  kill -USR1 "$worker_pid" 2>/dev/null || true
fi
while true; do
  # A trapped signal interrupts wait before the child exits. Continue waiting
  # until the worker has actually completed its atomic checkpoint and exited.
  wait "$worker_pid"
  worker_code=$?
  if kill -0 "$worker_pid" 2>/dev/null; then continue; fi
  break
done
printf 'WORKER_EXIT task=%s code=%s utc=%s\n' "$TASK_ID" "$worker_code" "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
if [ "$cancel_code" -ne 0 ]; then
  printf 'CANCELLED_NO_REQUEUE task=%s\n' "$TASK_ID"
  exit "$cancel_code"
fi
if [ "$usr1_requested" -eq 1 ] && [ "$worker_code" -eq 75 ]; then
  if [ -n "${SLURM_ARRAY_JOB_ID:-}" ]; then
    requeue_id="${SLURM_ARRAY_JOB_ID}_${SLURM_ARRAY_TASK_ID}"
  else
    requeue_id="${SLURM_JOB_ID:?Slurm job ID is required}"
  fi
  printf 'CHECKPOINT_EXIT_CONFIRMED attempting_requeue=%s\n' "$requeue_id"
  # Exactly one attempt. A denied requeue never launches a replacement itself.
  if scontrol requeue "$requeue_id"; then
    printf 'REQUEUE_REQUEST_ACCEPTED job=%s\n' "$requeue_id"
  else
    printf 'REQUEUE_UNAVAILABLE: rerun the same LAUNCH.sh command to resume task=%s\n' "$TASK_ID" >&2
  fi
  exit 75
fi
exit "$worker_code"
