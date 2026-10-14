#!/usr/bin/env bash
set -euo pipefail
# Linux + NVIDIA launcher. Credentials are collected privately by the supervisor.
REVISION=''
RESUME=''
RATE=''
WORK_DIR=''
R2=0
RESET=0
ORIGINAL_ARGS=("$@")
while (($#)); do
 case "$1" in
  --revision) REVISION="${2:?}"; shift 2;;
  --resume) RESUME="${2:?}"; shift 2;;
  --hourly-rate) RATE="${2:?}"; shift 2;;
  --work-dir) WORK_DIR="${2:?}"; shift 2;;
  --r2) R2=1; shift;;
  --reset-credentials) RESET=1; shift;;
  --help) echo 'Usage: bash launch.sh --revision <40-character commit> [--work-dir <persistent Linux directory>] [--hourly-rate <actual USD/hour, <=0.75>] [--resume <job id>] [--r2] [--reset-credentials]'; exit 0;;
  *) echo 'Unknown option'; exit 2;;
 esac
done
[[ "$REVISION" =~ ^[0-9a-f]{40}$ ]] || { echo 'An immutable --revision is required.'; exit 2; }
[[ -z "$RESUME" || "$RESUME" =~ ^[a-zA-Z0-9_-]+$ ]] || { echo 'Invalid job id'; exit 2; }
[[ "$(uname -s)" == Linux ]] || { echo 'This launcher requires Linux with an NVIDIA CUDA GPU.'; exit 2; }
PY=''
for candidate in python3.12 python3.11 python3 python; do
 if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import sys; raise SystemExit(0 if sys.version_info[:2] in ((3,11),(3,12)) else 1)' >/dev/null 2>&1; then
  PY="$(command -v "$candidate")"; break
 fi
done
[[ -n "$PY" ]] || { echo 'Install Python 3.11 or 3.12 (including venv) before retrying; no fitting started.'; exit 2; }
if [[ -z "$WORK_DIR" ]]; then
 if [[ -d /workspace ]]; then WORK_DIR='/workspace/mi-eeg-cloud'; else WORK_DIR="${HOME:?}/mi-eeg-cloud"; fi
fi
BASE="$("$PY" - "$WORK_DIR" <<'PY'
from pathlib import Path
import sys
print(Path(sys.argv[1]).expanduser().resolve())
PY
)"
export MI_EEG_WORK_ROOT="$BASE"
# Guard checkout/runtime construction on the LOCAL /tmp filesystem, never flock
# the persistent FUSE/network volume. The child receives the live locked fd.
exec {USER_STDIN_FD}<&0
"$PY" - "$0" "$BASE" "$USER_STDIN_FD" "${ORIGINAL_ARGS[@]}" <<'PY'
import fcntl,hashlib,os,stat,subprocess,sys
from pathlib import Path
folder=Path('/tmp')/('mi-eeg-bootstrap-'+str(os.getuid()))
try:folder.mkdir(mode=0o700)
except FileExistsError:pass
s=folder.lstat()
if stat.S_ISLNK(s.st_mode) or not stat.S_ISDIR(s.st_mode) or s.st_uid!=os.getuid() or stat.S_IMODE(s.st_mode)!=0o700:
 raise SystemExit('Unsafe local bootstrap lock directory; no worker started.')
path=folder/(hashlib.sha256(sys.argv[2].encode()).hexdigest()+'.lock')
inherited=os.environ.get('_MI_EEG_BOOTSTRAP_LOCK_FD')
if inherited:
 try:
  fd=int(inherited);a=os.fstat(fd);b=path.lstat()
  if (a.st_dev,a.st_ino)!=(b.st_dev,b.st_ino) or not stat.S_ISREG(a.st_mode) or a.st_uid!=os.getuid() or stat.S_IMODE(a.st_mode)!=0o600:raise ValueError()
  fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
 except (OSError,ValueError):raise SystemExit('Invalid inherited bootstrap lock; no worker started.')
 raise SystemExit(0)
fd=os.open(path,os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600)
s=os.fstat(fd)
if not stat.S_ISREG(s.st_mode) or s.st_uid!=os.getuid() or stat.S_IMODE(s.st_mode)!=0o600:
 os.close(fd);raise SystemExit('Unsafe bootstrap lock file; no worker started.')
try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
except BlockingIOError:
 os.close(fd);raise SystemExit('Another launcher is preparing this work directory. Wait for its startup receipt; no second worker started.')
env=dict(os.environ);env['_MI_EEG_BOOTSTRAP_LOCK_FD']=str(fd)
try:
 result=subprocess.run(['bash',sys.argv[1],*sys.argv[4:]],stdin=int(sys.argv[3]),env=env,pass_fds=(fd,))
 raise SystemExit(result.returncode)
finally:os.close(fd)
PY
# An outer invocation exits after its locked child; only the inherited child
# continues. The inherited descriptor is verified above before any workspace write.
[[ -n "${_MI_EEG_BOOTSTRAP_LOCK_FD:-}" ]] || exit 0
command -v git >/dev/null 2>&1 || { echo 'Install git before retrying; no fitting started.'; exit 2; }
command -v nvidia-smi >/dev/null 2>&1 && nvidia-smi -L >/dev/null 2>&1 || { echo 'NVIDIA hardware/driver unavailable. Install the provider NVIDIA driver or choose an NVIDIA GPU server; no fitting started.'; exit 2; }
if [[ -z "$RATE" ]]; then
 read -r -p 'Actual total running server price in USD/hour (visible input, <=0.75): ' RATE
fi
"$PY" - "$RATE" <<'PY'
import math,sys
try:value=float(sys.argv[1])
except ValueError:raise SystemExit('Enter the actual total USD/hour rate, not a token; no fitting started.')
if not math.isfinite(value) or not 0<value<=0.75:raise SystemExit('Approved total running server rate must be >0 and <=0.75 USD/hour; no fitting started.')
PY
mkdir -p "$BASE"
# A persistent registration is authoritative across script revisions. Never
# create another checkout/runtime for a recorded job just because the command
# changed. Resume must name that job and its original science revision.
"$PY" - "$BASE" "$RESUME" "$REVISION" <<'PYREG'
import json,re,sys
from pathlib import Path
base=Path(sys.argv[1]);path=base/'execution_registration.json'
if path.is_symlink():raise SystemExit('Unsafe execution registration; no worker started.')
if not path.exists():
 if sys.argv[2]:raise SystemExit('No existing execution registration for the requested resume; no worker started.')
 raise SystemExit(0)
try:
 record=json.loads(path.read_text());job=record['job_id'];revision=record['code_revision']
 if not isinstance(job,str) or not re.fullmatch(r'[a-zA-Z0-9_-]+',job) or not isinstance(revision,str) or not re.fullmatch(r'[0-9a-f]{40}',revision):raise ValueError()
except (ValueError,KeyError,TypeError):raise SystemExit('Invalid execution registration; no worker started.')
if not sys.argv[2]:
 stage='unavailable_in_registration_checkout'
 status=base/('code-'+revision)/'research_runs/REDESIGN_CLOUD_20261013/jobs'/job/'job_status.json'
 if status.is_file() and not status.is_symlink():
  try:
   candidate=json.loads(status.read_text()).get('stage','unknown')
   if isinstance(candidate,str) and re.fullmatch(r'[A-Za-z0-9_-]{1,120}',candidate):stage=candidate
  except (ValueError,OSError):pass
 print(json.dumps({'status':'EXISTING_JOB_REQUIRES_EXPLICIT_RESUME','job_id':job,'code_revision':revision,'last_saved_stage':stage,'live_worker_status':'NOT_OBSERVED'}))
 raise SystemExit('Existing job registration retained. Use its original --revision and --resume job_id after checking the saved status; no reinstall or second worker started.')
if sys.argv[2]!=job or sys.argv[3]!=revision:raise SystemExit('Resume must match the existing job id and original code revision; registration retained and no worker started.')
PYREG
# Preserve the original eight-hour clock across revisions and all retries.
LAUNCH_STARTED_UTC="$("$PY" - "$BASE" <<'PY'
from datetime import datetime,timezone,timedelta
from pathlib import Path
import json,os,shutil,sys
base=Path(sys.argv[1]);p=base/'budget_origin.json'
if p.is_symlink():raise SystemExit('Unsafe budget origin file; no fitting started.')
if p.exists():started=datetime.fromisoformat(json.loads(p.read_text())['started_at_utc'])
else:
 started=datetime.now(timezone.utc);tmp=p.with_suffix('.tmp');tmp.write_text(json.dumps({'started_at_utc':started.isoformat()})+'\n');os.replace(tmp,p)
if started.tzinfo is None or started.utcoffset().total_seconds()!=0 or started>datetime.now(timezone.utc)+timedelta(seconds=5):raise SystemExit('Invalid budget origin timestamp; no fitting started.')
if datetime.now(timezone.utc)>=started+timedelta(hours=8):raise SystemExit('Original eight-hour budget clock is exhausted. Stop server billing manually; no fitting started.')
if shutil.disk_usage(base).free<10*1024**3:raise SystemExit('At least 10 GiB of free working storage is required; no fitting started.')
print(started.isoformat())
PY
)"
# Bound setup/network/install subprocesses by the same clock as the worker.
run_bounded() {
 "$PY" - "$BASE/budget_origin.json" "$USER_STDIN_FD" "$@" <<'PY'
from datetime import datetime,timezone,timedelta
from pathlib import Path
import json,os,signal,subprocess,sys
started=datetime.fromisoformat(json.loads(Path(sys.argv[1]).read_text())['started_at_utc'])
seconds=(started+timedelta(hours=8)-datetime.now(timezone.utc)).total_seconds()
if seconds<=0:raise SystemExit('Original eight-hour budget clock exhausted; stop server billing manually.')
process=subprocess.Popen(sys.argv[3:],stdin=int(sys.argv[2]),start_new_session=True)
try:code=process.wait(timeout=seconds)
except subprocess.TimeoutExpired:
 try:os.killpg(process.pid,signal.SIGTERM);process.wait(timeout=5)
 except ProcessLookupError:pass
 except subprocess.TimeoutExpired:os.killpg(process.pid,signal.SIGKILL);process.wait()
 raise SystemExit('Setup reached the original eight-hour deadline; stop server billing manually.')
raise SystemExit(code)
PY
}
CODE="$BASE/code-$REVISION"
if [[ ! -d "$CODE/.git" ]]; then
 run_bounded git clone --depth 1 --branch research/source-selection-redesign-20261012 https://github.com/jackzhu119/cross-subject-mi-eeg.git "$CODE"
 run_bounded git -C "$CODE" fetch --depth 1 origin "$REVISION"
 run_bounded git -C "$CODE" checkout --detach "$REVISION"
fi
[[ "$(git -C "$CODE" rev-parse HEAD)" == "$REVISION" ]] || { echo 'Code revision mismatch; existing checkout left intact.'; exit 2; }
REQUIREMENTS="$CODE/research_runs/REDESIGN_CLOUD_20261013/requirements.txt"
runtime_ok() {
 "$1" - "$REQUIREMENTS" <<'PY' >/dev/null 2>&1
import importlib.metadata,sys
from pathlib import Path
import torch,torchaudio
assert sys.version_info[:2] in ((3,11),(3,12))
assert torch.__version__.split('+')[0]==torchaudio.__version__.split('+')[0]=='2.8.0' and torch.version.cuda=='12.8' and torch.cuda.is_available()
for line in Path(sys.argv[1]).read_text().splitlines():
 if '==' in line and not line.lstrip().startswith('#'):
  name,version=line.strip().split('==');assert importlib.metadata.version(name)==version
PY
}
# Reuse only a measured exact runtime, including all pinned packages. This also
# avoids downloading PyTorch again when a launcher-only fix changes the revision.
RUNTIME=''
for existing in "$BASE"/runtime-*/bin/python; do
 if [[ -x "$existing" ]] && runtime_ok "$existing"; then RUNTIME="${existing%/bin/python}"; break; fi
done
if [[ -z "$RUNTIME" ]]; then
 MODE='isolated'
 if "$PY" - <<'PY' >/dev/null 2>&1
import torch,torchaudio
assert torch.__version__.split('+')[0]==torchaudio.__version__.split('+')[0]=='2.8.0' and torch.version.cuda=='12.8' and torch.cuda.is_available()
PY
 then MODE='inherit'; fi
 RECIPE="$("$PY" - "$REQUIREMENTS" "$MODE" <<'PY'
import hashlib,sys
from pathlib import Path
print(hashlib.sha256(Path(sys.argv[1]).read_bytes()+b'|torch2.8.0|torchaudio2.8.0|cu128|'+sys.argv[2].encode()+str(sys.version_info[:2]).encode()).hexdigest()[:20])
PY
)"
 RUNTIME="$BASE/runtime-$RECIPE"
 if [[ ! -x "$RUNTIME/bin/python" ]]; then
  if [[ "$MODE" == inherit ]]; then run_bounded "$PY" -m venv --system-site-packages "$RUNTIME"; else run_bounded "$PY" -m venv "$RUNTIME"; fi
 fi
 LOG="$BASE/dependency-install-$RECIPE.log"
 if [[ "$MODE" == isolated ]]; then
  echo 'Installing exact PyTorch 2.8.0 / CUDA 12.8 in an isolated environment. No fitting started.'
  run_bounded "$RUNTIME/bin/python" -m pip install --disable-pip-version-check torch==2.8.0 torchaudio==2.8.0 --index-url https://download.pytorch.org/whl/cu128 > "$LOG" 2>&1 || { echo "GPU dependency installation failed. Inspect $LOG locally; do not paste credentials."; exit 1; }
 fi
 run_bounded "$RUNTIME/bin/python" -m pip install --disable-pip-version-check -r "$REQUIREMENTS" >> "$LOG" 2>&1 || { echo "Dependency installation failed. Inspect $LOG locally; do not paste credentials."; exit 1; }
 runtime_ok "$RUNTIME/bin/python" || { echo 'Exact CUDA runtime/package verification failed. No CPU fallback, fitting or worker started.'; exit 2; }
 printf '%s\n' "$RECIPE" > "$RUNTIME/.requirements-installed"
fi
"$RUNTIME/bin/python" - <<'PY'
import torch
x=torch.ones(1,device='cuda');assert x.item()==1.0
print('Exact GPU runtime verified. No fitting has started.')
PY
ARGS=(--code-revision "$REVISION" --launch-started-at "$LAUNCH_STARTED_UTC" --hourly-rate "$RATE")
[[ -z "$RESUME" ]] || ARGS+=(--resume "$RESUME")
((R2==0)) || ARGS+=(--r2)
((RESET==0)) || ARGS+=(--reset-credentials)
run_bounded "$RUNTIME/bin/python" "$CODE/research_runs/REDESIGN_CLOUD_20261013/scripts/cloud_supervisor.py" launch "${ARGS[@]}"
