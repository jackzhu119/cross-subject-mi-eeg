#!/usr/bin/env bash
set -euo pipefail
set +x
umask 077
Q15_HELPER_REVISION=4cec775357e8dcf7db1b68d994e2ab9a9f721049
Q15_HELPER_PATH=research_runs/Q15-MIGRATION-20261004
Q15_MODE=${1:-}
[[ "$Q15_MODE" == backup || "$Q15_MODE" == restore || "$Q15_MODE" == from-r2 ]] || { printf 'Usage: bash Q15_MIGRATE_ON_RUNPOD.sh from-r2|backup|restore [--job-id ID] [--object-key KEY --archive-sha256 SHA]\n' >&2; exit 2; }
shift
Q15_OBJECT_KEY=''
Q15_ARCHIVE_SHA=''
Q15_JOB_ID=''
while (($#)); do
  [[ $# -ge 2 ]] || { printf 'Missing argument value.\n' >&2; exit 2; }
  case "$1" in
    --object-key) Q15_OBJECT_KEY=$2 ;;
    --archive-sha256) Q15_ARCHIVE_SHA=$2 ;;
    --job-id) Q15_JOB_ID=$2 ;;
    *) printf 'Unknown migration option.\n' >&2; exit 2 ;;
  esac
  shift 2
done
[[ "$Q15_HELPER_REVISION" =~ ^[a-f0-9]{40}$ ]] || { printf 'Migration release is not pinned.\n' >&2; exit 1; }
[[ "${RUNPOD_POD_ID:-}" =~ ^[A-Za-z0-9_-]{1,64}$ ]] || { printf 'Run this on the intended RunPod.\n' >&2; exit 1; }
if [[ "$Q15_MODE" == restore ]]; then
  [[ "$Q15_ARCHIVE_SHA" =~ ^[a-f0-9]{64}$ && "$Q15_OBJECT_KEY" == q15/migrations/* ]] || { printf 'Supply the verified backup object key and SHA256.\n' >&2; exit 2; }
fi
[[ -z "$Q15_JOB_ID" || "$Q15_JOB_ID" =~ ^[A-Za-z0-9_-]{1,80}$ ]] || { printf 'Invalid migration job ID.\n' >&2; exit 2; }
command -v flock >/dev/null
exec 8>/root/.q15-migration-setup.lock
flock -n 8 || { printf 'Another migration launcher is active.\n' >&2; exit 1; }
exec 9>/root/.q15-migration-active.lock
flock -n 9 || { printf 'A migration worker is already active.\n' >&2; exit 1; }
Q15_PRIVATE=$(mktemp -d /root/q15-migration-runtime.XXXXXXXX)
Q15_CREDENTIAL_NAMES=(R2_BUCKET R2_ENDPOINT R2_ACCESS_KEY_ID R2_SECRET_ACCESS_KEY)
[[ "$Q15_MODE" == backup ]] || Q15_CREDENTIAL_NAMES+=(GH_TOKEN RUNPOD_API_KEY)
Q15_TTY_FD=''
for Q15_NAME in "${Q15_CREDENTIAL_NAMES[@]}"; do
  Q15_VALUE=${!Q15_NAME:-}
  Q15_VALUE="${Q15_VALUE#"${Q15_VALUE%%[![:space:]]*}"}"
  Q15_VALUE="${Q15_VALUE%"${Q15_VALUE##*[![:space:]]}"}"
  [[ "$Q15_VALUE" != *[[:space:]]* ]] || Q15_VALUE=''
  if [[ -z "$Q15_VALUE" ]]; then
    if [[ -z "$Q15_TTY_FD" ]]; then
      { exec {Q15_TTY_FD}<>/dev/tty; } 2>/dev/null || { printf 'An interactive terminal is required for hidden credential input.\n' >&2; exit 1; }
    fi
    for Q15_ATTEMPT in 1 2 3; do
      IFS= read -r -s -u "$Q15_TTY_FD" -p "$Q15_NAME (hidden; $Q15_ATTEMPT/3): " Q15_VALUE || { printf '\nInput interrupted.\n' >&2; exit 1; }
      printf '\n' >&"$Q15_TTY_FD"
      Q15_VALUE="${Q15_VALUE#"${Q15_VALUE%%[![:space:]]*}"}"
      Q15_VALUE="${Q15_VALUE%"${Q15_VALUE##*[![:space:]]}"}"
      [[ -z "$Q15_VALUE" || "$Q15_VALUE" == *[[:space:]]* ]] || break
      Q15_VALUE=''
      printf 'Paste a nonempty value; hidden input shows no characters.\n' >&"$Q15_TTY_FD"
    done
    [[ -n "$Q15_VALUE" ]] || { printf 'Missing required credential: %s\n' "$Q15_NAME" >&2; exit 1; }
  fi
  printf -v "$Q15_NAME" '%s' "$Q15_VALUE"
  export -n "$Q15_NAME"
done
[[ -z "$Q15_TTY_FD" ]] || exec {Q15_TTY_FD}>&-
# Remove even unused inherited credentials from curl, venv and pip children.
for Q15_NAME in R2_BUCKET R2_ENDPOINT R2_ACCESS_KEY_ID R2_SECRET_ACCESS_KEY GH_TOKEN GITHUB_TOKEN RUNPOD_API_KEY; do
  export -n "$Q15_NAME" 2>/dev/null || true
done
Q15_BASE_URL="https://raw.githubusercontent.com/jackzhu119/cross-subject-mi-eeg/$Q15_HELPER_REVISION/$Q15_HELPER_PATH"
for Q15_FILE in q15_migration_bundle.py q15_migration_transport.py q15_continue_validated.py q15_migration_supervisor.py q15_restore_from_r2.py requirements-migration.txt SHA256SUMS; do
  curl -fSsL --retry 3 "$Q15_BASE_URL/$Q15_FILE" -o "$Q15_PRIVATE/$Q15_FILE"
done
(cd "$Q15_PRIVATE" && sha256sum --check SHA256SUMS)
python3 -m venv --system-site-packages "$Q15_PRIVATE/venv"
"$Q15_PRIVATE/venv/bin/python" -m pip install --disable-pip-version-check -r "$Q15_PRIVATE/requirements-migration.txt" >"$Q15_PRIVATE/client-install.log" 2>&1 || { printf 'S3 client installation failed; private log: %s/client-install.log\n' "$Q15_PRIVATE" >&2; exit 1; }
Q15_JOB_ID=${Q15_JOB_ID:-$(date -u +%Y%m%dT%H%M%SZ)-migration-$Q15_MODE-$(python3 -c 'import uuid;print(uuid.uuid4().hex[:8])')}
Q15_JOB_DIR=/workspace/q15-migration/jobs/$Q15_JOB_ID
[[ ! -L /workspace/q15-migration && ! -L "$Q15_JOB_DIR" ]] || { printf 'Unsafe migration output path.\n' >&2; exit 1; }
mkdir -p "$Q15_JOB_DIR"
python3 - "/workspace/q15-migration/jobs/current_job.json" "$Q15_JOB_ID" "$Q15_MODE" <<'PY'
import json, os, sys, tempfile
from pathlib import Path
path = Path(sys.argv[1])
fd, temporary = tempfile.mkstemp(prefix='.q15-current-', dir=path.parent)
with os.fdopen(fd, 'w') as stream:
    json.dump({'job_id': sys.argv[2], 'operation': sys.argv[3],
               'branch': 'q15/run-' + sys.argv[2]}, stream)
    stream.write('\n')
os.replace(temporary, path)
PY
for Q15_NAME in "${Q15_CREDENTIAL_NAMES[@]}"; do export "$Q15_NAME"; done
Q15_ARGS=("$Q15_MODE" --job-directory "$Q15_JOB_DIR" --job-id "$Q15_JOB_ID" --private-log "$Q15_PRIVATE/scientific-install.log")
if [[ "$Q15_MODE" == restore ]]; then Q15_ARGS+=(--object-key "$Q15_OBJECT_KEY" --archive-sha256 "$Q15_ARCHIVE_SHA"); fi
# Worker inherits FD9's lock and credentials only in memory. No secret is stored in a file.
nohup "$Q15_PRIVATE/venv/bin/python" "$Q15_PRIVATE/q15_migration_supervisor.py" "${Q15_ARGS[@]}" 8>&- >"$Q15_JOB_DIR/supervisor.log" 2>&1 </dev/null &
Q15_PID=$!
printf '{"status":"detached_migration_started_not_scientifically_complete","operation":"%s","pid":%s,"job_id":"%s","new_source_fits":0,"target_fits":0}\n' "$Q15_MODE" "$Q15_PID" "$Q15_JOB_ID"
printf 'Progress: cat %s/migration_status.json\n' "$Q15_JOB_DIR"
printf 'Logs: tail -n 25 %s/supervisor.log\n' "$Q15_JOB_DIR"
printf 'Results branch: https://github.com/jackzhu119/cross-subject-mi-eeg/tree/q15/run-%s\n' "$Q15_JOB_ID"
