#!/usr/bin/env bash
# Small login-node bootstrap. Large EEG transfer/extraction runs in Slurm.
set -euo pipefail
PROJECTS_ROOT="${1:-/public/home/zhuziyuan/projects}"
PYTHON_BIN="${PAPER1_PYTHON:-/public/home/zhuziyuan/.venvs/paper3-hpc-cu121-offline/bin/python}"
BUNDLE_SHA="72225f30c83be9bbc94d52eac672bee272690f6cf9949933e3d61380401d2675"
BUNDLE_URL="https://raw.githubusercontent.com/jackzhu119/cross-subject-mi-eeg/67de0abda18d1d64fa468d3f4907ac23c70d0b45/research_runs/PAPER1_HPC_20261023/dist/paper1-hpc-offline.tar.gz"
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
  if [ "${PART_SHA%% *}" != "$BUNDLE_SHA" ]; then
    curl -fL --connect-timeout 20 --max-time 900 --retry 3 --retry-delay 5 -C - "$BUNDLE_URL" -o "$ARCHIVE.part"
  fi
  OBSERVED_SHA="$(sha256sum "$ARCHIVE.part")"
  if [ "${OBSERVED_SHA%% *}" != "$BUNDLE_SHA" ]; then
    printf 'Downloaded archive checksum differs; partial retained: %s.part\n' "$ARCHIVE" >&2
    exit 2
  fi
  mv "$ARCHIVE.part" "$ARCHIVE"
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
ACTIVE="$(squeue -h -u zhuziyuan -n "$JOB_NAME" -o '%i')"
if [ -n "$ACTIVE" ]; then
  printf 'Existing data-download job: %s\n' "$ACTIVE"
  exit 0
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
JOB_ID="$(sbatch --parsable --account=zhuziyuan --partition=hpc_gpu1 --nodes=1 --ntasks=1 --gres=gpu:NVIDIAA100-SXM4-80GB:1 --cpus-per-task=24 --mem=128G --time=1-00:00:00 --exclude=gpu3 --job-name="$JOB_NAME" --chdir="$PROJECT" --output="$PROJECT/logs/slurm/download-%j.out" --error="$PROJECT/logs/slurm/download-%j.err" "$JOB_SCRIPT" "$CODE_ROOT" "$PROJECT" "$PYTHON_BIN")"
printf '%s\n' "$JOB_ID" > "$PROJECT/state/latest_download_job.txt"
printf 'Data download submitted: %s\n' "$JOB_ID"
printf 'Raw destination: %s/raw\n' "$PROJECT"
printf 'Logs: %s/logs/slurm/download-*.out and *.err\n' "$PROJECT"
printf 'Training has not been submitted. When ALL_RAW_DATASETS_READY appears, run:\n'
printf 'bash %q --project %q --raw-dir %q\n' "$CODE_ROOT/LAUNCH.sh" "$PROJECT" "$PROJECT/raw"
