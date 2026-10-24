#!/usr/bin/env bash
# Compatibility entry: install a coherent current operations overlay, not one
# old submitter that could be incompatible with the login-side pipeline.
set -euo pipefail
BOOTSTRAP_BLOB="b505e60ead3b309fb22d78b3226cba5b6ea854b4"
BOOTSTRAP_SHA="95e3841c3e4da4978e164e435bb55b44d909b9f815c1e352520c4bf75a6f5b06"
BOOTSTRAP="$(mktemp /tmp/paper1-current-launch.XXXXXX)"
trap 'rm -f "$BOOTSTRAP"' EXIT
curl -4 -f --connect-timeout 8 --max-time 60 --retry 1 \
  -H 'Accept: application/vnd.github.raw+json' \
  "https://api.github.com/repos/jackzhu119/cross-subject-mi-eeg/git/blobs/$BOOTSTRAP_BLOB" -o "$BOOTSTRAP"
OBSERVED="$(sha256sum "$BOOTSTRAP")"
if [ "${OBSERVED%% *}" != "$BOOTSTRAP_SHA" ]; then
  printf 'Current launcher checksum differs; installed code and jobs retained.\n' >&2
  exit 2
fi
bash "$BOOTSTRAP" "$@"
