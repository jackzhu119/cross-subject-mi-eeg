#!/usr/bin/env bash
set -euo pipefail
CODE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="${PAPER1_PYTHON:-/public/home/zhuziyuan/.venvs/paper3-hpc-cu121-offline/bin/python}"
cd "$CODE_ROOT"
exec "$PYTHON_BIN" -u -m hpcmi.cli status "$@"
