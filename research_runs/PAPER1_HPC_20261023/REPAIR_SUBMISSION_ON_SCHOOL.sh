#!/usr/bin/env bash
# Compatibility entry: install a coherent current operations overlay, not one
# old submitter that could be incompatible with the login-side pipeline.
set -euo pipefail
BOOTSTRAP_BLOB="9446bceec839ad3b6e3158e160c0eab5e9887c84"
BOOTSTRAP_SHA="1aa47bd990be8a3e2a5e081d2894da6f7287196b22fedcd33d00f8572313267e"
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
