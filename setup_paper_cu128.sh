#!/usr/bin/env bash
# Separate paper-stage CUDA 12.8 environment. Never alter legacy .venv-cloud.
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

if [[ "$(uname -s)" != "Linux" ]]; then
  echo "This environment is for the Linux GPU host only." >&2
  exit 2
fi

if [[ -n "${PAPER_PYTHON_BIN:-}" ]]; then
  BASE_PYTHON="$PAPER_PYTHON_BIN"
elif command -v python3.12 >/dev/null 2>&1; then
  BASE_PYTHON="$(command -v python3.12)"
else
  BASE_PYTHON="$(command -v python)"
fi

if [[ "$("$BASE_PYTHON" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')" != "3.12" ]]; then
  echo "A Python 3.12 interpreter is required; set PAPER_PYTHON_BIN explicitly." >&2
  exit 2
fi

VENV_DIR="$PROJECT_ROOT/.venv-paper"
if [[ ! -x "$VENV_DIR/bin/python" ]]; then
  "$BASE_PYTHON" -m venv "$VENV_DIR"
fi
PYTHON="$VENV_DIR/bin/python"
if [[ "$("$PYTHON" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')" != "3.12" ]]; then
  echo "Existing .venv-paper does not use Python 3.12; inspect it manually." >&2
  exit 2
fi

"$PYTHON" -m pip install --upgrade pip
# The cloud-side official cu128 wheel endpoint was too slow for this host.
# The PyPI mirror's Linux 2.8.0 wheel is accepted only if the independent
# runtime check below proves CUDA 12.8, matching TorchAudio and a GPU operation.
# Override the HTTPS package index explicitly if this mirror is unavailable.
PAPER_INDEX_URL="${PAPER_INDEX_URL:-https://repo.huaweicloud.com/repository/pypi/simple}"
"$PYTHON" -m pip install 'torch==2.8.0' 'torchaudio==2.8.0' \
  --index-url "$PAPER_INDEX_URL"
"$PYTHON" -m pip install -r requirements-paper-cu128.txt \
  --index-url "$PAPER_INDEX_URL"
"$PYTHON" -m pip install --no-deps -e .
"$PYTHON" -m pip check
"$PYTHON" scripts/check_paper_env.py
"$PYTHON" -m pip freeze > "$VENV_DIR/pip-freeze.txt"
printf '%s\n' "$PAPER_INDEX_URL" > "$VENV_DIR/package-index.txt"
echo "Paper-stage environment ready: $PYTHON"
echo "Installed package inventory: $VENV_DIR/pip-freeze.txt"
