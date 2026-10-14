#!/usr/bin/env bash
set -euo pipefail
# Future execution entrypoint, not an authorization to launch an old blocked job.
[[ -n "${MI_EEG_R2_IMPORT_MANIFEST:-}" && -n "${MI_EEG_R2_IMPORT_SHA256:-}" ]] || { echo 'Reviewed complete R2 mapping and SHA256 required; nothing started.'; exit 2; }
[[ -n "${GH_TOKEN:-}" && -n "${R2_ENDPOINT:-}" && -n "${R2_BUCKET:-}" && -n "${R2_ACCESS_KEY_ID:-}" && -n "${R2_SECRET_ACCESS_KEY:-}" ]] || { echo 'Existing secure environment bindings required; no credentials created.'; exit 2; }
export MI_EEG_ENV_ONLY_CREDENTIALS=1
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
exec bash "$SCRIPT_DIR/LAUNCH_ON_GPU.sh" "$@" --r2
