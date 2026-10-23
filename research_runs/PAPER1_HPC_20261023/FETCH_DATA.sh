#!/usr/bin/env bash
set -euo pipefail
printf 'paper1 data fetch host=%s time=%s\n' "$(hostname)" "$(date -u +%FT%TZ)"
cd "$(dirname "${BASH_SOURCE[0]}")"
PYTHON_BIN="${PAPER1_FETCH_PYTHON:-python3}"
exec "$PYTHON_BIN" -u -m hpcmi.acquire "$@"
