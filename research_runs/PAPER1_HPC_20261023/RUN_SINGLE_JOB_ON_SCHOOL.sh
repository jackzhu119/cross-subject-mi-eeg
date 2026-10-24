#!/usr/bin/env bash
# Fixed operations overlay; one enclosing Slurm job after login preparation.
set -euo pipefail
PROJECTS_ROOT="${1:-/public/home/zhuziyuan/projects}"
PYTHON_BIN="${PAPER1_PYTHON:-/public/home/zhuziyuan/.venvs/paper3-hpc-cu121-offline/bin/python}"
SOURCE_REV="1b1aa792f866add27a01d52e55cd593621880888"
PATCH_SHA="35943ff0f30426ac98a1d7fe1968fab2f9c0cf0609490c473510fc39cdacfa7b"
SETUP_SHA="12c8d38e29185283648c08f3450ae8f31e6c94e14aa931d37ac442e4df875f82"
BASE_URL="https://raw.githubusercontent.com/jackzhu119/cross-subject-mi-eeg/$SOURCE_REV/research_runs/PAPER1_HPC_20261023"
mkdir -p "$PROJECTS_ROOT/paper1-risk-v1/state"
PROJECTS_ROOT="$(cd "$PROJECTS_ROOT" && pwd)"
PROJECT="$PROJECTS_ROOT/paper1-risk-v1"
CODE_ROOT="$PROJECTS_ROOT/PAPER1_HPC_20261023"
CACHE="$PROJECT/state/single-job-install-cache"
mkdir -p "$CACHE"
exec 9>"$PROJECT/state/single-job-install.lock"
if ! flock -n 9; then
  printf 'Another single-job setup is active; no duplicate setup/submission started.\n'
  exit 0
fi
if [ ! -x "$PYTHON_BIN" ]; then
  printf 'Existing school Python is not executable: %s\n' "$PYTHON_BIN" >&2
  exit 2
fi
export PAPER1_PYTHON="$PYTHON_BIN"
fetch_verified() {
  local url="$1" target="$2" expected="$3" observed
  if [ -f "$target" ]; then
    observed="$(sha256sum "$target")"
    if [ "${observed%% *}" = "$expected" ]; then return; fi
    printf 'Cached operations file checksum differs; retained: %s\n' "$target" >&2
    exit 2
  fi
  curl -fL --connect-timeout 20 --max-time 600 --retry 3 --retry-delay 5 "$url" -o "$target.part"
  observed="$(sha256sum "$target.part")"
  if [ "${observed%% *}" != "$expected" ]; then
    printf 'Operations download checksum differs; partial retained: %s.part\n' "$target" >&2
    exit 2
  fi
  mv "$target.part" "$target"
}
SETUP="$CACHE/setup-$SOURCE_REV.sh"
PATCH="$CACHE/operations-$PATCH_SHA.tar.gz"
fetch_verified "$BASE_URL/DOWNLOAD_ON_SCHOOL.sh" "$SETUP" "$SETUP_SHA"
fetch_verified "$BASE_URL/dist/paper1-single-job-operations.tar.gz" "$PATCH" "$PATCH_SHA"
# The bootstrap's setup-only branch never submits the historical download job.
PAPER1_SETUP_ONLY=1 bash "$SETUP" "$PROJECTS_ROOT"
"$PYTHON_BIN" - "$PATCH" "$CODE_ROOT" "$PROJECT" "$PATCH_SHA" <<'INSTALL_OPERATIONS'
import datetime,hashlib,json,os,sys,tarfile,tempfile
from pathlib import Path
archive,code,project=map(Path,sys.argv[1:4]); expected=sys.argv[4]
assert hashlib.sha256(archive.read_bytes()).hexdigest()==expected,'Operations archive SHA mismatch'
allowed={'LAUNCH.sh','hpcmi/acquire.py','hpcmi/cli.py','hpcmi/github_sync.py',
         'hpcmi/single_job.py','hpcmi/submit_single.py','slurm/single_job.sh','SINGLE_JOB.md'}
with tarfile.open(archive,'r:gz') as source:
    members=source.getmembers()
    assert all(m.isfile() for m in members),'Unexpected non-file operations member'
    assert {m.name for m in members}==allowed|{'OPERATIONS_MANIFEST.json'},'Unexpected operations inventory'
    assert len(members)==len(allowed)+1 and sum(m.size for m in members)<2*1024*1024,'Invalid operations size'
    manifest=json.load(source.extractfile('OPERATIONS_MANIFEST.json'))
    assert {r['path'] for r in manifest['files']}==allowed and len(manifest['files'])==len(allowed)
    payloads={}
    for row in manifest['files']:
        data=source.extractfile(row['path']).read()
        assert len(data)==row['bytes'] and hashlib.sha256(data).hexdigest()==row['sha256'],'Operations payload SHA mismatch'
        payloads[row['path']]=data
backup=project/'state/single-job-overlay'/expected
backup.mkdir(parents=True,exist_ok=True);backup.chmod(0o700)
changes=[]
for relative,data in payloads.items():
    dest=code/relative
    assert dest.resolve().is_relative_to(code.resolve()),'Operations destination leaves project code'
    before=dest.read_bytes() if dest.exists() else None
    if before==data:
        continue
    if before is not None:
        saved=backup/'before'/relative
        saved.parent.mkdir(parents=True,exist_ok=True)
        if not saved.exists():
            saved.write_bytes(before);saved.chmod(0o600)
    dest.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix=dest.name+'.',suffix='.tmp',dir=dest.parent)
    with os.fdopen(fd,'wb') as out:
        out.write(data);out.flush();os.fsync(out.fileno())
    os.chmod(tmp,0o755 if relative.endswith('.sh') else 0o644)
    os.replace(tmp,dest)
    changes.append({'path':relative,'previous_sha256':hashlib.sha256(before).hexdigest() if before is not None else None,
                    'installed_sha256':hashlib.sha256(data).hexdigest()})
receipt=backup/'installation.json'
if not receipt.exists():
    receipt.write_text(json.dumps({'installed_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'operations_archive_sha256':expected,'changes':changes,'scientific_model_or_input_files_changed':False},indent=2)+'\n')
print(json.dumps({'single_job_operations_ready':True,'updated_files':len(changes)}),flush=True)
INSTALL_OPERATIONS
# Token input and the small isolated CPU environment are prepared on login1;
# download, preprocessing, model checks, fits and scoring share one Slurm job.
exec bash "$CODE_ROOT/LAUNCH.sh" --project "$PROJECT" --raw-dir "$PROJECT/raw" --wheelhouse "$CODE_ROOT/wheelhouse"
