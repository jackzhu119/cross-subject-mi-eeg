#!/usr/bin/env bash
printf 'SINGLE_JOB_BATCH_START job=%s host=%s utc=%s\n' "${SLURM_JOB_ID:-unknown}" "$(hostname)" "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
set -uo pipefail
if [ "$#" -ne 3 ]; then
  printf 'Expected PROJECT PYTHON CODE_ROOT\n' >&2
  exit 2
fi
PROJECT="$1"
PYTHON_BIN="$2"
CODE_ROOT="$3"
export PYTHONUNBUFFERED=1 PYTHONNOUSERSITE=1
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
export CUBLAS_WORKSPACE_CONFIG=:4096:8
# Slurm owns CUDA_VISIBLE_DEVICES; the runner assigns its existing slots.
cd "$CODE_ROOT" || exit 2
runner_pid=""
usr1_requested=0
cancel_code=0
forward_usr1() {
  usr1_requested=1
  printf 'SINGLE_JOB_SIGNAL signal=USR1 utc=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  if [ -n "$runner_pid" ]; then kill -USR1 "$runner_pid" 2>/dev/null || true; fi
}
forward_cancel() {
  cancel_code="$1"
  printf 'SINGLE_JOB_SIGNAL signal=%s utc=%s\n' "$2" "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  if [ -n "$runner_pid" ]; then kill -"$2" "$runner_pid" 2>/dev/null || true; fi
}
trap forward_usr1 USR1
trap 'forward_cancel 143 TERM' TERM
trap 'forward_cancel 130 INT' INT
"$PYTHON_BIN" -u -m hpcmi.single_job --project "$PROJECT" &
runner_pid=$!
printf 'SINGLE_JOB_RUNNER_START pid=%s utc=%s\n' "$runner_pid" "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
if [ "$cancel_code" -ne 0 ]; then
  kill -TERM "$runner_pid" 2>/dev/null || true
elif [ "$usr1_requested" -eq 1 ]; then
  kill -USR1 "$runner_pid" 2>/dev/null || true
fi
while true; do
  # Trapped signals interrupt wait. Wait again until the supervisor has waited
  # for its children to finish saving their real checkpoints and exited.
  wait "$runner_pid"
  runner_code=$?
  if kill -0 "$runner_pid" 2>/dev/null; then continue; fi
  break
done
printf 'SINGLE_JOB_RUNNER_EXIT code=%s utc=%s\n' "$runner_code" "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
if [ "$cancel_code" -ne 0 ]; then
  printf 'SINGLE_JOB_CANCELLED_NO_REQUEUE\n'
  exit "$cancel_code"
fi
if [ "$usr1_requested" -eq 1 ] && [ "$runner_code" -eq 75 ]; then
  requeue_id="${SLURM_JOB_ID:?Slurm job ID is required}"
  printf 'SINGLE_JOB_CHECKPOINT_EXIT_CONFIRMED attempting_requeue=%s\n' "$requeue_id"
  # Only the current enclosing job is requeued, once. No new sbatch/array.
  if scontrol requeue "$requeue_id"; then
    printf 'SINGLE_JOB_REQUEUE_REQUEST_ACCEPTED job=%s\n' "$requeue_id"
  else
    printf 'SINGLE_JOB_REQUEUE_UNAVAILABLE: rerun the same single-job launch command to resume.\n' >&2
  fi
  exit 75
fi
exit "$runner_code"
