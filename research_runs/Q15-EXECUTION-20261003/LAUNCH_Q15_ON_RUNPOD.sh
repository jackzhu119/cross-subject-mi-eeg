#!/usr/bin/env bash
# Run this manually on the intended, already-running RunPod after preparation.
# The detached worker trains source only after committed audits and freezes.
set -euo pipefail
umask 077

CODE_REVISION=271af288a2f3863430ab80e3145c2dee9bd5571d
Q15_REPOSITORY=https://github.com/jackzhu119/cross-subject-mi-eeg.git
Q15_WORKSPACE=/workspace
Q15_REPO="$Q15_WORKSPACE/q15-execution/repo"
Q15_CONTROL="$Q15_WORKSPACE/.q15-cloud"
Q15_CHECK_ONLY=0
Q15_JOB_ID=''
while (($#)); do
  case "$1" in
    --check-only) Q15_CHECK_ONLY=1; shift ;;
    --job-id) [[ $# -ge 2 ]] || { printf 'Missing --job-id value.\n' >&2; exit 2; }; Q15_JOB_ID=$2; shift 2 ;;
    *) printf 'Usage: bash LAUNCH_Q15_ON_RUNPOD.sh [--check-only] [--job-id existing-id]\n' >&2; exit 2 ;;
  esac
done
[[ "$CODE_REVISION" =~ ^[0-9a-f]{40}$ ]] || { printf 'Launcher code revision has not been pinned.\n' >&2; exit 1; }
[[ "${RUNPOD_POD_ID:-}" =~ ^[A-Za-z0-9_-]{1,64}$ ]] || { printf 'RUNPOD_POD_ID is missing or invalid; no worker started.\n' >&2; exit 1; }
[[ -z "$Q15_JOB_ID" || "$Q15_JOB_ID" =~ ^[A-Za-z0-9_-]{1,80}$ ]] || { printf 'Invalid job ID.\n' >&2; exit 2; }
command -v flock >/dev/null || { printf 'flock is required; no worker started.\n' >&2; exit 1; }
[[ -d "$Q15_WORKSPACE" && ! -L "$Q15_CONTROL" && ! -L "$Q15_REPO" ]] || { printf 'Persistent workspace path is unsafe.\n' >&2; exit 1; }
mkdir -p "$Q15_CONTROL" "$Q15_WORKSPACE/q15-execution"
# Keep duplicate launches outside dependency setup and all stop/failure paths.
[[ ! -L "$Q15_CONTROL/launch.lock" && ! -L "$Q15_CONTROL/active.lock" ]] || { printf 'Unsafe supervisor lock path.\n' >&2; exit 1; }
exec 8>"$Q15_CONTROL/launch.lock"
flock -n 8 || { printf 'Another Q15 launcher is active; no worker started.\n' >&2; exit 1; }
exec 9>"$Q15_CONTROL/active.lock"
flock -n 9 || { printf 'A cloud supervisor is already active; no worker started or stopped.\n' >&2; exit 1; }

Q15_RUNTIME=$(mktemp -d /tmp/q15-full-runtime.XXXXXXXX)
trap 'printf "Q15 launcher exited with an error. Check the printed job status; private dependency log: %s/dependency-install.log\n" "$Q15_RUNTIME" >&2' ERR
mkdir -m 700 "$Q15_RUNTIME/tmp" "$Q15_RUNTIME/pip-cache"
export GIT_TERMINAL_PROMPT=0
if [[ ! -d "$Q15_REPO/.git" ]]; then
  [[ ! -e "$Q15_REPO" ]] || { printf 'Execution repository exists without Git metadata.\n' >&2; exit 1; }
  env -u GH_TOKEN -u GITHUB_TOKEN -u RUNPOD_API_KEY git init -q "$Q15_REPO"
  env -u GH_TOKEN -u GITHUB_TOKEN -u RUNPOD_API_KEY git -C "$Q15_REPO" remote add origin "$Q15_REPOSITORY"
  env -u GH_TOKEN -u GITHUB_TOKEN -u RUNPOD_API_KEY git -C "$Q15_REPO" fetch -q --depth=1 origin "$CODE_REVISION"
  env -u GH_TOKEN -u GITHUB_TOKEN -u RUNPOD_API_KEY git -C "$Q15_REPO" checkout -q --detach FETCH_HEAD
  [[ "$(git -C "$Q15_REPO" rev-parse HEAD)" == "$CODE_REVISION" ]]
else
  [[ "$(git -C "$Q15_REPO" remote get-url origin)" == "$Q15_REPOSITORY" ]] || { printf 'Execution repository origin differs.\n' >&2; exit 1; }
  # Preserve validated checkpoints and publication commits on a resumed volume.
  env -u GH_TOKEN -u GITHUB_TOKEN -u RUNPOD_API_KEY git -C "$Q15_REPO" fetch -q origin "$CODE_REVISION"
fi

# The user's CUDA template provides these wheels. Never replace them from PyPI.
env -u GH_TOKEN -u GITHUB_TOKEN -u RUNPOD_API_KEY python3 - <<'PY'
import importlib.metadata
import sys
import torch
assert sys.version_info[:2] == (3, 12), 'Expected template Python 3.12'
assert torch.__version__ == '2.8.0+cu128', 'Expected template Torch 2.8.0+cu128'
assert torch.version.cuda == '12.8' and torch.cuda.is_available(), 'CUDA 12.8 GPU unavailable'
assert importlib.metadata.version('torchaudio') == '2.8.0+cu128', 'Expected template TorchAudio 2.8.0+cu128'
PY
env -u GH_TOKEN -u GITHUB_TOKEN -u RUNPOD_API_KEY python3 -m venv --system-site-packages "$Q15_RUNTIME/venv"
printf 'Installing the committed Q15 runtime in a private environment. No fitting has started.\n'
env -u GH_TOKEN -u GITHUB_TOKEN -u RUNPOD_API_KEY TMPDIR="$Q15_RUNTIME/tmp" PIP_CACHE_DIR="$Q15_RUNTIME/pip-cache" \
  "$Q15_RUNTIME/venv/bin/python" -m pip install --disable-pip-version-check --no-cache-dir \
  -r "$Q15_REPO/requirements-q15-runtime.txt" >"$Q15_RUNTIME/dependency-install.log" 2>&1
env -u GH_TOKEN -u GITHUB_TOKEN -u RUNPOD_API_KEY TMPDIR="$Q15_RUNTIME/tmp" PIP_CACHE_DIR="$Q15_RUNTIME/pip-cache" \
  "$Q15_RUNTIME/venv/bin/python" -m pip install --disable-pip-version-check --no-cache-dir --no-deps \
  --editable "$Q15_REPO" >>"$Q15_RUNTIME/dependency-install.log" 2>&1

if [[ -z "${GH_TOKEN:-}" && -t 0 ]]; then
  read -r -s -p 'GitHub repo-scoped Contents write token (hidden): ' GH_TOKEN
  printf '\n'
fi
if [[ -z "${RUNPOD_API_KEY:-}" && -t 0 ]]; then
  read -r -s -p 'RunPod API key for this current Pod only (hidden): ' RUNPOD_API_KEY
  printf '\n'
fi
[[ -n "${GH_TOKEN:-}" && -n "${RUNPOD_API_KEY:-}" ]] || { printf 'Both private credentials are required; no worker started.\n' >&2; exit 1; }
export GH_TOKEN RUNPOD_API_KEY
if [[ -z "$Q15_JOB_ID" ]]; then
  Q15_JOB_ID=$(python3 - <<'PY'
from datetime import datetime, timezone
import uuid
print(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:12])
PY
)
elif [[ "$Q15_CHECK_ONLY" == 0 && ! -f "$Q15_WORKSPACE/q15-execution/jobs/$Q15_JOB_ID/job_status.json" ]]; then
  printf 'The supplied resume job ID has no existing status receipt.\n' >&2
  exit 1
fi
Q15_JOB="$Q15_WORKSPACE/q15-execution/jobs/$Q15_JOB_ID"
mkdir -p "$Q15_JOB"
Q15_ARGUMENTS=(--job-id "$Q15_JOB_ID" --revision "$CODE_REVISION" --workspace "$Q15_WORKSPACE")

if [[ "$Q15_CHECK_ONLY" == 1 ]]; then
  # No raw downloads, EEG load, source fits, target inference, or Pod stop.
  flock -u 9
  "$Q15_RUNTIME/venv/bin/python" "$Q15_REPO/scripts/q15_cloud/q15_full_job.py" "${Q15_ARGUMENTS[@]}" --check-only 9>&- 8>&-
  exit $?
fi

printf 'Starting Q15 on the current Pod. Source fits require two committed audit/freeze gates.\n'
flock -u 9
nohup "$Q15_RUNTIME/venv/bin/python" "$Q15_REPO/scripts/q15_cloud/q15_full_job.py" \
  "${Q15_ARGUMENTS[@]}" >"$Q15_JOB/supervisor.log" 2>&1 < /dev/null 9>&- 8>&- &
Q15_WORKER_PID=$!
"$Q15_RUNTIME/venv/bin/python" - "$Q15_WORKER_PID" "$Q15_JOB" "$CODE_REVISION" <<'PY'
import json, os, sys, time
from pathlib import Path
pid, job, revision = int(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
seen = False
for attempt in range(450):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        print(json.dumps({'status': 'worker_exited_before_startup_verification', 'job_id': job.name}))
        raise SystemExit(1)
    status_path = job / 'job_status.json'
    if status_path.is_file():
        state = json.loads(status_path.read_text())
        if state.get('supervisor_pid') != pid:
            time.sleep(0.1)
            continue
        if state.get('startup_verified') is True:
            seen = True
            break
        if state.get('status') in ('failed_or_blocked', 'failed_backup_manual_attention_required', 'manual_attention_required'):
            print(json.dumps({'status': 'worker_startup_failed', 'job_id': job.name, 'error_code': state.get('error_code')}))
            raise SystemExit(1)
    time.sleep(0.1)
if not seen:
    print(json.dumps({'status': 'worker_startup_unverified', 'job_id': job.name, 'worker_may_still_be_running': True}))
    raise SystemExit(1)
receipt = {'status': 'detached_worker_startup_verified', 'pid': pid, 'job_id': job.name,
           'code_revision': revision, 'pod_id': os.environ['RUNPOD_POD_ID'],
           'target_fits': 0, 'fits_started_at_verification': state.get('fits_started'),
           'gpu_runtime_preflight_verified': state.get('gpu_computation_verified') is True,
           'auto_shutdown_requires_verified_github_backup': True}
(job / 'launch_receipt.json').write_text(json.dumps(receipt, sort_keys=True, indent=2) + '\n')
print(json.dumps(receipt), flush=True)
PY
printf 'Progress: cat %s/job_status.json\n' "$Q15_JOB"
printf 'Logs: tail -n 30 %s/supervisor.log\n' "$Q15_JOB"
printf 'Keep the network volume attached; resume with --job-id %s after interruption.\n' "$Q15_JOB_ID"
