#!/usr/bin/env bash
set -euo pipefail
CODE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="${PAPER1_PYTHON:-/public/home/zhuziyuan/.venvs/paper3-hpc-cu121-offline/bin/python}"
if [ ! -x "$PYTHON_BIN" ]; then
  printf 'Python is not executable: %s\nSet PAPER1_PYTHON to the prepared interpreter.\n' "$PYTHON_BIN" >&2
  exit 2
fi
export PYTHONUNBUFFERED=1 PYTHONNOUSERSITE=1
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
cd "$CODE_ROOT"
exec "$PYTHON_BIN" -u -m hpcmi.cli launch "$@"
