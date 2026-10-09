#!/usr/bin/env bash
set -euo pipefail
set +x
umask 077
Q15_HELPER_REVISION=c7c06ee57cde2cc9e2d4d75704f1c92ab96a0325
Q15_HELPER_PATH=research_runs/Q15-MIGRATION-20261004
Q15_MODE=${1:-}
[[ "$Q15_MODE" == backup || "$Q15_MODE" == restore || "$Q15_MODE" == from-r2 ]] || { printf 'Usage: bash Q15_MIGRATE_ON_RUNPOD.sh from-r2|backup|restore [--manual-stop] [--job-id ID] [--reset-credential NAME] [--object-key KEY --archive-sha256 SHA]\n' >&2; exit 2; }
shift
Q15_OBJECT_KEY=''
Q15_ARCHIVE_SHA=''
Q15_JOB_ID=''
Q15_MANUAL_STOP=false
Q15_RESET_CREDENTIALS=()
while (($#)); do
  if [[ "$1" == --manual-stop ]]; then Q15_MANUAL_STOP=true; shift; continue; fi
  [[ $# -ge 2 ]] || { printf 'Missing argument value.\n' >&2; exit 2; }
  case "$1" in
    --object-key) Q15_OBJECT_KEY=$2 ;;
    --archive-sha256) Q15_ARCHIVE_SHA=$2 ;;
    --job-id) Q15_JOB_ID=$2 ;;
    --reset-credential)
      case "$2" in
        R2_BUCKET|R2_ENDPOINT|R2_ACCESS_KEY_ID|R2_SECRET_ACCESS_KEY|GH_TOKEN|RUNPOD_API_KEY) Q15_RESET_CREDENTIALS+=("$2") ;;
        *) printf 'Unsupported credential name.\n' >&2; exit 2 ;;
      esac ;;
    *) printf 'Unknown migration option.\n' >&2; exit 2 ;;
  esac
  shift 2
done
[[ "$Q15_HELPER_REVISION" =~ ^[a-f0-9]{40}$ ]] || { printf 'Migration release is not pinned.\n' >&2; exit 1; }
[[ "${RUNPOD_POD_ID:-}" =~ ^[A-Za-z0-9_-]{1,64}$ ]] || { printf 'Run this on the intended RunPod.\n' >&2; exit 1; }
if [[ "$Q15_MODE" == restore ]]; then
  [[ "$Q15_ARCHIVE_SHA" =~ ^[a-f0-9]{64}$ && "$Q15_OBJECT_KEY" == q15/migrations/* ]] || { printf 'Supply the verified backup object key and SHA256.\n' >&2; exit 2; }
fi
if [[ "$Q15_MANUAL_STOP" == true ]]; then unset RUNPOD_API_KEY; fi
[[ -z "$Q15_JOB_ID" || "$Q15_JOB_ID" =~ ^[A-Za-z0-9_-]{1,80}$ ]] || { printf 'Invalid migration job ID.\n' >&2; exit 2; }
command -v flock >/dev/null
exec 8>/root/.q15-migration-setup.lock
flock -n 8 || { printf 'Another migration launcher is active.\n' >&2; exit 1; }
exec 9>/root/.q15-migration-active.lock
flock -n 9 || { printf 'A migration worker is already active.\n' >&2; exit 1; }
Q15_PRIVATE=$(mktemp -d /root/q15-migration-runtime.XXXXXXXX)
# Public code fetches never receive inherited credentials. Values remain in
# this shell for later private input; no credential file is created.
for Q15_NAME in R2_BUCKET R2_ENDPOINT R2_ACCESS_KEY_ID R2_SECRET_ACCESS_KEY GH_TOKEN GITHUB_TOKEN RUNPOD_API_KEY; do
  export -n "$Q15_NAME" 2>/dev/null || true
done
Q15_BASE_URL="https://raw.githubusercontent.com/jackzhu119/cross-subject-mi-eeg/$Q15_HELPER_REVISION/$Q15_HELPER_PATH"
for Q15_FILE in q15_migration_bundle.py q15_migration_transport.py q15_continue_validated.py q15_migration_supervisor.py q15_restore_from_r2.py requirements-migration.txt SHA256SUMS; do
  curl -fSsL --retry 3 "$Q15_BASE_URL/$Q15_FILE" -o "$Q15_PRIVATE/$Q15_FILE"
done
(cd "$Q15_PRIVATE" && sha256sum --check SHA256SUMS)
Q15_TTY_FD=''
q15_collect_credentials() {
for Q15_NAME in "$@"; do
  Q15_VALUE=${!Q15_NAME:-}
  if [[ " ${Q15_RESET_CREDENTIALS[*]} " == *" $Q15_NAME "* ]]; then Q15_VALUE=''; fi
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
}
q15_check_accounts() {
  if [[ "$Q15_MANUAL_STOP" == true ]]; then
    GH_TOKEN="$GH_TOKEN" python3 "$Q15_PRIVATE/q15_migration_supervisor.py" check-accounts --manual-stop
  else
    GH_TOKEN="$GH_TOKEN" RUNPOD_API_KEY="$RUNPOD_API_KEY" python3 "$Q15_PRIVATE/q15_migration_supervisor.py" check-accounts
  fi
}
if [[ "$Q15_MODE" != backup ]]; then
  q15_collect_credentials GH_TOKEN
  [[ "$Q15_MANUAL_STOP" == true ]] || q15_collect_credentials RUNPOD_API_KEY
  # Only account credentials reach this standard-library-only, read-only
  # preflight. An inherited value is presence, never API authorization.
  for Q15_API_ATTEMPT in 1 2 3; do
    if Q15_ACCOUNT_REPORT=$(q15_check_accounts); then
      printf '%s\n' "$Q15_ACCOUNT_REPORT"
      break
    fi
    printf '%s\n' "$Q15_ACCOUNT_REPORT"
    Q15_ERROR_CODE=$(python3 -c 'import json,sys; print(json.load(sys.stdin).get("error_code", ""))' <<<"$Q15_ACCOUNT_REPORT")
    Q15_REJECTED_NAME=''
    case "$Q15_ERROR_CODE" in
      runpod_account_api_http_401|runpod_account_api_http_403|runpod_account_api_http_404) Q15_REJECTED_NAME=RUNPOD_API_KEY ;;
      github_account_api_http_401|github_account_api_http_403|github_account_api_http_404|github_publication_access_unverified) Q15_REJECTED_NAME=GH_TOKEN ;;
    esac
    if [[ "$Q15_API_ATTEMPT" == 3 || -z "$Q15_REJECTED_NAME" ]]; then
      printf 'Account preflight failed; no migration worker or R2 download started.\n' >&2
      exit 1
    fi
    printf 'Account access was rejected. Re-enter %s; other values remain in memory.\n' "$Q15_REJECTED_NAME" >&2
    printf -v "$Q15_REJECTED_NAME" '%s' ''
    q15_collect_credentials "$Q15_REJECTED_NAME"
  done
fi
q15_collect_credentials R2_BUCKET R2_ENDPOINT R2_ACCESS_KEY_ID R2_SECRET_ACCESS_KEY
[[ -z "$Q15_TTY_FD" ]] || exec {Q15_TTY_FD}>&-
Q15_CREDENTIAL_NAMES=(R2_BUCKET R2_ENDPOINT R2_ACCESS_KEY_ID R2_SECRET_ACCESS_KEY)
if [[ "$Q15_MODE" != backup ]]; then
  Q15_CREDENTIAL_NAMES+=(GH_TOKEN)
  [[ "$Q15_MANUAL_STOP" == true ]] || Q15_CREDENTIAL_NAMES+=(RUNPOD_API_KEY)
fi
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
[[ "$Q15_MANUAL_STOP" == false ]] || Q15_ARGS+=(--manual-stop)
if [[ "$Q15_MODE" == restore ]]; then Q15_ARGS+=(--object-key "$Q15_OBJECT_KEY" --archive-sha256 "$Q15_ARCHIVE_SHA"); fi
# Worker inherits FD9's lock and credentials only in memory. No secret is stored in a file.
nohup "$Q15_PRIVATE/venv/bin/python" "$Q15_PRIVATE/q15_migration_supervisor.py" "${Q15_ARGS[@]}" 8>&- >"$Q15_JOB_DIR/supervisor.log" 2>&1 </dev/null &
Q15_PID=$!
Q15_STOP_FIELDS=''
[[ "$Q15_MANUAL_STOP" == false ]] || Q15_STOP_FIELDS=',"automatic_shutdown_enabled":false,"runpod_api_checked":false,"manual_stop_required":true'
printf '{"status":"detached_migration_started_not_scientifically_complete","operation":"%s","pid":%s,"job_id":"%s","new_source_fits":0,"target_fits":0%s}\n' "$Q15_MODE" "$Q15_PID" "$Q15_JOB_ID" "$Q15_STOP_FIELDS"
printf 'Progress: cat %s/migration_status.json\n' "$Q15_JOB_DIR"
printf 'Logs: tail -n 25 %s/supervisor.log\n' "$Q15_JOB_DIR"
printf 'Results branch: https://github.com/jackzhu119/cross-subject-mi-eeg/tree/q15/run-%s\n' "$Q15_JOB_ID"
[[ "$Q15_MANUAL_STOP" == false ]] || printf 'Manual stop mode: no RunPod API key or API calls. Stop this Pod in the console after verified results backup.\n'
