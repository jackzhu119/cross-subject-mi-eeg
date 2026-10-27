#!/usr/bin/env bash
printf 'COMPOSITION_BATCH_START job=%s host=%s utc=%s\n' "${SLURM_JOB_ID:-unknown}" "$(hostname)" "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
set -uo pipefail
if [ "$#" -ne 3 ]; then printf 'Expected PROJECT PYTHON CODE_ROOT\n' >&2; exit 2; fi
PROJECT="$1"
PYTHON_BIN="$2"
CODE_ROOT="$3"
export PYTHONUNBUFFERED=1 PYTHONNOUSERSITE=1
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
export CUBLAS_WORKSPACE_CONFIG=:4096:8
export PYTHONPATH="$CODE_ROOT:$CODE_ROOT/shared"
cd "$CODE_ROOT" || exit 2
runner_pid=""
usr1_requested=0
cancel_code=0
forward_usr1() {
  usr1_requested=1
  if [ -n "$runner_pid" ]; then kill -USR1 "$runner_pid" 2>/dev/null || true; fi
}
forward_cancel() {
  cancel_code="$1"
  if [ -n "$runner_pid" ]; then kill -"$2" "$runner_pid" 2>/dev/null || true; fi
}
trap forward_usr1 USR1
trap 'forward_cancel 143 TERM' TERM
trap 'forward_cancel 130 INT' INT
"$PYTHON_BIN" -u -m compmi.runner --project "$PROJECT" &
runner_pid=$!
printf 'COMPOSITION_RUNNER_START pid=%s utc=%s\n' "$runner_pid" "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
if [ "$cancel_code" -ne 0 ]; then kill -TERM "$runner_pid" 2>/dev/null || true
elif [ "$usr1_requested" -eq 1 ]; then kill -USR1 "$runner_pid" 2>/dev/null || true; fi
while true; do
  wait "$runner_pid"
  runner_code=$?
  if kill -0 "$runner_pid" 2>/dev/null; then continue; fi
  break
done
printf 'COMPOSITION_RUNNER_EXIT code=%s utc=%s\n' "$runner_code" "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
if [ "$cancel_code" -ne 0 ]; then exit "$cancel_code"; fi
if [ "$usr1_requested" -eq 1 ] && [ "$runner_code" -eq 75 ]; then
  if scontrol requeue "${SLURM_JOB_ID:?}"; then
    printf 'COMPOSITION_REQUEUE_ACCEPTED\n'
  else
    printf 'Requeue unavailable; use the same launch command to continue saved tasks.\n' >&2
  fi
  exit 75
fi
exit "$runner_code"
