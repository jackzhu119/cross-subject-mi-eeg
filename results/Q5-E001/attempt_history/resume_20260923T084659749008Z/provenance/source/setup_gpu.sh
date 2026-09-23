#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

if [[ -z "${VIRTUAL_ENV:-}" ]]; then
  echo "Activate the project .venv-cloud first, or start with bash run_gpu.sh." >&2
  exit 2
fi

if [[ "$(python -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')" != "3.12" ]]; then
  echo "This environment is pinned for Python 3.12." >&2
  exit 2
fi

python -m pip install --upgrade pip
python -m pip install "torch==2.14.0" --index-url https://download.pytorch.org/whl/cu132
python -m pip install -r requirements-cloud.txt
python -m pip install --no-deps -e .

echo "Dependencies installed. The following check uses the real CUDA device."
python check_gpu.py
