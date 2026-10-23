#!/usr/bin/env bash
printf 'SMOKE_BATCH_START job=%s host=%s utc=%s\n' "${SLURM_JOB_ID:-unknown}" "$(hostname)" "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
set -euo pipefail
if [ "$#" -ne 3 ]; then printf 'Expected PROJECT PYTHON CODE_ROOT\n' >&2; exit 2; fi
PROJECT="$1"
PYTHON_BIN="$2"
CODE_ROOT="$3"
export PYTHONUNBUFFERED=1 PYTHONNOUSERSITE=1
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
export CUBLAS_WORKSPACE_CONFIG=:4096:8
cd "$CODE_ROOT"
exec "$PYTHON_BIN" -u -m hpcmi.smoke --project "$PROJECT" --device cuda
