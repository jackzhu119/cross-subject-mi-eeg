#!/usr/bin/env bash
# Data preparation and GitHub report publication only; no fit or Pod stop.
set -euo pipefail
umask 077
trap 'printf "Q15 preparation launcher failed; no training was started.\n" >&2' ERR

REVISION=380fbf5306b84a53959b141d70800ccefff5abca
printf 'Q15 migration preparation: fits_started = 0. This release does not train or stop the Pod.\n'

if [[ -z "${GH_TOKEN:-}" && "${1:-}" != "--no-github" && -t 0 ]]; then
  printf 'GitHub repo-scoped Contents write token is needed for automatic report publication.\n'
  read -r -s -p 'GH_TOKEN (hidden input; Enter saves reports locally only): ' GH_TOKEN
  printf '\n'
fi
if [[ "${1:-}" == "--no-github" ]]; then
  unset GH_TOKEN
fi
if [[ -n "${GH_TOKEN:-}" ]]; then
  export GH_TOKEN
else
  printf 'GitHub publication is not configured; reports will remain on the mounted volume.\n'
fi

runtime=$(mktemp -d /tmp/q15-prepare-runtime.XXXXXXXX)
python3 - "$runtime" <<'PY'
import os,stat,sys
s=os.stat(sys.argv[1]); assert s.st_uid==os.getuid() and stat.S_IMODE(s.st_mode)==0o700
PY
export GIT_TERMINAL_PROMPT=0
git init -q "$runtime/repo"
git -C "$runtime/repo" remote add origin https://github.com/jackzhu119/cross-subject-mi-eeg.git
git -C "$runtime/repo" fetch -q --depth=1 origin "$REVISION"
git -C "$runtime/repo" checkout -q --detach FETCH_HEAD
[[ "$(git -C "$runtime/repo" rev-parse HEAD)" == "$REVISION" ]]
python3 -m venv "$runtime/venv"
printf 'Installing isolated metadata observation dependencies...\n'
"$runtime/venv/bin/python" -m pip install --disable-pip-version-check --quiet numpy==2.5.3 scipy==1.18.1 >"$runtime/dependency-install.log" 2>&1

job_id=$(python3 - <<'PY'
from datetime import datetime,timezone
import uuid
print(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:12])
PY
)
job="/workspace/q15-preparation/jobs/$job_id"
mkdir -p "$job"
nohup "$runtime/venv/bin/python" "$runtime/repo/scripts/q15_cloud/q15_prepare.py" \
  --output "$job" >"$job/supervisor.log" 2>&1 < /dev/null &
worker_pid=$!

# Verify that the child has entered preparation, rather than merely printing a PID.
"$runtime/venv/bin/python" - "$worker_pid" "$job" <<'PY'
import json,os,sys,time
from pathlib import Path
pid=int(sys.argv[1]);job=Path(sys.argv[2]);seen=False
for attempt in range(50):
    if (job/'failure.json').exists():
        print(json.dumps({'status':'worker_startup_failed','fits_started':0}));raise SystemExit(1)
    if (job/'preparation_status.json').exists():
        seen=True;break
    try:os.kill(pid,0)
    except ProcessLookupError:
        print(json.dumps({'status':'worker_exited_before_startup','fits_started':0}));raise SystemExit(1)
    time.sleep(0.1)
if not seen:
    print(json.dumps({'status':'worker_startup_unverified','fits_started':0}));raise SystemExit(1)
pod=os.environ.get('RUNPOD_POD_ID','')
if pod and not all(c.isalnum() or c in '-_' for c in pod):pod='unverified'
receipt={'status':'detached_preparation_started_training_not_started','pid':pid,
         'pod_id_from_environment':pod or 'unavailable','job_directory':str(job),
         'github_publication_configured':bool(os.environ.get('GH_TOKEN')),
         'fits_started':0,'auto_training_enabled':False,'auto_shutdown_enabled':False}
(job/'launch_receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt),flush=True)
PY
printf 'Track progress: cat %s/preparation_status.json\n' "$job"
printf 'Read logs: tail -n 20 %s/supervisor.log\n' "$job"
