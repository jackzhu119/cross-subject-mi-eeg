#!/usr/bin/env bash
# Small login-node bootstrap. Large EEG transfer/extraction runs in Slurm.
set -euo pipefail
PROJECTS_ROOT="${1:-/public/home/zhuziyuan/projects}"
PYTHON_BIN="${PAPER1_PYTHON:-/public/home/zhuziyuan/.venvs/paper3-hpc-cu121-offline/bin/python}"
PARTITION="${PAPER1_PARTITION:-hpc_gpu}"
GPU_REQUEST="${PAPER1_GRES:-gpu:1}"
BUNDLE_SHA="72225f30c83be9bbc94d52eac672bee272690f6cf9949933e3d61380401d2675"
# Exact original Git blob, served directly by the official API. This does not
# redirect through raw.githubusercontent.com (which timed out on the observed school link).
BUNDLE_URL="https://api.github.com/repos/jackzhu119/cross-subject-mi-eeg/git/blobs/6e4661c5fc6f1ac5530bcebddd746608cf6310e8"
mkdir -p "$PROJECTS_ROOT"
PROJECTS_ROOT="$(cd "$PROJECTS_ROOT" && pwd)"
PROJECT="$PROJECTS_ROOT/paper1-risk-v1"
CODE_ROOT="$PROJECTS_ROOT/PAPER1_HPC_20261023"
ARCHIVE="$PROJECTS_ROOT/paper1-hpc-offline.tar.gz"
mkdir -p "$PROJECT/state" "$PROJECT/logs/slurm"
if [ ! -x "$PYTHON_BIN" ]; then
  printf 'Prepared Python is not executable: %s\nSet PAPER1_PYTHON to its actual path.\n' "$PYTHON_BIN" >&2
  exit 2
fi
exec 9>"$PROJECT/state/download-submit.lock"
if ! flock -n 9; then
  printf 'Another download submission is being prepared; no duplicate submitted.\n'
  exit 0
fi
if [ -f "$ARCHIVE" ]; then
  OBSERVED_SHA="$(sha256sum "$ARCHIVE")"
  if [ "${OBSERVED_SHA%% *}" != "$BUNDLE_SHA" ]; then
    printf 'Existing archive checksum differs; file retained: %s\n' "$ARCHIVE" >&2
    exit 2
  fi
else
  printf 'Downloading the fixed 53MB code/dependency bundle directly to school storage.\n'
  PART_SHA=""
  if [ -f "$ARCHIVE.part" ]; then PART_SHA="$(sha256sum "$ARCHIVE.part")"; fi
  if [ "${PART_SHA%% *}" = "$BUNDLE_SHA" ]; then
    mv "$ARCHIVE.part" "$ARCHIVE"
  else
    # The API returns the complete blob rather than HTTP byte ranges. Never
    # append that response to an old raw-host partial or silently truncate it.
    API_PART="$ARCHIVE.api-download.part"
    API_SHA=""
    if [ -f "$API_PART" ]; then API_SHA="$(sha256sum "$API_PART")"; fi
    if [ -f "$API_PART" ] && [ "${API_SHA%% *}" != "$BUNDLE_SHA" ]; then
      SAVED_API_PART="$(mktemp "$ARCHIVE.api-interrupted.XXXXXX")"
      mv "$API_PART" "$SAVED_API_PART"
      printf 'Preserved interrupted API transfer: %s\n' "$SAVED_API_PART"
    fi
    if [ "${API_SHA%% *}" != "$BUNDLE_SHA" ]; then
      curl -4 -f --connect-timeout 8 --max-time 900 --speed-time 30 --speed-limit 128 --retry 1 --retry-delay 2 \
        -H 'Accept: application/vnd.github.raw+json' "$BUNDLE_URL" -o "$API_PART"
    fi
    OBSERVED_SHA="$(sha256sum "$API_PART")"
    if [ "${OBSERVED_SHA%% *}" != "$BUNDLE_SHA" ]; then
      printf 'Downloaded archive checksum differs; partial retained: %s\n' "$API_PART" >&2
      exit 2
    fi
    mv "$API_PART" "$ARCHIVE"
  fi
fi
if [ -d "$CODE_ROOT" ]; then
  if [ ! -f "$CODE_ROOT/OFFLINE_MANIFEST.json" ]; then
    printf 'Existing code directory has no distribution manifest; retained: %s\n' "$CODE_ROOT" >&2
    exit 2
  fi
  "$PYTHON_BIN" -c 'import json,sys; p=json.load(open(sys.argv[1])); assert p["revision"]=="74faa2e580263da1486be35bf9fd73e6a9754b9f", "Existing package revision differs; directory retained"' "$CODE_ROOT/OFFLINE_MANIFEST.json"
  printf 'Reusing the extracted fixed package.\n'
else
  # Publish the code directory only after the entire archive was extracted.
  # Interrupted extraction is reconstructed from the already verified archive.
  STAGING="$PROJECTS_ROOT/.paper1-hpc-extract"
  mkdir -p "$STAGING"
  tar -xzf "$ARCHIVE" -C "$STAGING"
  mv "$STAGING/PAPER1_HPC_20261023" "$CODE_ROOT"
  rmdir "$STAGING"
fi
cd "$CODE_ROOT"
# The immutable archive retains its original source identity. These are
# resource-only overrides, applied to both fresh defaults and an existing run.
"$PYTHON_BIN" - "$CODE_ROOT" "$PROJECT" "$PARTITION" "$GPU_REQUEST" <<'SCHOOL_CLUSTER_OVERRIDE'
import datetime,json,os,sys,tempfile
from pathlib import Path
code,project=map(Path,sys.argv[1:3]); partition,gres=sys.argv[3:]
changes=[]
for path in (code/'config/cluster.json',project/'config/cluster.json'):
    if not path.exists():
        continue
    old=json.loads(path.read_text())
    new={**old,'partition':partition,'gres':gres,'exclude':[],
         'cpus_per_task':13,'max_parallel':2}
    if old==new:
        continue
    journal=project/'state/cluster-overrides'
    journal.mkdir(parents=True,exist_ok=True)
    stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    tag='code' if path.parent.parent==code else 'project'
    (journal/(stamp+'-'+tag+'-before.json')).write_bytes(path.read_bytes())
    fd,tmp=tempfile.mkstemp(prefix=path.name+'.',suffix='.tmp',dir=path.parent)
    with os.fdopen(fd,'w') as f:
        json.dump(new,f,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
    os.replace(tmp,path)
    changes.append({'path':str(path),'before':old,'after':new})
if changes:
    (journal/(stamp+'-amendment.json')).write_text(json.dumps({
        'reason':'User requested one node, two GPUs, total 26 CPUs and 128G on 24 October; this covers legacy per-worker CPU metadata',
        'scientific_configuration_changed':False,'changes':changes},indent=2)+'\n')
print(json.dumps({'partition':partition,'gres':gres,'updated_cluster_configs':len(changes)}),flush=True)
SCHOOL_CLUSTER_OVERRIDE
if [ "${PAPER1_SETUP_ONLY:-0}" = 1 ]; then
  printf 'Fixed bundle prepared; no Slurm job submitted by setup-only mode.\n'
  exit 0
fi
if "$PYTHON_BIN" -c 'import sys; from hpcmi.acquire import quick_raw_ready; sys.exit(0 if quick_raw_ready(sys.argv[1]) else 10)' "$PROJECT/raw"; then
  printf 'All raw inputs are already present. Start/resume training with:\n'
  printf 'bash %q --project %q --raw-dir %q\n' "$CODE_ROOT/LAUNCH.sh" "$PROJECT" "$PROJECT/raw"
  exit 0
else
  READY_EXIT=$?
  if [ "$READY_EXIT" -ne 10 ]; then exit "$READY_EXIT"; fi
fi
PROJECT_KEY="$(printf '%s' "$PROJECT" | sha256sum)"
JOB_NAME="p1-download-${PROJECT_KEY:0:10}"
ACTIVE="$(squeue -h -u zhuziyuan -n "$JOB_NAME" -o '%i|%j|%u|%T|%P|%Z')"
if [ -n "$ACTIVE" ]; then
  if [[ "$ACTIVE" == *$'\n'* ]]; then
    printf 'Multiple matching download jobs observed; records retained: %s\n' "$ACTIVE" >&2
    exit 2
  fi
  IFS='|' read -r OLD_ID OLD_NAME OLD_OWNER OLD_STATE OLD_PARTITION OLD_DIRECTORY <<< "$ACTIVE"
  if [[ ! "$OLD_ID" =~ ^[0-9]+$ ]] || [ "$OLD_NAME" != "$JOB_NAME" ] || [ "$OLD_OWNER" != zhuziyuan ] || [ "$OLD_DIRECTORY" != "$PROJECT" ]; then
    printf 'Existing scheduler identity does not match this download; no job cancelled: %s\n' "$ACTIVE" >&2
    exit 2
  fi
  if [ "$OLD_PARTITION" = "$PARTITION" ]; then
    printf 'Existing data-download job already uses %s: %s\n' "$PARTITION" "$OLD_ID"
    exit 0
  fi
  if [ "$OLD_STATE" != PENDING ]; then
    printf 'Existing download is %s on %s, job %s; it was preserved and no duplicate was submitted.\n' "$OLD_STATE" "$OLD_PARTITION" "$OLD_ID"
    exit 0
  fi
  MIGRATION="$PROJECT/state/download-migration-$OLD_ID"
  printf '%s\n' "$ACTIVE" > "$MIGRATION-before.txt"
  if [ -f "$PROJECT/state/download-data.sbatch" ] && [ ! -f "$MIGRATION-original.sbatch" ]; then
    cp -p "$PROJECT/state/download-data.sbatch" "$MIGRATION-original.sbatch"
  fi
  # Filter again inside scancel: if it started since squeue, preserve it.
  scancel --state=PENDING "$OLD_ID"
  AFTER="$(squeue -h -u zhuziyuan -n "$JOB_NAME" -o '%i|%j|%u|%T|%P|%Z')"
  printf '%s\n' "$AFTER" > "$MIGRATION-after.txt"
  if [ -n "$AFTER" ]; then
    printf 'Old download is still observed; retained, no replacement submitted: %s\n' "$AFTER"
    exit 0
  fi
  printf 'Replaced pending download %s from %s; existing raw files retained.\n' "$OLD_ID" "$OLD_PARTITION"
fi
JOB_SCRIPT="$PROJECT/state/download-data.sbatch"
JOB_TEMP="$(mktemp "$PROJECT/state/download-data.XXXXXX")"
cat > "$JOB_TEMP" <<'SCHOOL_DOWNLOAD_JOB'
#!/usr/bin/env bash
printf 'DOWNLOAD_BATCH_START job=%s host=%s utc=%s\n' "${SLURM_JOB_ID:-unknown}" "$(hostname)" "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
set -euo pipefail
export PYTHONUNBUFFERED=1 PYTHONNOUSERSITE=1
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
CODE_ROOT="$1"
PROJECT="$2"
PYTHON_BIN="$3"
cd "$CODE_ROOT"
export PAPER1_FETCH_PYTHON="$PYTHON_BIN"
bash "$CODE_ROOT/FETCH_DATA.sh" --raw-dir "$PROJECT/raw"
"$PYTHON_BIN" -c 'import sys; from hpcmi.acquire import quick_raw_ready; assert quick_raw_ready(sys.argv[1]), "Raw download did not finish"; print("ALL_RAW_DATASETS_READY: complete pinned inputs present", flush=True)' "$PROJECT/raw"
printf 'DATA_READY start/resume training on login1 with:\n'
printf 'bash %q --project %q --raw-dir %q\n' "$CODE_ROOT/LAUNCH.sh" "$PROJECT" "$PROJECT/raw"
SCHOOL_DOWNLOAD_JOB
mv "$JOB_TEMP" "$JOB_SCRIPT"
JOB_ID="$(sbatch --parsable --account=zhuziyuan --partition="$PARTITION" --nodes=1 --ntasks=1 --gres="$GPU_REQUEST" --cpus-per-task=16 --mem=128G --time=1-00:00:00 --job-name="$JOB_NAME" --chdir="$PROJECT" --output="$PROJECT/logs/slurm/download-%j.out" --error="$PROJECT/logs/slurm/download-%j.err" "$JOB_SCRIPT" "$CODE_ROOT" "$PROJECT" "$PYTHON_BIN")"
printf '%s\n' "$JOB_ID" > "$PROJECT/state/latest_download_job.txt"
printf 'Data download submitted: %s\n' "$JOB_ID"
printf 'Raw destination: %s/raw\n' "$PROJECT"
printf 'Logs: %s/logs/slurm/download-*.out and *.err\n' "$PROJECT"
printf 'Training has not been submitted. When ALL_RAW_DATASETS_READY appears, run:\n'
printf 'bash %q --project %q --raw-dir %q\n' "$CODE_ROOT/LAUNCH.sh" "$PROJECT" "$PROJECT/raw"
