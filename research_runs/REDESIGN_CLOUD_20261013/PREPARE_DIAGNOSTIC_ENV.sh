#!/usr/bin/env bash
set -euo pipefail
# CPU diagnostic dependencies only. No GPU operation, raw import, credentials or job registration.
DEST="${1:?Usage: bash PREPARE_DIAGNOSTIC_ENV.sh /workspace/paper1-diagnostic-runtime}"
[[ ! -e "$DEST" && ! -L "$DEST" ]] || { echo 'Choose a new isolated environment path; existing environment retained.'; exit 2; }
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
python3 -c 'import sys; assert sys.version_info[:2] == (3,12), "Python3.12 required for this diagnostic recipe"'
python3 -m venv "$DEST"
"$DEST/bin/python" -m pip install --no-cache-dir --disable-pip-version-check -r "$SCRIPT_DIR/requirements-diagnostic.txt"
"$DEST/bin/python" -m pip check
"$DEST/bin/python" -c 'import numpy,scipy,pandas,boto3; assert (numpy.__version__,scipy.__version__,pandas.__version__,boto3.__version__)==("2.3.5","1.17.0","2.2.3","1.40.61"); print("PINNED_CPU_DIAGNOSTIC_ENV_READY_NO_FITS")'
"$DEST/bin/python" -m pip freeze > "$DEST/installed-packages.txt"
