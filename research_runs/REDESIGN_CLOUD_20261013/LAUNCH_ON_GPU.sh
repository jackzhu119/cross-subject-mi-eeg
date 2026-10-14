#!/usr/bin/env bash
set -euo pipefail
# No credential appears in the command or in a network-volume file.
REVISION=''
RESUME=''
RATE=''
R2=0
RESET=0
while (($#)); do
 case "$1" in
  --revision) REVISION="${2:?}"; shift 2;;
  --resume) RESUME="${2:?}"; shift 2;;
  --hourly-rate) RATE="${2:?}"; shift 2;;
  --r2) R2=1; shift;;
  --reset-credentials) RESET=1; shift;;
  --help) echo 'Usage: bash launch.sh --revision <40-character commit> [--hourly-rate <actual USD/hour>] [--resume <job id>] [--r2]'; exit 0;;
  *) echo 'Unknown option'; exit 2;;
 esac
done
[[ "$REVISION" =~ ^[0-9a-f]{40}$ ]] || { echo 'An immutable --revision is required.'; exit 2; }
[[ -z "$RESUME" || "$RESUME" =~ ^[a-zA-Z0-9_-]+$ ]] || { echo 'Invalid job id'; exit 2; }
LAUNCH_STARTED_UTC="$(date -u +%Y-%m-%dT%H:%M:%S+00:00)"
BASE='/workspace/mi-eeg-cloud'
CODE="$BASE/code-$REVISION"
mkdir -p "$BASE"
python - <<'PY'
import shutil
if shutil.disk_usage('/workspace/mi-eeg-cloud').free < 10*1024**3:
 raise SystemExit('At least 10 GiB of free working storage is required; no fitting started.')
PY
python - <<'PY'
import sys,torch,torchaudio
if sys.version_info[:2] not in ((3,11),(3,12)):
 raise SystemExit('Use Python 3.11/3.12 with the RunPod PyTorch 2.8.0 CUDA 12.8 template.')
if torch.__version__.split('+')[0]!='2.8.0' or torchaudio.__version__.split('+')[0]!='2.8.0' or torch.version.cuda!='12.8':
 raise SystemExit('Use the RunPod PyTorch 2.8.0 CUDA 12.8 template; no CPU or package-version substitution is allowed.')
if not torch.cuda.is_available():raise SystemExit('CUDA GPU unavailable; no worker started.')
print('GPU runtime found. No fitting has started.')
PY
# Preserve the first launcher time across installation/preflight retries.
LAUNCH_STARTED_UTC="$(python - "$BASE" "$LAUNCH_STARTED_UTC" <<'PY'
import json,sys,os
from pathlib import Path
p=Path(sys.argv[1])/'budget_origin.json'
if p.exists():
 print(json.loads(p.read_text())['started_at_utc'])
else:
 tmp=p.with_suffix('.tmp');tmp.write_text(json.dumps({'started_at_utc':sys.argv[2]})+'\n');os.replace(tmp,p);print(sys.argv[2])
PY
)"
if [[ ! -d "$CODE/.git" ]]; then
 git clone --depth 1 --branch research/source-selection-redesign-20261012 https://github.com/jackzhu119/cross-subject-mi-eeg.git "$CODE"
 git -C "$CODE" fetch --depth 1 origin "$REVISION"
 git -C "$CODE" checkout --detach "$REVISION"
fi
[[ "$(git -C "$CODE" rev-parse HEAD)" == "$REVISION" ]] || { echo 'Code revision mismatch; existing checkout left intact.'; exit 2; }
RUNTIME="$BASE/runtime-$REVISION"
if [[ ! -x "$RUNTIME/bin/python" ]]; then
 python -m venv --system-site-packages "$RUNTIME"
 "$RUNTIME/bin/python" -m pip install --disable-pip-version-check -r "$CODE/research_runs/REDESIGN_CLOUD_20261013/requirements.txt" > "$BASE/dependency-install-$REVISION.log" 2>&1 || { echo 'Dependency installation failed. Inspect the non-credential dependency log in /workspace/mi-eeg-cloud.'; exit 1; }
fi
ARGS=(--code-revision "$REVISION" --launch-started-at "$LAUNCH_STARTED_UTC")
[[ -z "$RATE" ]] || ARGS+=(--hourly-rate "$RATE")
[[ -z "$RESUME" ]] || ARGS+=(--resume "$RESUME")
((R2==0)) || ARGS+=(--r2)
((RESET==0)) || ARGS+=(--reset-credentials)
"$RUNTIME/bin/python" "$CODE/research_runs/REDESIGN_CLOUD_20261013/scripts/cloud_supervisor.py" launch "${ARGS[@]}"
