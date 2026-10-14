#!/usr/bin/env bash
set -euo pipefail
# Optional future preparation: reuse read-only exact host torch, shadow other packages in a NEW venv.
DEST="${1:?Usage: bash PREPARE_TRAINING_ENV.sh /workspace/mi-eeg-cloud/runtime-reviewed-r2}"
[[ ! -e "$DEST" && ! -L "$DEST" ]] || { echo 'Existing environment retained; choose a new reviewed destination.'; exit 2; }
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
python3 - <<'PY'
import sys,torch,shutil
assert sys.version_info[:2] == (3,12)
assert torch.__version__ == '2.8.0+cu128' and torch.version.cuda == '12.8', 'Exact host torch required; no duplicate CUDA installation attempted'
assert shutil.disk_usage('/workspace').free >= 12*1024**3, 'Insufficient working storage before environment preparation'
PY
python3 -m venv --system-site-packages "$DEST"
# Never install torch again. Constraints also keep resolver decisions from upgrading the host pair.
printf '%s\n' 'torch==2.8.0' 'torchaudio==2.8.0' > "$DEST/paper1-constraints.txt"
"$DEST/bin/python" -m pip install --no-cache-dir --no-deps torchaudio==2.8.0 --index-url https://download.pytorch.org/whl/cu128
"$DEST/bin/python" -m pip install --no-cache-dir --disable-pip-version-check -c "$DEST/paper1-constraints.txt" -r "$SCRIPT_DIR/requirements.txt"
"$DEST/bin/python" -m pip check
"$DEST/bin/python" - "$SCRIPT_DIR/requirements.txt" <<'PY'
import importlib.metadata as m,sys,shutil
from pathlib import Path
import torch,torchaudio
assert torch.__version__=='2.8.0+cu128' and torchaudio.__version__.split('+')[0]=='2.8.0'
for line in Path(sys.argv[1]).read_text().splitlines():
 if '==' in line and not line.startswith('#'):
  name,version=line.split('==');assert m.version(name)==version
assert shutil.disk_usage('/workspace').free>=10*1024**3, 'Less than10GiB remains; do not proceed with import or fitting'
print('PINNED_TRAINING_PACKAGES_PREPARED_NO_CUDA_FIT_OR_JOB_STARTED')
PY
"$DEST/bin/python" -m pip list --format=json > "$DEST/installed-packages.json"
