#!/usr/bin/env bash
set -euo pipefail
# Read metadata only. No credentials, downloads, training or registration changes.
BASE="${1:-/workspace/mi-eeg-cloud}"
df -B1 /workspace
findmnt -T /workspace -o TARGET,FSTYPE,SOURCE
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader
python3 - "$BASE" <<'PY'
import json,sys
from pathlib import Path
base=Path(sys.argv[1])
print(json.dumps({'work_root_exists':base.is_dir(),'registration_exists':(base/'execution_registration.json').is_file(),'budget_origin_exists':(base/'budget_origin.json').is_file(),'source_mat_files':len(list((base/'data/bnci').glob('A*.mat'))),'runtime_candidates':len(list(base.glob('runtime-*/bin/python'))),'fits_started_by_probe':0}))
PY
